# Realtime Vision Pipeline

Multi-stream, real-time object **detection and tracking** built as a
distributed streaming system: RTSP ingestion → YOLO26 detection → SORT
tracking → live WebSocket dashboard, with Kafka as the spine and
Prometheus/Grafana observability at every stage.

> Phase 1 status: scaffold complete; SORT implementation in progress
> (`services/tracker/sort.py` — see the paper-mapped TODOs).

## Architecture

```
video file ─ffmpeg─▶ mediamtx ─RTSP─▶ ingest ─▶ [frames] ─▶ detector ─▶ [detections] ─▶ tracker ─▶ [tracks] ─▶ api ─WS─▶ browser
                     (camera sim)      │                      │                          │                      │
                                       └──────────────── Prometheus :9100 scrapes ──────┴──────────────────────┘
```

- `[x]` = Kafka topic. Partition key = `camera_id`, so per-camera ordering
  is guaranteed (the tracker depends on it).
- `captured_ts` is stamped at decode time and rides every message; any
  stage's `now - captured_ts` = true end-to-end latency to that stage.

## Quickstart

```bash
cp .env.example .env
./scripts/download_sample_videos.sh   # put 1-3 mp4s in videos/ as cam1.mp4 ...
make up                                # builds + starts everything
./scripts/start_streams.sh             # push the files into mediamtx as RTSP
# open http://localhost:8000  (live view)
# open http://localhost:3000  (grafana — add a panel on pipeline_e2e_latency_ms)
```

The self-healing demo:

```bash
make chaos-detector   # kills detector mid-run; it restarts, rejoins its
                      # consumer group, and resumes from its Kafka offset
```

## Measured results (fill these in — they are the resume bullets)

| Metric | Value | Conditions |
|---|---|---|
| End-to-end p95 latency | _TBD_ ms | 1 stream, 10 fps, CPU (laptop model: _TBD_) |
| End-to-end p99 latency | _TBD_ ms | same |
| Detector inference p50 | _TBD_ ms | YOLO26n, 640px, CPU |
| Recovery after detector kill | _TBD_ s | zero events lost: _verify via seq gaps_ |

## Repo map

| Path | What it is |
|---|---|
| `common/schemas.py` | **The contract.** Message shapes between all services — read this first. |
| `common/kafka_io.py` | Producer/consumer config in one place (acks, offsets, partition keying). |
| `common/metrics.py` | Prometheus histograms/counters every stage shares. |
| `services/ingest/` | RTSP → decode → throttle → JPEG → `frames` topic. |
| `services/detector/` | `frames` → YOLO26n → `detections`. The `infer()` function is the Phase-2 Triton seam. |
| `services/tracker/` | `detections` → **your SORT** → `tracks`. `sort.py` is the learning centerpiece. |
| `services/api/` | `tracks` → WebSocket → live canvas dashboard. |
| `DECISIONS.md` | Alternatives considered, written as decisions happen. |

## Roadmap

- **Phase 1 (now):** single stream on CPU, own SORT, full observability. Exit: p95 number in the table above.
- **Phase 2:** Triton + dynamic batching on a T4 (g4dn.xlarge), N streams, ByteTrack vs SORT comparison on identical footage. Exit: streams-per-GPU number.
- **Phase 3:** backpressure policies, DLQ + replay, chaos suite, autoscaling on Prometheus metrics, DeepStream ingestion. Exit: documented recovery + sustained-load numbers.
