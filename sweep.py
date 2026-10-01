"""n=500, four rules, thirty seeds each. One run per cell is what
Section 5 criticises everyone else for, so don't do it here."""
import re, statistics as st, sys, tempfile, warnings
sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
from nandatown.sim.runner import run_lab

SEEDS = range(1, 31)
RULES = ("random", "price", "reputation", "crowd")

def hhi_of(result):
    for s in result.stages:
        if s.name == "concentration":
            m = re.search(r"HHI ([0-9.]+)", s.note)
            if m:
                return float(m.group(1))
    return None

print(f"{'RULE':<12} {'MEAN':<7} {'SD':<7} {'MIN':<7} {'MAX':<7} {'RANGE'}")
with tempfile.TemporaryDirectory() as tmp:
    for rule in RULES:
        vals = []
        for seed in SEEDS:
            _, res = run_lab(f"scenarios/fest_500_{rule}.yaml", tmp, seed=seed)
            h = hhi_of(res)
            if h is not None:
                vals.append(h)
        print(f"{rule:<12} {st.mean(vals):<7.3f} {st.stdev(vals):<7.3f} "
              f"{min(vals):<7.3f} {max(vals):<7.3f} "
              f"{max(vals)-min(vals):.3f}   (n={len(vals)})")
print("\neven across 9 stalls = 0.111")
