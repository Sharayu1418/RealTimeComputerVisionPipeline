"""
TRACKER — Stage 3. Detections in, stable track IDs out.

Flow: consume "detections" -> route to that camera's Sort instance ->
publish "tracks". One Sort PER CAMERA: tracks must never bleed across
cameras (per-camera ordering is guaranteed because camera_id is the
Kafka partition key — see common/kafka_io.publish).

This file is COMPLETE — it's plumbing. The algorithm lives in sort.py,
which is yours to implement. Until sort.py is done, this service will
crash with NotImplementedError, which is honest behavior.
"""

import os
import time

import numpy as np

from sort import Sort
from common.schemas import Tracks, TrackedObject, to_json, from_json, now_ms
from common.kafka_io import make_producer, make_consumer, publish
from common.metrics import (
    start_metrics_server, STAGE_E2E_MS, STAGE_PROC_MS, FRAMES_TOTAL,
)
from dataclasses import asdict

STAGE = "tracker"

# one tracker state machine per camera, created lazily on first frame
trackers: dict[str, Sort] = {}


def main():
    start_metrics_server()
    producer = make_producer()
    consumer = make_consumer(group_id="tracker", topics=["detections"])

    while True:
        rec = consumer.poll(1.0)
        if rec is None or rec.error():
            continue

        det = from_json(rec.value())
        cam = det["camera_id"]
        t0 = time.time()

        sort = trackers.setdefault(cam, Sort())

        # detections -> (N,4) numpy array the Sort API expects
        dets = np.array(
            [[b["x1"], b["y1"], b["x2"], b["y2"]] for b in det["boxes"]]
        ) if det["boxes"] else np.empty((0, 4))

        # class names keyed by rough box position, so we can re-attach them
        # to tracked boxes (SORT itself is class-agnostic)
        tracked = sort.update(dets)

        objects = []
        for t in tracked:
            # nearest original detection gives us the class label
            cls = "object"
            if det["boxes"]:
                dists = [abs(b["x1"] - t["x1"]) + abs(b["y1"] - t["y1"]) for b in det["boxes"]]
                cls = det["boxes"][int(np.argmin(dists))]["cls_name"]
            objects.append(asdict(TrackedObject(
                track_id=t["track_id"],
                x1=t["x1"], y1=t["y1"], x2=t["x2"], y2=t["y2"],
                cls_name=cls, age=t["age"],
            )))

        out = Tracks(
            camera_id=cam,
            frame_id=det["frame_id"],
            seq=det["seq"],
            captured_ts=det["captured_ts"],   # anchor still riding along
            track_ts=now_ms(),
            objects=objects,
            jpeg_b64=det["jpeg_b64"],
        )
        publish(producer, "tracks", key=cam, value=to_json(out))

        FRAMES_TOTAL.labels(STAGE, cam).inc()
        STAGE_PROC_MS.labels(STAGE, cam).observe((time.time() - t0) * 1000)
        STAGE_E2E_MS.labels(STAGE, cam).observe(now_ms() - det["captured_ts"])


if __name__ == "__main__":
    main()
