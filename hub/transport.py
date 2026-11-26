"""Where gateway lines come from.

SerialTransport: the real gateway on USB.
SimTransport:    a fake gateway driven by the simulator, so the LIVE game loop (rounds,
                 witness pings, button votes, reveal) can be run end to end with no hardware.
Both expose poll() -> [(arrival_ms, line)] and send(command). A Clock decides what "now" is.
Lines are stamped on ARRIVAL (badges have no shared clock), in the reader thread for serial.
"""
from __future__ import annotations

import json
import queue
import random
import threading
import time
from collections import defaultdict

from sim.world import SimVoter, World


class RealClock:
    def __init__(self):
        self.t0 = time.monotonic()

    def now_ms(self) -> int:
        return int((time.monotonic() - self.t0) * 1000)

    def sleep(self, s: float) -> None:
        time.sleep(s)


class SimClock:
    """Virtual time: sleep() returns immediately and moves the clock forward."""

    def __init__(self):
        self.t = 0

    def now_ms(self) -> int:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += int(s * 1000)


class SerialTransport:
    def __init__(self, port: str, clock: RealClock, baud: int = 115200):
        import serial  # pyserial

        self.ser = serial.Serial(port, baud, timeout=0.2)
        self.clock = clock
        self.q: queue.Queue[tuple[int, str]] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            line = self.ser.readline().decode(errors="replace").strip()
            if line:
                self.q.put((self.clock.now_ms(), line))

    def poll(self) -> list[tuple[int, str]]:
        out = []
        while not self.q.empty():
            out.append(self.q.get_nowait())
        return out

    def send(self, line: str) -> None:
        self.ser.write((line + "\n").encode())

    def open_vote(self, claim) -> None:  # real players press real buttons
        pass


class SimTransport:
    """Emits the gateway JSON lines a real gateway would print, from a simulated world."""

    def __init__(self, world: World, clock: SimClock, seed: int = 0):
        self.world, self.clock = world, clock
        self.rng = random.Random(seed)
        self.badge_of = {p: i + 1 for i, p in enumerate(world.players)}
        self.beacon_id = {b: int(b[1:]) for b in world.zone_of_beacon}
        packets = defaultdict(list)
        for p in world.pings:
            packets[(p.t_ms, p.badge)].append(["B", self.beacon_id[p.beacon], round(p.rssi)])
        self.packets = sorted(packets.items())
        self.cursor = 0
        self.pending_presses: dict[str, tuple[int, int]] = {}  # player -> (t_ms, bits)
        self.sent: list[str] = []
        self.buzzed: dict[str, list[int]] = defaultdict(list)
        self.voters = {p: SimVoter(p) for p in world.players}

    def poll(self) -> list[tuple[int, str]]:
        now, out = self.clock.now_ms(), []
        sim_end = self.world.duration_s * 1000
        while self.cursor < len(self.packets) and self.packets[self.cursor][0][0] <= now:
            (t, player), peers = self.packets[self.cursor]
            self.cursor += 1
            out.append((t, self._line(player, peers, t)))
        # after the simulated walk ends, badges keep reporting (empty) so votes still arrive
        if now > sim_end:
            for player in self.world.players:
                if player in self.pending_presses and self.pending_presses[player][0] <= now:
                    out.append((now, self._line(player, [], now)))
        return out

    def _line(self, player: str, peers, t: int) -> str:
        bits = 0
        press = self.pending_presses.get(player)
        if press and press[0] <= t:
            bits = press[1]
            del self.pending_presses[player]
        return json.dumps({"badge": self.badge_of[player], "seq": 0, "buttons": bits, "peers": peers})

    def send(self, line: str) -> None:
        self.sent.append(line)
        parts = line.split()
        if parts[0] == "BUZZ":
            player = next(p for p, b in self.badge_of.items() if b == int(parts[1]))
            self.buzzed[player].append(self.clock.now_ms() // 10_000)

    def open_vote(self, claim) -> None:
        """Simulated players decide and press a button 1-8 s later."""
        for p, v in self.voters.items():
            believes = v.vote(claim, self.world, self.buzzed[p], self.rng)
            self.pending_presses[p] = (self.clock.now_ms() + self.rng.randint(1000, 8000), 1 if believes else 2)
