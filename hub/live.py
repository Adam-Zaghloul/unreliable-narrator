"""The live game: real gateway (or the fake one), real rounds, button votes, reveal page.

    python -m hub.live --config game.json --port /dev/cu.usbmodem1101     # real hardware
    python -m hub.live --config game.json --sim                           # fake gateway, instant
    python -m hub.live --sim                                              # built-in demo config

Flow per round: PLAY (players move; random badges buzz as witness pings) -> MEETING
(the narrator reads each statement; players have `vote_seconds` to press TRUE or LIE; the
last press counts) -> next round. Each round uses a different liar, in a counterbalanced
order set by `session`. Ctrl+C ends the game early and still writes the reveal.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from . import db
from .config import GameConfig, load, validate
from .ingest import parse_line
from .liars import TemplateLiar
from .reveal import write_reveal
from .screen import NullScreen, Screen
from .rounds import arm_order, make_liar, round_statements, truth_so_far
from .truth import estimate_zones

TRUE_BIT, LIE_BIT = 1, 2


def speak(text: str, enabled: bool) -> None:
    print(f"NARRATOR: {text}")
    if enabled and shutil.which("say"):
        subprocess.run(["say", text], check=False)


class LiveGame:
    def __init__(self, cfg: GameConfig, transport, clock, con, seed: int = 0, mode: str = "LIVE", liars=None,
                 screen=None):
        self.cfg, self.t, self.clock, self.con = cfg, transport, clock, con
        self.screen = screen or NullScreen()
        self.rng = random.Random(seed)
        self.mode = mode
        self.pings = []
        self.presses: list[tuple[int, str, int]] = []  # (t_ms, player, bits)
        self.liars = liars  # optional override for tests: {arm: liar}
        self.round = 0

    # ---- input -------------------------------------------------------------
    def pump(self) -> None:
        for now, line in self.t.poll():
            pings, bid, buttons = parse_line(line, now, self.cfg.name_of_badge)
            if pings:
                self.pings.extend(pings)
                db.save_pings(self.con, pings)
            if bid is not None and buttons:
                self.presses.append((now, self.cfg.name_of_badge.get(str(bid), f"P{bid}"), buttons))

    def wait(self, seconds: float, step: float = 0.5, on_tick=None) -> None:
        end = self.clock.now_ms() + int(seconds * 1000)
        while self.clock.now_ms() < end:
            self.clock.sleep(min(step, (end - self.clock.now_ms()) / 1000))
            self.pump()
            if on_tick:
                on_tick()

    # ---- phases ------------------------------------------------------------
    def play_phase(self) -> None:
        round_s = self.cfg.round_minutes * 60
        elapsed = 0.0
        every = self.cfg.witness_ping_every_s
        self.screen.update(phase="play", round=self.round, rounds=self.cfg.rounds, players=len(self.cfg.players),
                           seconds_left=round_s)
        while elapsed < round_s:
            gap = min(self.rng.uniform(0.5 * every, 1.5 * every), round_s - elapsed)
            self.wait(gap)
            elapsed += gap
            if elapsed < round_s:
                bid = self.rng.choice(list(self.cfg.players))
                self.t.send(f"BUZZ {bid} 400")
                self.screen.update(buzzed=True)
                self.con.execute("INSERT INTO buzzes VALUES (?,?)",
                                 (self.cfg.players[bid], self.clock.now_ms() // 10_000))

    def collect_votes(self, idx: int, opened_ms: int, closed_ms: int) -> int:
        last: dict[str, int] = {}
        for t, player, bits in self.presses:
            if opened_ms <= t <= closed_ms and bits in (TRUE_BIT, LIE_BIT):
                last[player] = bits
        for player, bits in last.items():
            self.con.execute("INSERT INTO votes VALUES (?,?,?)", (player, idx, int(bits == TRUE_BIT)))
        return sum(1 for b in last.values() if b == TRUE_BIT)

    def run(self) -> Path | None:
        cfg = self.cfg
        arms = arm_order(cfg.session)
        self.con.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)",
                             [("mode", self.mode), ("session", str(cfg.session)), ("arms", ",".join(arms)),
                              ("started", datetime.now().isoformat(timespec="seconds")),
                              ("players", ",".join(cfg.players.values())), ("zones", ",".join(cfg.zones.values())),
                              ("zone_of_beacon", json.dumps(cfg.zone_of_beacon))])
        fill = TemplateLiar(cfg.session + 99)
        history: list[dict] = []
        used: set[str] = set()
        idx = 0
        try:
            for rnd in range(1, cfg.rounds + 1):
                self.round = rnd
                arm = arms[(rnd - 1) % len(arms)]
                liar = (self.liars or {}).get(arm) or make_liar(arm, self.con, cfg.session * 10 + rnd)
                speak(f"Round {rnd}. Go.", cfg.speak)
                self.play_phase()
                speak("Meeting. Listen carefully.", cfg.speak)
                truth = truth_so_far(self.pings, cfg.zone_of_beacon, self.clock.now_ms())
                statements = round_statements(rnd, truth, list(cfg.zones.values()), liar, fill, self.con,
                                              cfg.statements_per_round, cfg.lies_per_round, history, used, self.rng)
                if not statements:
                    speak("The sensors saw too little this round. No statements.", cfg.speak)
                for k, st in enumerate(statements, 1):
                    db.save_statement(self.con, idx, rnd, st)
                    self.screen.update(phase="meeting", round=rnd, rounds=cfg.rounds, index=k, count=len(statements),
                                       text=st.text, vote_seconds=cfg.vote_seconds, players=len(cfg.players), voted=0,
                                       seconds_left=cfg.vote_seconds)
                    speak(st.text + " True, or lie?", cfg.speak)
                    opened = self.clock.now_ms()
                    self.t.open_vote(st.claim)

                    def tick(opened=opened):
                        voted = {p for t, p, b in self.presses if t >= opened and b in (TRUE_BIT, LIE_BIT)}
                        self.screen.update(voted=len(voted))

                    self.wait(cfg.vote_seconds, on_tick=tick)
                    believed = self.collect_votes(idx, opened, self.clock.now_ms())
                    history.append({"text": st.text, "is_lie": st.claim.is_lie, "believed": believed,
                                    "voters": len(cfg.players)})
                    idx += 1
                self.con.commit()
        except KeyboardInterrupt:
            print("\nGame stopped by host.")
        db.save_estimates(self.con, estimate_zones(self.pings, cfg.zone_of_beacon))
        self.con.commit()
        self.screen.update(phase="over", players=len(cfg.players))
        speak("The game is over. Here is what really happened.", cfg.speak)
        return None


DEMO = GameConfig(players={1: "Sara", 2: "Karim", 3: "Lina", 4: "Omar", 5: "Maya", 6: "Theo"},
                  zones={1: "kitchen", 2: "living room", 3: "hallway", 4: "balcony"},
                  round_minutes=2, speak=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--port", help="gateway serial port")
    ap.add_argument("--sim", action="store_true", help="fake gateway + simulated players, runs instantly")
    ap.add_argument("--out", default="sessions", help="folder for the session db and reveal page")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-screen", action="store_true", help="don't serve the big-screen page")
    a = ap.parse_args(argv)

    cfg = load(a.config) if a.config else DEMO
    cfg.errors = validate(cfg)
    if cfg.errors:
        print("Config problems:\n- " + "\n- ".join(cfg.errors))
        return 2
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    db_path = out / f"{stamp}-s{cfg.session}{'-SIM' if a.sim else ''}.db"
    con = db.connect(db_path)

    if a.sim:
        from sim.world import simulate
        from .transport import SimClock, SimTransport
        meeting_s = cfg.statements_per_round * cfg.vote_seconds + 5
        duration = int(cfg.rounds * (cfg.round_minutes * 60 + meeting_s)) + 60
        world = simulate(a.seed, players=list(cfg.players.values()), zones=list(cfg.zones.values()),
                         duration_s=duration)
        clock = SimClock()
        game = LiveGame(cfg, SimTransport(world, clock, a.seed), clock, con, a.seed, mode="SIMULATED")
    else:
        if not a.port:
            print("Give --port (the gateway) or --sim.")
            return 2
        print("Before starting: every player has read and agreed to the consent card (docs/HOSTING.md).")
        if input("Type YES to start: ").strip() != "YES":
            return 1
        from .transport import RealClock, SerialTransport
        clock = RealClock()
        screen = None
        if not a.no_screen:
            screen = Screen()
            url = screen.start()
            print(f"Big screen: open {url} on the TV/laptop players can see.")
        game = LiveGame(cfg, SerialTransport(a.port, clock), clock, con, a.seed, screen=screen)

    game.run()
    html = write_reveal(con, db_path.with_suffix(".html"))
    print(f"Session: {db_path}\nReveal:  {html}")
    if not a.no_open:
        webbrowser.open(html.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
