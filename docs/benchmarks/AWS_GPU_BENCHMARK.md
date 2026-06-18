## Benchmark

This project includes a local CPU vs AWS GPU benchmark for the multi-camera real-time vision pipeline.

- Local CPU/Triton clean run: 3 cameras × 1 FPS, ~0.6–1.6 sec latency
- Local CPU/Triton stress test: 3 cameras × 10 FPS, ~42 sec latency under backlog
- AWS GPU/Triton test: EC2 g4dn.xlarge with NVIDIA Tesla T4, 3 cameras × 10 FPS, ~3.0–3.5 sec latency

Full report: [AWS GPU Benchmark](docs/benchmarks/AWS_GPU_BENCHMARK.md)