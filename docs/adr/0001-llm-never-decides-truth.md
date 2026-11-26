# ADR 0001: The LLM never decides what is true

**Date:** 2026-11-26 · **Status:** accepted

## Context
The game is only fair if the reveal is right: a "lie" must really be false and a "truth" really true. LLMs label facts inconsistently and can invent people, rooms or times. If a player is told they believed a lie that was actually true, the game loses all credibility, and so does the eval.

## Decision
- `truth.py` (deterministic) computes where each player was, with a confidence.
- The liar returns **structured claims** (`claim_type`, `players`, `zone`, `window`, `is_lie`) through JSON-schema structured output.
- `validator.py` recomputes `is_lie` from the truth engine. It rejects mismatches, unknown names, uncertain windows and banned claim types.
- The spoken sentence is **rendered by code** from the accepted claim. The model writes no text that players hear.
- Any shortfall is filled by the template liar, so a bad response can't stall the game.

## Consequences
- The model's only job is strategy: which moments to lie about, about whom, and when. That is exactly what E3 measures.
- Narration is plain. Flavour text would need its own safety filter and an E4 gate before players hear it.
- The rejection rate becomes a metric of its own: how often the model mislabels the truth.
