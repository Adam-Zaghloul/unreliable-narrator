# The Unreliable Narrator

An in-person party game where **the AI narrator is the traitor**.

Players walk between rooms wearing cheap ESP32 badges. The narrator announces where people were ("At 3:40, Karim was in the living room."), and some of those announcements are deliberate lies meant to turn the group against each other. Players vote TRUE or LIE on their badge. The badges logged where everyone really was, so at the end the log shows every lie and who believed it.

Nobody has to play the villain, and nobody needs a phone. It also produces data on a question that has so far been studied mostly in text-only games: **how well do people catch a lying AI when they can check its claims against what physically happened?**

> **Status (2026-11-26): all the software is ready, but nothing has been tested on hardware or with people.**
> - The full live game loop runs end to end against a **fake gateway**: rounds, badge buzzes, button votes, reveal page and dataset export.
> - The firmware **compiles** for ESP32-C3 but has **not been flashed or bench-tested**.
> - No real game has been played yet.
> - Every number below comes from the simulator and is a development check, not a result about people.

## Try it (no hardware needed)

```sh
uv venv -p python3.12 .venv && uv pip install -p .venv anthropic pytest
.venv/bin/python -m pytest -q                        # 24 tests
.venv/bin/python -m hub.live --sim                   # full live game vs a fake gateway, opens the reveal page
.venv/bin/python -m hub.game --seed 3                # quick text-only game
.venv/bin/python -m hub.game --compare 50            # template vs heuristic liar over 50 seeds
.venv/bin/python -m evals.e4_safety                  # red-team, must print 0 violations
```

Running a real game night (setup, rules and consent card) is covered in [docs/HOSTING.md](docs/HOSTING.md).

**Using Claude as the liar:** the `llm` liar needs Anthropic credentials (`ANTHROPIC_API_KEY`, or `ant auth login`). Without them, the round falls back to the template liar. Those statements are marked `template-fill` and excluded from the E3 analysis, so the AI never gets credit for statements it didn't make.

## How it works

```
[player badges] --BLE scan of zone beacons, 2 buttons, vibration motor
      | ESP-NOW, 1 packet / 2 s
[zone beacons]  --one per room, advertise only
[gateway ESP32] --USB serial JSON--> [hub, Python]
                                       ingest.py    serial -> SQLite
                                       truth.py     who was where, per 10 s window (deterministic)
                                       liars.py     template / heuristic liars (baselines)
                                       llm.py       Claude proposes lies as structured JSON
                                       validator.py recomputes every label, renders the spoken text
                                       rounds.py    one round: liar -> validator -> fixed lie/truth mix
                                       live.py      real game: play phase, witness buzzes, button votes
                                       reveal.py    self-contained HTML reveal page
                                       export.py    anonymised JSONL dataset (no raw RSSI)
                                       walk.py      scripted-walk recorder for the real E1
                                       game.py      quick simulator-only game + liar comparison
```

**Design rule: the AI never decides what is true.**
- Code computes the truth.
- The liar only proposes structured claims labelled `is_lie`.
- The validator rejects any claim whose label disagrees with the log, or that rests on an uncertain reading.
- Code, not the model, renders the sentence players hear. See [docs/adr/0001-llm-never-decides-truth.md](docs/adr/0001-llm-never-decides-truth.md).

**How a position becomes a usable fact**, for each player and each 10 s window ([hub/truth.py](hub/truth.py)):
1. Take the median RSSI per beacon.
2. Pick the strongest beacon.
3. Apply hysteresis: keep the previous room unless the new one is at least 4 dB stronger.
4. Compute a confidence: the share of packets that agree with that room.

The narrator may only use a fact that is confident (≥ 0.8) **and** held for at least 20 s.

**Claims are limited to where someone was.** Allowed claims are "X was in room R", "X and Y were both in room R" and "X was not in room R". "Alone together" claims are banned, and so is anything about what someone did, said or felt.

## Evals

| Eval | What it checks | Simulated result (2026-11-26) |
|---|---|---|
| E1 zone accuracy (`python -m evals.e1_zone_accuracy`) | Accuracy of the facts the narrator may use, and how many player-windows it can use (coverage), at different noise levels | 99.8–99.9% accurate. Coverage falls from 70% to 39% as noise rises from 2 to 10 dB with heavy body shadowing |
| E2 validator (`python -m evals.e2_validator`) | 300 logs. Accepted lies are really lies, accepted truths are really true, and adversarial claims are rejected | 2344/2344 lies correct. **1438/1439** truths correct: the one miss is a truth-engine error at a room boundary, not a validator bug. 30000/30000 adversarial claims rejected |
| Liar comparison (`python -m hub.game --compare 50`) | Share of lies believed, and share of true statements rejected | Template 37% / 23%, heuristic 47% / 22%. **Circular:** the simulated voters are built to miss lies told about moments nobody witnessed, which is exactly what the heuristic exploits |
| E1 bench (`python -m hub.walk`, then `python -m evals.e1_bench`) | The same check on real hardware, against a baseline that just takes the strongest reading | Ready to run; needs hardware |
| E3 headline (`python -m evals.e3_analysis sessions/*.db`) | Template vs heuristic vs LLM lies, judged by real people. Rounds are counterbalanced, and confidence intervals come from resampling whole sessions | Pipeline checked on 6 simulated sessions only. The LLM liar has to beat the **heuristic**, not just the random liar, or the AI is decorative and this README will say so |
| E4 safety (`python -m evals.e4_safety`) | 41 attacks: banned claim types, injected names, invented places, mislabelled lies, HTML in names | **0 violations** |
| E5 models (`python -m evals.e5_models --yes`) | Validator pass rate, latency and cost per model | Not run (billed) |

Details and run notes: [evals/results.md](evals/results.md).

## Cost

Every Claude call is logged to the session database: model, tokens, latency and estimated $. The model is set by `NARRATOR_MODEL` and defaults to `claude-opus-5-5`.

A game makes 3 calls of a few thousand tokens each, so it costs cents. `claude-haiku-5-5` costs a small fraction of that and is the model to compare against in E5. If a call fails or is refused, the template liar fills in for that round so the game never stalls.

## Hardware (planned, about CA$100)

| Item | Qty |
|---|---|
| ESP32-C3 SuperMini | 15 (8 badges, 4 beacons, 1 gateway, 2 spares) |
| 400–500 mAh LiPo with TP4056 USB-C charger | 8 |
| Coin vibration motor, 2N7000, 2 tactile buttons | 8 sets |

Firmware is in [firmware/](firmware/). It compiles with Arduino-ESP32 core 3.3.13 and NimBLE-Arduino 2.5.2. Build steps are in [firmware/README.md](firmware/README.md). **It has not been flashed or bench-tested yet.**

## Known limitations

- Everything so far is simulated. The RSSI model is a guess until it is checked against bench data.
- Body shadowing and room boundaries are the main sources of error in real RSSI. The simulator models them only roughly.
- The simulated voters are crude, so they can't tell you whether one liar is better than another. Only real players can.
- Badges are named `P<id>` until `players.json` maps them to names.
- The gateway, badge buttons and buzz motor have only been tested through the fake gateway.
- The Ctrl+C safe word ends the game. There is no pause-and-resume.
