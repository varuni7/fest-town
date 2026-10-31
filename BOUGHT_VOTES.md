# What a vote costs under reputation.capped.v1

`reputation.capped.v1` landed upstream in PR #290. It fixes a real
problem: the default `reputation.v1` sums every receipt, so one account
writing receipts in a loop moves a score without limit. The capped layer
bounds each observer to +/-1 and gives an observer weight 0 until it has
traded.

Both halves read off the event log, which is the right instinct. The
gap is in the second one:

```python
def traded(self, observer: str) -> bool:
    for event in self.engine.events:
        if event.kind != "payment_settled":
            continue
        detail = event.detail if isinstance(event.detail, dict) else {}
        if observer in (detail.get("from"), detail.get("to")):
            return True
    return False
```

Any settled payment anywhere in the run earns full weight. Not a payment
to the stall being rated. So a vote is for sale at the price of the
cheapest item on the ground.

## The attack

`buying_shill` in `fest_attacks.py` buys one 80 cent item from the bake
sale, rates nothing there, and spends its weight praising a stall it
never bought from. Straight from the trace:

```
shill-0 -> burger-3  weight=1 delta=1 reason=counted
shill-0 -> burger-3  weight=1 delta=0 reason=observer_cap_reached
shill purchases: 60 | to: ['bake-sale'] | each: 80 cents
```

The cap is working. The second praise is correctly discarded. The first
one counted because an unrelated 80 cent purchase bought it.

## How much it costs

Target is burger-3, the worst food at the fest (quality 0.45). "Reached
#1" means it ended the day as the highest rated stall. 150 honest
attendees, 5 seeds per row.

| accounts | cost | `reputation.v1` | `reputation.capped.v1` | `earned.v1` |
|---|---|---|---|---|
| 0 | 0c | 0/5 | 0/5 | 0/5 |
| 4 | 320c | 0/5 | 0/5 | 0/5 |
| 10 | 800c | 2/5 | 0/5 | 0/5 |
| 20 | 1600c | **5/5** | 2/5 | 0/5 |
| 30 | 2400c | **5/5** | **4/5** | 0/5 |
| 40 | 3200c | **5/5** | **4/5** | 0/5 |
| 60 | 4800c | **5/5** | **4/5** | 0/5 |

```
python sweep_votes.py reputation.capped.v1 1,2,3,4,5
```

The capped layer raises the price of taking first place from about 1600
cents to about 2400 cents. It does not close the door. Above that, the
worst stall at the fest is the best reviewed one in four runs out of
five.

## What closes it

`earned.v1` in `fest_earned_trust.py` counts a rating only from an
account with a settled payment **to that subject**, once per pair. The
target never reaches first place at any price tested, and its score
stays pinned between -2 and +2 while the attack scales to sixty
accounts.

The two are complementary, and the merge is small: keep the clamp, make
the weight per-subject.

```python
def weight(self, observer: str, subject: str) -> int:
    return 1 if self.traded_with(observer, subject) else 0
```

## What it costs in turn

Requiring a trade with the subject silences everyone who has not bought
from that stall, so a new stall opens with no reviews and no way to get
the first one except from people who buy on no information. The capped
layer does not have that problem. Whether that is worse than a vote
costing 80 cents is a judgement, not a measurement, and this does not
make it.

## Scope

Five seeds per row, one fest topology, 150 attendees, one target. The
price in cents is the cheapest item in this particular fest; the real
quantity is "one purchase", and what that costs depends on the market.
Rank is by reputation score at the end of the day, not by sales.
