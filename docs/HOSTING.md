# Hosting a game

## Before game night (once per space)
1. **Flash.** Flash every beacon with its own `ZONE_ID` and every badge with its own `BADGE_ID`; see [firmware/README.md](../firmware/README.md).
2. **Configure.** Copy `game.example.json` to `game.json`. Set `zones` to your rooms (beacon id → room) and `players` to tonight's names (badge id → first name).
3. **Place the beacons.** Put one in each room, all at the same height, away from metal, roughly in the middle of the room.
4. **Walk-test:** `python -m hub.walk --config game.json --port <gateway port>`. Carry a badge through every room a few times, typing the room id each time you enter one. Then run `python -m evals.e1_bench walks/*.db`. If "mine clean" accuracy is below about 90%, move the beacons apart or add one before playing.

## Starting the game
```sh
uv pip install -p .venv pyserial
.venv/bin/python -m hub.live --config game.json --port /dev/cu.usbmodemXXXX
```
Read the consent card aloud and get a yes from everyone before you type `YES`.

**Big screen:** the game prints a local address (`http://127.0.0.1:8765`). Open it full-screen on a TV or a second laptop the players can see. It shows the round timer, each statement in large type, the vote countdown and *how many* players have voted, never what they voted. Use `--no-screen` to turn it off.

**Liars by round:** the narrator uses a different liar each round: random, rule-based, then Claude. The order comes from `session`. Add 1 to `session` for every new game so the order rotates.

**To stop at any time:** press **Ctrl+C**. That is the safe word. The game stops and the reveal is still written.

## Rules to read out
- Wear your badge on the lanyard at chest height. Don't swap badges, hide them or cover them.
- Walk, don't run. Stay inside the rooms we're using.
- When your badge buzzes, take a mental snapshot: who is in the room with you right now?
- At each meeting, the narrator makes statements about where people were. Some are lies. Discuss, then press **TRUE** (left button) or **LIE** (right button) on your badge before the time runs out. Only your last press counts.
- You're all on the same team, against the narrator.

## Consent card (read aloud)
> Tonight's game records which room your badge was in every 10 seconds, plus your TRUE/LIE button presses. That data stays on this laptop.
>
> The narrator will deliberately say false things about where people were. That's the game. It only ever talks about rooms and times, never about anything you did or said.
>
> After the game I may publish an anonymised dataset. In it your name becomes a number like P3, and it contains room-level positions and votes only. You can ask me to delete your data at any time, and you can stop playing whenever you want.
>
> Is everyone OK with that?

## After the game
- **The reveal** opens in the browser automatically (`sessions/<time>.html`). Walk through it together: it's the best part.
- **Analysis:** once you've played some games, run `python -m evals.e3_analysis sessions/*.db`.
- **Dataset:** to publish, run `python -m hub.export sessions/*.db --out dataset.jsonl`. It contains anonymised names and no raw signal data. Then delete the `.db` files you no longer need.
