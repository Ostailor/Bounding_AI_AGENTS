# ADR 001: Engine Choice (Custom Minimal CDA)

Context
- Need a transparent, auditable CDA/LOB engine to study compute–profit–stability with strong control over determinism and instrumentation.

Options
- Custom minimal CDA/LOB engine.
- External framework (e.g., ABIDES-style).

Decision
- Implement a custom minimal CDA/LOB for M1–M2. Re-evaluate integration with external engines at M3+ if needed.

Consequences
- Pros: Tight control, minimal dependencies, easier to reason about invariants and compute accounting.
- Cons: Fewer features than mature frameworks; more engineering effort for advanced scenarios.

