#!/usr/bin/env bash
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)

echo "[M3] Running RL/compute sweep (overnight grid)"
bash "$ROOT/scripts/run_m3_sweeps.sh"

echo "[M4] Running mid-size frontier sweep"
python3 "$ROOT/scripts/sweep_m4.py" \
  --base_config "$ROOT/experiments/configs/m4_base.json" \
  --seeds 200 201 202 203 204 205 206 207 208 209 \
  --rl_capacity 4 8 12 \
  --rl_refill 4 8 12 \
  --optimizer_share 0.0 0.2 0.5 0.8 1.0 \
  --total_agents 20 \
  --out_dir "$ROOT/analysis/out/m4_frontier_mid"

echo "[M4] Building Pareto and change-points"
python3 "$ROOT/analysis/pareto_multi.py" --index_csv "$ROOT/analysis/out/m4_frontier_mid/index.csv" --out_dir "$ROOT/analysis/out/m4_frontier_mid"
python3 "$ROOT/analysis/change_point.py" --index_csv "$ROOT/analysis/out/m4_frontier_mid/index.csv" --out_json "$ROOT/analysis/out/m4_frontier_mid/change_point_vol_share0.5.json" --metric realized_vol_mean --share_filter 0.5 --bootstrap 1000
python3 "$ROOT/analysis/change_point.py" --index_csv "$ROOT/analysis/out/m4_frontier_mid/index.csv" --out_json "$ROOT/analysis/out/m4_frontier_mid/change_point_crash_share0.5.json" --metric crash_prob_mean --share_filter 0.5 --bootstrap 1000

echo "[M4] Plotting and exporting figures"
python3 "$ROOT/analysis/plot_m4.py" --index_csv "$ROOT/analysis/out/m4_frontier_mid/index.csv" --out_dir "$ROOT/analysis/out/m4_frontier_mid/plots" --capacities 4 8 12
python3 "$ROOT/analysis/export_figures_m4.py" --index_csv "$ROOT/analysis/out/m4_frontier_mid/index.csv" --out_dir "$ROOT/analysis/out/m4_frontier_mid/plots_cam" --capacities 4 8 12 --formats png pdf

echo "[M4] Shock resilience run and metrics"
SHOCK_OUT=$(python3 "$ROOT/scripts/run_with_shock.py" --config "$ROOT/experiments/configs/m4_base.json" --seed 123 --shock_t 800 --shock_side BUY --shock_qty 100 | sed -n 's/Completed shock run. Logs at: \(.*\)/\1/p')
if [ -n "$SHOCK_OUT" ]; then
  python3 "$ROOT/analysis/metrics_run.py" --run_dir "$SHOCK_OUT" --out_json "$ROOT/analysis/out/m4_frontier_mid/shock_metrics.json"
  echo "Shock metrics written to analysis/out/m4_frontier_mid/shock_metrics.json"
else
  echo "WARN: Could not parse shock run directory; skipping shock metrics."
fi

echo "[Summary] Generating Markdown frontier summary"
python3 "$ROOT/analysis/summarize_frontiers_md.py" --m3_dir "$ROOT/analysis/out/frontier_sweep_overnight" --m4_dir "$ROOT/analysis/out/m4_frontier_mid" --out "$ROOT/analysis/out/frontier_summary.md"

echo "[Summary] Exporting LaTeX table for M4 Pareto"
python3 "$ROOT/analysis/export_pareto_table_tex.py" --pareto_csv "$ROOT/analysis/out/m4_frontier_mid/pareto_multi.csv" --out_tex "$ROOT/paper/tables/pareto_m4.tex" --max_rows 10

# Optional M6 policy sweeps: set RUN_M6=1 or pass --m6
if [ "${RUN_M6:-0}" = "1" ] || [ "${1:-}" = "--m6" ]; then
  echo "[M6] Running policy sweeps"
  python3 "$ROOT/scripts/sweep_m6_policies.py" --base_config "$ROOT/experiments/configs/m4_base.json" --seeds 200 201 202 203 204 205 206 207 208 209 --out_dir "$ROOT/analysis/out/m6_policies"
  echo "[M6] Plotting policy deltas"
  python3 "$ROOT/analysis/plot_m6.py" --index_csv "$ROOT/analysis/out/m6_policies/index.csv" --out_dir "$ROOT/analysis/out/m6_policies/plots"
  echo "[M6] Exporting LaTeX table for policies"
  python3 "$ROOT/analysis/export_policies_table_tex.py" --index_csv "$ROOT/analysis/out/m6_policies/index.csv" --out_tex "$ROOT/paper/tables/policies_m6.tex"
  echo "[Summary] Updating Markdown summary with M6"
  python3 "$ROOT/analysis/summarize_frontiers_md.py" --m3_dir "$ROOT/analysis/out/frontier_sweep_overnight" --m4_dir "$ROOT/analysis/out/m4_frontier_mid" --m6_dir "$ROOT/analysis/out/m6_policies" --out "$ROOT/analysis/out/frontier_summary.md"
fi

echo "Reproduction complete. Outputs under analysis/out/."
