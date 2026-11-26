"""The live game loop, run end to end against the fake gateway (no hardware, no API)."""
import json
import sqlite3

from evals.e1_bench import evaluate
from evals.e3_analysis import load, report
from hub import db
from hub.config import GameConfig, validate
from hub.export import session_records
from hub.liars import HeuristicLiar, TemplateLiar
from hub.live import LiveGame
from hub.reveal import build
from hub.rounds import arm_order
from hub.transport import SimClock, SimTransport
from hub.walk import record
from sim.world import simulate

CFG = GameConfig(players={1: "Sara", 2: "Karim", 3: "Lina", 4: "Omar", 5: "Maya", 6: "Theo"},
                 zones={1: "kitchen", 2: "living room", 3: "hallway", 4: "balcony"},
                 round_minutes=2, speak=False)


def run_game(tmp_path, session=0, seed=0):
    cfg = GameConfig(**{**CFG.__dict__, "session": session})
    world = simulate(seed, players=list(cfg.players.values()), zones=list(cfg.zones.values()), duration_s=700)
    clock = SimClock()
    transport = SimTransport(world, clock, seed)
    path = tmp_path / f"s{session}.db"
    con = db.connect(path)
    # the llm arm is replaced by a second heuristic liar so the test never calls the API
    liars = {"llm": HeuristicLiar(seed + 5)}
    liars["llm"].name = "llm"
    LiveGame(cfg, transport, clock, con, seed, mode="SIMULATED", liars=liars).run()
    return con, transport, path


def test_full_game_produces_rounds_statements_votes(tmp_path):
    con, transport, _ = run_game(tmp_path)
    assert [a for _, a in con.execute("SELECT round, arm FROM rounds ORDER BY round")] == arm_order(0)
    n_st = con.execute("SELECT count(*) FROM statements").fetchone()[0]
    assert n_st == 12
    lies = con.execute("SELECT count(*) FROM statements WHERE is_lie=1").fetchone()[0]
    assert lies == 6
    votes = con.execute("SELECT count(*) FROM votes").fetchone()[0]
    assert votes >= n_st * 5  # nearly every simulated player's press arrives in the 15 s window
    assert any(s.startswith("BUZZ") for s in transport.sent)


def test_votes_come_from_button_presses_last_press_wins():
    con = db.connect()
    game = LiveGame(CFG, transport=None, clock=SimClock(), con=con)
    game.presses = [(1000, "Sara", 1), (3000, "Sara", 2), (2000, "Lina", 1), (99_000, "Omar", 1), (2500, "Theo", 3)]
    believed = game.collect_votes(0, 0, 10_000)
    rows = dict(con.execute("SELECT voter, believes_true FROM votes").fetchall())
    assert rows == {"Sara": 0, "Lina": 1}  # Omar too late, Theo pressed both = ignored
    assert believed == 1


def test_arm_order_is_counterbalanced():
    orders = {tuple(arm_order(s)) for s in range(6)}
    assert len(orders) == 6
    for pos in range(3):
        assert {o[pos] for o in orders} == {"template", "heuristic", "llm"}


def test_reveal_and_export_and_e3(tmp_path):
    paths = []
    for s in range(3):
        con, _, path = run_game(tmp_path, session=s, seed=s)
        con.close()
        paths.append(str(path))
    page = build(sqlite3.connect(paths[0]))
    assert "The statements" in page and "stamp lie" in page and "Simulated players" in page and "<del>" in page
    recs = session_records(__import__("pathlib").Path(paths[0]))
    names = {r.get("voter") for r in recs if r["type"] == "vote"}
    assert names and all(n.startswith("P") for n in names)  # anonymised
    assert not any("Sara" in json.dumps(r) for r in recs)
    assert load(paths, include_sim=False) == []  # simulated sessions are excluded by default
    text = report(load(paths, include_sim=True))
    assert "WARNING" in text and "heuristic" in text


def test_config_validation():
    assert validate(CFG) == []
    bad = GameConfig(players={1: "Sara", 2: "sara", 3: "Omar"}, zones={1: "kitchen"})
    errs = validate(bad)
    assert any("unique" in e for e in errs) and any("2-8 zones" in e for e in errs)


def test_walk_recorder_and_e1_bench():
    world = simulate(4, players=["Sara"], duration_s=300)
    clock = SimClock()
    transport = SimTransport(world, clock)
    cfg = GameConfig(players={1: "Sara"}, zones={i + 1: z for i, z in enumerate(world.zones)})
    zid = {z: i for i, z in cfg.zones.items()}
    # replay the simulated walk: type the zone id at every room change
    changes = [(t, world.true_zone[("Sara", t)]) for t in range(300)
               if t == 0 or world.true_zone[("Sara", t)] != world.true_zone[("Sara", t - 1)]]
    script = iter([(t, str(zid[z])) for t, z in changes] + [(300, "q")])

    def read(_):
        t, key = next(script)
        clock.t = t * 1000
        return key

    con = db.connect()
    assert record(transport, clock, con, cfg, read=read, out=lambda *a: None) == len(changes)
    r = evaluate(con)["results"]
    right, n = r["mine clean"]
    assert n > 10 and right / n > 0.95
