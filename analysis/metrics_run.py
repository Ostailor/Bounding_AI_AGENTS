#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from typing import Dict, List, Optional, Tuple


def load_json(path: str) -> Dict:
    with open(path, "r") as f:
        return json.load(f)


def read_steps(run_dir: str) -> List[Dict]:
    steps = []
    with open(os.path.join(run_dir, "steps.jsonl"), "r") as f:
        for line in f:
            try:
                steps.append(json.loads(line))
            except Exception:
                pass
    return steps


def read_trades(run_dir: str) -> List[Dict]:
    path = os.path.join(run_dir, "trades.jsonl")
    if not os.path.exists(path):
        return []
    out: List[Dict] = []
    with open(path, "r") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def window_slice(steps: List[Dict], warmup: int, measure: int) -> List[Dict]:
    return [s for s in steps if warmup < int(s.get("t", 0)) <= warmup + measure]


def series_from_steps(steps: List[Dict]) -> List[float]:
    prices: List[float] = []
    for s in steps:
        mid = s.get("mid")
        if mid is not None:
            prices.append(float(mid))
        else:
            lt = s.get("last_trade")
            if lt is not None:
                prices.append(float(lt))
    return prices


def log_returns(prices: List[float]) -> List[float]:
    rets: List[float] = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0 and prices[i] > 0:
            rets.append(math.log(prices[i]/prices[i-1]))
    return rets


def stdev(xs: List[float]) -> float:
    n = len(xs)
    if n == 0:
        return float('nan')
    m = sum(xs)/n
    return (sum((x-m)**2 for x in xs)/n) ** 0.5


def kurtosis(xs: List[float]) -> float:
    n = len(xs)
    if n < 4:
        return float('nan')
    m = sum(xs)/n
    s2 = sum((x-m)**2 for x in xs)/n
    if s2 == 0:
        return float('nan')
    s4 = sum((x-m)**4 for x in xs)/n
    return s4/(s2*s2)


def crash_probability(prices: List[float], drop_pct: float = 0.05, window: int = 50) -> float:
    if not prices:
        return float('nan')
    n = 0
    crashes = 0
    for i in range(1, len(prices)):
        start = max(0, i - window)
        prev_max = max(prices[start:i]) if i > start else prices[i-1]
        if prev_max > 0:
            drawdown = (prev_max - prices[i]) / prev_max
            if drawdown >= drop_pct:
                crashes += 1
        n += 1
    return crashes / n if n else float('nan')


def gini(values: List[float]) -> float:
    n = len(values)
    if n == 0:
        return float('nan')
    # shift to non-negative
    mn = min(values)
    xs = [v - mn + 1e-9 for v in values]
    s = sum(xs)
    if s == 0:
        return 0.0
    xs_sorted = sorted(xs)
    cum = 0.0
    for i, v in enumerate(xs_sorted, 1):
        cum += i * v
    return (2*cum)/(n*s) - (n+1)/n


def messages_and_trades(steps: List[Dict]) -> Tuple[int, int]:
    msgs = sum(int(s.get("num_messages", 0)) for s in steps)
    trades = sum(int(s.get("num_trades", 0)) for s in steps)
    return msgs, trades


