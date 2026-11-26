import json
import urllib.request

from hub.screen import Screen, page


def test_state_merges_and_counts_down_and_serves_http():
    s = Screen(port=0)
    s.update(phase="meeting", text="At 0:10, Sara was in the kitchen.", seconds_left=15, voted=0, players=6)
    s.update(voted=3)
    st = s.state()
    assert st["phase"] == "meeting" and st["voted"] == 3 and 14 < st["seconds_left"] <= 15
    s.update(phase="over")
    assert "text" not in s.state()  # a new phase clears the old fields

    url = s.start()
    port = s._server.server_address[1]
    base = f"http://127.0.0.1:{port}"
    assert json.loads(urllib.request.urlopen(base + "/state").read())["phase"] == "over"
    assert "The Unreliable Narrator" in urllib.request.urlopen(base + "/").read().decode()
    s.stop()
    assert url.startswith("http://")


def test_page_escapes_statement_text_client_side():
    assert "function esc(" in page() and "esc(st.text)" in page()
