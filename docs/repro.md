# Reproducibility and Environment

This document describes how to reproduce the M3–M6 results with pinned environments and containers.

## Python/Conda

- Python 3.11 recommended. Create env via conda:
```
conda env create -f environment.yml
conda activate welfare-frontiers
```
- Or via pip:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Determinism

- Seeds: our scripts accept `--seed`/`--seeds`. The runner writes unique per-seed run folders and logs the chosen seed to `run.json`.
- Set `PYTHONHASHSEED=0` (Dockerfile sets this) for consistent hash seeding.
- We use CPU-only code; no CUDA nondeterminism. Matplotlib backend is set to `Agg` for headless plots.

## One-click Repro

- Full pipeline (M3 + M4, optional M6):
```
# Optional: export RUN_M6=1 to include policies
RUN_M6=1 bash scripts/reproduce_frontiers.sh
```
- M6 only:
```
bash scripts/run_m6.sh
```

## Docker

Build and run inside a container:
```
docker build -t welfare-frontiers .
docker run --rm -it -v "$PWD:/app" welfare-frontiers bash -lc 'bash scripts/reproduce_frontiers.sh'
```

## Outputs

- M3: `analysis/out/frontier_sweep_overnight`
- M4: `analysis/out/m4_frontier_mid` (CSV, Pareto, change-points, plots, camera-ready)
- M6 (optional): `analysis/out/m6_policies` (CSV, plots) and `paper/tables/policies_m6.tex`
- Summary: `analysis/out/frontier_summary.md`

## Logging Schema

See `docs/logging_schema.md` for JSONL formats (steps, agent actions, trades) and example fields.

