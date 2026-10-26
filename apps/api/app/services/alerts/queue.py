"""Outbox queue for alert delivery: Redis Streams in production, in-memory for development.

Redis Streams give us a durable log with consumer groups: several workers can share the load,
and a message is only removed (XACK) after it was delivered, so a crashed worker loses nothing.
"""
from __future__ import annotations

import queue as _q

from app.settings import get_settings

STREAM = "nh:alerts:outbox"
GROUP = "senders"


class MemoryQueue:
    def __init__(self):
        self.q: _q.Queue = _q.Queue()

    def put(self, alert_id: str) -> None:
        self.q.put(alert_id)

    def get(self, consumer: str, block_ms: int = 5000) -> list[tuple[str, str]]:
        try:
            aid = self.q.get(timeout=block_ms / 1000)
            return [(aid, aid)]
        except _q.Empty:
            return []

    def ack(self, msg_id: str) -> None:
        pass


class RedisStreamQueue:
    def __init__(self, url: str):
        import redis
        self.r = redis.Redis.from_url(url, decode_responses=True)
        try:
            self.r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    def put(self, alert_id: str) -> None:
        self.r.xadd(STREAM, {"alert_id": alert_id}, maxlen=100_000, approximate=True)

    def get(self, consumer: str, block_ms: int = 5000) -> list[tuple[str, str]]:
        # First reclaim messages another worker took but never acknowledged (crash recovery).
        claimed = self.r.xautoclaim(STREAM, GROUP, consumer, min_idle_time=60_000, start_id="0-0", count=10)
        msgs = list(claimed[1]) if claimed and claimed[1] else []
        if not msgs:
            resp = self.r.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=10, block=block_ms)
            msgs = resp[0][1] if resp else []
        return [(mid, fields["alert_id"]) for mid, fields in msgs if fields]

    def ack(self, msg_id: str) -> None:
        self.r.xack(STREAM, GROUP, msg_id)


_queue = None


def get_queue():
    global _queue
    if _queue is None:
        url = get_settings().redis_url
        _queue = RedisStreamQueue(url) if url else MemoryQueue()
    return _queue
