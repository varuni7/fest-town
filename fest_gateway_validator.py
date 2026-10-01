"""Gateway invariants: nothing orphaned on either side.

With an atomic ledger these are trivially true. With a gateway they are
the whole question, because a webhook can be lost, doubled or late.
"""

from __future__ import annotations

from collections import Counter

from nandatown.records import StageResult
from nandatown.sim.validators import validator


@validator("gateway")
def gateway(spec, trace) -> list[StageResult]:
    captured = trace.find("payment_captured")
    issued = trace.find("ticket_issued")
    paid = trace.find("paid")
    stages: list[StageResult] = []

    stages.append(StageResult(
        name="flow_observed",
        status="passed" if paid else "failed",
        evidence=[e.event_id for e in paid][:8],
        note=f"{len(paid)} payers settled, {len(captured)} captures,"
             f" {len(issued)} tickets issued"))

    cap_ids = {e.subject for e in captured}
    tick_intents = Counter(e.detail.get("intent") for e in issued)

    # 1. One payment must not buy two tickets. This is what a duplicated
    #    webhook attacks.
    doubled = [i for i, n in tick_intents.items() if n > 1]
    stages.append(StageResult(
        name="one_payment_one_ticket",
        status="passed" if not doubled else "failed",
        evidence=[e.event_id for e in issued][:8],
        note=(f"{len(issued)} tickets from {len(tick_intents)} payments"
              if not doubled else
              f"{len(doubled)} payments each produced more than one"
              f" ticket: {doubled[:5]}")))

    # 2. Nobody holds a ticket they did not pay for.
    unpaid = [i for i in tick_intents if i not in cap_ids]
    stages.append(StageResult(
        name="no_unpaid_ticket",
        status="passed" if not unpaid else "failed",
        evidence=[e.event_id for e in issued][:8],
        note=("every ticket traces to a captured payment" if not unpaid
              else f"{len(unpaid)} tickets with no capture behind them")))

    # 3. Nobody paid and got nothing. This is the one a lost webhook
    #    breaks, and the one that matters to the person who paid.
    orphan = sorted(cap_ids - set(tick_intents))
    stages.append(StageResult(
        name="no_payment_without_ticket",
        status="passed" if not orphan else "failed",
        evidence=[e.event_id for e in captured][:8],
        note=("every captured payment produced a ticket" if not orphan
              else f"{len(orphan)} payments captured with no ticket"
                   f" issued: {orphan[:5]}")))

    return stages
