from __future__ import annotations
import html,json,os,shutil,subprocess,tempfile,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

from director import make_storyboard
from visual_provider import generate_image
from render import render_video

BASE=Path(__file__).resolve().parent
OUTPUT=BASE/"output"; OUTPUT.mkdir(exist_ok=True)
STATE={"status":"Ready","progress":0.0,"stage":"Ready","error":"","output":"","storyboard":None}
LOCK=threading.Lock()

def page():
    s=dict(STATE)
    busy=s["status"] not in ("Ready","✓ Complete","⚠ Generation stopped")
    msg=""
    if s["error"]:
        msg=f'<div class="error">{html.escape(s["error"])}</div>'
    elif s["output"]:
        msg=f'<div class="ok">✓ Video ready — <a href="/download">Download MP4</a></div>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXORA Studio Engine</title>
<style>
:root{{--bg:#080a0b;--panel:#101415;--line:#273033;--text:#f5f7f6;--muted:#8e989a;--lime:#b9f33d}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 85% 0,#1a2418,transparent 32%),var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif}}
.wrap{{max-width:920px;margin:auto;padding:44px 24px 70px}}.brand{{font-size:27px;font-weight:850;letter-spacing:-.03em}}.tag{{font-size:10px;letter-spacing:.22em;color:var(--muted);margin-top:7px;margin-bottom:34px}}
.card{{background:rgba(16,20,21,.94);border:1px solid var(--line);border-radius:16px;padding:22px;margin:14px 0}}.label{{font-size:10px;font-weight:800;letter-spacing:.16em}}.hint{{font-size:12px;color:var(--muted);margin:7px 0 14px}}
textarea{{width:100%;min-height:250px;background:#0b0e0f;border:1px solid var(--line);border-radius:11px;color:var(--text);padding:15px;font:14px/1.55 inherit;outline:none}}
input[type=file]{{width:100%;color:var(--muted)}}button{{width:100%;padding:15px;border:0;border-radius:11px;background:var(--lime);color:#080a09;font-weight:850;font-size:15px;cursor:pointer}}button:disabled{{opacity:.45;cursor:default}}
.status{{margin-top:22px;font-size:13px}}.stage{{font-size:11px;color:var(--muted);margin-top:5px}}.bar{{height:6px;background:#161b1c;border-radius:9px;margin-top:10px;overflow:hidden}}.fill{{height:100%;width:{int(s["progress"]*100)}%;background:var(--lime);transition:width .4s}}
.ok,.error{{margin-top:16px;padding:13px;border-radius:10px;font-size:13px}}.ok{{background:#121b10;border:1px solid #31472a}}.ok a{{color:var(--lime)}}.error{{background:#241515;border:1px solid #603030;color:#ffc0c0}}
.note{{font-size:11px;color:var(--muted);line-height:1.45;margin-top:12px}}.foot{{margin-top:22px;font-size:10px;color:var(--muted);letter-spacing:.12em}}
</style></head><body><main class="wrap">
<div class="brand">NEXORA STUDIO ENGINE</div><div class="tag">TURN KNOWLEDGE INTO VISUAL STORIES.</div>
<form method="post" enctype="multipart/form-data" action="/generate">
<div class="card"><div class="label">NARRATION AUDIO</div><div class="hint">Upload the narration audio for the video.</div><input name="audio" type="file" accept="audio/*" required></div>
<div class="card"><div class="label">SCRIPT</div><div class="hint">Paste the exact narration. The AI Director uses this to decide what should be shown.</div>
<textarea name="script" required placeholder="Paste your narration here..."></textarea>
<div class="note">The first prototype uses Gemini to understand the story and generate scene-specific visuals. If GEMINI_API_KEY is not configured, the engine will explain what is missing instead of silently falling back to meaningless graphics.</div>
</div>
<button type="submit" {"disabled" if busy else ""}>GENERATE VIDEO</button></form>
<div class="status">{html.escape(s["status"])}</div><div class="stage">{html.escape(s["stage"])}</div>
<div class="bar"><div class="fill"></div></div>{msg}
<div class="foot">16:9 • AI DIRECTOR • NEXORA STUDIO ENGINE</div>
<script>
let lastStatus=null;
setInterval(()=>fetch('/status').then(r=>r.json()).then(s=>{{
  if(lastStatus!==null && s.status!==lastStatus) location.reload();
  lastStatus=s.status;
}}).catch(()=>{{}}),1200);
</script>
</main></body></html>"""

def multipart(rfile,length,boundary):
    data=rfile.read(length); out={}
    for part in data.split(b"--"+boundary):
        if b"Content-Disposition:" not in part: continue
        head,body=part.split(b"\r\n\r\n",1); body=body.rstrip(b"\r\n-")
        hs=head.decode("utf-8","replace")
        import re
        m=re.search(r'name="([^"]+)"',hs); f=re.search(r'filename="([^"]*)"',hs)
        if m: out[m.group(1)]=(f.group(1) if f else "",body)
    return out

def duration_of(audio):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(audio)],capture_output=True,text=True,timeout=30)
    if r.returncode: raise RuntimeError("Could not read audio duration.")
    return float(r.stdout.strip())

def unique_output():
    stamp=int(time.time())
    return OUTPUT/f"NEXORA_video_{stamp}.mp4"

def worker(audio,script,out):
    try:
        STATE.update(status="Understanding story…",progress=.08,stage="AI Director is analysing the narration")
        duration=duration_of(audio)
        storyboard=make_storyboard(script.read_text(encoding="utf-8"),duration)
        events=storyboard["events"]
        STATE["storyboard"]=storyboard
        STATE.update(status="Designing visuals…",progress=.25,stage=f"Planning {len(events)} semantic scenes")

        work=Path(tempfile.mkdtemp(prefix="nexora_assets_"))
        try:
            images=[]
            for i,e in enumerate(events):
                STATE.update(status=f"Generating visual {i+1}/{len(events)}…",
                             progress=.30+.42*(i/max(1,len(events))),
                             stage=e.get("visual_concept","Creating the scene"))
                p=work/f"scene_{i:02d}.png"
                generate_image(e["visual_prompt"],p,e.get("continuity",""))
                images.append(p)

            STATE.update(status="Editing video…",progress=.78,stage="Synchronising scenes with narration")
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
            p=Path(STATE["output"]); self.send_response(200); self.send_header("Content-Type","video/mp4"); self.send_header("Content-Disposition",f'attachment; filename="{p.name}"'); self.send_header("Content-Length",str(p.stat().st_size)); self.end_headers()
            with p.open("rb") as f: shutil.copyfileobj(f,self.wfile)
            return
        self.send(404,"Not found")
    def do_POST(self):
        if self.path!="/generate": return self.send(404,"Not found")
        ctype=self.headers.get("Content-Type",""); length=int(self.headers.get("Content-Length","0"))
        if "multipart/form-data" not in ctype: return self.send(400,"Invalid upload")
        boundary=ctype.split("boundary=",1)[1].encode()
        parts=multipart(self.rfile,length,boundary)
        if "audio" not in parts or "script" not in parts: return self.send(400,"Please provide audio and script.")
        if STATE["status"] not in ("Ready","✓ Complete","⚠ Generation stopped"): return self.send(409,"A generation is already running.")
        name,audio_bytes=parts["audio"]; _,script_bytes=parts["script"]
        script_text=script_bytes.decode("utf-8","replace").strip()
        if not script_text: return self.send(400,"Script is empty.")
        work=Path(tempfile.mkdtemp(prefix="nexora_upload_"))
        audio=work/(Path(name).name or "narration.wav"); audio.write_bytes(audio_bytes)
        script=work/"script.txt"; script.write_text(script_text,encoding="utf-8")
        out=unique_output()
        STATE.update(status="Starting…",progress=.02,stage="Preparing project",error="",output="",storyboard=None)
        threading.Thread(target=worker,args=(audio,script,out),daemon=True).start()
        self.send_response(303); self.send_header("Location","/"); self.send_header("Content-Length","0"); self.end_headers()

def main():
    port=int(os.environ.get("PORT","10000"))
    ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()

if __name__=="__main__":
    main()
