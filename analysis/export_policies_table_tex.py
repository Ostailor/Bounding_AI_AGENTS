#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
from typing import Any, Dict, List


def load_rows(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def fmt(x: Any, nd: int = 3) -> str:
    try:
        v = float(x)
        if abs(v) >= 1000:
            return f"{v:.0f}"
        return f"{v:.{nd}f}"
    except Exception:
        return str(x)


def make_table(rows: List[Dict[str, Any]]) -> str:
    header = (
        "% Auto-generated M6 policy table\n"
        "\\begin{table}[t]\n\\centering\\small\n"
        "\\begin{tabular}{lrrrrrrr}\\hline\n"
        "Policy & $\\Delta$Profit & $\\Delta$Vol & $\\Delta$Spread & $\\Delta$Gini & $\\Delta$Msg/Trade & $\\Delta$AllocEff & $\\Delta$DepthHL \\\\ \\hline\n"
    )
    lines: List[str] = [header]
    order = [r for r in rows if r.get("policy")]
    # Place baseline first without deltas
    order.sort(key=lambda r: (0 if r.get("policy") == "baseline" else 1, r.get("policy")))
    for r in order:
        pol = r.get("policy")
        if pol == "baseline":
            lines.append(
                f"baseline & -- & -- & -- & -- & -- & -- & -- \\\\" 
            )
            continue
        dp = r.get("d_mean_agent_pnl", "")
        dv = r.get("d_realized_vol", "")
        ds = r.get("d_mean_spread", "")
        dg = r.get("d_gini_pnl", "")
        dm = r.get("d_msg_to_trade", "")
        da = r.get("d_alloc_eff_mid", r.get("d_alloc_eff_call", ""))
        dd = r.get("d_depth_halflife", "")
        lines.append(
            f"{pol} & {fmt(dp)} & {fmt(dv)} & {fmt(ds)} & {fmt(dg)} & {fmt(dm)} & {fmt(da)} & {fmt(dd)} \\\\" 
        )
    footer = (
        "\n\\hline\n\\end{tabular}\n"
        "\\caption{Policy deltas (M6) relative to baseline: mean profit, realized volatility, spread, PnL Gini, message-to-trade ratio, allocative efficiency (mid proxy), and depth half-life. Negative $\\Delta$Vol/Spread/Msg/Trade indicate stability/efficiency improvements.}\\label{tab:m6_policies}\n"
        "\\end{table}\n"
    )
    lines.append(footer)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Export M6 policy results to LaTeX table")
    ap.add_argument("--index_csv", required=True)
    ap.add_argument("--out_tex", required=True)
    args = ap.parse_args()

    rows = load_rows(args.index_csv)
    tex = make_table(rows)
    os.makedirs(os.path.dirname(args.out_tex), exist_ok=True)
    with open(args.out_tex, "w") as f:
        f.write(tex)
    print(f"Wrote LaTeX table to {args.out_tex}")


if __name__ == "__main__":
    main()

