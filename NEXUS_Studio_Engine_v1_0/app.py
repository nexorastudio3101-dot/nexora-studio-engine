from __future__ import annotations
import html, json, os, shutil, subprocess, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from director import make_storyboard
from visual_provider import generate_image
from render import render_video

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "output"
OUTPUT.mkdir(exist_ok=True)
STATE = {"status":"Ready","progress":0.0,"stage":"Ready","error":"","output":"","storyboard":None}

def page():
    s = dict(STATE)
    busy = s["status"] not in ("Ready","✓ Complete","⚠ Generation stopped")
    msg = f'<div class="error">{html.escape(s["error"])}</div>' if s["error"] else (
        f'<div class="ok">✓ Video ready — <a href="/download">Download MP4</a></div>' if s["output"] else "")
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEVORA Studio Engine</title>
<style>
:root{{--bg:#080a0b;--panel:#101415;--line:#273033;--text:#f5f7f6;--muted:#8e989a;--lime:#b9f33d}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 85% 0,#1a2418,transparent 32%),var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif}}
.wrap{{max-width:920px;margin:auto;padding:44px 24px 70px}}.brand{{font-size:27px;font-weight:850;letter-spacing:-.03em}}.tag{{font-size:10px;letter-spacing:.22em;color:var(--muted);margin:7px 0 34px}}
.card{{background:rgba(16,20,21,.94);border:1px solid var(--line);border-radius:16px;padding:22px;margin:14px 0}}.label{{font-size:10px;font-weight:800;letter-spacing:.16em}}.hint{{font-size:12px;color:var(--muted);margin:7px 0 14px}}
textarea{{width:100%;min-height:260px;background:#0b0e0f;border:1px solid var(--line);border-radius:11px;color:var(--text);padding:15px;font:14px/1.55 inherit;outline:none}}
button{{width:100%;padding:15px;border:0;border-radius:11px;background:var(--lime);color:#080a09;font-weight:850;font-size:15px;cursor:pointer}}button:disabled{{opacity:.45;cursor:default}}
.status{{margin-top:22px;font-size:13px}}.stage{{font-size:11px;color:var(--muted);margin-top:5px}}.bar{{height:6px;background:#161b1c;border-radius:9px;margin-top:10px;overflow:hidden}}.fill{{height:100%;width:{int(s["progress"]*100)}%;background:var(--lime)}}
.ok,.error{{margin-top:16px;padding:13px;border-radius:10px;font-size:13px}}.ok{{background:#121b10;border:1px solid #31472a}}.ok a{{color:var(--lime)}}.error{{background:#241515;border:1px solid #603030;color:#ffc0c0}}
.note{{font-size:11px;color:var(--muted);line-height:1.45;margin-top:12px}}.foot{{margin-top:22px;font-size:10px;color:var(--muted);letter-spacing:.12em}}
</style></head><body><main class="wrap">
<div class="brand">NEVORA STUDIO ENGINE</div><div class="tag">TURN KNOWLEDGE INTO VISUAL STORIES.</div>
<form method="post" action="/generate">
<div class="card"><div class="label">SCRIPT</div><div class="hint">Paste the narration. NEVORA's AI Director decides what each scene should show.</div>
<textarea name="script" required placeholder="Paste your narration here..."></textarea>
<div class="note">No audio upload is required. The engine builds the visual story from the script.</div>
</div>
<button type="submit" {"disabled" if busy else ""}>GENERATE VIDEO</button></form>
<div class="status">{html.escape(s["status"])}</div><div class="stage">{html.escape(s["stage"])}</div>
<div class="bar"><div class="fill"></div></div>{msg}
<div class="foot">16:9 • AI DIRECTOR • NEVORA STUDIO ENGINE</div>
<script>
let lastStatus=null;
setInterval(()=>fetch('/status').then(r=>r.json()).then(s=>{{if(lastStatus!==null&&s.status!==lastStatus)location.reload();lastStatus=s.status}}).catch(()=>{{}}),1200);
</script></main></body></html>"""

def duration_from_script(script):
    words = max(1, len(script.split()))
    return max(20.0, min(60.0, words / 2.35))

def make_silent_audio(duration, output):
    r = subprocess.run(["ffmpeg","-y","-loglevel","error","-f","lavfi","-i","anullsrc=r=48000:cl=stereo",
                        "-t",f"{duration:.3f}","-c:a","aac","-b:a","128k",str(output)],
                       capture_output=True,text=True,timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr[-3000:] or "Could not create temporary audio track.")

def worker(script_text, out):
    try:
        STATE.update(status="Understanding story…",progress=.08,stage="AI Director is analysing the script")
        duration = duration_from_script(script_text)
        storyboard = make_storyboard(script_text,duration)
        events = storyboard["events"]
        STATE["storyboard"] = storyboard
        STATE.update(status="Designing visuals…",progress=.22,stage=f"Planning {len(events)} semantic scenes")
        work = Path(tempfile.mkdtemp(prefix="nevora_"))
        try:
            images=[]
            for i,e in enumerate(events):
                STATE.update(status=f"Generating visual {i+1}/{len(events)}…",
                             progress=.25+.48*(i/max(1,len(events))),
                             stage=e.get("visual_concept","Creating the scene"))
                p=work/f"scene_{i:02d}.png"
                generate_image(e["visual_prompt"],p,e.get("continuity",""))
                images.append(p)
            STATE.update(status="Editing video…",progress=.80,stage="Assembling the visual story")
            audio=work/"silence.m4a"
            make_silent_audio(duration,audio)
            render_video(events,audio,images,out,duration)
            STATE.update(status="✓ Complete",progress=1.0,stage="Your video is ready",output=str(out))
        finally:
            shutil.rmtree(work,ignore_errors=True)
    except Exception as exc:
        STATE.update(status="⚠ Generation stopped",progress=0,stage="No partial video was published",error=str(exc),output="")

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self,code,body,ctype="text/html; charset=utf-8"):
        b=body.encode() if isinstance(body,str) else body
        self.send_response(code); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path=="/": return self.send(200,page())
        if self.path=="/status": return self.send(200,json.dumps(STATE),"application/json")
        if self.path=="/storyboard": return self.send(200,json.dumps(STATE.get("storyboard") or {}),"application/json")
        if self.path=="/download" and STATE.get("output") and Path(STATE["output"]).exists():
            p=Path(STATE["output"])
            self.send_response(200); self.send_header("Content-Type","video/mp4")
            self.send_header("Content-Disposition",f'attachment; filename="{p.name}"')
            self.send_header("Content-Length",str(p.stat().st_size)); self.end_headers()
            with p.open("rb") as f: shutil.copyfileobj(f,self.wfile)
            return
        self.send(404,"Not found")
    def do_POST(self):
        if self.path!="/generate": return self.send(404,"Not found")
        length=int(self.headers.get("Content-Length","0"))
        body=self.rfile.read(length)
        ctype=self.headers.get("Content-Type","")
        if "application/x-www-form-urlencoded" not in ctype:
            return self.send(400,"Invalid request")
        from urllib.parse import parse_qs
        data=parse_qs(body.decode("utf-8","replace"))
        script=data.get("script",[""])[0].strip()
        if not script: return self.send(400,"Script is empty.")
        if STATE["status"] not in ("Ready","✓ Complete","⚠ Generation stopped"):
            return self.send(409,"A generation is already running.")
        out=OUTPUT/f"NEVORA_video_{int(time.time())}.mp4"
        STATE.update(status="Starting…",progress=.02,stage="Preparing project",error="",output="",storyboard=None)
        threading.Thread(target=worker,args=(script,out),daemon=True).start()
        self.send_response(303); self.send_header("Location","/"); self.send_header("Content-Length","0"); self.end_headers()

def main():
    port=int(os.environ.get("PORT","10000"))
    ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()

if __name__=="__main__": main()
