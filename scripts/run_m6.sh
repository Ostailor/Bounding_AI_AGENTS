#!/usr/bin/env bash
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)

# Defaults
BASE_CFG="$ROOT/experiments/configs/m4_base.json"
OUT_DIR="$ROOT/analysis/out/m6_policies"
SEEDS="200 201 202 203 204 205 206 207 208 209"

# Parse simple flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base_config)
      BASE_CFG="$2"; shift 2;;
    --out_dir)
      OUT_DIR="$2"; shift 2;;
    --seeds)
      SEEDS="$2"; shift 2;;
    *)
      echo "Unknown argument: $1" >&2; exit 2;;
  esac
done

echo "[M6] Policy sweep starting"
python3 "$ROOT/scripts/sweep_m6_policies.py" \
  --base_config "$BASE_CFG" \
  --seeds $SEEDS \
  --out_dir "$OUT_DIR"

echo "[M6] Plotting deltas"
python3 "$ROOT/analysis/plot_m6.py" \
  --index_csv "$OUT_DIR/index.csv" \
  --out_dir "$OUT_DIR/plots"

echo "[M6] Exporting LaTeX table"
mkdir -p "$ROOT/paper/tables"
python3 "$ROOT/analysis/export_policies_table_tex.py" \
  --index_csv "$OUT_DIR/index.csv" \
  --out_tex "$ROOT/paper/tables/policies_m6.tex"

echo "M6 policy sweep complete. Outputs:"
echo " - CSV:    $OUT_DIR/index.csv"
echo " - Plots:  $OUT_DIR/plots"
echo " - LaTeX:  $ROOT/paper/tables/policies_m6.tex"

