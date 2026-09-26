from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

STOP = set("""
the a an and or of to in on for with that this is are be as we you your it they their
from more than into how what why not but can will our at by
os aos as um uma e ou de do da dos das para com que isto isso é são mais como por não se no na
nos nas uns umas
""".split())

def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", re.sub(r"\s+", " ", text).strip())
    return [p.strip() for p in parts if p.strip()]

def words(text):
    return re.findall(r"[A-Za-zÀ-ÿ0-9'-]+", text)

def concepts(text):
    out=[]
    for w in words(text):
        x=w.lower().strip("'")
        if len(x)>=4 and x not in STOP and x not in out:
            out.append(x)
    return out[:10]

def has(text,*terms):
    t=text.lower()
    return any(x in t for x in terms)

def semantic_spec(text, previous=None):
    t=text.lower()
    spec={
        "subject":"concept",
        "objects":[],
        "action":"show",
        "relationship":"none",
        "state_before":None,
        "state_after":None,
        "visual_metaphor":None,
    }
    if has(t,"ai agent","ai agents","agente de ia","agentes de ia"):
        spec["subject"]="AI agent"; spec["objects"]=["AI tools"]
    if has(t,"tool","tools","ferramenta","ferramentas","app","apps","application","applications"):
        spec["objects"]=list(dict.fromkeys(spec["objects"]+["tools"]))
    if has(t,"connect","connects","connected","connecting","conecta","conectar","ligam","liga"):
        spec["action"]="connect"
        spec["relationship"]="agent connects tools"
    if has(t,"communicate","communicate","comunicar","comunicam","talk to each other"):
        spec["action"]="communicate"
        spec["relationship"]="tools communicate"
    if has(t,"switch","switching","alternating","alternar","mudar entre","trocar entre"):
        spec["action"]="switch"
        spec["relationship"]="person moves between tools"
    if has(t,"decide","decides","decision","decisão","decidir","next step","próximo passo"):
        spec["action"]="decide"
        spec["relationship"]="agent chooses next step"
    if has(t,"automate","automation","automatically","automatiza","automático","automaticamente"):
        spec["action"]="automate"
        spec["relationship"]="system executes next step automatically"
    if has(t,"person","people","human","pessoa","pessoas","user","utilizador","utilizadora"):
        spec["subject"]="person"
    if has(t,"don't communicate","do not communicate","não comunicam","isolated","separate","separadas","isoladas"):
        spec["state_before"]="tools isolated"
    if has(t,"connect","connected","conectadas","ligadas"):
        spec["state_after"]="tools connected"
    if has(t,"instead of","rather than","em vez de"):
        spec["visual_metaphor"]="before_after"
    if has(t,"because","therefore","so","because","porque","por isso","faz com que","leva a","resulta"):
        spec["visual_metaphor"]="cause_effect"
    if spec["subject"]=="concept" and spec["objects"]:
        spec["subject"]=spec["objects"][0]
    if previous and spec["subject"]=="concept":
        spec["subject"]=previous.get("subject","concept")
    return spec

def split_story(text,duration,max_scenes):
    ss=sentences(text)
    if not ss: return []
    n=min(max_scenes,max(1,len(ss)))
    if len(ss)>n:
        # Merge adjacent sentences so a scene contains a complete idea.
        groups=[[] for _ in range(n)]
        for i,s in enumerate(ss):
            groups[min(n-1, i*n//len(ss))].append(s)
        ss=[" ".join(g) for g in groups if g]
    out=[]
    total=len(ss)
    for i,s in enumerate(ss):
        out.append((duration*i/total,duration*(i+1)/total,s))
    return out

def make_director(manifest,script_text="",max_scenes=None):
    duration=float(manifest.get("duration",0))
    if not script_text.strip() or duration<=0:
        return {"version":5,"director":"nexora-semantic-story-director","duration":duration,"events":[]}
    max_scenes=max_scenes or 8
    chunks=split_story(script_text,duration,max_scenes)
    events=[]; previous=None
    for i,(start,end,text) in enumerate(chunks):
        spec=semantic_spec(text,previous)
        # If the sentence contains a concrete entity, keep it alive in later scenes.
        persistent=list(dict.fromkeys((previous or {}).get("concepts",[])+concepts(text)))[:8]
        role="opening" if i==0 else ("closing" if i==len(chunks)-1 else "development")
        events.append({
            "start":round(start,3),"end":round(end,3),
            "type":"semantic",
            "scene":"meaning_driven",
            "role":role,
            "sequence":i,"sequence_total":len(chunks),
            "narration":text,
            "concepts":concepts(text),
            "persistent_concepts":persistent,
            "semantic":spec,
            "continuity":{"keep_objects":True,"previous_scene":i-1 if i else None,"next_scene":i+1 if i<len(chunks)-1 else None},
        })
        previous={"subject":spec["subject"],"concepts":persistent}
    return {"version":5,"director":"nexora-semantic-story-director","duration":duration,"events":events}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--alignment",required=True); ap.add_argument("--script"); ap.add_argument("--output",required=True); ap.add_argument("--max-scenes",type=int)
    args=ap.parse_args()
    manifest=json.loads(Path(args.alignment).read_text())
    script=Path(args.script).read_text(encoding="utf-8") if args.script else ""
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(make_director(manifest,script,args.max_scenes),indent=2,ensure_ascii=False),encoding="utf-8")
    print(out)
