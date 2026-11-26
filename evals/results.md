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
