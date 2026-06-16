"""
Thin wrappers around confluent-kafka so every service produces/consumes
the same way. Centralizing this means retry/config decisions live in ONE file.
"""

import os
from confluent_kafka import Producer, Consumer

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")


def make_producer() -> Producer:
    return Producer({
        "bootstrap.servers": BOOTSTRAP,
        # acks=all: broker confirms the write is durable before we move on.
        # Slower than acks=1, but "no detection events lost" is the Phase 3
        # reliability story — start with the honest setting and measure it.
        "acks": "all",
        "linger.ms": 5,        # tiny batching window; latency/throughput dial #1
    })


def make_consumer(group_id: str, topics: list[str]) -> Consumer:
    c = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        # group.id is how Kafka remembers WHERE THIS SERVICE LEFT OFF.
        # Restart the container -> consumer rejoins group -> resumes at its
        # committed offset. That is the self-healing you demo in Phase 1.
        "group.id": group_id,
        "auto.offset.reset": "latest",   # new group starts at live edge, not history
        "enable.auto.commit": True,      # fine for Phase 1; Phase 3 = manual commits
    })
    c.subscribe(topics)
    return c


def publish(producer: Producer, topic: str, key: str, value: bytes):
    """Key = camera_id so all frames from one camera land in ONE partition,
    preserving per-camera ordering. Cross-camera order doesn't matter;
    per-camera order absolutely does (the tracker assumes it)."""
    producer.produce(topic, key=key.encode(), value=value)
    producer.poll(0)   # serve delivery callbacks without blocking
