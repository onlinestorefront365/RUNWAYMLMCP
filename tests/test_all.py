import httpx, pytest
from fastapi.testclient import TestClient

from runwaymcp import script as sl, server
from runwaymcp.client import RunwayClient, RunwayError

SCRIPT = """
steps:
  - id: a
    type: text_to_image
    promptText: hi
  - id: b
    type: image_to_video
    promptImage: "{{a.output}}"
"""


def fake_client():
    calls, n = [], {"i": 0}

    def handler(req: httpx.Request):
        if req.method == "POST":
            n["i"] += 1
            calls.append((req.url.path, req.content.decode()))
            return httpx.Response(200, json={"id": f"t{n['i']}"})
        return httpx.Response(200, json={"id": req.url.path.split("/")[-1], "status": "SUCCEEDED",
                                         "output": [f"https://x/{req.url.path.split('/')[-1]}.png"]})

    return RunwayClient("k", transport=httpx.MockTransport(handler), poll_interval=0), calls


def test_chaining():
    c, calls = fake_client()
    res = sl.run_script(sl.load(SCRIPT, is_text=True), c)
    assert res["b"]["id"] == "t2"
    assert "https://x/t1.png" in calls[1][1] and calls[1][0].endswith("/image_to_video")


def test_validation():
    with pytest.raises(RunwayError):
        sl.load("steps: [{type: nope}]", is_text=True)
    with pytest.raises(RunwayError):
        sl.load("steps: [{id: a, type: image_to_video, promptImage: '{{z.output}}'}]", is_text=True)


def test_server():
    server.client_factory = lambda: fake_client()[0]
    tc = TestClient(server.app)
    assert tc.get("/").status_code == 200
    r = tc.post("/api/jobs", json={"script": SCRIPT})
    jid = r.json()["id"]
    import time
    for _ in range(50):
        j = tc.get(f"/api/jobs/{jid}").json()
        if j["status"] != "RUNNING":
            break
        time.sleep(0.05)
    assert j["status"] == "DONE" and j["steps"]["b"]["output"]
    assert tc.post("/api/jobs", json={}).status_code == 400
