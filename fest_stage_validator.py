"""Stage slot invariants, rebuilt from the trace.

The stage keeps its own record of what it awarded. These checks never
read it. They rebuild the schedule from the award events, so a stage
manager that skips one of its own guards is still caught.
"""

from __future__ import annotations

from nandatown.sim.validators import StageResult, validator


def _overlaps(a: dict, b: dict) -> bool:
    return a["from"] < b["to"] and b["from"] < a["to"]


@validator("stage")
def stage(spec, trace) -> list[StageResult]:
    stages: list[StageResult] = []

    announced = trace.find("task_announced")
    bids = trace.find("bid_placed")
    awards = trace.find("slot_awarded")
    ev = [e.event_id for e in awards]

    # One slot, one band.
    taken: dict[tuple[str, str], str] = {}
    doubled = []
    for e in awards:
        key = (e.detail["stage"], e.subject)
        if key in taken:
            doubled.append(e)
        taken[key] = e.detail["band"]
    stages.append(StageResult(
        name="one_band_per_slot",
        status="failed" if doubled else "passed",
        evidence=ev,
        note=f"{len(awards)} slots awarded across"
             f" {len({e.detail['stage'] for e in awards})} stages;"
             f" {len(doubled)} awarded twice"))

    # Two bands cannot hold the stage at the same time.
    clashes = []
    by_stage: dict[str, list[dict]] = {}
    for e in awards:
        by_stage.setdefault(e.detail["stage"], []).append(
            {"slot": e.subject, "band": e.detail["band"],
             "from": e.detail["from"], "to": e.detail["to"]})
    for st, held in by_stage.items():
        for i, a in enumerate(held):
            for b in held[i + 1:]:
                if _overlaps(a, b):
                    clashes.append(f"{st}: {a['slot']} and {b['slot']}")
    stages.append(StageResult(
        name="no_overlapping_awards",
        status="failed" if clashes else "passed",
        evidence=ev,
        note="; ".join(clashes) or
             f"no two awards on one stage share a minute"))

    # A band cannot be in two places at once, even on two stages.
    clash_band = []
    by_band: dict[str, list[dict]] = {}
    for e in awards:
        by_band.setdefault(e.detail["band"], []).append(
            {"slot": f"{e.detail['stage']}/{e.subject}",
             "from": e.detail["from"], "to": e.detail["to"]})
    for band, held in by_band.items():
        for i, a in enumerate(held):
            for b in held[i + 1:]:
                if _overlaps(a, b):
                    clash_band.append(f"{band}: {a['slot']} and {b['slot']}")
    stages.append(StageResult(
        name="band_not_double_booked",
        status="failed" if clash_band else "passed",
        evidence=ev,
        note="; ".join(clash_band) or
             f"no band holds two awards that overlap in time"))

    # The winner has to be the bid the declared rule picks.
    wrong = []
    for e in awards:
        task = f"{e.detail['stage']}-{e.subject}"
        placed = {b.observer: b.detail["cents"]
                  for b in bids if b.subject == task}
        if not placed:
            continue
        rule = next((a.detail["rule"] for a in announced
                     if a.subject == task), "highest")
        best = (max if rule == "highest" else min)(placed.values())
        if e.detail["cents"] != best:
            wrong.append(f"{e.subject} went to {e.detail['band']} at"
                         f" {e.detail['cents']}, but {rule} was {best}")
    stages.append(StageResult(
        name="award_follows_rule",
        status="failed" if wrong else "passed",
        evidence=ev,
        note="; ".join(wrong) or
             f"every award matched the rule it was announced under"))

    # A bid is money. Anything else is not a bid.
    bad = [b for b in bids if b.detail["cents"] <= 0]
    stages.append(StageResult(
        name="bids_are_money",
        status="failed" if bad else "passed",
        evidence=[b.event_id for b in bids],
        note=f"{len(bad)} of {len(bids)} bids were not a positive amount"
             f" of money"
             + (f"; lowest was {min(b.detail['cents'] for b in bids)}"
                if bids else "")))

    # Nobody plays a slot they were not awarded.
    performed = trace.find("performed")
    gatecrashed = [e for e in performed
                   if taken.get((e.detail["stage"], e.subject))
                   != e.detail["band"]]
    refused = trace.find("stage_refused")
    stages.append(StageResult(
        name="only_the_winner_plays",
        status="failed" if gatecrashed else "passed",
        evidence=[e.event_id for e in performed] or ev,
        note=f"{len(performed)} performances, {len(gatecrashed)} by a band"
             f" that did not hold the slot; {len(refused)} attempts"
             f" refused at the stage"))

    # Money only moves for a band that actually played.
    released = trace.find("escrow_released")
    refunded = trace.find("escrow_refunded")
    played = {e.subject for e in performed}
    paid_without_playing = [e for e in released
                            if e.subject.rsplit("-", 1)[-1] not in played]
    stages.append(StageResult(
        name="paid_only_for_playing",
        status="failed" if paid_without_playing else "passed",
        evidence=[e.event_id for e in released + refunded] or ev,
        note=f"{len(released)} slots paid out, {len(refunded)} refunded"
             f" to no-shows; {len(paid_without_playing)} paid for a slot"
             f" nobody played"))
    # An award nobody can pay for is not an allocation.
    unsettled = trace.find("settlement_refused")
    if unsettled:
        stages.append(StageResult(
            name="awards_are_settleable",
            status="failed",
            evidence=[e.event_id for e in unsettled],
            note="; ".join(f"{e.subject} was awarded at"
                           f" {e.detail['cents']} and could not be paid:"
                           f" {e.detail['reason']}" for e in unsettled)))

    # Were the slots actually allocated? An empty slot with a live bid
    # on it is the auction failing to clear, not a lack of demand.
    declined = trace.find("award_declined")
    offered = {a.subject for a in announced}
    filled = {f"{e.detail['stage']}-{e.subject}" for e in awards}
    empty_with_bids = sorted(
        {b.subject for b in bids if b.subject not in filled}
        & offered)
    stages.append(StageResult(
        name="slots_filled",
        status="not_enough_evidence" if not offered else
               ("failed" if empty_with_bids else "passed"),
        evidence=ev + [d.event_id for d in declined],
        note=f"{len(filled)} of {len(offered)} slots filled;"
             f" {len(empty_with_bids)} left empty with a live bid on them"
             + (f" ({', '.join(empty_with_bids)});"
                f" {len(declined)} awards were declined and never"
                f" re-offered to the runner-up" if empty_with_bids
                else "")))
    return stages
