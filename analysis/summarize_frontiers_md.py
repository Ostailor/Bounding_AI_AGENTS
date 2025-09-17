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


def main():
    ap = argparse.ArgumentParser(description="Summarize M3+M4 frontiers to Markdown")
    ap.add_argument("--m3_dir", required=True)
    ap.add_argument("--m4_dir", required=True)
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
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write("\n".join(md))
    print(f"Wrote Markdown summary to {args.out}")


if __name__ == "__main__":
    main()

