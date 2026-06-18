## Benchmark

This project includes a local CPU vs AWS GPU benchmark for the multi-camera real-time vision pipeline.

- Local CPU/Triton clean run: 3 cameras × 1 FPS, ~0.6–1.6 sec latency
- Local CPU/Triton stress test: 3 cameras × 10 FPS, ~42 sec latency under backlog
- AWS GPU/Triton test: EC2 g4dn.xlarge with NVIDIA Tesla T4, 3 cameras × 10 FPS, ~3.0–3.5 sec latency

## Grafana Observability Evidence

### Local CPU Observability

The local CPU run was monitored using Grafana panels for throughput, dropped frames, and average end-to-end latency.

![Local FPS Throughput](../assets/local_fps_throughput_by_stage_camera.png)

![Local Dropped Frames](../assets/local_dropped_frames_by_reason.png)

![Local Average E2E Latency](../assets/local_average_e2e_latency.png)

### AWS GPU Observability

The AWS GPU run was monitored using the same Prometheus/Grafana metrics. The p95 and p99 latency panels confirm end-to-end latency behavior under GPU-backed Triton inference.

![AWS GPU FPS Throughput](../assets/aws_gpu_fps_throughput_by_stage_camera.png)

![AWS GPU Dropped Frames](../assets/aws_gpu_dropped_frames_by_reason.png)

![AWS GPU Average E2E Latency](../assets/aws_gpu_average_e2e_latency.png)

![AWS GPU p95 E2E Latency](../assets/aws_gpu_p95_e2e_latency.png)

![AWS GPU p99 E2E Latency](../assets/aws_gpu_p99_e2e_latency.png)

Full report: [AWS GPU Benchmark](docs/benchmarks/AWS_GPU_BENCHMARK.md)