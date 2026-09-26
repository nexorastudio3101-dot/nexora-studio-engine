from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

API = "https://api.dev.runwayml.com/v1"
VERSION = "2024-11-06"


class RunwayError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.environ.get("RUNWAYML_API_SECRET"))


def _request(method: str, path: str, payload: Optional[dict] = None) -> dict:
    key = os.environ.get("RUNWAYML_API_SECRET")
    if not key:
        raise RunwayError(
            "AI Visual Mode requires the RUNWAYML_API_SECRET environment variable."
        )

    data = None
    headers = {
        "Authorization": f"Bearer {key}",
        "X-Runway-Version": VERSION,
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{API}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RunwayError(f"Runway API {exc.code}: {detail[:1200]}") from exc
    except urllib.error.URLError as exc:
        raise RunwayError(f"Could not reach Runway API: {exc}") from exc


def _wait(task_id: str, timeout: int = 900) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = _request("GET", f"/tasks/{task_id}")
        status = task.get("status")
        if status == "SUCCEEDED":
            output = task.get("output") or []
            if not output:
                raise RunwayError("Runway task succeeded without an output asset.")
            return task
        if status in {"FAILED", "CANCELED"}:
            code = task.get("failureCode") or "UNKNOWN"
            detail = task.get("failure") or task.get("failureMessage") or ""
            raise RunwayError(f"Runway task {status}: {code} {detail}".strip())
        time.sleep(5)
    raise RunwayError(f"Runway task {task_id} timed out after {timeout}s.")


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "NEXORA-Studio/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            destination.write_bytes(response.read())
    except urllib.error.URLError as exc:
        raise RunwayError(f"Could not download generated asset: {exc}") from exc


def generate_image(prompt: str, destination: Path) -> str:
    task = _request(
        "POST",
        "/text_to_image",
        {
            "model": os.environ.get("NEXORA_IMAGE_MODEL", "gen4_image"),
            "ratio": "1920:1080",
            "promptText": prompt,
        },
    )
    done = _wait(task["id"])
    url = done["output"][0]
    _download(url, destination)
    return url


def generate_video_from_image(
    image_url: str,
    motion_prompt: str,
    destination: Path,
    duration: int = 5,
) -> str:
    task = _request(
        "POST",
        "/image_to_video",
        {
            "model": os.environ.get("NEXORA_VIDEO_MODEL", "gen4.5"),
            "promptImage": image_url,
            "promptText": motion_prompt,
            "ratio": "1280:720",
            "duration": duration,
        },
    )
    done = _wait(task["id"], timeout=1200)
    url = done["output"][0]
    _download(url, destination)
    return url


def build_ai_assets(
    events: list[dict],
    output_dir: Path,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> list[dict]:
    if not configured():
        raise RunwayError("RUNWAYML_API_SECRET is not configured.")

    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(events)
    result = []

    for index, event in enumerate(events):
        scene_dir = output_dir / f"scene_{index:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        image_path = scene_dir / "image.jpg"
        if progress:
            progress(index, total, f"Generating AI image {index + 1}/{total}…")
        image_url = generate_image(event["visual_prompt"], image_path)

        item = {
            **event,
            "asset_type": "image",
            "image_path": str(image_path),
            "image_url": image_url,
        }

        if event.get("use_video"):
            video_path = scene_dir / "video.mp4"
            if progress:
                progress(index, total, f"Animating scene {index + 1}/{total}…")
            video_url = generate_video_from_image(
                image_url,
                event["motion_prompt"],
                video_path,
                duration=5,
            )
            item["asset_type"] = "video"
            item["video_path"] = str(video_path)
            item["video_url"] = video_url

        result.append(item)

    return result
