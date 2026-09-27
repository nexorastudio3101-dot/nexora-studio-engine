from __future__ import annotations
import json, os, re

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

MODEL = os.getenv("NEXUS_TEXT_MODEL", "gemini-3.8-flash")

SYSTEM = """You are the NEXORA Studio Engine AI Director.
Turn educational narration into a coherent visual storyboard.
Never invent generic circles, nodes, particles or abstract tech graphics unless the narration genuinely requires them.
For every scene decide what the viewer should SEE to understand the narration.
Prefer concrete subjects, objects, environments, actions, comparisons, processes, interfaces, people, diagrams and meaningful visual metaphors.
Maintain continuity between scenes.
Output valid JSON only.
Create 4 to 5 scenes for a short prototype.
Each scene contains: id, start, end, narration, purpose, visual_concept, visual_prompt, composition, motion, continuity, transition.
visual_prompt must describe the actual content of the frame, not just its style. 16:9, cinematic, educational, polished, visually specific. Avoid visible text unless essential.
"""

def _fallback(script: str, duration: float) -> dict:
    sentences=[s.strip() for s in re.split(r"(?<=[.!?])\s+",script) if s.strip()] or [script.strip()]
    n=max(1,min(5,len(sentences)))
    chunk=duration/n
    events=[]
    for i in range(n):
        text=sentences[i] if i<len(sentences) else sentences[-1]
        events.append({
            "id":i+1,"start":round(i*chunk,2),"end":round((i+1)*chunk,2),
            "narration":text,"purpose":"Explain the idea clearly",
            "visual_concept":"A concrete visual representation of the sentence",
            "visual_prompt":f"Create a concrete cinematic educational scene that directly illustrates: {text}. Use real objects, people or a clear diagram when appropriate. 16:9, premium documentary quality, no random abstract graphics.",
            "composition":"Clear focal subject with supporting elements",
            "motion":"Subtle cinematic camera movement",
            "continuity":"Preserve important subjects and environment from previous scenes",
            "transition":"Clean cinematic cut"
        })
    return {"duration":duration,"events":events}

def make_storyboard(script: str, duration: float) -> dict:
    key=os.getenv("GEMINI_API_KEY")
    if not key or genai is None:
        return _fallback(script,duration)
    client=genai.Client(api_key=key)
    prompt=f"""{SYSTEM}

Narration:
{script}

Audio duration: {duration:.2f} seconds.

Create the storyboard now. Keep all timings inside the audio duration.
Return JSON with duration, global_visual_style, visual_continuity and events.
"""
    response=client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.35,
            max_output_tokens=5000,
        ),
    )
    data=json.loads(response.text)
    data["duration"]=duration
    events=[]
    for e in data.get("events",[]):
        if not isinstance(e,dict): continue
        e["start"]=max(0.0,float(e.get("start",0)))
        e["end"]=min(duration,float(e.get("end",duration)))
        if e["end"]>e["start"]: events.append(e)
    data["events"]=events or _fallback(script,duration)["events"]
    return data
