"""A validator that describes a population instead of a script.

The bundled validators assert an expected trace: two sellers, three
requests, reputation exactly 2. Those cannot survive a change of cast.
These stages ask about shape instead, so the same checks apply whether
the fest has fifty attendees or five hundred.
"""

from __future__ import annotations

from collections import Counter

from nandatown.records import StageResult
from nandatown.sim.validators import validator


def _share_of_top(counts: Counter) -> float:
    total = sum(counts.values())
    return (counts.most_common(1)[0][1] / total) if total else 0.0


def _hhi(counts: Counter) -> float:
    """Herfindahl index: 1/n when trade is spread evenly across n
    stalls, 1.0 when a single stall takes everything."""
    total = sum(counts.values())
    if not total:
        return 0.0
    return sum((c / total) ** 2 for c in counts.values())


@validator("fest")
def fest(spec, trace) -> list[StageResult]:
    bought = trace.find("bought")
    stalls = [a.name for a in spec.agents if a.role == "stall"]
    counts = Counter(e.subject for e in bought)
    ids = [e.event_id for e in bought]

    stages: list[StageResult] = []

    if not bought:
        stages.append(StageResult(
            name="trade_happened", status="failed", evidence=[],
            note="no attendee completed a purchase"))
        return stages

    stages.append(StageResult(
        name="trade_happened", status="passed", evidence=ids[:8],
        note=f"{len(bought)} purchases across {len(counts)} of"
             f" {len(stalls)} stalls"))

    # Concentration. Reported, never judged: the number is the result.
    top_share = _share_of_top(counts)
    hhi = _hhi(counts)
    even = 1.0 / len(stalls) if stalls else 0.0
    leader, leader_n = counts.most_common(1)[0]
    stages.append(StageResult(
        name="concentration", status="passed", evidence=ids[:8],
        note=f"top stall {leader} took {leader_n} of {len(bought)}"
             f" purchases ({top_share:.0%}); HHI {hhi:.3f} against"
             f" {even:.3f} if trade were spread evenly"))

    # Did any stall get nothing at all?
    idle = [s for s in stalls if s not in counts]
    stages.append(StageResult(
        name="stall_coverage",
        status="passed" if not idle else "failed",
        evidence=ids[:8],
        note=(f"every stall traded" if not idle else
              f"{len(idle)} of {len(stalls)} stalls sold nothing:"
              f" {', '.join(sorted(idle)[:5])}")))

    # Attendees turned away because the popular stall ran dry.
    turned = trace.find("turned_away")
    gave_up = trace.find("gave_up")
    stages.append(StageResult(
        name="unmet_demand", status="passed",
        evidence=[e.event_id for e in turned][:8],
        note=f"{len(turned)} orders hit an empty stall;"
             f" {len(gave_up)} attendees left without buying"))

    # Money is the one hard invariant here.
    settled = trace.find("payment_settled")
    stages.append(StageResult(
        name="payments_recorded",
        status="passed" if len(settled) == len(bought) else "failed",
        evidence=[e.event_id for e in settled][:8],
        note=f"{len(settled)} settlements for {len(bought)} purchases"))

    return stages
