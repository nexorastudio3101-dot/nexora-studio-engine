from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

# The director is intentionally deterministic and zero-cost. It converts the
# narration into a small visual story rather than assigning decorative scene types.

STOP = {
    "the","a","an","and","or","of","to","in","on","for","with","that","this",
    "is","are","be","as","we","you","your","it","they","their","from","more",
    "than","into","how","what","why","not","but","can","will","our","at","by",
    "os","aos","as","um","uma","e","ou","de","do","da","dos","das","para",
    "com","que","isto","isso","é","são","mais","como","por","não","se","no","na",
    "nos","nas","um","uma","uns","umas"
}

def clean_words(text: str) -> list[str]:
    return re.findall(r"\S+", re.sub(r"\s+", " ", text).strip())

def keywords(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-zÀ-ÿ0-9-]+", text.lower())
    out = []
    for w in raw:
        w = w.strip("-")
        if len(w) >= 4 and w not in STOP and w not in out:
            out.append(w)
    return out[:12]

def world_for(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ("ai","artificial intelligence","inteligência artificial","agent","agente","automation","automação","software","tool","tools","ferramenta")):
        return "technology"
    if any(x in t for x in ("money","money","finance","finanças","market","mercado","investment","investimento","bank","banco")):
        return "finance"
    if any(x in t for x in ("data","dados","analytics","análise","sql","database","base de dados")):
        return "data"
    if any(x in t for x in ("people","person","pessoa","human","trabalh","customer","cliente","company","empresa")):
        return "human_system"
    return "abstract_system"

def classify(text: str, index: int, total: int) -> str:
    t = text.lower()
    if index == 0:
        return "hook"
    if index == total - 1:
        return "resolution"
    if any(x in t for x in ("because","therefore","so that","causes","leads to","because","porque","por isso","faz com que","leva a","resulta")):
        return "cause_effect"
    if any(x in t for x in ("but","however","instead","versus","rather","while","mas","contudo","em vez","enquanto")):
        return "contrast"
    if any(x in t for x in ("example","for instance","imagine","case","example","por exemplo","imagina","caso")):
        return "example"
    if any(x in t for x in ("how","works","process","step","first","then","finally","como","funciona","processo","passo","primeiro","depois","finalmente")):
        return "process"
    return "concept"

def scene_role(kind: str, index: int, total: int) -> str:
    return {
        "hook":"introduce",
        "concept":"establish",
        "cause_effect":"transform",
        "contrast":"compare",
        "example":"demonstrate",
        "process":"develop",
        "resolution":"resolve",
    }.get(kind, "develop")

def make_director(manifest: dict, script_text: str = "", max_scenes: int | None = None) -> dict:
    duration = float(manifest.get("duration", 0))
    words = clean_words(script_text)
    if not words or duration <= 0:
        return {"version": 4, "director": "nexora-story-director", "duration": duration, "events": []}

    target = max(4, min(8, int(math.ceil(duration / 9.0))))
    if duration <= 18:
        target = 4
    elif duration <= 35:
        target = 5
    if max_scenes:
        target = min(target, max_scenes)
    target = min(target, len(words))

    # Split by word count, but preserve a single continuous visual world.
    chunk_size = math.ceil(len(words) / target)
    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    chunks = chunks[:target]

    events = []
    world = world_for(script_text)
    previous_keywords: list[str] = []

    for i, chunk in enumerate(chunks):
        start = duration * i / len(chunks)
        end = duration * (i + 1) / len(chunks)
        text = " ".join(chunk)
        kind = classify(text, i, len(chunks))
        kws = keywords(text)
        # Keep a few recurring concepts so the visual engine can preserve identity.
        persistent = list(dict.fromkeys(previous_keywords[:4] + kws[:6]))[:6]
        events.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "type": kind,
            "scene": "semantic_cinematic",
            "role": scene_role(kind, i, len(chunks)),
            "world": world,
            "sequence": i,
            "sequence_total": len(chunks),
            "narration": text,
            "keywords": kws,
            "persistent_concepts": persistent,
            "continuity": {
                "world": world,
                "keep_objects": True,
                "previous_scene": i - 1 if i else None,
                "next_scene": i + 1 if i < len(chunks) - 1 else None,
            },
            "camera": ["push_in","orbit","track","lateral","pull_back"][i % 5],
        })
        previous_keywords = persistent

    return {
        "version": 4,
        "director": "nexora-story-director",
        "duration": duration,
        "world": world,
        "events": events,
    }

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--alignment", required=True)
    ap.add_argument("--script")
    ap.add_argument("--output", required=True)
    ap.add_argument("--max-scenes", type=int)
    args = ap.parse_args()
    manifest = json.loads(Path(args.alignment).read_text())
    script = Path(args.script).read_text(encoding="utf-8") if args.script else ""
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(make_director(manifest, script, args.max_scenes), indent=2, ensure_ascii=False), encoding="utf-8")
    print(output)
