# Design decisions

Two sentences per decision: what was chosen, what it beat, and why.
Written AS decisions are made, not reconstructed later. This file is
the "alternatives considered" story for the README and for interviews.

## 001 — Kafka as the inter-stage transport (vs Redis Streams, NATS, direct HTTP)
Kafka chosen for durable offsets (restart = resume, the reliability story),
per-key partition ordering (per-camera order is load-bearing for tracking),
and industry recognition. Redis Streams would be lighter but demonstrates
no new depth; NATS is elegant but the consumer-group offset semantics of
Kafka map exactly onto the self-healing demo this project needs.

## 002 — JPEG frames inside Kafka messages (vs shared volume / object store pointer)
Chosen for Phase 1 simplicity: one transport, no second storage system.
Known cost: broker bandwidth grows linearly with streams x fps x frame size;
the Phase 2 fix is publishing pointers once frame traffic dominates.

## 003 — In-process YOLO in the detector (vs Triton from day one)
Chosen so Phase 1 has one fewer moving part and the bottleneck is VISIBLE
in Grafana before the fix is introduced. The swap point is isolated to
detector/main.py:infer() — Phase 2 replaces that one function with a
Triton client and the before/after becomes a measured, documented win.

## 004 — Drop frames at ingest via throttling (vs process everything)
Load-shedding at the source is the cheapest place to shed: nothing is
encoded, published, or inferred for a frame we can't afford. Drops are
counted in pipeline_frames_dropped_total so shedding is observable.

## 005 — (yours) ...
