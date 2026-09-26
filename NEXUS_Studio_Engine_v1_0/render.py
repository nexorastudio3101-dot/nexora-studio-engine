from __future__ import annotations
import json, shutil, subprocess, tempfile
from pathlib import Path

FFMPEG="ffmpeg"
W,H,FPS=1280,720,24

def run(cmd, timeout):
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    if r.returncode:
        raise RuntimeError(r.stderr[-4000:] or r.stdout[-4000:] or "FFmpeg failed.")

def _motion_filter(duration: float, mode: str):
    frames=max(1,int(duration*FPS))
    mode=(mode or "").lower()
    if "pan" in mode or "move" in mode:
        z="min(zoom+0.0007,1.06)"
    elif "zoom out" in mode:
        z="max(zoom-0.00045,1.0)"
    else:
        z="min(zoom+0.00025,1.025)"
    return (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={W}x{H}:fps={FPS},"
        f"fade=t=in:st=0:d=.22,"
        f"fade=t=out:st={max(0,duration-.22):.3f}:d=.22"
    )

def render_video(events, audio: Path, images: list[Path], output: Path, duration: float):
    work=Path(tempfile.mkdtemp(prefix="nexus_render_"))
    segments=[]
    try:
        for i,(event,image) in enumerate(zip(events,images)):
            d=max(.25,float(event["end"])-float(event["start"]))
            seg=work/f"scene_{i:02d}.mp4"
            run([
                FFMPEG,"-y","-loglevel","error","-loop","1","-i",str(image),
                "-t",f"{d:.3f}","-vf",_motion_filter(d,event.get("motion","")),
                "-c:v","libx264","-preset","ultrafast","-crf","22",
                "-pix_fmt","yuv420p","-an",str(seg)
            ],max(60,int(d*8)+30))
            segments.append(seg)

        concat=work/"concat.txt"
        concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments),encoding="utf-8")
        visual=work/"visual.mp4"
        run([FFMPEG,"-y","-loglevel","error","-f","concat","-safe","0","-i",str(concat),
             "-c","copy","-movflags","+faststart",str(visual)],180)

        output.parent.mkdir(parents=True,exist_ok=True)
        run([FFMPEG,"-y","-loglevel","error","-i",str(visual),"-i",str(audio),
             "-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","192k",
             "-shortest","-movflags","+faststart",str(output)],240)
        return output
    finally:
        shutil.rmtree(work,ignore_errors=True)
