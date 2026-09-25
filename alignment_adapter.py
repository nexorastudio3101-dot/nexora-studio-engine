from __future__ import annotations
import argparse,hashlib,json,re,subprocess,ctypes,ctypes.util,tempfile,wave
from pathlib import Path
def duration(p): return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)],text=True).strip())
def sha256(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def whisper_align(audio,script,model_name='base',language='en'):
 from faster_whisper import WhisperModel
 model=WhisperModel(model_name,device='cpu',compute_type='int8')
 segments,info=model.transcribe(str(audio),language=language,word_timestamps=True,vad_filter=True)
 words=[]; segs=[]
 for s in segments:
  segs.append({'start':float(s.start),'end':float(s.end),'text':s.text.strip()})
  for w in (s.words or []): words.append({'word':w.word.strip(),'start':float(w.start),'end':float(w.end)})
 return {'version':1,'provider':'faster-whisper','language':language,'duration':duration(audio),'script_sha256':sha256(script),'segments':segs,'words':words,'events':[]}
if __name__=='__main__':
 ap=argparse.ArgumentParser(); ap.add_argument('--audio',required=True); ap.add_argument('--script',required=True); ap.add_argument('--output',required=True); ap.add_argument('--model',default='base'); ap.add_argument('--language',default='en'); a=ap.parse_args()
 m=whisper_align(Path(a.audio),Path(a.script),a.model,a.language); o=Path(a.output); o.parent.mkdir(parents=True,exist_ok=True); o.write_text(json.dumps(m,indent=2)); print(o)
