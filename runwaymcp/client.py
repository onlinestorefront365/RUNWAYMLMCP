"""Thin client for the Runway REST API."""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

BASE_URL = "https://api.dev.runwayml.com/v1"
API_VERSION = "2024-11-06"

# kind -> (endpoint, default params). Any param can be overridden per step.
KINDS: dict[str, tuple[str, dict]] = {
    "text_to_image": ("/text_to_image", {"model": "gen4_image", "ratio": "1920:1080"}),
    "image_to_video": ("/image_to_video", {"model": "gen4_turbo", "ratio": "1280:720", "duration": 5}),
    "text_to_video": ("/text_to_video", {"model": "veo3.1_fast", "ratio": "1280:720", "duration": 8}),
    "video_to_video": ("/video_to_video", {"model": "gen4_aleph", "ratio": "1280:720"}),
    "video_upscale": ("/video_upscale", {"model": "upscale_v1"}),
    "character_performance": ("/character_performance", {"model": "act_two", "ratio": "1280:720"}),
}

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}


class RunwayError(RuntimeError):
    pass


class RunwayClient:
    def __init__(self, api_key: str | None = None, *, transport: httpx.BaseTransport | None = None,
                 poll_interval: float = 5.0):
        key = api_key or os.environ.get("RUNWAYML_API_SECRET") or os.environ.get("RUNWAY_API_KEY")
        if not key:
            raise RunwayError("Set RUNWAYML_API_SECRET (get a key at dev.runwayml.com)")
        self.poll_interval = poll_interval
        self.http = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {key}", "X-Runway-Version": API_VERSION},
            timeout=60,
            transport=transport,
        )

    def _check(self, r: httpx.Response) -> dict:
        if r.status_code >= 400:
            raise RunwayError(f"Runway API {r.status_code}: {r.text[:500]}")
        return r.json()

    def submit(self, kind: str, params: dict) -> str:
        if kind not in KINDS:
            raise RunwayError(f"Unknown step type '{kind}'. Valid: {', '.join(KINDS)}")
        endpoint, defaults = KINDS[kind]
        return self._check(self.http.post(endpoint, json={**defaults, **params}))["id"]

    def task(self, task_id: str) -> dict:
        return self._check(self.http.get(f"/tasks/{task_id}"))

    def cancel(self, task_id: str) -> None:
        r = self.http.delete(f"/tasks/{task_id}")
        if r.status_code >= 400:
            raise RunwayError(f"Cancel failed {r.status_code}: {r.text[:200]}")

    def wait(self, task_id: str, timeout: float = 900, on_update=None) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            t = self.task(task_id)
            if on_update:
                on_update(t)
            if t["status"] in TERMINAL:
                if t["status"] != "SUCCEEDED":
                    raise RunwayError(f"Task {task_id} {t['status']}: {t.get('failure', '')}")
                return t
            if time.monotonic() > deadline:
                raise RunwayError(f"Task {task_id} timed out")
            time.sleep(self.poll_interval)

    def run(self, kind: str, params: dict, **kw) -> dict:
        return self.wait(self.submit(kind, params), **kw)

    def upload_data_uri(self, path: str) -> str:
        """Local files are sent inline as data URIs (images)."""
        import base64, mimetypes
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()

    def download(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return dest
