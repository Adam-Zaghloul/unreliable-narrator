from hub.ingest import parse_line


def test_parses_gateway_line_and_names_players():
    line = '{"badge":1,"seq":4,"buttons":2,"peers":[["B",1,-57],["P",3,-70]]}'
    pings, bid, buttons = parse_line(line, 1234, {"1": "Sara"})
    assert bid == 1 and buttons == 2
    assert [(p.badge, p.beacon, p.rssi, p.t_ms) for p in pings] == [("Sara", "B1", -57.0, 1234), ("Sara", "P3", -70.0, 1234)]


def test_ignores_non_packet_lines():
    assert parse_line('{"gateway":"ready"}', 0, {})[0] == []
    assert parse_line("garbage", 0, {})[0] == []
