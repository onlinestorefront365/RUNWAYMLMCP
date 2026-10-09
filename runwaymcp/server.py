"""Web GUI backend: submit scripts or single steps, watch progress, preview outputs."""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import script as scriptlib
from .client import KINDS, RunwayClient, RunwayError

app = FastAPI(title="Runway GUI")
STATIC = Path(__file__).parent / "static"
JOBS: dict[str, dict] = {}
client_factory = RunwayClient  # overridable in tests


class JobIn(BaseModel):
    script: str | None = None   # YAML/JSON text
    type: str | None = None     # or a single step
    params: dict = {}


def _worker(job_id: str, sc: dict):
    job = JOBS[job_id]

    def ev(sid, status, detail):
        job["steps"].setdefault(sid, {})["status"] = status
        if status == "DONE":
            job["steps"][sid]["output"] = detail
        elif detail is not None:
            job["steps"][sid]["detail"] = detail

    try:
        scriptlib.run_script(sc, client_factory(), on_event=ev)
        job["status"] = "DONE"
    except Exception as e:  # surface any failure to the UI
        job["status"], job["error"] = "FAILED", str(e)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/kinds")
def kinds():
    return {k: v[1] for k, v in KINDS.items()}


@app.post("/api/jobs")
def create_job(body: JobIn):
    try:
        if body.script:
            sc = scriptlib.load(body.script, is_text=True)
        elif body.type:
            sc = scriptlib.validate({"steps": [{"id": "gen", "type": body.type, **body.params}]})
        else:
            raise RunwayError("Provide 'script' or 'type'")
    except Exception as e:
        raise HTTPException(400, str(e))
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"id": jid, "status": "RUNNING", "steps": {s["id"]: {"status": "PENDING"} for s in sc["steps"]}}
    threading.Thread(target=_worker, args=(jid, sc), daemon=True).start()
    return JOBS[jid]


@app.get("/api/jobs")
def list_jobs():
    return list(JOBS.values())


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    if jid not in JOBS:
        raise HTTPException(404)
    return JOBS[jid]
