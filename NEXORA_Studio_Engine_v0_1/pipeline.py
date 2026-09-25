from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import hashlib
from pathlib import Path

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

from PIL import Image
import soundfile as sf

from scene_renderer import render_scene
from scene_director import make_director

W, H, FPS = 1280, 720, 10
ROOT = Path(__file__).resolve().parent


def run(cmd, timeout=None):
    subprocess.run(cmd, check=True, timeout=timeout)


def duration(p):
    return float(
        subprocess.check_output(
            [
                FFPROBE,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(p),
            ],
            text=True,
        ).strip()
    )


def _scene_key(scene, event):
    payload = dict(event)
    payload.pop("start", None)
    payload.pop("end", None)
    if scene not in ("tools", "example_cards"):
        payload.pop("active", None)
    return scene + ":" + hashlib.sha1(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def render_visual(duration, events, out):
    """
    Fast cloud renderer.

    The previous implementation pushed every 1920x1080 frame from Python
    into ffmpeg. For a five-minute video that means thousands of large frames
    crossing the Python/ffmpeg pipe and can look completely frozen on a
    low-CPU cloud instance.

    NEXORA scenes are currently static images, so render each distinct scene
    once, create short ffmpeg video segments, then concatenate them. This
    removes the per-frame Python loop entirely.
    """
    tmp = Path(tempfile.mkdtemp(prefix="nexora_pipeline_"))
    visual = tmp / "visual.mp4"
    cache = {}
    image_paths = {}
    segment_paths = []

    try:
        # Render each distinct visual only once.
        for e in events:
            scene = e.get("scene") or e.get("type")
            if scene == "hold":
                scene = "concept"
            key = _scene_key(scene, e)
            if key not in cache:
                cache[key] = render_scene(scene, e, 0).convert("RGB")
                image_path = tmp / f"scene_{len(image_paths):03d}.jpg"
                cache[key].resize((W, H), Image.Resampling.LANCZOS).save(image_path, format="JPEG", quality=88, optimize=True)
                image_paths[key] = image_path

        # Merge adjacent timeline entries that use exactly the same visual.
        groups = []
        for e in events:
            scene = e.get("scene") or e.get("type")
            if scene == "hold":
                scene = "concept"
            key = _scene_key(scene, e)
            start = float(e["start"])
            end = float(e["end"])
            if end <= start:
                continue

            if groups and groups[-1]["key"] == key and abs(groups[-1]["end"] - start) < 0.01:
                groups[-1]["end"] = end
            else:
                groups.append({"key": key, "start": start, "end": end})

        if not groups:
            raise RuntimeError("No visual segments available.")

        # Encode each static scene once. ultrafast is deliberate: this is a
        # cloud generation service, not an offline quality benchmark.
        for i, g in enumerate(groups):
            seg = tmp / f"segment_{i:03d}.mp4"
            seg_duration = max(0.05, g["end"] - g["start"])
            run(
                [
                    FFMPEG,
                    "-y",
                    "-loglevel",
                    "error",
                    "-loop",
                    "1",
                    "-i",
                    str(image_paths[g["key"]]),
                    "-t",
                    f"{seg_duration:.3f}",
                    "-r",
                    str(FPS),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-tune",
                    "stillimage",
                    "-crf",
                    "28",
                    "-pix_fmt",
                    "yuv420p",
                    str(seg),
                ],
                timeout=45,
            )
            segment_paths.append(seg)

        concat = tmp / "concat.txt"
        concat.write_text(
            "".join(f"file '{p.as_posix()}'\n" for p in segment_paths),
            encoding="utf-8",
        )

        run(
            [
                FFMPEG,
                "-y",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(visual),
            ],
            timeout=90,
        )

        return tmp, visual
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def make_sfx(duration, events, path):
    sr = 48000
    n = int(duration * sr)
    y = [0.0] * n

    # Tiny deterministic SFX layer. Keep it lightweight for cloud execution.
    import math

    for e in events:
        if not e.get("active"):
            continue
        idx = int(float(e["start"]) * sr)
        length = min(int(0.18 * sr), n - idx)
        if length <= 0:
            continue
        for j in range(length):
            u = j / sr
            y[idx + j] += (
                0.045 * math.sin(2 * math.pi * 880 * u)
                + 0.018 * math.sin(2 * math.pi * 1174 * u)
            ) * math.exp(-24 * u)

    # soundfile accepts a list for mono PCM.
    import numpy as np
    sf.write(path, np.asarray(y, dtype=np.float32), sr, subtype="PCM_16")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--manifest")
    args = ap.parse_args()

    audio = Path(args.audio)
    script = Path(args.script)
    out = Path(args.output)

    manifest = (
        Path(args.manifest)
        if args.manifest
        else ROOT / "projects" / (audio.stem + "_alignment.json")
    )

    if not manifest.exists():
        run(
            [
                sys.executable,
                str(ROOT / "alignment_adapter.py"),
                "--audio",
                str(audio),
                "--script",
                str(script),
                "--output",
                str(manifest),
                "--model",
                "base",
            ],
            timeout=120,
        )

    raw = json.loads(manifest.read_text())
    directed = make_director(raw, script.read_text(encoding="utf-8"))
    video_duration = float(directed["duration"])
    events = directed["events"]

    if not events:
        raise RuntimeError("No visual events available.")

    tmp, visual = render_visual(video_duration, events, out)
    try:
        sfx = tmp / "sfx.wav"
        make_sfx(video_duration, events, sfx)

        music = tmp / "music.wav"
        run(
            [
                FFMPEG,
                "-y",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"aevalsrc=0.018*sin(2*PI*110*t)+0.009*sin(2*PI*164.81*t)+0.006*sin(2*PI*220*t):s=48000:d={video_duration}",
                "-af",
                f"afade=t=in:st=0:d=1.5,afade=t=out:st={max(0, video_duration-1.5)}:d=1.5,loudnorm=I=-30:TP=-6:LRA=8",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(music),
            ],
            timeout=300,
        )

        mix = tmp / "mix.m4a"
        fc = (
            "[0:a]loudnorm=I=-11:TP=-1.2:LRA=7,"
            "acompressor=threshold=-22dB:ratio=3:attack=5:release=80:makeup=5,"
            "alimiter=limit=0.92[v];"
            "[1:a]volume=0.70[m];"
            "[2:a]volume=0.55[s];"
            "[v][m][s]amix=inputs=3:duration=first:normalize=0,"
            "alimiter=limit=0.95[a]"
        )
        run(
            [
                FFMPEG,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(audio),
                "-i",
                str(music),
                "-i",
                str(sfx),
                "-filter_complex",
                fc,
                "-t",
                str(video_duration),
                "-map",
                "[a]",
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                str(mix),
            ],
            timeout=600,
        )

        out.parent.mkdir(parents=True, exist_ok=True)
        run(
            [
                FFMPEG,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(visual),
                "-i",
                str(mix),
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(out),
            ],
            timeout=600,
        )
        print(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
