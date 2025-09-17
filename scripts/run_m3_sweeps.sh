#!/usr/bin/env bash
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)

BASE_CFG="$ROOT/experiments/configs/m3_agents.json"
OUT_DIR="$ROOT/analysis/out/frontier_sweep_overnight"

# Broad grid, 10 seeds
python3 "$ROOT/scripts/sweep_frontier.py" \
  --base_config "$BASE_CFG" \
  --seeds 300 301 302 303 304 305 306 307 308 309 \
  --epsilons 0.02 0.05 0.1 \
  --alphas 0.01 0.02 0.05 \
  --inv_penalties 0.02 0.05 0.1 \
  --tokens_eval 2 4 \
  --tokens_update 1 \
  --rl_capacity 8 12 20 \
  --rl_refill 8 12 20 \
  --out_dir "$OUT_DIR" \
  --continue_on_error

# Assemble Pareto and summary
python3 "$ROOT/analysis/assemble_frontier.py" --index_csv "$OUT_DIR/index.csv" --out_dir "$OUT_DIR"

# Quick plots (requires matplotlib)
python3 "$ROOT/analysis/plot_pnl_spread.py" --frontier_dir "$OUT_DIR" --out_dir "$OUT_DIR/plots"

echo "Overnight M3 sweeps complete. Outputs in: $OUT_DIR"
