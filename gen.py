"""Generate a fest scenario.

The fest runs 10:00 to 22:00, mapped onto 60 units of logical time, so
one hour is five units. Lunch is 13:00 to 15:00, which is units 15 to
25: more people arrive then, and most of them want food.
"""

from __future__ import annotations

import pathlib
import random

OPEN, CLOSE = 0.0, 60.0
LUNCH_FROM, LUNCH_TO = 15.0, 25.0          # 13:00 to 15:00
LUNCH_SHARE = 0.45                          # of all arrivals
WANTS_FOOD_AT_LUNCH = 0.85
WANTS_FOOD_OTHERWISE = 0.30

# name, kind, category, price (cents), quality
STALLS = [
    ("burger-1",    "burgers",   "food",     250, 0.80),
    ("burger-2",    "burgers",   "food",     220, 0.55),
    ("burger-3",    "burgers",   "food",     300, 0.35),
    ("ice-cream-1", "ice cream", "food",     120, 0.75),
    ("ice-cream-2", "ice cream", "food",     150, 0.45),
    ("bake-sale",   "bakes",     "food",      80, 0.65),
    ("games",       "games",     "activity", 100, 0.60),
    ("darts",       "darts",     "activity",  50, 0.50),
    ("photo-booth", "photos",    "activity", 200, 0.70),
]


def clock(t: float) -> str:
    mins = int(10 * 60 + t * 12)            # 1 unit = 12 minutes
    return f"{mins // 60:02d}:{mins % 60:02d}"


def gen(n_attendees: int, rule: str = "reputation", seed: int = 42) -> str:
    rng = random.Random(1234)               # scenario shape, not run seed
    stock = max(20, n_attendees)            # never the binding constraint

    out = [
        "name: fest",
        f"description: Nine stalls over a twelve hour fest with a lunch"
        f" rush; {n_attendees} attendees choosing by {rule}.",
        f"seed: {seed}",
        "validator: fest",
        "plugin_files: [fest_roles.py, fest_trust.py, fest_validator.py]",
        "agents:",
    ]

    for name, kind, cat, price, quality in STALLS:
        out.append(
            f"  - name: {name}\n    role: stall\n"
            f"    config: {{kind: {kind}, category: {cat},"
            f" price_cents: {price}, stock: {stock},"
            f" quality: {quality}, balance_cents: 0}}")

    for i in range(n_attendees):
        if rng.random() < LUNCH_SHARE:
            at = rng.uniform(LUNCH_FROM, LUNCH_TO)
            wants_food = rng.random() < WANTS_FOOD_AT_LUNCH
        else:
            at = rng.uniform(OPEN + 1.0, CLOSE - 5.0)
            wants_food = rng.random() < WANTS_FOOD_OTHERWISE
        want = "food" if wants_food else "activity"
        out.append(
            f"  - name: att-{i}\n    role: attendee\n"
            f"    config: {{want: {want}, arrive_at: {round(at, 3)},"
            f" rule: {rule}, look_at: 3, balance_cents: 5000}}")

    out += ["faults: []", f"max_time: {int(CLOSE)}", ""]
    return "\n".join(out)


if __name__ == "__main__":
    for n in (50, 200, 500):
        for rule in ("random", "price", "reputation", "crowd"):
            pathlib.Path(f"scenarios/fest_{n}_{rule}.yaml").write_text(gen(n, rule))
    print(f"wrote 12 scenarios: {{50,200,500}} x "
          f"{{random,price,reputation,crowd}}")
    print(f"lunch window {clock(LUNCH_FROM)}-{clock(LUNCH_TO)},"
          f" fest {clock(OPEN)}-{clock(CLOSE)}")
