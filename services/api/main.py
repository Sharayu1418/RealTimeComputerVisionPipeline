"""
API / DASHBOARD — Stage 4. The window into the pipeline.

Flow: a background thread consumes "tracks" and keeps ONLY the latest
message per camera in memory. Browsers connect over WebSocket and
receive that latest state ~10x/sec.

Why "latest only" (and not every frame)? The dashboard is a LIVE VIEW,
not a recorder. If the browser is slower than the pipeline, we want it
showing the freshest frame, not falling progressively behind on a
backlog. Dropping intermediate frames at the VIEW layer is correct —
nothing downstream depends on the dashboard. (Contrast: we'd never
drop in the tracker, where every frame matters for ID continuity.)
"""

import asyncio
import json
import threading

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from common.kafka_io import make_consumer
from common.schemas import from_json
from common.metrics import start_metrics_server

app = FastAPI()

# camera_id -> latest Tracks dict. The whole "database" of this service.
latest: dict[str, dict] = {}


def consume_loop():
    """Runs in a daemon thread; keeps `latest` fresh."""
    consumer = make_consumer(group_id="api", topics=["tracks"])
    while True:
        rec = consumer.poll(1.0)
        if rec is None or rec.error():
            continue
        msg = from_json(rec.value())
        latest[msg["camera_id"]] = msg


@app.on_event("startup")
def startup():
    start_metrics_server()
    threading.Thread(target=consume_loop, daemon=True).start()


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # push current state of every camera, 10x/sec
            await websocket.send_text(json.dumps(latest))
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass

# serves static/index.html at /
app.mount("/", StaticFiles(directory="static", html=True), name="static")
