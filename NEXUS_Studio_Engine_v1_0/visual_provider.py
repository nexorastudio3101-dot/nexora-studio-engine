from __future__ import annotations
import base64, os, time
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except Exception:
    genai=None
    types=None

MODEL=os.getenv("NEXUS_IMAGE_MODEL","gemini-3.1-flash-image")

def generate_image(prompt: str, output: Path, continuity: str = ""):
    key=os.getenv("GEMINI_API_KEY")
    if not key or genai is None:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add a Gemini API key in Render to enable AI visual generation."
        )

    client=genai.Client(api_key=key)
    full_prompt=f"""Create a single 16:9 cinematic educational visual for a professional YouTube explainer.

The image must communicate the subject below literally and clearly. Do not make an abstract
technology wallpaper. Do not add random circles, nodes, glowing dots, decorative network
lines, fake UI, or meaningless symbols. Use concrete people, objects, environments, interfaces,
diagrams or physical processes when they are appropriate.

Visual direction:
- premium documentary / modern editorial quality
- sophisticated lighting and depth
- clean composition with one clear visual idea
- realistic or highly polished cinematic illustration depending on the subject
- leave safe negative space for optional captions
- no watermark-like branding
- no unnecessary written words

Scene description:
{prompt}

Continuity requirement:
{continuity}
"""
    last_error=None
    for attempt in range(4):
        try:
            response=client.models.generate_content(
                model=MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    response_format={"image":{"aspect_ratio":"16:9","image_size":"1K"}},
                ),
            )
            for part in response.parts:
                if getattr(part,"inline_data",None) is not None:
                    data=part.inline_data.data
                    output.write_bytes(data if isinstance(data,bytes) else base64.b64decode(data))
                    return output
            raise RuntimeError("The image model returned no image data.")
        except Exception as exc:
            last_error=exc
            message=str(exc).upper()
            transient=("503" in message or "UNAVAILABLE" in message or "SERVICE UNAVAILABLE" in message)
            if not transient or attempt==3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Image generation failed: {last_error}")
