# KGreedyTrader — Model Card

Summary
- k-greedy/epsilon-greedy satisficer over a small discrete action set.

Policy
- Candidates: hold, limit buy/sell; optional market buy/sell.
- Samples up to k actions uniformly, scores with a cheap utility proxy, selects best with ε-exploration.
- Utility proxy balances value signal (ref − mid), inventory penalty, and message cost proxy.

Compute/Latency
- Tokens requested ≈ `k * tokens_per_eval` per decision.
- Latency derived from tokens via sim latency model.

Safety
- Deterministic under fixed seed; no background compute.

Known Limitations
- Heuristic utility; no long-horizon planning.
- Sensitive to scaling of proxy coefficients.
