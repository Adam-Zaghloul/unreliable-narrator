# The Unreliable Narrator

An in-person party game where **the AI narrator is the traitor**.

Players walk between rooms wearing cheap ESP32 badges. The narrator announces where people were ("At 3:40, Karim was in the living room."), and some of those announcements are deliberate lies meant to turn the group against each other. Players vote TRUE or LIE on their badge. The badges logged where everyone really was, so at the end the log shows every lie and who believed it.

Nobody has to play the villain, and nobody needs a phone. It also produces data on a question that has so far been studied mostly in text-only games: **how well do people catch a lying AI when they can check its claims against what physically happened?**

> **Status (2026-11-26): week 1, simulator only.**
> - The hub runs end to end against simulated players.
> - The firmware is written but has **not been compiled or bench-tested**.
> - No real game has been played yet.
> - Every number below comes from the simulator and is a development check, not a result about people.

## Try it (no hardware needed)

```sh
uv venv -p python3.12 .venv && uv pip install -p .venv anthropic pytest
.venv/bin/python -m pytest -q                       # 18 tests
.venv/bin/python -m hub.game --seed 3               # one simulated game, then the reveal
.venv/bin/python -m hub.game --liar heuristic       # rule-based "strategic" liar, no AI
.venv/bin/python -m hub.game --compare 50           # template vs heuristic liar over 50 seeds
.venv/bin/python -m hub.game --liar llm --seed 3    # Claude picks the lies (billed, see Cost)
.venv/bin/python -m hub.game --speak                # macOS reads each statement aloud
```

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
                                       game.py      rounds, votes, reveal
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
| E3 headline (needs real players) | Template-random vs heuristic vs LLM lies, judged by real people | Not run. The LLM liar has to beat the **heuristic**, not just the random liar, or the AI is decorative and this README will say so |
| E4 safety red-team | 40 bait scenarios | Not built yet |

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

Firmware is in [firmware/](firmware/). It targets Arduino-ESP32 core 3.x and NimBLE-Arduino 2.x. **It has not been compiled yet.**

## Known limitations

- Everything so far is simulated. The RSSI model is a guess until it is checked against bench data.
- Body shadowing and room boundaries are the main sources of error in real RSSI. The simulator models them only roughly.
- The simulated voters are crude, so they can't tell you whether one liar is better than another. Only real players can.
- Badges are named `P<id>` until `players.json` maps them to names.
- Not built yet: the live hardware game loop (`ingest.py` writes pings, but `game.py` still reads from the simulator), the reveal web page, witness pings over the gateway, and the safety red-team set.
