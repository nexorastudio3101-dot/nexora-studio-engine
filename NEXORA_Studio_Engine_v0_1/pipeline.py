from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image
import soundfile as sf

from scene_director import make_director
from scene_renderer import render_scene

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
W, H, FPS = 1920, 1080, 24
ROOT = Path(__file__).resolve().parent


def run(cmd, timeout=None):
    subprocess.run(cmd, check=True, timeout=timeout)


def duration(p):
    return float(
        subprocess.check_output(
            [
                FFPROBE, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(p)
            ],
            text=True,
        ).strip()
    )


def _escape_filter(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:")


def render_cinematic_visual(events, out_dir, visual_out):
    from cinematic_visual_engine import render_cinematic_frame

    assets_dir = out_dir / "cinematic_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    segments = []

    for i, asset in enumerate(events):
        start = float(asset["start"])
        end = float(asset["end"])
        seg_duration = max(0.25, end - start)
        seg = out_dir / f"cinematic_segment_{i:02d}.mp4"
        image_path = assets_dir / f"scene_{i:03d}.png"
        render_cinematic_frame(asset, image_path, W, H)
        title = _escape_filter(asset.get("label", "NEXORA")[:24])
        frames = max(24, int(round(seg_duration * FPS)))
        vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"zoompan=z='min(zoom+0.0007,1.055)':d={frames}:s={W}x{H}:fps={FPS},"
            f"fade=t=in:st=0:d=0.35,"
            f"fade=t=out:st={max(0, seg_duration-0.35):.3f}:d=0.35,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{title}':x=80:y=65:fontsize=22:fontcolor=white:alpha=0.72"
        )
        cmd = [
            FFMPEG,"-y","-loglevel","error","-loop","1","-i",str(image_path),
            "-t",f"{seg_duration:.3f}","-vf",vf,"-r",str(FPS),
            "-c:v","libx264","-preset","veryfast","-crf","20",
            "-pix_fmt","yuv420p",str(seg)
        ]
        run(cmd, timeout=max(90, int(seg_duration*12)))
        segments.append(seg)

    concat = out_dir / "ai_concat.txt"
    concat.write_text(
        "".join(f"file '{p.as_posix()}'\n" for p in segments),
        encoding="utf-8",
    )
    run(
        [
            FFMPEG, "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat),
            "-c", "copy", "-movflags", "+faststart", str(visual_out),
        ],
        timeout=180,
    )
    return visual_out


def make_sfx(duration_seconds, events, path):
    import numpy as np
    sr = 48000
    n = max(1, int(duration_seconds * sr))
    y = np.zeros(n, dtype=np.float32)
    for e in events:
        idx = int(float(e["start"]) * sr)
        length = min(int(0.14 * sr), n - idx)
        if length <= 0:
            continue
        u = np.arange(length, dtype=np.float32) / sr
        tone = (
            0.025 * np.sin(2 * np.pi * 880 * u)
            + 0.010 * np.sin(2 * np.pi * 1174 * u)
        ) * np.exp(-28 * u)
        y[idx:idx + length] += tone
    sf.write(path, y, sr, subtype="PCM_16")


def make_music(duration_seconds, path):
    # Very quiet harmonic bed. It is intentionally subtle so the narration
    # remains dominant and the AI visuals carry the production value.
    run(
        [
            FFMPEG, "-y", "-loglevel", "error",
            "-f", "lavfi",
            "-i",
            (
                "aevalsrc="
                "0.010*sin(2*PI*110*t)+"
                "0.006*sin(2*PI*164.81*t)+"
                "0.004*sin(2*PI*220*t):"
                f"s=48000:d={duration_seconds}"
            ),
            "-af",
            f"afade=t=in:st=0:d=1.5,afade=t=out:st={max(0, duration_seconds-1.5)}:d=1.5",
            "-ar", "48000", "-ac", "2", str(path),
        ],
        timeout=120,
    )


def mux_audio(video, audio, sfx, music, output, video_duration):
    mix = output.parent / "nexora_audio_mix.m4a"
    fc = (
        "[0:a]volume=0.95[v];"
        "[1:a]volume=0.10[s];"
        "[2:a]volume=0.08[m];"
        "[v][s][m]amix=inputs=3:duration=first:normalize=0,"
        "alimiter=limit=0.95[a]"
    )
    run(
        [
            FFMPEG, "-y", "-loglevel", "error",
            "-i", str(audio), "-i", str(sfx), "-i", str(music),
            "-filter_complex", fc,
            "-t", str(video_duration),
            "-map", "[a]", "-c:a", "aac", "-b:a", "192k", str(mix),
        ],
        timeout=180,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            FFMPEG, "-y", "-loglevel", "error",
            "-i", str(video), "-i", str(mix),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", str(output),
        ],
        timeout=240,
    )


def render_static_visual(events, visual_out):
    # Backward-compatible local fallback when AI mode is not selected.
    tmp = visual_out.parent / "static_visual"
    tmp.mkdir(parents=True, exist_ok=True)
    segments = []
    for i, e in enumerate(events):
        scene = e.get("scene") or e.get("type") or "concept"
        if scene == "hold":
            scene = "concept"
        image = render_scene(scene, e, 0).convert("RGB")
        image_path = tmp / f"scene_{i:03d}.jpg"
        image.resize((W, H), Image.Resampling.LANCZOS).save(image_path, "JPEG", quality=82)
        seg = tmp / f"seg_{i:03d}.mp4"
        d = max(0.25, float(e["end"]) - float(e["start"]))
        run([
            FFMPEG, "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(image_path), "-t", str(d),
            "-vf", f"scale={W}:{H},zoompan=z='min(zoom+0.0006,1.04)':d={max(1,int(d*FPS))}:s={W}x{H}:fps={FPS}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", str(seg),
        ], timeout=max(60, int(d*10)))
        segments.append(seg)
    concat = tmp / "concat.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments))
    run([
        FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(visual_out)
    ], timeout=180)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--manifest")
    ap.add_argument("--ai", action="store_true")
    ap.add_argument("--max-scenes", type=int)
    args = ap.parse_args()

    audio = Path(args.audio)
    script = Path(args.script)
    out = Path(args.output)
    work = Path(tempfile.mkdtemp(prefix="nexora_pipeline_"))

    try:
        manifest = Path(args.manifest) if args.manifest else work / "alignment.json"
        if not manifest.exists():
            raise RuntimeError("Alignment manifest was not supplied.")

        raw = json.loads(manifest.read_text(encoding="utf-8"))
        directed = make_director(
            raw,
            script.read_text(encoding="utf-8"),
            args.max_scenes,
        )
        events = directed["events"]
        video_duration = float(directed["duration"])
        if not events:
            raise RuntimeError("No visual events available.")

        visual = work / "visual.mp4"
        if args.ai:
            render_cinematic_visual(events, work, visual)
        else:
            render_static_visual(events, visual)

        sfx = work / "sfx.wav"
        music = work / "music.wav"
        make_sfx(video_duration, events, sfx)
        make_music(video_duration, music)
        mux_audio(visual, audio, sfx, music, out, video_duration)
        print(out, flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
