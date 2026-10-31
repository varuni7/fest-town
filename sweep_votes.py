"""What does a vote cost under reputation.capped.v1?

The cap bounds one observer to +/-1, and the weight is earned by any
settled payment anywhere in the run. So the attack is no longer "rate
in a loop", it is "bring more accounts". This sweeps the number of
accounts and finds where the target stall's score overtakes the honest
leader, and what that cost in cents.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import yaml

NANDATOWN = "/tmp/ntvenv/bin/nandatown"
BASE = pathlib.Path("scenarios/rep_attacked_naive.yaml")
TARGET = "burger-3"
CHEAPEST = 80          # the bake sale, what a vote costs
QUALITY = {"burger-1": 0.85, "burger-2": 0.65, "burger-3": 0.45,
           "ice-cream-1": 0.75, "ice-cream-2": 0.55, "bake-sale": 0.35}


def scenario(n_shills: int, layer: str, out: pathlib.Path,
             seed: int) -> None:
    spec = yaml.safe_load(BASE.read_text())
    spec["seed"] = seed
    spec["name"] = f"votes_{n_shills}"
    spec["description"] = (f"{n_shills} accounts buying a vote under"
                           f" {layer}.")
    spec["layers"] = {"trust": layer}
    # Plugin paths resolve against the scenario file, and these are
    # written to a temp dir.
    here = BASE.resolve().parent
    spec["plugin_files"] = [str((here / f).resolve())
                            for f in spec["plugin_files"]]
    spec["agents"] = [a for a in spec["agents"] if a["role"] != "shill"]
    for i in range(n_shills):
        spec["agents"].append({
            "name": f"shill-{i}", "role": "buying_shill",
            "config": {"target": TARGET, "praises": 2,
                       "buy_at": round(3.0 + i * 0.05, 2),
                       "praise_at": round(9.0 + i * 0.05, 2),
                       "balance_cents": 500}})
    out.write_text(yaml.safe_dump(spec, sort_keys=False))


def run(path: pathlib.Path) -> dict:
    r = subprocess.run([NANDATOWN, "run", str(path), "--out", "/tmp/sweep"],
                       capture_output=True, text=True)
    m = re.search(r"Evidence bundle: (\S+)", r.stdout)
    if not m:
        return {"error": (r.stdout + r.stderr)[-200:]}
    b = pathlib.Path(m.group(1))
    ev = [json.loads(l) for l in (b / "events.jsonl").read_text().splitlines()]
    score, sold = {}, {}
    for e in ev:
        if e["kind"] == "reputation_updated":
            score[e["subject"]] = e["detail"].get("score", 0)
        elif e["kind"] == "bought":
            sold[e["subject"]] = sold.get(e["subject"], 0) + 1
    return {"score": score, "sold": sold}


def main() -> None:
    layer = sys.argv[1] if len(sys.argv) > 1 else "reputation.capped.v1"
    seeds = [int(s) for s in (sys.argv[2].split(",") if len(sys.argv) > 2
                              else ["1", "2", "3", "4", "5"])]
    print(f"layer: {layer}   target: {TARGET} (quality {QUALITY[TARGET]},"
          f" the worst food at the fest)   seeds: {len(seeds)}\n")
    print(f"{'accounts':>8} {'cost':>7} {'reached #1':>11} "
          f"{'median rank':>12} {'median score':>13}")
    for n in (0, 4, 10, 20, 30, 40, 60):
        ranks, scores = [], []
        for seed in seeds:
            path = pathlib.Path(f"/tmp/votes_{n}_{seed}.yaml")
            scenario(n, layer, path, seed)
            out = run(path)
            if "error" in out:
                continue
            s = out["score"]
            ranks.append(sorted(s, key=lambda k: -s.get(k, 0)).index(TARGET) + 1)
            scores.append(s.get(TARGET, 0))
        if not ranks:
            print(f"{n:>8}  all runs failed")
            continue
        ranks.sort(); scores.sort()
        won = sum(1 for r in ranks if r == 1)
        print(f"{n:>8} {n * CHEAPEST:>6}c {f'{won}/{len(ranks)}':>11} "
              f"{ranks[len(ranks)//2]:>12} {scores[len(scores)//2]:>13}")


if __name__ == "__main__":
    main()
