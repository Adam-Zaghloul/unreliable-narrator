# Eval results

Every row is labelled SIMULATED or REAL. As of 2026-11-26 everything is simulated.

## 2026-11-26: SIMULATED, week-1 scaffold
**Commands:**
- `python -m evals.e1_zone_accuracy`
- `python -m evals.e2_validator`
- `python -m hub.game --compare 50`

**E1: accuracy of stable facts and coverage** (20 seeds × 6 players × 6 min)

| noise dB | body-shadow p | accuracy | coverage |
|---|---|---|---|
| 2 | 0.08 | 99.8% | 70.5% |
| 4 | 0.08 | 99.8% | 70.0% |
| 6 | 0.25 | 99.8% | 62.8% |
| 8 | 0.25 | 99.9% | 52.2% |
| 10 | 0.25 | 99.9% | 38.9% |

Accuracy stays high because the "stable" rule throws away doubtful windows. The cost shows up as coverage: noisier rooms leave the narrator fewer facts to use. **Next:** replace the simulator with scripted walks on real badges and redraw this table.

**E2: validator** (300 logs, ground truth taken from the simulator rather than the truth engine)
- Accepted lies that were really lies: 2344/2344.
- Accepted truths that were really true: 1438/1439. The single miss is a truth-engine error at a room boundary that passed the stable rule, not a validator bug. The validator is exact *relative to the truth engine*; overall correctness is capped by E1.
- Adversarial claims rejected: 30000/30000.

**Liar comparison** (50 seeds, simulated voters)

| liar | lie acceptance | truth rejection |
|---|---|---|
| template (random) | 37% | 23% |
| heuristic (unwitnessed moments) | 47% | 22% |

These voters miss lies told about unwitnessed moments by construction, so the heuristic's lead is partly circular. This only shows the pipeline works. It is not a finding.

## 2026-11-26: SIMULATED, full live loop
**E4 safety:** 0 violations in 41 cases.
- 16 attacks on the liar's output.
- 14 bad player names and 5 bad zone names.
- 5 normal names, which must still be accepted (over-blocking check).
- 1 HTML-escaping check on the reveal page.

**E3 pipeline check** (6 simulated sessions through `hub.live --sim`, session orders 0–5, 3-minute rounds). Without credentials the `llm` arm falls back to template-fill and is correctly excluded.

| arm | lie acceptance (95% CI) | truth rejection | d' (95% CI) |
|---|---|---|---|
| template | 50% [33%, 67%] | 21% | 0.77 [0.28, 1.43] |
| heuristic | 60% [50%, 70%] | 41% | −0.03 [−0.47, 0.41] |
| llm | no data | | |

This only shows the analysis runs end to end. The simulated voters are crude, so it is not a finding.

## 2026-11-26: SIMULATED, transition windows excluded
The one wrong truth in E2 was a player who moved from the kitchen to the living room exactly halfway through a 10 s window. The old "stable" rule accepted it because the next window agreed. New rule: a window is not stable if a confident neighbour puts the player in a different room, since that window is where the move happened. Tried and rejected: requiring both neighbours to agree. It was just as accurate but cut coverage roughly in half (12–33%).

**E1** (same setup as above)

| noise dB | body-shadow p | accuracy | coverage |
|---|---|---|---|
| 2 | 0.08 | 100.0% | 60.9% |
| 4 | 0.08 | 100.0% | 60.7% |
| 6 | 0.25 | 100.0% | 55.6% |
| 8 | 0.25 | 100.0% | 46.9% |
| 10 | 0.25 | 99.9% | 36.1% |

Cost: 3–10 points of coverage, depending on noise.

**E2:** 1995/1995 lies, 1267/1267 truths, 30000/30000 adversarial rejected. Fewer claims pass now because transition windows are no longer usable.

**Liar comparison** (50 seeds): template 36% / 23%, heuristic 47% / 22%. Same as before within a point.

**E4:** 0 violations in 41. The reveal-page check used to flag the page's own `<script>` tag (added in the redesign) as an injection. It now checks for the raw injected payload, which is escaped everywhere it appears.
