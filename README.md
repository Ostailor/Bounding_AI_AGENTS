# Welfare and Stability Frontiers in Algorithmic Trading

Reproducible simulation and analysis of compute–profit–stability trade‑offs in a CDA/LOB market with compute/latency‑bounded agents.

## Setup
- Python (recommended): `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Conda: `conda env create -f environment.yml && conda activate welfare-frontiers`
- Docker: `docker build -t welfare-frontiers .` then `docker run --rm -it -v "$PWD:/app" welfare-frontiers bash -lc 'bash scripts/reproduce_frontiers.sh'`

## Quickstart
Run a single episode: `python3 scripts/run.py --config experiments/configs/m3_agents.json --seed 123`

## Reproduce figures (M3–M4; optional M6)
`RUN_M6=1 bash scripts/reproduce_frontiers.sh` (adds policy sweeps when RUN_M6=1 or `--m6`).

## M6 (policies) only
`bash scripts/run_m6.sh`

## Shock resilience
`python3 scripts/run_with_shock.py --config experiments/configs/m4_base.json --seed 123 --shock_t 800 --shock_side BUY --shock_qty 100`
Then: `python3 analysis/metrics_run.py --run_dir <printed_path> --out_json analysis/out/m4_shock_metrics.json`

## Theory demo (SCM/RBA)
`python3 analysis/theory_rba_demo.py --n_list 200 400 800 --samples 2 4 8 16 32 64 128 --trials 300 --seed 123 --plot --out analysis/out/theory_rba_efficiency.png`

## Outputs
- M3: `analysis/out/frontier_sweep_overnight/` (index, Pareto, summary)
- M4: `analysis/out/m4_frontier_mid/` (index, Pareto multi, change‑points, plots/plots_cam)
- M6: `analysis/out/m6_policies/` (index with deltas, plots); LaTeX: `paper/tables/policies_m6.tex`
- Summary: `analysis/out/frontier_summary.md`

## Config and policies
- Example configs: `experiments/configs/m3_agents.*`, `experiments/configs/m4_base.json`
- Simulator policies (in `sim/market.py:MarketConfig`): `latency_floor_ms`, `batch_interval_ticks`, `message_limit_per_tick`, `min_resting_ticks`.

## Logging
See `docs/logging_schema.md`. Key files: `steps.jsonl`, `agent_<id>.jsonl` (intents/timing/PnL/rejects), `trades.jsonl`.

## Determinism
- CLI seeds are authoritative; per‑run dirs include microseconds + seed; Docker sets `PYTHONHASHSEED=0` and Agg backend.

## Tests
`pytest -q`

## Docs & theory
`docs/overview.md`, `docs/metrics.md`, `docs/repro.md`, `docs/theory.md`, `paper/supp/proofs.tex`, `paper/sections/theory_section.tex`.

## Citation & license
- Cite: `CITATION.cff`  •  License: Apache‑2.0 (`LICENSE`).
