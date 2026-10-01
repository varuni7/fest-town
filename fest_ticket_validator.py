"""Ticketing invariants, all computed from the trace.

These are properties, not expected traces, so they hold whatever the
cast size: no sale outside the window, no show oversold, no transfer by
a non-holder, no ticket admitted twice, and a settlement for every
ticket issued.
"""

from __future__ import annotations

from collections import Counter

from nandatown.records import StageResult
from nandatown.sim.validators import validator


@validator("tickets")
def tickets(spec, trace) -> list[StageResult]:
    offices = {a.name: a.config for a in spec.agents
               if a.role == "box_office"}
    issued = trace.find("ticket_issued")
    refused = trace.find("sale_refused")
    admitted = trace.find("admitted")
    transferred = trace.find("ticket_transferred")
    tr_refused = trace.find("transfer_refused")
    refunded = trace.find("ticket_refunded")
    rf_refused = trace.find("refund_refused")
    settled = trace.find("payment_settled")

    stages: list[StageResult] = []

    if not issued:
        return [StageResult(name="tickets_sold", status="failed",
                            evidence=[], note="no ticket was ever issued")]

    stages.append(StageResult(
        name="tickets_sold", status="passed",
        evidence=[e.event_id for e in issued][:8],
        note=f"{len(issued)} issued, {len(refused)} refused,"
             f" {len(transferred)} transferred, {len(refunded)} refunded,"
             f" {len(admitted)} admitted"))

    # 1. Nothing sold outside the advertised window.
    windows = {n: (c.get("sale_from", 0.0), c.get("sale_to", 15.0))
               for n, c in offices.items()}
    lo = min(w[0] for w in windows.values())
    hi = max(w[1] for w in windows.values())
    outside = [e for e in issued if not (lo <= e.detail["at"] <= hi)]
    stages.append(StageResult(
        name="sale_window", status="passed" if not outside else "failed",
        evidence=[e.event_id for e in (outside or issued)][:8],
        note=(f"every sale fell inside {lo}-{hi}; {len(refused)} later"
              " attempts were refused" if not outside else
              f"{len(outside)} tickets sold outside the window")))

    # 2. No show oversold. Counted as seats out at the same time, not
    #    tickets ever issued: a refunded seat can be sold again, so the
    #    running total is the only thing capacity can mean.
    live: dict[str, int] = {}
    peak: dict[str, int] = {}
    for e in sorted(issued + refunded, key=lambda e: (e.detail["at"],
                                                      e.event_id)):
        show = e.detail["show"]
        live[show] = live.get(show, 0) + (1 if e.kind == "ticket_issued"
                                         else -1)
        peak[show] = max(peak.get(show, 0), live[show])
    over = [(s, n, offices[f"box-{s}"]["capacity"]) for s, n in peak.items()
            if f"box-{s}" in offices and n > offices[f"box-{s}"]["capacity"]]
    stages.append(StageResult(
        name="capacity_respected", status="passed" if not over else "failed",
        evidence=[e.event_id for e in issued][:8],
        note=("; ".join(f"{s} {n}/{offices['box-'+s]['capacity']} at its"
                        f" fullest" for s, n in sorted(peak.items()))
              if not over else
              "; ".join(f"{s} held {n} seats against a capacity of {c}"
                        for s, n, c in over))))

    # 3. Every ticket issued was paid for.
    ticket_pay = [e for e in settled
                  if str(e.subject).startswith("ticket-")]
    stages.append(StageResult(
        name="tickets_paid",
        status="passed" if len(ticket_pay) == len(issued) else "failed",
        evidence=[e.event_id for e in ticket_pay][:8],
        note=f"{len(ticket_pay)} payments for {len(issued)} tickets"))

    # 4. Only the holder can pass a ticket on. Ownership is rebuilt
    #    from the trace, so a box office that skipped its own check
    #    still fails here.
    unauthorised = []
    owner = {e.subject: e.detail["to"] for e in issued}
    for e in transferred:
        if owner.get(e.subject) != e.detail["from"]:
            unauthorised.append(e)
        owner[e.subject] = e.detail["to"]
    stages.append(StageResult(
        name="transfer_authorised",
        status="passed" if not unauthorised else "failed",
        evidence=[e.event_id for e in (unauthorised or transferred)][:8],
        note=(f"{len(transferred)} transfers, each by the current holder;"
              f" {len(tr_refused)} rejected"
              if not unauthorised else
              f"{len(unauthorised)} tickets transferred by someone who"
              f" did not hold them")))

    # 5. Refunds. Skipped entirely when a scenario has none, rather
    #    than reported as passing.
    if refunded:
        stages += _refunds(offices, issued, refunded, rf_refused,
                           transferred, admitted, settled)

    # 6. One ticket, one entry. The invariant that matters.
    entries = Counter(e.subject for e in admitted)
    twice = [t for t, n in entries.items() if n > 1]
    stages.append(StageResult(
        name="one_ticket_one_entry",
        status="passed" if not twice else "failed",
        evidence=[e.event_id for e in admitted][:8],
        note=(f"{len(admitted)} admissions, no ticket used twice"
              if not twice else
              f"{len(twice)} tickets admitted more than once: {twice[:5]}")))

    return stages


