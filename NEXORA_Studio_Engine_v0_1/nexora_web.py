from __future__ import annotations
import html, json, os, shutil, subprocess, sys, tempfile, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE=Path(__file__).resolve().parent
ENGINE=BASE
PYTHON=Path(sys.executable)
MODULE_DIR=BASE/'NEXORA_Studio_Engine_v0_1'
def engine_file(name):
    for p in (BASE/name, MODULE_DIR/name):
        if p.exists(): return p
    raise FileNotFoundError(f'Engine module not found: {name}')
OUTPUT=ENGINE/'output'; PROJECTS=ENGINE/'projects'
OUTPUT.mkdir(exist_ok=True); PROJECTS.mkdir(exist_ok=True)
STATE={'status':'Ready','progress':0,'error':'','output':'','stage':'Ready'}

HTML_HEAD='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEXORA Studio Engine</title><style>
:root{--bg:#090b0c;--panel:#111517;--text:#f4f6f5;--muted:#8d9698;--lime:#b8f23a;--border:#283033}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 85% 5%,#182219 0,transparent 30%),var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif}.wrap{max-width:900px;margin:0 auto;padding:44px 28px 70px}.brand{font-size:28px;font-weight:800}.tag{font-size:10px;color:var(--muted);letter-spacing:.2em;margin:7px 0 30px}.modes{display:flex;gap:10px;margin-bottom:18px}.mode{flex:1;border:1px solid var(--border);border-radius:12px;padding:14px;text-align:center;font-size:11px;font-weight:800;letter-spacing:.12em;color:var(--muted)}.mode.active{border-color:var(--lime);color:var(--lime);background:#131a11}.card{background:rgba(17,21,23,.92);border:1px solid var(--border);padding:20px;margin:12px 0;border-radius:14px}.title{font-size:11px;font-weight:800;letter-spacing:.12em}.hint{font-size:12px;color:var(--muted);margin:7px 0 12px}textarea{width:100%;min-height:290px;resize:vertical;background:#0b0e0f;border:1px solid #242c2e;border-radius:10px;color:var(--text);padding:15px;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;outline:none}input[type=file]{width:100%;color:var(--muted)}button{width:100%;border:0;border-radius:10px;background:var(--lime);color:#0b0d0e;font-weight:800;font-size:15px;padding:15px;margin-top:20px;cursor:pointer}button:disabled{opacity:.5;cursor:default}.status{font-size:13px;margin-top:20px}.sub{font-size:11px;color:var(--muted);margin-top:5px}.bar{height:6px;background:#151a1b;border-radius:10px;margin-top:10px;overflow:hidden}.fill{height:100%;width:VAR_PROGRESS%;background:var(--lime);transition:width .3s}.success,.error{margin-top:18px;padding:13px;border-radius:9px;font-size:13px}.success{background:#151e14;border:1px solid #31452a}.success a{color:var(--lime)}.error{background:#211515;border:1px solid #5b3030;color:#ffb7b7}.foot{margin-top:22px;color:var(--muted);font-size:10px;letter-spacing:.12em}.ai{display:flex;align-items:center;gap:12px;margin-top:14px;padding:14px;border:1px solid #34402d;border-radius:12px;background:#101610}.ai input{accent-color:var(--lime);width:18px;height:18px}.ai strong{font-size:13px}.ai small{display:block;color:var(--muted);margin-top:4px;font-size:11px;line-height:1.35}</style></head>'''

def page():
 st=STATE.copy(); disabled=st['status'] not in ('Ready','✓ Complete'); msg=''
 if st['error']: msg='<div class="error">'+html.escape(st['error'])+'</div>'
 elif st['output']: msg='<div class="success">✓ Video ready — <a href="/download">Download MP4</a></div>'
 h=HTML_HEAD.replace('VAR_PROGRESS',str(int(st['progress']*100)))
 ai_available=True
 ai_note='Zero-cost NEXORA cinematic visual engine — no API key or credits required'
 body='''<body><main class="wrap"><div class="brand">NEXORA STUDIO ENGINE</div><div class="tag">SMARTER TODAY. BRIGHTER TOMORROW.</div><div class="modes"><div class="mode active">ACADEMY</div><div class="mode">YOUTUBE</div><div class="mode">SHORTS</div></div><form method="post" enctype="multipart/form-data" action="/generate"><div class="card"><div class="title">VOICE / AUDIO</div><div class="hint">Select your narration audio</div><input name="audio" type="file" accept="audio/*" required></div><div class="card"><div class="title">SCRIPT</div><div class="hint">Paste the narration directly — no .txt file needed</div><textarea name="script" required placeholder="Paste your full narration here..."></textarea><label class="ai"><input name="ai" type="checkbox" AI_CHECKED><span><strong>CINEMATIC STORY VISUALS</strong><small>Visuals are planned from the meaning of the narration. '''+html.escape(ai_note)+'''</small></span></label></div><button type="submit" DISABLED>✨ &nbsp; GENERATE ACADEMY VIDEO</button></form><div class="status">STATUS_TEXT</div><div class="sub">STAGE_TEXT</div><div class="bar"><div class="fill"></div></div>MSG<div class="foot">ACADEMY • 16:9 • NEXORA Studio</div></main><script>setInterval(()=>fetch('/status').then(r=>r.json()).then(s=>{if(s.status!=='Ready'||s.output||s.error) location.reload()}),1200)</script></body></html>'''
 body=body.replace('AI_CHECKED',' checked' if ai_available else '').replace('DISABLED','disabled' if disabled else '').replace('STATUS_TEXT',html.escape(st['status'])).replace('STAGE_TEXT',html.escape(st.get('stage',''))).replace('MSG',msg)
 return h+body

def parse_multipart(rfile,length,boundary):
 data=rfile.read(length); sep=b'--'+boundary; out={}
 for part in data.split(sep):
  if b'Content-Disposition:' not in part: continue
  head,body=part.split(b'\r\n\r\n',1); body=body.rstrip(b'\r\n-')
  hs=head.decode('utf-8','replace'); import re
  m=re.search(r'name="([^"]+)"',hs); fn=re.search(r'filename="([^"]*)"',hs)
  if m: out[m.group(1)]=(fn.group(1) if fn else '',body)
 return out

def run_cmd(cmd,timeout=None):
 return subprocess.run(cmd,capture_output=True,text=True)

def run_pipeline(audio,script,out,use_ai):
 try:
  if use_ai:
   STATE.update(status='Storyboarding…',progress=.08,stage='Interpreting the narration and mapping meaning to visuals',error='',output='')
  else:
   STATE.update(status='Preparing audio…',progress=.10,stage='Reading narration and creating timings',error='',output='')
  director=engine_file('scene_director.py'); pipeline=engine_file('pipeline.py')
  stamp=int(time.time()); alignment=PROJECTS/f'{audio.stem}_{stamp}_alignment.json'; directed=PROJECTS/f'{audio.stem}_{stamp}_directed.json'
  STATE.update(status='Preparing audio…',progress=.15,stage='Reading narration duration')
  r=run_cmd(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(audio)],timeout=30)
  if r.returncode: raise RuntimeError(r.stderr.strip() or 'Could not read audio duration.')
  try: duration=float(r.stdout.strip())
  except ValueError: raise RuntimeError('Could not read audio duration.')
  import re as _re
  tokens=_re.findall(r'\S+',script.read_text(encoding='utf-8'))
  if not tokens: raise RuntimeError('Script is empty.')
  step=duration/len(tokens); words=[]
  for i,w in enumerate(tokens):
   words.append({'word':w,'start':round(i*step,3),'end':round(duration if i==len(tokens)-1 else (i+1)*step,3)})
  segments=[]; chunk=max(1,len(words)//12)
  for i in range(0,len(words),chunk):
   part=words[i:i+chunk]; segments.append({'start':part[0]['start'],'end':part[-1]['end'],'text':' '.join(x['word'] for x in part)})
  alignment.write_text(json.dumps({'version':2,'provider':'deterministic-script-timing','duration':duration,'segments':segments,'words':words,'events':[]},indent=2),encoding='utf-8')
  max_scenes=8 if use_ai else 12
  STATE.update(status='Directing scenes…',progress=.25,stage='Building the visual plan from the narration')
  cmd=[str(PYTHON),str(director),'--alignment',str(alignment),'--script',str(script),'--output',str(directed),'--max-scenes',str(max_scenes)]
  r=run_cmd(cmd,timeout=120)
  if r.returncode: raise RuntimeError(r.stderr.strip() or r.stdout.strip() or 'Scene Director failed.')
  STATE.update(status='Generating visuals…' if use_ai else 'Rendering visuals…',progress=.35,stage='Rendering meaning-driven visual scenes' if use_ai else 'Rendering local visual scenes')
  cmd=[str(PYTHON),str(pipeline),'--audio',str(audio),'--script',str(script),'--manifest',str(directed),'--output',str(out)]
  if use_ai: cmd.append('--ai')
  r=run_cmd(cmd,timeout=3600 if use_ai else 1200)
  if r.returncode: raise RuntimeError(r.stderr.strip() or r.stdout.strip() or 'Renderer failed.')
  STATE.update(status='✓ Complete',progress=1.0,stage='Your video is ready',output=str(out))
 except subprocess.TimeoutExpired:
  STATE.update(status='⚠ Generation stopped',progress=0,error='One stage took longer than expected and was stopped safely.',stage='Try again.')
 except Exception as e:
  STATE.update(status='⚠ Generation stopped',progress=0,error=str(e),stage='The browser interface is still available.')

def unique_output(stem):
 p=OUTPUT/f'NEXORA_{stem}.mp4'; i=2
 while p.exists(): p=OUTPUT/f'NEXORA_{stem}_{i}.mp4'; i+=1
 return p

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def send(self,code,body,ctype='text/html; charset=utf-8'):
  b=body.encode() if isinstance(body,str) else body; self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_GET(self):
  if self.path=='/': return self.send(200,page())
  if self.path=='/status': return self.send(200,json.dumps(STATE),'application/json')
  if self.path=='/download' and STATE['output'] and Path(STATE['output']).exists():
   p=Path(STATE['output']); self.send_response(200); self.send_header('Content-Type','video/mp4'); self.send_header('Content-Disposition',f'attachment; filename="{p.name}"'); self.send_header('Content-Length',str(p.stat().st_size)); self.end_headers()
   with p.open('rb') as f: shutil.copyfileobj(f,self.wfile)
   return
  self.send(404,'Not found')
 def do_POST(self):
  if self.path!='/generate': return self.send(404,'Not found')
  ctype=self.headers.get('Content-Type',''); length=int(self.headers.get('Content-Length','0'))
  if 'multipart/form-data' not in ctype: return self.send(400,'Invalid upload')
  parts=parse_multipart(self.rfile,length,ctype.split('boundary=',1)[1].encode())
  if 'audio' not in parts or 'script' not in parts: return self.send(400,'Please select audio and paste the script.')
  aname,abytes=parts['audio']; _,sbytes=parts['script']; _,ai_bytes=parts.get('ai',('',b''))
  script_text=sbytes.decode('utf-8','replace').strip()
  use_ai=bool(ai_bytes)
  if not script_text: return self.send(400,'Please paste the script.')
  work=Path(tempfile.mkdtemp(prefix='nexora_upload_')); audio=work/(Path(aname).name or 'voice.wav'); script=work/'script.txt'; audio.write_bytes(abytes); script.write_text(script_text,encoding='utf-8')
  out=unique_output(script.stem); STATE.update(status='Starting…',progress=.03,error='',output='',stage='Preparing the project')
  threading.Thread(target=run_pipeline,args=(audio,script,out,use_ai),daemon=True).start()
  self.send_response(303); self.send_header('Location','/'); self.send_header('Content-Length','0'); self.end_headers()

def main():
 port=int(os.environ.get('PORT','8765')); host=os.environ.get('HOST','0.0.0.0'); server=ThreadingHTTPServer((host,port),Handler)
 print(f'NEXORA Studio Engine listening on {host}:{port}',flush=True)
 if os.environ.get('OPEN_BROWSER')=='1': threading.Timer(.8,lambda:webbrowser.open(f'http://127.0.0.1:{port}/')).start()
 server.serve_forever()

if __name__=='__main__': main()
