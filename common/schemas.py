"""
Message schemas — the CONTRACT between services.

This file is the most important design artifact in the repo. Every service
only knows about these shapes, never about each other. That is what lets you
kill/restart/replace any single service without touching the rest.

Flow of one frame through the system:

  IngestFrame  -> topic "frames"      (published by ingest)
  Detections   -> topic "detections"  (published by detector)
  Tracks       -> topic "tracks"      (published by tracker, consumed by api)

Two fields ride on EVERY message, end to end:
  * frame_id     — lets you join a detection back to its source frame
  * captured_ts  — wall-clock time the frame left the camera. Subtracting
                   this from "now" at any stage = true end-to-end latency
                   up to that stage. This one field powers your whole
                   latency dashboard. Never drop it.
"""

from dataclasses import dataclass, field, asdict
import json
import time
import uuid


def now_ms() -> float:
    """Single definition of 'now' so every stage measures the same clock."""
    return time.time() * 1000.0


@dataclass
class IngestFrame:
    """One decoded video frame, downscaled and JPEG-compressed.

    Why JPEG bytes inside the Kafka message (instead of a shared volume or
    Redis pointer)? Simplicity for Phase 1: one transport for everything.
    A 640px JPEG is ~50-100 KB, well under Kafka's 1 MB default max.
    TRADEOFF to record in DECISIONS.md: at high stream counts this bloats
    the broker; the Phase 2 fix is publishing a pointer to shared storage.
    """
    camera_id: str
    frame_id: str            # uuid — unique per frame
    seq: int                 # monotonic per camera; gaps = dropped frames (measurable!)
    captured_ts: float       # ms epoch at decode time — the latency anchor
    width: int
    height: int
    jpeg_b64: str            # base64-encoded JPEG bytes

    @staticmethod
    def new(camera_id: str, seq: int, width: int, height: int, jpeg_b64: str):
        return IngestFrame(
            camera_id=camera_id,
            frame_id=str(uuid.uuid4()),
            seq=seq,
            captured_ts=now_ms(),
            width=width,
            height=height,
            jpeg_b64=jpeg_b64,
        )


@dataclass
class Box:
    """One detected object. Coordinates are PIXELS in the published frame."""
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float              # detector confidence 0..1
    cls_id: int              # COCO class index (2 = car, 0 = person, ...)
    cls_name: str


@dataclass
class Detections:
    """Output of the detector for one frame. captured_ts is COPIED FORWARD
    from the IngestFrame — that is how latency survives stage boundaries."""
    camera_id: str
    frame_id: str
    seq: int
    captured_ts: float
    detect_ts: float         # when detection finished (per-stage latency = detect_ts - captured_ts)
    boxes: list = field(default_factory=list)   # list[Box as dict]
    jpeg_b64: str = ""       # frame passed through so the dashboard can draw on it


@dataclass
class TrackedObject:
    """A Box that has been claimed by a track. track_id is the whole point:
    it stays STABLE across frames. 'car 14' is still 'car 14' a second later."""
    track_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    cls_name: str
    age: int                 # frames this track has existed (useful for debugging your SORT)


@dataclass
class Tracks:
    """Output of the tracker for one frame — what the dashboard renders."""
    camera_id: str
    frame_id: str
    seq: int
    captured_ts: float
    track_ts: float
    objects: list = field(default_factory=list)  # list[TrackedObject as dict]
    jpeg_b64: str = ""


# --- serialization helpers (every service uses these, so format changes in ONE place)

def to_json(msg) -> bytes:
    return json.dumps(asdict(msg)).encode("utf-8")


def from_json(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"))
