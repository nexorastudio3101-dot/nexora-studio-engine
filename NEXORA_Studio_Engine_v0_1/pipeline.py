from __future__ import annotations

import argparse
import json
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

# Cloud-safe render profile: 720p keeps the cinematic composition while
# avoiding the CPU-heavy 1080p/24fps encode that can stall a free instance.
W, H, FPS = 1280, 720, 24


def run(cmd, timeout=None):
    subprocess.run(cmd, check=True, timeout=timeout)


def _escape_filter(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:")


def render_cinematic_visual(events, out_dir, visual_out):
    from cinematic_visual_engine import render_cinematic_frame

    assets_dir = out_dir / "cinematic_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    segments = []

    for i, asset in enumerate(events):
        seg_duration = max(0.25, float(asset["end"]) - float(asset["start"]))
        seg = out_dir / f"cinematic_segment_{i:02d}.mp4"
        image_path = assets_dir / f"scene_{i:03d}.png"

        # Generate one polished keyframe per directed scene.
        render_cinematic_frame(asset, image_path, W, H)

        frames = max(24, int(round(seg_duration * FPS)))

        # The visual engine owns meaning and composition. Do not inject
        # decorative labels, branding or artificial zooms at the video layer.
        vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"zoompan=z='1.0':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={W}x{H}:fps={FPS},"
            f"fade=t=in:st=0:d=0.25,"
            f"fade=t=out:st={max(0, seg_duration-0.25):.3f}:d=0.25"
        )

        cmd = [
            FFMPEG, "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(image_path),
            "-t", f"{seg_duration:.3f}",
            "-vf", vf,
            "-r", str(FPS),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
            str(seg),
        ]

        # Keep each scene bounded, but give short cloud renders enough time.
        run(cmd, timeout=max(60, int(seg_duration * 8)))
        segments.append(seg)

    if not segments:
        raise RuntimeError("Cinematic renderer produced no scene segments.")

    concat = out_dir / "cinematic_concat.txt"
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
        timeout=120,
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
    tmp = visual_out.parent / "static_visual"
    tmp.mkdir(parents=True, exist_ok=True)
    segments = []

    for i, e in enumerate(events):
        scene = e.get("scene") or e.get("type") or "concept"
        if scene == "hold":
            scene = "concept"

        image = render_scene(scene, e, 0).convert("RGB")
        image_path = tmp / f"scene_{i:03d}.jpg"
        image.resize((W, H), Image.Resampling.LANCZOS).save(
            image_path, "JPEG", quality=82
        )

        seg = tmp / f"seg_{i:03d}.mp4"
        d = max(0.25, float(e["end"]) - float(e["start"]))

        run([
            FFMPEG, "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(image_path), "-t", str(d),
            "-vf",
            f"scale={W}:{H},zoompan=z='min(zoom+0.0006,1.04)':"
            f"d={max(1,int(d*FPS))}:s={W}x{H}:fps={FPS}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", str(seg),
        ], timeout=max(60, int(d*8)))
        segments.append(seg)

    concat = tmp / "concat.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments))
    run([
        FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-c", "copy", "-movflags", "+faststart",
        str(visual_out)
    ], timeout=120)


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
