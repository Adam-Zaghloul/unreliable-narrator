"""Big screen: what players see on a TV or laptop during the game.

The game loop pushes its state here; a tiny local web server (stdlib only) serves one page
that polls /state twice a second. It never shows votes as they come in, only HOW MANY
players have voted, so nobody can copy the room.

    open http://127.0.0.1:8765 on the screen (python -m hub.live ... --screen)
    http://127.0.0.1:8765/?demo=play | meeting | over     static demo states (for docs)
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .design import base_css, logo_svg

CSS = """
html,body{height:100%}
body{display:flex;flex-direction:column;overflow:hidden}
.bar{display:flex;justify-content:space-between;align-items:center;padding:22px 36px;font-size:18px}
.stage{flex:1;display:flex;flex-direction:column;justify-content:center;padding:0 7vw 6vh}
.eyebrow{font-size:clamp(14px,1.6vw,22px);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:650;
  margin-bottom:2.2vh}
.timer{font-size:clamp(90px,19vw,260px);line-height:.95;font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.03em}
.hint{font-size:clamp(20px,2.4vw,34px);color:var(--muted);max-width:30ch;margin-top:3vh;line-height:1.35}
.quote{font-size:clamp(36px,5.6vw,84px);line-height:1.12;max-width:20ch;font-weight:500}
.quote::before{content:"\\201C";color:var(--lie);margin-left:-.45em;padding-right:.05em}
.quote::after{content:"\\201D";color:var(--lie)}
.vote{display:flex;align-items:center;gap:3vw;margin-top:6vh;flex-wrap:wrap}
.track{flex:1;min-width:240px;height:10px;border-radius:99px;background:var(--line);overflow:hidden;max-width:560px}
.track i{display:block;height:100%;background:var(--ink);border-radius:99px;transition:width .5s linear}
.count{font-size:clamp(18px,2vw,28px);font-variant-numeric:tabular-nums}
.dots{display:flex;gap:10px}
.dots b{width:18px;height:18px;border-radius:50%;border:2px solid var(--muted);transition:background .2s}
.dots b.on{background:var(--ink);border-color:var(--ink)}
.keys{display:flex;gap:16px;margin-top:4vh;font-size:clamp(16px,1.6vw,22px)}
.key{display:inline-flex;align-items:center;gap:10px;padding:10px 18px;border-radius:14px;border:1px solid var(--line);
  background:var(--surface)}
.key i{width:22px;height:22px;border-radius:50%;display:inline-block}
.buzz{position:fixed;inset:auto 36px 30px auto;font-size:18px;padding:10px 16px;border-radius:12px;background:var(--surface);
  border:1px solid var(--line);opacity:0;transition:opacity .3s}
.buzz.on{opacity:1}
"""

PAGE_JS = """
const DEMO={
 play:{phase:'play',round:2,rounds:3,seconds_left:221,players:6,buzzed:true},
 meeting:{phase:'meeting',round:2,rounds:3,index:2,count:4,text:'At 3:40, Karim was in the living room.',
          seconds_left:9,vote_seconds:15,voted:4,players:6},
 over:{phase:'over',players:6}};
const q=new URLSearchParams(location.search).get('demo');
const $=s=>document.querySelector(s);
const mm=s=>{s=Math.max(0,Math.ceil(s));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')};
let st={phase:'idle'},recv=performance.now();
function render(){
  const left=(st.seconds_left??0)-(performance.now()-recv)/1000;
  const h=[];
  if(st.phase==='idle'){h.push(`<div class="eyebrow">Get ready</div><div class="timer serif" style="font-size:clamp(56px,9vw,130px)">Badges on.</div>
    <div class="hint">The game starts when the host says go.</div>`)}
  if(st.phase==='play'){h.push(`<div class="eyebrow">Round ${st.round} of ${st.rounds} · walk around</div>
    <div class="timer">${mm(left)}</div>
    <div class="hint">When your badge buzzes, take a mental snapshot: who is in the room with you?</div>`)}
  if(st.phase==='meeting'){
    const pct=Math.max(0,Math.min(100,100*left/(st.vote_seconds||15)));
    const dots=Array.from({length:st.players},(_,i)=>`<b class="${i<st.voted?'on':''}"></b>`).join('');
    h.push(`<div class="eyebrow">Meeting · statement ${st.index} of ${st.count}</div>
      <div class="quote serif">${esc(st.text)}</div>
      <div class="vote"><div class="track"><i style="width:${pct}%"></i></div>
        <span class="count">${mm(left)}</span><span class="dots" aria-label="${st.voted} of ${st.players} voted">${dots}</span></div>
      <div class="keys"><span class="key"><i style="background:var(--true)"></i>Left button · TRUE</span>
        <span class="key"><i style="background:var(--lie)"></i>Right button · LIE</span></div>`)}
  if(st.phase==='over'){h.push(`<div class="eyebrow">That's the game</div>
    <div class="timer serif" style="font-size:clamp(56px,9vw,130px)">Now, the truth.</div>
    <div class="hint">The reveal is open on the host's laptop: every lie, and who fell for it.</div>`)}
  $('.stage').innerHTML=h.join('');
  $('.buzz').classList.toggle('on',!!st.buzzed&&st.phase==='play');
}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function poll(){try{const r=await fetch('/state',{cache:'no-store'});st=await r.json();recv=performance.now()}catch(e){}}
if(q&&DEMO[q]){st=DEMO[q];render()}else{poll();setInterval(poll,500);setInterval(render,250)}
"""


def page() -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>The Unreliable Narrator</title>"
            f"<style>{base_css()}{CSS}</style></head><body>"
            f"<div class='bar'><span class='mark'>{logo_svg()}The Unreliable Narrator</span>"
            f"<span class='muted'>The narrator is lying to you. Some of the time.</span></div>"
            f"<div class='stage'></div><div class='buzz'>A badge just buzzed</div>"
            f"<script>{PAGE_JS}</script></body></html>")


class Screen:
    """Thread-safe state holder + server. `update()` merges keys; deadlines become seconds_left."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host, self.port = host, port
        self._state: dict = {"phase": "idle"}
        self._deadline: float | None = None
        self._buzz_until = 0.0
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None

    def update(self, seconds_left: float | None = None, buzzed: bool = False, **kw) -> None:
        with self._lock:
            if "phase" in kw:
                self._state = {}
            self._state.update(kw)
            if seconds_left is not None:
                self._deadline = time.monotonic() + seconds_left
            if buzzed:
                self._buzz_until = time.monotonic() + 4

    def state(self) -> dict:
        with self._lock:
            s = dict(self._state)
            if self._deadline is not None:
                s["seconds_left"] = max(0.0, self._deadline - time.monotonic())
            s["buzzed"] = time.monotonic() < self._buzz_until
            return s

    def start(self) -> str:
        screen = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/state"):
                    body, ctype = json.dumps(screen.state()).encode(), "application/json"
                elif self.path == "/" or self.path.startswith("/?"):
                    body, ctype = page().encode(), "text/html; charset=utf-8"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self._server = ThreadingHTTPServer((self.host, self.port), H)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


class NullScreen:
    def update(self, *a, **kw) -> None:
        pass


if __name__ == "__main__":
    s = Screen()
    print(f"{s.start()}  (demo: /?demo=play, /?demo=meeting, /?demo=over); Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
