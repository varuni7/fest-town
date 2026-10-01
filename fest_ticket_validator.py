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
    settled = trace.find("payment_settled")

    stages: list[StageResult] = []

    if not issued:
        return [StageResult(name="tickets_sold", status="failed",
                            evidence=[], note="no ticket was ever issued")]

    stages.append(StageResult(
        name="tickets_sold", status="passed",
        evidence=[e.event_id for e in issued][:8],
        note=f"{len(issued)} issued, {len(refused)} refused,"
             f" {len(transferred)} transferred, {len(admitted)} admitted"))

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

    # 2. No show oversold.
    per_show = Counter(e.detail["show"] for e in issued)
    over = [(s, n, offices[f"box-{s}"].get("capacity"))
            for s, n in per_show.items()
            if f"box-{s}" in offices and n > offices[f"box-{s}"]["capacity"]]
    stages.append(StageResult(
        name="capacity_respected", status="passed" if not over else "failed",
        evidence=[e.event_id for e in issued][:8],
        note=("; ".join(f"{s} {n}/{offices['box-'+s]['capacity']}"
                        for s, n in sorted(per_show.items()))
              if not over else
              f"oversold: {over}")))

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

    # 5. One ticket, one entry. The invariant that matters.
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
