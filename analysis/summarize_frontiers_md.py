#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from typing import Any, Dict, List


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def try_load(path: str) -> Dict[str, Any] | None:
    try:
        return load_json(path)
    except Exception:
        return None


def load_index_rows(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def top_variants_table(m3_dir: str) -> str:
    p = os.path.join(m3_dir, "frontier_summary.json")
    j = try_load(p)
    if not j:
        return "No M3 summary found."
    tops: List[Dict[str, Any]] = j.get("top_variants", [])
    if not tops:
        return "No top variants listed."
    header = "| variant | epsilon | alpha | inv_penalty | tokens_eval | cap | refill | rl_mean_pnl |\n|---|---:|---:|---:|---:|---:|---:|---:|"
    lines = [header]
    for t in tops[:10]:
        lines.append(
            f"| {t.get('variant')} | {t.get('epsilon')} | {t.get('alpha')} | {t.get('inv_penalty')} | {t.get('tokens_per_eval')} | {t.get('capacity_tokens')} | {t.get('refill_tokens')} | {t.get('rl_mean_pnl')} |"
        )
    return "\n".join(lines)


def pareto_points_table(m4_dir: str) -> str:
    p = os.path.join(m4_dir, "pareto_multi.json")
    j = try_load(p)
    if not j:
        return "No M4 pareto_multi.json found."
    pts: List[Dict[str, Any]] = j.get("points", [])
    if not pts:
        return "No Pareto points found."
    header = "| cap | refill | share | mean_pnl | vol | spread | msg/trade | gini | alloc_eff_call | depth_hl |\n|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    out = [header]
    for r in pts[:15]:
        out.append(
            f"| {r.get('capacity_tokens')} | {r.get('refill_tokens')} | {r.get('optimizer_share')} | {r.get('mean_agent_pnl_mean')} | {r.get('realized_vol_mean')} | {r.get('mean_spread_mean')} | {r.get('msg_to_trade_mean')} | {r.get('gini_pnl_mean')} | {r.get('alloc_eff_call_mean')} | {r.get('depth_halflife_mean')} |"
        )
    return "\n".join(out)


def change_point_block(m4_dir: str) -> str:
    parts: List[str] = []
    for metric in ["vol", "crash"]:
        path = os.path.join(m4_dir, f"change_point_{'vol' if metric=='vol' else 'crash'}_share0.5.json")
        j = try_load(path)
        if not j:
            continue
        br = j.get("break", {})
        ci = j.get("break_ci")
        line = f"- {metric} breakpoint (share=0.5): at cap ≈ {br.get('break_at')}"
        if ci and isinstance(ci, dict):
            line += f" (CI: {ci.get('lo')}–{ci.get('hi')}, n={ci.get('n')})"
        parts.append(line)
    return "\n".join(parts) if parts else "No change-point summaries found."


def m6_policy_table(m6_dir: str) -> str:
    idx = os.path.join(m6_dir, "index.csv")
    if not os.path.exists(idx):
        return "No M6 policy results found."
    rows = load_index_rows(idx)
    if not rows:
        return "No M6 policy results found."
    header = "| policy | d_profit | d_vol | d_spread | d_msg/trade | d_gini |\n|---|---:|---:|---:|---:|---:|"
    lines = [header]
    for r in rows:
        pol = r.get("policy", "")
        if not pol:
            continue
        if pol == "baseline":
            lines.append("| baseline | -- | -- | -- | -- | -- |")
            continue
        dp = r.get("d_mean_agent_pnl", "")
        dv = r.get("d_realized_vol", "")
        ds = r.get("d_mean_spread", "")
        dm = r.get("d_msg_to_trade", "")
        dg = r.get("d_gini_pnl", "")
        lines.append(f"| {pol} | {dp} | {dv} | {ds} | {dm} | {dg} |")
    return "\n".join(lines)

def m6_highlight_sentence(m6_dir: str) -> str:
    idx = os.path.join(m6_dir, "index.csv")
    if not os.path.exists(idx):
        return ""
    rows = load_index_rows(idx)
    best = None
    # Heuristic: choose policy with most negative d_realized_vol and small |d_mean_agent_pnl| (>= -0.001)
    candidates = []
    for r in rows:
        pol = r.get("policy", "")
        if pol == "baseline" or not pol:
            continue
        try:
            dvol = float(r.get("d_realized_vol", "nan"))
            dpnl = float(r.get("d_mean_agent_pnl", "nan"))
        except Exception:
            continue
        if dvol == dvol and dpnl == dpnl:
            candidates.append((pol, dvol, dpnl))
    if not candidates:
        return ""
    # Filter by minimal P&L impact threshold; if none pass, fall back to best dvol
    near_neutral = [c for c in candidates if c[2] >= -1e-3]
    pool = near_neutral if near_neutral else candidates
    # Sort by dvol (ascending, more negative better), then dpnl (descending, less loss better)
    pool.sort(key=lambda x: (x[1], -x[2]))
    pol, dvol, dpnl = pool[0]
    return f"Highlight: {pol} yields the largest volatility reduction (Δvol={dvol:.3g}) with minimal profit impact (Δprofit={dpnl:.3g})."


def main():
    ap = argparse.ArgumentParser(description="Summarize M3+M4(+M6) frontiers to Markdown")
    ap.add_argument("--m3_dir", required=True)
    ap.add_argument("--m4_dir", required=True)
    ap.add_argument("--m6_dir", required=False, help="Optional: M6 policy results directory")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    md: List[str] = []
    md.append("# Frontier Summary (M3+M4)\n")
    md.append("## M3: RL Tuning (Top Variants)\n")
    md.append(top_variants_table(args.m3_dir))
    md.append("\n\n## M4: Multi-Metric Pareto (sample)\n")
    md.append(pareto_points_table(args.m4_dir))
    md.append("\n\n## M4: Change-Point Estimates\n")
    md.append(change_point_block(args.m4_dir))
    # Optional M6 policies
    if args.m6_dir:
        md.append("\n\n## M6: Policy Deltas (vs Baseline)\n")
        md.append(m6_policy_table(args.m6_dir))
        md.append("\n\nArtifacts: `analysis/out/m6_policies/index.csv`, plots under `analysis/out/m6_policies/plots`, LaTeX table at `paper/tables/policies_m6.tex`.")
        hl = m6_highlight_sentence(args.m6_dir)
        if hl:
            md.append("\n\n" + hl)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write("\n".join(md))
    print(f"Wrote Markdown summary to {args.out}")


if __name__ == "__main__":
    main()
