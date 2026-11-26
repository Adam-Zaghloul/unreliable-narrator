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

from .design import MONO, SERIF, base_css, logo_svg

CSS = f"""
html,body{{height:100%}}
body{{display:flex;flex-direction:column;overflow:hidden}}
.bar{{display:flex;justify-content:space-between;align-items:center;margin:26px 44px 0;padding-bottom:14px;
  border-bottom:1.5px solid var(--ink)}}
.bar .brand{{display:inline-flex;align-items:center;gap:14px;font:600 20px {SERIF}}}
.stage{{flex:1;display:flex;flex-direction:column;justify-content:center;padding:0 8vw 7vh}}
.eyebrow{{display:flex;align-items:center;gap:18px;font:clamp(13px,1.3vw,18px) {MONO};letter-spacing:.2em;
  text-transform:uppercase;color:var(--muted);margin-bottom:3.4vh}}
.eyebrow b{{color:var(--red);font-weight:600}}
.eyebrow::after{{content:"";width:12vw;border-top:1px solid var(--rule)}}
.timer{{font:400 clamp(110px,22vw,300px)/.86 {SERIF};letter-spacing:-.04em}}
.timer small{{font-size:.32em;letter-spacing:0;color:var(--muted);margin-left:.15em}}
.big{{font:400 clamp(60px,9vw,136px)/1 {SERIF};letter-spacing:-.025em}}
.big i{{color:var(--red)}}
.hint{{font:italic clamp(22px,2.4vw,34px)/1.35 {SERIF};color:var(--muted);max-width:32ch;margin-top:4.5vh}}
.quote{{font:400 clamp(40px,5.8vw,92px)/1.1 {SERIF};letter-spacing:-.01em;max-width:19ch;text-indent:-.24em}}
.quote::before{{content:"\\201C";color:var(--red)}}
.quote::after{{content:"\\201D";color:var(--red)}}
.vote{{display:grid;grid-template-columns:minmax(260px,560px) auto auto;align-items:center;gap:3.2vw;margin-top:6.5vh}}
.ruler{{position:relative;height:22px;border-bottom:1.5px solid var(--ink);
  background:repeating-linear-gradient(90deg,var(--ink) 0 1.5px,transparent 1.5px calc(100% / 15)) bottom/100% 9px no-repeat}}
.ruler i{{position:absolute;left:0;bottom:-1.5px;height:6px;background:var(--red);transition:width .5s linear}}
.count{{font:clamp(22px,2.2vw,32px) {MONO};font-variant-numeric:tabular-nums}}
.dots{{display:flex;gap:12px}}
.dots b{{width:20px;height:20px;border-radius:50%;box-shadow:inset 0 0 0 2px var(--ink);transition:background .2s}}
.dots b.on{{background:var(--ink)}}
.keys{{display:flex;gap:26px;margin-top:5vh;align-items:center;font:clamp(14px,1.3vw,18px) {MONO};color:var(--muted)}}
.keys .stamp{{font-size:clamp(14px,1.3vw,19px);padding:9px 10px 8px 13px;margin-right:10px}}
.buzz{{position:fixed;right:44px;bottom:34px;opacity:0;transition:opacity .3s}}
.buzz.on{{opacity:1}}
.buzz .stamp{{font-size:16px;padding:10px 11px 9px 14px;color:var(--red)}}
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
  if(st.phase==='idle'){h.push(`<div class="eyebrow">Before we begin</div><div class="big">Badges on.<br>Phones <i>away.</i></div>
    <div class="hint">The game starts when the host says go.</div>`)}
  if(st.phase==='play'){h.push(`<div class="eyebrow"><b>Round ${st.round}</b> of ${st.rounds} &nbsp;·&nbsp; walk around</div>
    <div class="timer">${mm(left)}</div>
    <div class="hint">When your badge buzzes, take a mental photograph: who is in the room with you?</div>`)}
  if(st.phase==='meeting'){
    const pct=Math.max(0,Math.min(100,100*left/(st.vote_seconds||15)));
    const dots=Array.from({length:st.players},(_,i)=>`<b class="${i<st.voted?'on':''}"></b>`).join('');
    h.push(`<div class="eyebrow"><b>Meeting</b> &nbsp;·&nbsp; statement ${st.index} of ${st.count}</div>
      <div class="quote">${esc(st.text)}</div>
      <div class="vote"><div class="ruler"><i style="width:${pct}%"></i></div>
        <span class="count">${mm(left)}</span><span class="dots" aria-label="${st.voted} of ${st.players} voted">${dots}</span></div>
      <div class="keys"><span><span class="stamp true">True</span>left button</span>
        <span><span class="stamp lie">Lie</span>right button</span></div>`)}
  if(st.phase==='over'){h.push(`<div class="eyebrow">That&rsquo;s the game</div>
    <div class="big">Now, <i>the truth.</i></div>
    <div class="hint">The reveal is on the host&rsquo;s laptop: every lie, corrected, and who fell for it.</div>`)}
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
            f"<div class='bar'><span class='brand'>{logo_svg(24)}The Unreliable Narrator</span>"
            f"<span class='caps muted'>The narrator is lying to you. Some of the time.</span></div>"
            f"<div class='stage'></div><div class='buzz'><span class='stamp'>A badge just buzzed</span></div>"
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
