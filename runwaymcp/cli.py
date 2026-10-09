from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import script as scriptlib
from .client import KINDS, RunwayClient, RunwayError


def _log(sid, status, detail):
    extra = f" {detail}" if detail not in (None, "") else ""
    print(f"[{sid}] {status}{extra}", file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(prog="runwaymcp", description="Runway GUI + script runner")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a YAML/JSON script")
    r.add_argument("script")
    r.add_argument("-o", "--out", default="outputs", help="download directory")
    r.add_argument("--dry-run", action="store_true", help="validate only")

    g = sub.add_parser("gen", help="one-off generation")
    g.add_argument("type", choices=list(KINDS))
    g.add_argument("prompt", nargs="?", default="")
    g.add_argument("-p", "--param", action="append", default=[], metavar="KEY=VALUE",
                   help="extra API param, e.g. -p promptImage=@photo.png -p duration=10")
    g.add_argument("-o", "--out", default="outputs")

    s = sub.add_parser("serve", help="start the web GUI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    a = p.parse_args(argv)
    try:
        if a.cmd == "serve":
            import uvicorn
            uvicorn.run("runwaymcp.server:app", host=a.host, port=a.port)
            return 0
        if a.cmd == "run":
            sc = scriptlib.load(a.script)
            if a.dry_run:
                print(f"OK: {len(sc['steps'])} steps")
                return 0
            scriptlib.run_script(sc, RunwayClient(), out_dir=Path(a.out), on_event=_log)
            return 0
        params = {}
        if a.prompt:
            params["promptText"] = a.prompt
        for kv in a.param:
            k, _, v = kv.partition("=")
            params[k] = int(v) if v.isdigit() else v
        sc = {"steps": [{"id": "gen", "type": a.type, **params}]}
        scriptlib.run_script(scriptlib.validate(sc), RunwayClient(), out_dir=Path(a.out), on_event=_log)
        return 0
    except RunwayError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
