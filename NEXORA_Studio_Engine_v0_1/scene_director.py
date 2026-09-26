from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


STYLE = (
    "NEXORA Studio visual language: premium cinematic educational documentary, "
    "dark graphite and deep blue environment, restrained electric-lime accents, "
    "high-end editorial composition, realistic materials, volumetric light, "
    "subtle futuristic technology, sophisticated, clean, intelligent, "
    "photorealistic where appropriate, no cheap stock-photo look, no UI screenshot, "
    "no readable text, no captions, no logos, no watermark, 16:9."
)


def clean_words(text: str) -> list[str]:
    return re.findall(r"\S+", re.sub(r"\s+", " ", text).strip())


def classify(text: str, index: int, total: int) -> str:
    t = text.lower()
    if index == 0:
        return "hook"
    if index == total - 1:
        return "takeaway"
    if any(x in t for x in ("because", "how", "works", "mechanism", "process")):
        return "mechanism"
    if any(x in t for x in ("example", "for instance", "imagine", "case")):
        return "example"
    if any(x in t for x in ("but", "however", "instead", "versus", "rather")):
        return "contrast"
    return "context"


def visual_prompt(scene_type: str, text: str) -> str:
    core = text[:650]
    directions = {
        "hook": (
            "Create a striking opening metaphor for the idea in the narration. "
            "One dominant subject, dramatic depth, immediate visual curiosity."
        ),
        "context": (
            "Visualize the central concept as a concrete real-world scene or metaphor. "
            "Make the idea understandable without words."
        ),
        "mechanism": (
            "Show the underlying mechanism as a cinematic physical system: connected "
            "objects, flows, cause and effect, or layered processes. Make relationships "
            "visually obvious."
        ),
        "example": (
            "Turn the example into a believable cinematic scene with specific objects "
            "and actions. Prefer a human-scale situation over abstract decoration."
        ),
        "contrast": (
            "Create a visual contrast between two states or approaches in one coherent "
            "composition. Make the difference instantly legible through lighting, "
            "composition, scale, or action."
        ),
        "takeaway": (
            "End with a confident, memorable visual metaphor that communicates the "
            "main takeaway and feels like the closing shot of a premium documentary."
        ),
    }
    return f"{STYLE} {directions[scene_type]} Narration meaning: {core}"


def motion_prompt(scene_type: str, text: str) -> str:
    actions = {
        "hook": "Slow cinematic push-in with subtle environmental motion; reveal the subject gradually.",
        "context": "Controlled camera dolly through the scene, subtle parallax and natural environmental movement.",
        "mechanism": "Camera tracks the flow of the system as elements connect and react; elegant purposeful motion.",
        "example": "Natural human or object movement with a gentle handheld-documentary camera feel.",
        "contrast": "Slow lateral camera move revealing the contrast, with restrained motion on both sides.",
        "takeaway": "Slow pull-back with a subtle rise, leaving a strong final composition.",
    }
    return f"{actions[scene_type]} No text appears on screen."


def make_director(manifest: dict, script_text: str = "", max_scenes: int | None = None) -> dict:
    duration = float(manifest.get("duration", 0))
    words = clean_words(script_text)
    if not words or duration <= 0:
        return {"version": 3, "director": "nexora-ai-story-director", "duration": duration, "events": []}

    # The proof-of-concept deliberately targets short, meaningful shots rather than
    # dozens of tiny cuts. Longer videos can raise NEXORA_AI_MAX_SCENES later.
    target = max(5, min(8, int(math.ceil(duration / 10.0))))
    if duration <= 35:
        target = 5
    if max_scenes:
        target = min(target, max_scenes)
    target = min(target, len(words))

    chunk_size = math.ceil(len(words) / target)
    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    chunks = chunks[:target]

    events = []
    for i, chunk in enumerate(chunks):
        start = duration * i / len(chunks)
        end = duration * (i + 1) / len(chunks)
        text = " ".join(chunk)
        kind = classify(text, i, len(chunks))
        events.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "type": kind,
                "scene": "ai_cinematic",
                "label": kind.upper(),
                "narration": text,
                "visual_prompt": visual_prompt(kind, text),
                "motion_prompt": motion_prompt(kind, text),
                # Two animated hero shots in the proof-of-concept. This keeps
                # cost and generation time controlled while every scene remains AI-made.
                "use_video": i in {0, min(3, len(chunks) - 1)},
            }
        )

    return {
        "version": 3,
        "director": "nexora-ai-story-director",
        "duration": duration,
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
    output.write_text(
        json.dumps(
            make_director(manifest, script, args.max_scenes),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(output)
