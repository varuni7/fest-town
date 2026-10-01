"""Ticketed fest. Day runs 08:00-22:00 over 70 units (1 unit = 12 min).
Box office 08:00-11:00 = units 0-15. Shows run in the evening."""
import pathlib, random

def clock(t): 
    m = int(8*60 + t*12); return f"{m//60:02d}:{m%60:02d}"

SALE_FROM, SALE_TO = 0.0, 15.0            # 08:00 - 11:00
SHOWS = [   # name, capacity, price, showtime
    ("concert-1",   40, 1500, 55.0),      # 19:00
    ("concert-2",   40, 1200, 60.0),      # 20:00
    ("puppet-show", 25,  400, 45.0),      # 17:00
]

def gen(n_fans=120, seed=42, late_share=0.25, transfer_share=0.30):
    rng = random.Random(99)
    out = ["name: fest_tickets",
           f"description: Three ticketed shows, box office {clock(SALE_FROM)}"
           f"-{clock(SALE_TO)} only, with transfers afterwards.",
           f"seed: {seed}", "validator: tickets",
           "plugin_files: [fest_tickets.py, fest_ticket_validator.py]",
           "agents:"]
    for name, cap, price, show_at in SHOWS:
        out.append(
            f"  - name: box-{name}\n    role: box_office\n"
            f"    config: {{show: {name}, capacity: {cap},"
            f" price_cents: {price}, sale_from: {SALE_FROM},"
            f" sale_to: {SALE_TO}, balance_cents: 0}}")
    for i in range(n_fans):
        show = rng.choice([s[0] for s in SHOWS])
        show_at = dict((s[0], s[3]) for s in SHOWS)[show]
        # a quarter of fans try to buy after the window shuts
        if rng.random() < late_share:
            buy = round(rng.uniform(SALE_TO + 2, SALE_TO + 25), 2)
        else:
            buy = round(rng.uniform(SALE_FROM + 0.5, SALE_TO - 0.5), 2)
        cfg = (f"show: {show}, buy_at: {buy},"
               f" arrive_at: {round(show_at - 1.0, 2)}, balance_cents: 9000")
        # some pass their ticket on, in the afternoon
        if rng.random() < transfer_share:
            cfg += f", transfer_at: {round(rng.uniform(30.0, 40.0), 2)}"
        out.append(f"  - name: fan-{i}\n    role: fan\n    config: {{{cfg}}}")
    out += ["faults: []", "max_time: 70", ""]
    return "\n".join(out)

pathlib.Path("scenarios/fest_tickets.yaml").write_text(gen())
print(f"box office {clock(SALE_FROM)}-{clock(SALE_TO)} | "
      f"shows: " + ", ".join(f"{n} {clock(t)} cap {c}" for n,c,_,t in SHOWS))
