# Theory: Compute-Bounded Agents and Stability (M5)

This note formalizes compute-bounded agent classes, a latency-aware market model, and states the main results with proof sketches. Full LaTeX is in `paper/supp/proofs.tex`.

## Model Overview

- Agents i = 1..N submit messages to a market mechanism (CDA or batch auction). Each agent has a per-decision compute budget C (tokens) and latency model L (base + per-token cost + jitter).
- Compute-limited policy classes P(C):
  - Sampling/quantile rules with at most O(C) samples.
  - Linear function class with at most O(C) features (shallow RL proxy).
  - Planning depth at most O(C) in a tree or iterative solver steps ≤ C.
- Latency coupling: decisions with k used tokens incur latency L(k) and thus later arrival, affecting priority and fill probability.

## Stylized Settings

- Static Call Market (SCM): one-shot auction with private values v_i ~ F and unit demand/supply; welfare is total surplus under efficient matching.
- Random Batch Auctions (RBA): time sliced into batches; orders execute at uniform clearing price per batch.
- LQ Maker–Taker (LQ-MT): linear–quadratic inventory control with linear impact and quadratic holding costs.

## Main Results (Informal Statements)

- Lower bound (SCM/RBA): With O((1/ε^2) log N) compute per agent, a threshold/quantile policy attains allocative efficiency ≥ 1 − ε w.h.p. under smooth F and bounded noise. Latency independent in RBA.
- Upper bound (LQ-MT/CDA): If effective per-agent compute C ≥ O(N^α) yields sufficiently tight micro-predictions or faster arrival order, then realized volatility grows superlinearly in C (amplification via feedback and priority externalities) under mild mixing conditions.
- Phase transition: There exists C* at which stability order parameters (e.g., kurtosis, crash probability) undergo a sharp change; the break coincides with the regime where compute-driven arrival advantage dominates liquidity provision.

## Proof Sketches

- Lower bound: Estimating a (1−q)-quantile of the value distribution within ε accuracy requires O((1/ε^2) log(1/δ)) samples by Hoeffding/Chernoff. In SCM/RBA, bidding a threshold at the estimated quantile attains welfare within ε of optimal with probability ≥ 1−δ due to smoothness of F and Lipschitz surplus in price. Aggregating across N agents with union bounds yields O((1/ε^2) log N) compute per agent.
- Upper bound: In LQ-MT, the closed-loop inventory/price dynamics have feedback gain that increases with prediction sharpness and lower latency. When C lifts either (i) model class capacity (reduced bias) or (ii) effective arrival priority, the net amplification factor crosses >1, increasing variance and kurtosis. Under mixing (bounded correlation length) and light tails in exogenous noise, realized variance scales ≥ C^β for some β>0 in the high-C regime.
- Phase transition: Two-segment Lyapunov arguments show stability below C* (contractive inventories/spreads), and loss of contractivity above C* due to priority-induced externalities. Change-point concentration follows from segmented regression consistency.

## Implementation Hooks

- Empirical validation in `analysis/`:
  - `theory_rba_demo.py`: SCM/RBA welfare vs compute using sample-quantile thresholds, showing efficiency ≥ 1 − ε once C ≳ (1/ε^2) log N.
  - Use existing M4 sweep outputs to exhibit volatility growth and breakpoints vs capacity tokens.

## Notes

- The lower bound isolates compute as sampling/quantile complexity; other compute measures (features, solver iterations) can be reduced to equivalent token counts.
- The upper bound abstracts microstructure: any mechanism where earlier arrival increases expected fill and payoff suffices for amplification.
- Full statements and conditions appear in `paper/supp/proofs.tex`.

