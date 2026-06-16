"""
INGEST WORKER — Stage 1 of the pipeline.

Job: connect to one RTSP camera, decode frames, downscale, JPEG-encode,
stamp with captured_ts, publish to the "frames" topic. Nothing else.

Flow per frame:
  RTSP packet -> PyAV decode -> throttle to TARGET_FPS -> resize ->
  JPEG encode -> IngestFrame message -> Kafka "frames"

Design notes worth understanding (and stealing for interviews):
  * THROTTLING: cameras emit 25-30 fps; on CPU you cannot detect that fast.
    Dropping frames HERE, at the source, is deliberate load-shedding —
    it is cheaper to never encode a frame than to let it clog the pipeline.
    The drop is counted in metrics, so shedding is VISIBLE, not silent.
  * RECONNECT: real cameras drop. The loop catches errors and reconnects
    with a small backoff. docker's restart policy is the second safety net.
  * ONE WORKER = ONE CAMERA. Scaling to N cameras = running N containers,
    which is exactly the unit-of-scale story you want to tell.
"""

import base64
import os
import time

import av                       # PyAV: ffmpeg bindings; does RTSP + decode
import cv2
import numpy as np

from common.schemas import IngestFrame, to_json, now_ms
from common.kafka_io import make_producer, publish
from common.metrics import (
    start_metrics_server, STAGE_E2E_MS, STAGE_PROC_MS, FRAMES_TOTAL, FRAMES_DROPPED,
)

RTSP_URL = os.environ["RTSP_URL"]
CAMERA_ID = os.environ.get("CAMERA_ID", "cam1")
FRAME_WIDTH = int(os.environ.get("FRAME_WIDTH", "640"))
TARGET_FPS = float(os.environ.get("TARGET_FPS", "10"))

STAGE = "ingest"


def run_once(producer, seq_start: int) -> int:
    """One RTSP session. Returns last seq so reconnects keep the counter monotonic."""
    container = av.open(RTSP_URL, options={"rtsp_transport": "tcp"})  # tcp = fewer corrupt frames than udp
    stream = container.streams.video[0]
    min_interval = 1.0 / TARGET_FPS
    last_emit = 0.0
    seq = seq_start

    for frame in container.decode(stream):
        t0 = time.time()

        # --- throttle: skip frames arriving faster than TARGET_FPS ---------
        if t0 - last_emit < min_interval:
            FRAMES_DROPPED.labels(STAGE, CAMERA_ID, "throttle").inc()
            continue
        last_emit = t0

        # --- decode -> numpy -> downscale ----------------------------------
        img = frame.to_ndarray(format="bgr24")          # BGR because OpenCV draws in BGR
        h, w = img.shape[:2]
        scale = FRAME_WIDTH / w
        img = cv2.resize(img, (FRAME_WIDTH, int(h * scale)))

        # --- compress: raw 640x360 BGR is ~700KB; JPEG ~50KB ---------------
        ok, jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            FRAMES_DROPPED.labels(STAGE, CAMERA_ID, "encode_fail").inc()
            continue

        # --- build message; captured_ts is stamped INSIDE IngestFrame.new --
        msg = IngestFrame.new(
            camera_id=CAMERA_ID, seq=seq,
            width=img.shape[1], height=img.shape[0],
            jpeg_b64=base64.b64encode(jpeg.tobytes()).decode(),
        )
        publish(producer, "frames", key=CAMERA_ID, value=to_json(msg))
        seq += 1

        # --- instrument ------------------------------------------------------
        FRAMES_TOTAL.labels(STAGE, CAMERA_ID).inc()
        STAGE_PROC_MS.labels(STAGE, CAMERA_ID).observe((time.time() - t0) * 1000)
        STAGE_E2E_MS.labels(STAGE, CAMERA_ID).observe(now_ms() - msg.captured_ts)

    return seq


def main():
    start_metrics_server()          # exposes :9100/metrics for Prometheus
    producer = make_producer()
    seq = 0
    while True:                     # outer loop = reconnect forever
        try:
            seq = run_once(producer, seq)
        except Exception as e:      # camera dropped, network blip, etc.
            print(f"[ingest] stream error: {e}; reconnecting in 2s", flush=True)
            FRAMES_DROPPED.labels(STAGE, CAMERA_ID, "stream_error").inc()
            time.sleep(2)


if __name__ == "__main__":
    main()
