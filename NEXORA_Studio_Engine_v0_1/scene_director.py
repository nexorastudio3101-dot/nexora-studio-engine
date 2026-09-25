from __future__ import annotations
import argparse,json,re
from pathlib import Path
def norm(s): return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9'?-]"," ",s.lower())).strip()
def make_director(manifest,script_text=""):
 duration=float(manifest.get("duration",0)); events=[{"start":0,"end":duration,"type":"hold","scene":"concept"}]; text=norm(script_text)
 cues=[("question",["what is","what are","how does","why does","why is"],"WHAT EXACTLY IS","THE CONCEPT?"),("definition",["is defined as","means that","refers to"],"DEFINITION",""),("process",["first","then","finally","step one","step two"],"PROCESS",""),("comparison",["versus","vs","compared to","rather than"],"COMPARISON",""),("takeaway",["the key","the takeaway","in short"],"KEY TAKEAWAY","")]
 for scene,phrases,title,subtitle in cues:
  for p in phrases:
   m=re.search(r"\b"+re.escape(p)+r"\b",text)
   if m:
    t=min(duration,max(0,m.start()/max(1,len(text))*duration)); e={"start":max(0,t-.5),"end":min(duration,t+3),"type":scene,"scene":scene,"title":title}
    if subtitle:e["subtitle"]=subtitle
    events.append(e); break
 priority={"question":10,"definition":8,"process":7,"comparison":7,"takeaway":8,"hold":0}; points=sorted({0,duration,*[float(e["start"]) for e in events],*[float(e["end"]) for e in events]}); timeline=[]
 for a,b in zip(points,points[1:]):
  active=[e for e in events if e["start"]<=a and e["end"]>=b]
  if active:
   e=max(active,key=lambda x:priority.get(x["type"],0)); timeline.append({**e,"start":round(a,3),"end":round(b,3)})
 return {"version":2,"director":"cloud-rule-based","duration":duration,"events":timeline}
if __name__=="__main__":
 ap=argparse.ArgumentParser(); ap.add_argument("--alignment",required=True); ap.add_argument("--script"); ap.add_argument("--output",required=True); a=ap.parse_args()
 m=json.loads(Path(a.alignment).read_text()); s=Path(a.script).read_text() if a.script else ""; o=Path(a.output); o.parent.mkdir(parents=True,exist_ok=True); o.write_text(json.dumps(make_director(m,s),indent=2)); print(o)
