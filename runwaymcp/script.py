"""Text scripts: a YAML/JSON list of steps, run in order, with output chaining.

    name: demo
    steps:
      - id: still
        type: text_to_image
        promptText: "a lighthouse at dusk"
      - id: clip
        type: image_to_video
        promptImage: "{{still.output}}"     # URL of step 'still' (first output)
        promptText: "waves crash, camera pushes in"
        duration: 5

Placeholders: {{id.output}} (first URL), {{id.outputs}} (list), {{id.task}} (task id).
A value starting with '@' (e.g. "@photo.png") is inlined as a data URI.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .client import KINDS, RunwayClient, RunwayError

_PH = re.compile(r"\{\{\s*([\w-]+)\.(output|outputs|task)\s*\}\}")


def load(path_or_text: str, *, is_text: bool = False) -> dict:
    text = path_or_text if is_text else Path(path_or_text).read_text()
    data = yaml.safe_load(text)  # YAML is a superset of JSON
    return validate(data)


def validate(data) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list) or not data["steps"]:
        raise RunwayError("Script must be a mapping with a non-empty 'steps' list")
    seen = set()
    for i, s in enumerate(data["steps"]):
        if not isinstance(s, dict) or s.get("type") not in KINDS:
            raise RunwayError(f"Step {i+1}: 'type' must be one of {', '.join(KINDS)}")
        sid = s.get("id") or f"step{i+1}"
        s["id"] = sid
        if sid in seen:
            raise RunwayError(f"Duplicate step id '{sid}'")
        for ref in _PH.findall(json.dumps(s)):
            if ref[0] not in seen:
                raise RunwayError(f"Step '{sid}' references '{ref[0]}' which is not an earlier step")
        seen.add(sid)
    return data


def _resolve(value, results: dict, client: RunwayClient):
    if isinstance(value, str):
        m = _PH.fullmatch(value.strip())
        if m:
            r = results[m.group(1)]
            return {"output": r["output"][0], "outputs": r["output"], "task": r["id"]}[m.group(2)]
        value = _PH.sub(lambda m: str(_resolve("{{%s.%s}}" % m.groups(), results, client)), value)
        if value.startswith("@"):
            return client.upload_data_uri(value[1:])
        return value
    if isinstance(value, list):
        return [_resolve(v, results, client) for v in value]
    if isinstance(value, dict):
        return {k: _resolve(v, results, client) for k, v in value.items()}
    return value


def run_script(script: dict, client: RunwayClient, *, out_dir: Path | None = None,
               on_event=lambda *a: None) -> dict:
    """Run steps sequentially. on_event(step_id, status, detail). Returns {step_id: task}."""
    results: dict[str, dict] = {}
    for step in script["steps"]:
        sid = step["id"]
        params = {k: v for k, v in step.items() if k not in ("id", "type")}
        params = _resolve(params, results, client)
        on_event(sid, "SUBMITTING", None)
        task_id = client.submit(step["type"], params)
        on_event(sid, "SUBMITTED", task_id)
        task = client.wait(task_id, on_update=lambda t, sid=sid: on_event(sid, t["status"], t.get("progress")))
        results[sid] = task
        if out_dir:
            for n, url in enumerate(task["output"]):
                ext = Path(url.split("?")[0]).suffix or ".bin"
                client.download(url, out_dir / f"{sid}_{n}{ext}")
        on_event(sid, "DONE", task["output"])
    return results
