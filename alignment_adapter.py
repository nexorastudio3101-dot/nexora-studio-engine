from __future__ import annotations
import argparse,json,re,subprocess,hashlib
from pathlib import Path

def duration(p):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(p)],text=True).strip())

def sha256(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def align(audio,script):
    d=duration(audio)
    text=Path(script).read_text(encoding="utf-8")
    tokens=re.findall(r"\S+",text)
    words=[]
    if tokens:
        step=d/len(tokens)
        for i,w in enumerate(tokens):
            start=i*step; end=d if i==len(tokens)-1 else (i+1)*step
            words.append({"word":w.strip(),"start":round(start,3),"end":round(end,3)})
    segments=[]
    if words:
        chunk=max(1,len(words)//12)
        for i in range(0,len(words),chunk):
            part=words[i:i+chunk]
            segments.append({"start":part[0]["start"],"end":part[-1]["end"],"text":" ".join(x["word"] for x in part)})
    return {"version":2,"provider":"deterministic-script-timing","language":"en","duration":d,"script_sha256":sha256(script),"segments":segments,"words":words,"events":[]}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--audio",required=True); ap.add_argument("--script",required=True); ap.add_argument("--output",required=True)
    ap.add_argument("--model",default="tiny"); ap.add_argument("--language",default="en")
    a=ap.parse_args()
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(align(a.audio,a.script),indent=2),encoding="utf-8")
    print(out)
