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

    # Money is the one hard invariant here. Filter to stall purchases:
    # a combined fest also settles ticket payments, which are not ours.
    settled = [e for e in trace.find("payment_settled")
               if str(e.subject).startswith("buy-")]
    stages.append(StageResult(
        name="payments_recorded",
        status="passed" if len(settled) == len(bought) else "failed",
        evidence=[e.event_id for e in settled][:8],
        note=f"{len(settled)} settlements for {len(bought)} purchases"))

    return stages


@validator("fest_pricing")
def fest_pricing(spec, trace) -> list[StageResult]:
    """Everything the fest validator checks, plus what the prices did."""
    stages = fest(spec, trace)
    moves = trace.find("repriced")
    failed = trace.find("reprice_failed")

    if not moves:
        stages.append(StageResult(
            name="pricing", status="not_enough_evidence",
            note=f"no stall repriced; {len(failed)} attempts failed"))
        return stages

    # Where prices ended up, and how far apart they are.
    final: dict[str, int] = {}
    first: dict[str, int] = {}
    for e in moves:
        first.setdefault(e.subject, e.detail["from"])
        final[e.subject] = e.detail["to"]
    spread_start = max(first.values()) - min(first.values())
    spread_end = max(final.values()) - min(final.values())
    stages.append(StageResult(
        name="price_dispersion", status="passed",
        evidence=[e.event_id for e in moves][:8],
        note=f"{len(moves)} price changes across {len(final)} stalls;"
             f" spread {spread_start} -> {spread_end} cents"
             f" ({'converged' if spread_end < spread_start else 'widened'})"))

    # Does a busy stall put its price up? One sign the model is
    # responding to its situation rather than drifting.
    busy_up = sum(1 for e in moves
                  if e.detail["served_since"] > 0
                  and e.detail["to"] > e.detail["from"])
    busy = sum(1 for e in moves if e.detail["served_since"] > 0)
    quiet_down = sum(1 for e in moves
                     if e.detail["served_since"] == 0
                     and e.detail["to"] < e.detail["from"])
    quiet = sum(1 for e in moves if e.detail["served_since"] == 0)
    stages.append(StageResult(
        name="responds_to_demand", status="passed",
        evidence=[e.event_id for e in moves][:8],
        note=f"busy stalls raised price {busy_up}/{busy} times;"
             f" idle stalls cut price {quiet_down}/{quiet} times"
             + (f"; {len(failed)} calls failed" if failed else "")))

    return stages


@validator("fest_pricing_mixed")
def fest_pricing_mixed(spec, trace) -> list[StageResult]:
    """Pricing checks, plus the within-run control: do the stalls that
    reprice actually do better than the ones that cannot?"""
    stages = fest_pricing(spec, trace)
    thinkers = {a.name for a in spec.agents if a.role == "llm_stall"}
    fixed = {a.name for a in spec.agents if a.role == "stall"}
    if not thinkers or not fixed:
        return stages

    bought = trace.find("bought")
    sales = Counter(e.subject for e in bought)
    revenue = Counter()
    for e in bought:
        revenue[e.subject] += e.detail["price_cents"]

    t_sales = sum(sales[s] for s in thinkers)
    f_sales = sum(sales[s] for s in fixed)
    t_rev = sum(revenue[s] for s in thinkers)
    f_rev = sum(revenue[s] for s in fixed)
    stages.append(StageResult(
        name="adaptive_vs_fixed", status="passed",
        evidence=[e.event_id for e in bought][:8],
        note=f"{len(thinkers)} repricing stalls took {t_sales} sales for"
             f" {t_rev} cents ({t_rev // max(1, t_sales)}/sale);"
             f" {len(fixed)} fixed-price stalls took {f_sales} for"
             f" {f_rev} cents ({f_rev // max(1, f_sales)}/sale)"))
    return stages


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return None if dx == 0 or dy == 0 else num / (dx * dy)


@validator("fest_reputation")
def fest_reputation(spec, trace) -> list[StageResult]:
    """Does reputation still say anything true once people game it?

    The question is not whether an attack happened. It is whether a
    buyer reading the scores would be misled.
    """
    stages = fest(spec, trace)
    stalls = {a.name: a.config for a in spec.agents
              if a.role in ("stall", "smear_stall", "llm_stall")}
    if not stalls:
        return stages

    final: dict[str, int] = {}
    for e in trace.find("reputation_updated"):
        final[e.subject] = e.detail["score"]

    quality = [stalls[n].get("quality", 0.5) for n in stalls]
    scores = [final.get(n, 0) for n in stalls]
    r = _pearson(quality, scores)
    stages.append(StageResult(
        name="reputation_tracks_quality",
        status="passed" if (r is not None and r > 0.5) else "failed",
        evidence=trace.ids("reputation_updated")[:8],
        note=(f"correlation between stall quality and final reputation"
              f" r={r:.2f}" if r is not None else
              "no reputation movement to correlate")
             + ("; a buyer reading the scores would be misled"
                if (r is None or r <= 0.5) else "")))

    # What the attacks did, and whether the layer absorbed them.
    smears = trace.find("smeared")
    shills = trace.find("shilled")
    ignored = trace.find("rating_ignored")
    attempted = (sum(e.detail["count"] for e in smears)
                 + sum(e.detail["count"] for e in shills))
    if attempted:
        stages.append(StageResult(
            name="gaming_absorbed",
            status="passed" if len(ignored) >= attempted else "failed",
            evidence=[e.event_id for e in (smears + shills)][:8],
            note=f"{attempted} ratings sent by agents that bought nothing"
                 f" ({len(smears)} smear bursts, {len(shills)} shill"
                 f" bursts); {len(ignored)} were ignored by the trust"
                 f" layer"))
    return stages


@validator("midway")
def midway(spec, trace) -> list[StageResult]:
    """One fest: stalls on the midway and ticketed shows, judged together."""
    # Plugin files are loaded by path, so the ticket validator comes
    # from the registry rather than an import.
    from nandatown.sim.validators import VALIDATORS
    stages = fest_reputation(spec, trace)
    tickets = VALIDATORS.get("tickets")
    if tickets and any(a.role == "box_office" for a in spec.agents):
        stages += [s for s in tickets(spec, trace)
                   if s.name != "tickets_sold"]
    return stages