def _refunds(offices, issued, refunded, rf_refused, transferred,
             admitted, settled) -> list[StageResult]:
    """Four invariants and one open question."""
    stages: list[StageResult] = []
    price = {e.subject: e.detail["price_cents"] for e in issued}
    ev = [e.event_id for e in refunded][:8]

    # A refund cannot happen after the cutoff.
    until = max(c.get("refund_until", 30.0) for c in offices.values())
    late = [e for e in refunded if e.detail["at"] > until]
    stages.append(StageResult(
        name="refund_window", status="failed" if late else "passed",
        evidence=[e.event_id for e in (late or refunded)][:8],
        note=(f"every refund fell on or before {until}; {len(rf_refused)}"
              f" requests were refused"
              if not late else
              f"{len(late)} refunds granted after {until}")))

    # A ticket cannot be refunded twice.
    counts = Counter(e.subject for e in refunded)
    twice = [t for t, n in counts.items() if n > 1]
    stages.append(StageResult(
        name="refund_once_per_ticket",
        status="failed" if twice else "passed",
        evidence=ev,
        note=(f"{len(refunded)} refunds across {len(counts)} tickets"
              if not twice else
              f"{len(twice)} tickets refunded more than once: {twice[:5]}")))

    # The money back equals the money in.
    wrong = [e for e in refunded
             if price.get(e.subject) != e.detail["price_cents"]]
    paid_back = [e for e in settled
                 if str(e.subject).startswith("refund-")]
    stages.append(StageResult(
        name="refund_matches_price",
        status="failed" if wrong or len(paid_back) != len(refunded)
               else "passed",
        evidence=[e.event_id for e in paid_back][:8] or ev,
        note=(f"{len(paid_back)} settlements for {len(refunded)} refunds,"
              f" each at the price paid"
              if not wrong and len(paid_back) == len(refunded) else
              f"{len(wrong)} refunds at the wrong price;"
              f" {len(paid_back)} settlements for {len(refunded)} refunds")))

    # A refunded ticket is not a ticket. Ownership and voiding are both
    # rebuilt here, so a gate that skipped its own check still fails.
    # When it was voided matters: a ticket passed on in the morning and
    # refunded by its new holder at noon is an ordinary day.
    voided = {}
    for e in refunded:
        voided[e.subject] = min(voided.get(e.subject, e.at), e.at)
    walked_in = [e for e in admitted
                 if e.at > voided.get(e.subject, float("inf"))]
    moved_on = [e for e in transferred
                if e.at > voided.get(e.subject, float("inf"))]
    stages.append(StageResult(
        name="refunded_tickets_are_dead",
        status="failed" if walked_in or moved_on else "passed",
        evidence=[e.event_id for e in (walked_in + moved_on)][:8] or ev,
        note=(f"none of the {len(voided)} refunded tickets was admitted"
              f" or passed on afterwards"
              if not walked_in and not moved_on else
              f"{len(walked_in)} refunded tickets admitted at the gate,"
              f" {len(moved_on)} transferred after the refund")))

    # Not an invariant. A question nobody has answered: the payer and
    # the holder are the same account until a ticket changes hands.
    split = [e for e in refunded if e.detail["to"] != e.detail["held_by"]]
    stages.append(StageResult(
        name="refund_payee",
        status="not_tested" if not split else "not_enough_evidence",
        evidence=[e.event_id for e in split][:8] or ev,
        note=(f"every refund went to the account that held the ticket"
              if not split else
              f"{len(split)} refunds went to the original payer while"
              f" someone else held the ticket, e.g. {split[0].subject}"
              f" refunded to {split[0].detail['to']} but held by"
              f" {split[0].detail['held_by']}; no policy says which is"
              f" right")))
    return stages