def compute_metrics(run_dir: str) -> Dict[str, float]:
    meta = load_json(os.path.join(run_dir, "run.json"))
    warmup = int(meta.get("warmup_steps", 0))
    measure = int(meta.get("measure_steps", 0))
    steps = window_slice(read_steps(run_dir), warmup, measure)
    prices = series_from_steps(steps)
    rets = log_returns(prices)
    # stability metrics
    vol = stdev(rets)
    kurt = kurtosis(rets)
    crash = crash_probability(prices)
    # market health proxy
    mean_spread = sum(float(s.get("spread")) for s in steps if s.get("spread") is not None) / max(1, sum(1 for s in steps if s.get("spread") is not None))
    msgs, trades = messages_and_trades(steps)
    mtt = (msgs / trades) if trades > 0 else float('inf')
    # fairness
    summ = load_json(os.path.join(run_dir, "summary.json"))
    pnls = [float(r.get("pnl", 0.0)) for r in summ.get("summaries", [])]
    g = gini(pnls)
    # profit aggregates
    mean_pnl = sum(pnls) / len(pnls) if pnls else 0.0
    # welfare proxy: allocative efficiency using mid as reference (surplus share captured)
    # For each trade at time t, efficiency contribution = max(half_spread - |price - mid|, 0)
    # Normalized by total potential half_spread across traded volume
    t_to_ms: Dict[int, Tuple[Optional[float], Optional[float]]] = {int(s.get("t", 0)): (s.get("mid"), s.get("spread")) for s in steps}
    trades = read_trades(run_dir)
    num = 0.0
    den = 0.0
    for tr in trades:
        t = int(tr.get("t", -1))
        m, sp = t_to_ms.get(t, (None, None))
        if m is None or sp is None:
            continue
        hs = float(sp) / 2.0
        px = float(tr.get("price"))
        q = float(tr.get("qty", 0))
        dev = abs(px - float(m))
        num += max(hs - dev, 0.0) * q
        den += hs * q
    alloc_eff_mid = (num / den) if den > 0 else float('nan')
    # welfare (stronger): call-style clairvoyant surplus using observed buy/sell limits within rolling batches
    alloc_eff_call = float('nan')
    trades_full = read_trades(run_dir)
    if trades_full:
        from collections import defaultdict
        by_t: Dict[int, List[Dict]] = defaultdict(list)
        for tr in trades_full:
            by_t[int(tr.get("t", 0))].append(tr)
        ts_sorted = sorted(by_t.keys())
        W = 50
        effs: List[float] = []
        for i in range(0, len(ts_sorted)):
            t0 = ts_sorted[i]
            tw = [t for t in ts_sorted if t0 <= t < t0 + W]
            buys: List[float] = []
            sells: List[float] = []
            for t in tw:
                for tr in by_t[t]:
                    bl = tr.get("buyer_limit")
                    sl = tr.get("seller_limit")
                    q = int(tr.get("qty", 0))
                    # realized surplus (if both limits known)
                    if bl is not None and sl is not None:
                        pass  # accounted below via max computation; we focus on potential vs realized ratio via counts
                    # assemble limit lists for potential surplus
                    if bl is not None:
                        buys.extend([float(bl)] * q)
                    if sl is not None:
                        sells.extend([float(sl)] * q)
            if not buys or not sells:
                continue
            buys.sort(reverse=True)
            sells.sort()
            m = min(len(buys), len(sells))
            # maximum feasible surplus within window
            max_sur = 0.0
            realized_sur = 0.0
            for k in range(m):
                if buys[k] >= sells[k]:
                    max_sur += (buys[k] - sells[k])
            # realized surplus: match each trade by its own limits when available
            for t in tw:
                for tr in by_t[t]:
                    bl = tr.get("buyer_limit")
                    sl = tr.get("seller_limit")
                    q = int(tr.get("qty", 0))
                    if bl is not None and sl is not None and bl >= sl:
                        realized_sur += (float(bl) - float(sl)) * q
            if max_sur > 0:
                effs.append(realized_sur / max_sur)
        if effs:
            alloc_eff_call = sum(effs) / len(effs)

    # liquidity resilience: spread half-life after shocks
    spreads = [s.get("spread") for s in steps if s.get("spread") is not None]
    hl = float('nan')
    if spreads:
        import statistics
        baseline = statistics.median([float(x) for x in spreads])
        # shock threshold as 90th percentile
        s_sorted = sorted([float(x) for x in spreads])
        idx = int(0.9 * (len(s_sorted)-1))
        thresh = s_sorted[idx]
        half_lives: List[int] = []
        for i, s in enumerate([float(x) for x in spreads]):
            if s >= thresh:
                target = baseline + 0.5 * max(0.0, s - baseline)
                # find earliest j>i with spread <= target
                for j in range(i+1, len(spreads)):
                    sj = float(spreads[j])
                    if sj <= target:
                        half_lives.append(j - i)
                        break
        if half_lives:
            half_lives.sort()
            hl = float(half_lives[len(half_lives)//2])
    # depth recovery half-life
    depths = []
    for s in steps:
        b = s.get("depth1_bid")
        a = s.get("depth1_ask")
        if b is not None or a is not None:
            depths.append(float((b or 0) + (a or 0)))
    dhl = float('nan')
    if depths:
        import statistics
        baseline_d = statistics.median(depths)
        d_sorted = sorted(depths)
        idxd = max(0, int(0.1 * (len(d_sorted)-1)))
        thresh_d = d_sorted[idxd]
        half_lives_d: List[int] = []
        for i, dv in enumerate(depths):
            if dv <= thresh_d:
                target = baseline_d - 0.5 * max(0.0, baseline_d - dv)
                for j in range(i+1, len(depths)):
                    if depths[j] >= target:
                        half_lives_d.append(j - i)
                        break
        if half_lives_d:
            half_lives_d.sort()
            dhl = float(half_lives_d[len(half_lives_d)//2])

    return {
        "realized_vol": vol,
        "kurtosis": kurt,
        "crash_prob": crash,
        "mean_spread": mean_spread,
        "msg_to_trade": mtt,
        "gini_pnl": g,
        "mean_agent_pnl": mean_pnl,
        "alloc_eff_mid": alloc_eff_mid,
        "spread_halflife": hl,
        "alloc_eff_call": alloc_eff_call,
        "depth_halflife": dhl,
    }


def main():
    ap = argparse.ArgumentParser(description="Compute M4 metrics for a single run directory")
    ap.add_argument("--run_dir", required=True)
    ap.add_argument("--out_json", default=None)
    args = ap.parse_args()
    metrics = compute_metrics(args.run_dir)
    if args.out_json:
        os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
        with open(args.out_json, "w") as f:
            json.dump(metrics, f, indent=2)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
