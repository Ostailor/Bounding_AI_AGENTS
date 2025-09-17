#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
from typing import List, Tuple, Dict


def generate_values(n: int, seed: int, dist: str = "normal") -> List[float]:
    r = random.Random(seed)
    if dist == "normal":
        return [100.0 + r.gauss(0, 0.5) for _ in range(n)]
    if dist == "uniform":
        return [100.0 + (r.random() - 0.5) for _ in range(n)]
    raise ValueError("unknown dist")


def clairvoyant_surplus(vals: List[float]) -> Tuple[float, float]:
    # One-shot call: split around median
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    buys = s[mid:]
    sells = list(reversed(s[:mid]))  # highest asks
    m = min(len(buys), len(sells))
    surplus = sum(max(0.0, b - a) for b, a in zip(buys[:m], sells[:m]))
    return surplus, (sum(buys[:m]) / m if m else 0.0)


def quantile_threshold(vals: List[float], m_samples: int, seed: int) -> float:
    r = random.Random(seed)
    samples = [r.choice(vals) for _ in range(m_samples)]
    samples.sort()
    q = 0.5  # median
    idx = min(max(int(q * (len(samples) - 1)), 0), len(samples) - 1)
    return samples[idx]


def realized_surplus(vals: List[float], thresh: float) -> float:
    # Trade any buyer above thresh with any seller below thresh
    buys = sorted([v for v in vals if v >= thresh], reverse=True)
    sells = sorted([v for v in vals if v < thresh])
    m = min(len(buys), len(sells))
    return sum(max(0.0, buys[i] - sells[i]) for i in range(m))


def experiment(n: int, samples: int, trials: int, seed: int) -> dict:
    r = random.Random(seed)
    eff: List[float] = []
    for t in range(trials):
        vals = generate_values(n, r.randrange(10**9))
        opt, _ = clairvoyant_surplus(vals)
        th = quantile_threshold(vals, samples, r.randrange(10**9))
        rs = realized_surplus(vals, th)
        eff.append((rs / opt) if opt > 0 else 1.0)
    mean = sum(eff) / len(eff)
    lo = sorted(eff)[int(0.05 * len(eff))]
    hi = sorted(eff)[int(0.95 * len(eff)) - 1]
    return {"n": n, "samples": samples, "trials": trials, "eff_mean": mean, "eff_p05": lo, "eff_p95": hi}


def try_import_matplotlib():
    try:
        import matplotlib  # type: ignore
        try:
            matplotlib.use("Agg", force=True)
        except Exception:
            pass
        import matplotlib.pyplot as plt  # type: ignore
        return plt
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="SCM/RBA efficiency vs compute demo")
    ap.add_argument("--n", type=int, default=200, help="Single N if --n_list not set")
    ap.add_argument("--n_list", type=int, nargs="*", default=[], help="Optional list of N values")
    ap.add_argument("--samples", type=int, nargs="*", default=[2, 4, 8, 16, 32, 64])
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--out", default="analysis/out/theory_rba_efficiency.png")
    args = ap.parse_args()

    Ns = args.n_list if args.n_list else [args.n]
    results: Dict[int, List[dict]] = {}
    for N in Ns:
        curve = []
        for m in args.samples:
            curve.append(experiment(N, m, args.trials, args.seed + 1000 * N + m))
        results[N] = curve

    print(json.dumps({"results": results}, indent=2))

    if args.plot:
        plt = try_import_matplotlib()
        if plt is None:
            print("matplotlib not available; skipping plot")
            return
        import os
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        plt.figure(figsize=(6.5, 4))
        for N in sorted(results.keys()):
            xs = [r["samples"] for r in results[N]]
            # plot efficiency deficit on log–log: 1 - eff_mean vs samples
            ys = [max(1e-6, 1.0 - float(r["eff_mean"])) for r in results[N]]
            plt.loglog(xs, ys, marker="o", label=f"N={N}")
        plt.xlabel("samples per agent (compute), log scale")
        plt.ylabel("1 - efficiency (mean), log scale")
        plt.title("SCM/RBA: efficiency deficit vs compute")
        plt.legend(loc="best", fontsize=8)
        plt.tight_layout()
        plt.savefig(args.out, dpi=150)
        print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
