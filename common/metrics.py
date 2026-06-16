"""
Prometheus instrumentation shared by all services.

Pattern: each service calls start_metrics_server() once at boot, then
observes into these histograms in its main loop. Prometheus scrapes
port 9100 (see monitoring/prometheus.yml); Grafana draws the quantiles.

THE rule: instrument BEFORE you optimize. You cannot fix what you
cannot see, and 'where does the time go?' must be answerable with a
screenshot before any tuning work starts.
"""

from prometheus_client import Counter, Histogram, start_http_server

# Buckets tuned for a CPU pipeline: 5ms .. 5s. Adjust when you go GPU.
LATENCY_BUCKETS = (5, 10, 25, 50, 100, 200, 400, 800, 1500, 3000, 5000)

# end-to-end latency UP TO this stage (now - captured_ts), labeled by stage+camera
STAGE_E2E_MS = Histogram(
    "pipeline_e2e_latency_ms",
    "Latency from frame capture to completion of this stage (ms)",
    ["stage", "camera"],
    buckets=LATENCY_BUCKETS,
)

# time spent INSIDE this stage only (e.g. model inference itself)
STAGE_PROC_MS = Histogram(
    "pipeline_stage_processing_ms",
    "Processing time inside this stage (ms)",
    ["stage", "camera"],
    buckets=LATENCY_BUCKETS,
)

FRAMES_TOTAL = Counter(
    "pipeline_frames_total", "Frames processed", ["stage", "camera"]
)

FRAMES_DROPPED = Counter(
    "pipeline_frames_dropped_total",
    "Frames intentionally skipped (backpressure) or failed",
    ["stage", "camera", "reason"],
)


def start_metrics_server(port: int = 9100):
    start_http_server(port)
