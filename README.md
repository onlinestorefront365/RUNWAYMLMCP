# RUNWAYMLMCP

A web GUI and a text-script runner for [Runway](https://dev.runwayml.com)'s API.

```bash
pip install -e .[dev]
export RUNWAYML_API_SECRET=key_...

runwaymcp serve                              # GUI at http://127.0.0.1:8000
runwaymcp run examples/lighthouse.yaml       # run a script, downloads to ./outputs
runwaymcp run examples/lighthouse.yaml --dry-run
runwaymcp gen text_to_image "a corgi astronaut" -p ratio=1920:1080
runwaymcp gen image_to_video "slow orbit" -p promptImage=@photo.png -p duration=10
pytest
```

## Script format (YAML or JSON)

Each step has `type` (`text_to_image`, `image_to_video`, `text_to_video`, `video_to_video`,
`video_upscale`, `character_performance`), an optional `id`, and any Runway API parameter
(defaults for `model`/`ratio`/`duration` are in `runwaymcp/client.py`).

- `{{id.output}}` – first output URL of an earlier step; `{{id.outputs}}` – all; `{{id.task}}` – task id
- `@path/to/file.png` – inline a local image as a data URI

## First-run onboarding

Opening the GUI for the first time shows a 4-step wizard: welcome → paste and verify a Runway API key
(validated against Runway, saved to `~/.runwaymcp/config.json`, mode 0600) → pick a goal → run a first
generation. Use "Re-run setup" in the header to reopen it. `RUNWAYML_API_SECRET` still takes precedence.
