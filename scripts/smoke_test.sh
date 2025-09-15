#!/usr/bin/env bash
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
CFG="$ROOT/experiments/configs/m1_baseline.json"

python3 "$ROOT/scripts/run.py" --config "$CFG" --seed 42

echo "Smoke test complete"
