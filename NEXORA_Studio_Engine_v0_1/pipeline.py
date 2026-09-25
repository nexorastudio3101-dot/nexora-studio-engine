from __future__ import annotations
import argparse,json,subprocess,tempfile,shutil,sys,hashlib
from pathlib import Path
FFMPEG='ffmpeg'; FFPROBE='ffprobe'
import numpy as np
from PIL import Image
import soundfile as sf
from scene_renderer import render_scene
from scene_director import make_director
W,H,FPS=1920,1080,30
ROOT=Path(__file__).resolve().parent
def run(cmd): subprocess.run(cmd,check=True)
def duration(p): return float(subprocess.check_output([FFPROBE,'-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)],text=True).strip())
def _scene_key(scene,event):
 payload=dict(event); payload.pop('start',None); payload.pop('end',None); payload.pop('active',None) if scene not in ('tools','example_cards') else None
 return scene+':'+hashlib.sha1(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
def render_visual(duration,events,out):
 tmp=Path(tempfile.mkdtemp(prefix='nexora_pipeline_')); visual=tmp/'visual.mp4'; cache={}
 for e in events:
  scene=e.get('scene') or e.get('type')
  if scene=='hold': scene='concept'
  key=_scene_key(scene,e)
  if key not in cache: cache[key]=render_scene(scene,e,0).convert('RGB')
 proc=subprocess.Popen([FFMPEG,'-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p',str(visual)],stdin=subprocess.PIPE)
 try:
  for fi in range(int(duration*FPS)):
   t=fi/FPS; active=[e for e in events if e['start']<=t<e['end']]
   e=active[-1] if active else ([e for e in events if e['start']<=t] or events)[-1]
   scene=e.get('scene') or e.get('type'); scene='concept' if scene=='hold' else scene; im=cache[_scene_key(scene,e)]
   proc.stdin.write(np.asarray(im,dtype=np.uint8).tobytes())
 finally:
  proc.stdin.close(); proc.wait()
 return tmp,visual
def make_sfx(duration,events,path):
 sr=48000; n=int(duration*sr); y=np.zeros(n,np.float32)
 for e in events:
  if not e.get('active'): continue
  idx=int(float(e['start'])*sr); L=int(.18*sr); u=np.arange(L)/sr; tone=(.045*np.sin(2*np.pi*880*u)+.018*np.sin(2*np.pi*1174*u))*np.exp(-24*u); end=min(n,idx+L); y[idx:end]+=tone[:end-idx]
 sf.write(path,y,sr,subtype='PCM_16')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--audio',required=True); ap.add_argument('--script',required=True); ap.add_argument('--output',required=True); ap.add_argument('--manifest'); args=ap.parse_args()
 audio=Path(args.audio); script=Path(args.script); out=Path(args.output)
 manifest=Path(args.manifest) if args.manifest else ROOT/'projects'/(audio.stem+'_alignment.json')
 if not manifest.exists():
  run([sys.executable,str(ROOT/'alignment_adapter.py'),'--audio',str(audio),'--script',str(script),'--output',str(manifest),'--model','base'])
 raw=json.loads(manifest.read_text()); directed=make_director(raw,script.read_text(encoding='utf-8')); duration=float(directed['duration']); events=directed['events']
 if not events: raise RuntimeError('No visual events available.')
 tmp,visual=render_visual(duration,events,out); sfx=tmp/'sfx.wav'; make_sfx(duration,events,sfx); music=tmp/'music.wav'
 run([FFMPEG,'-y','-loglevel','error','-f','lavfi','-i',f'aevalsrc=0.018*sin(2*PI*110*t)+0.009*sin(2*PI*164.81*t)+0.006*sin(2*PI*220*t):s=48000:d={duration}','-af',f'afade=t=in:st=0:d=1.5,afade=t=out:st={max(0,duration-1.5)}:d=1.5,loudnorm=I=-30:TP=-6:LRA=8','-ar','48000','-ac','2',str(music)])
 mix=tmp/'mix.m4a'; fc='[0:a]loudnorm=I=-11:TP=-1.2:LRA=7,acompressor=threshold=-22dB:ratio=3:attack=5:release=80:makeup=5,alimiter=limit=0.92[v];[1:a]volume=0.70[m];[2:a]volume=0.55[s];[v][m][s]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.95[a]'
 run([FFMPEG,'-y','-loglevel','error','-i',str(audio),'-i',str(music),'-i',str(sfx),'-filter_complex',fc,'-t',str(duration),'-map','[a]','-c:a','aac','-b:a','256k',str(mix)])
 out.parent.mkdir(parents=True,exist_ok=True); run([FFMPEG,'-y','-loglevel','error','-i',str(visual),'-i',str(mix),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','256k','-shortest','-movflags','+faststart',str(out)]); shutil.rmtree(tmp,ignore_errors=True); print(out)
if __name__=='__main__': main()
