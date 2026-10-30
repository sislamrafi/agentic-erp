"""Tiny in-process pub/sub used for realtime UI refresh over SSE."""
import asyncio
import json

_subscribers: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue):
    _subscribers.discard(q)


def publish(event: dict):
    msg = json.dumps(event)
    for q in list(_subscribers):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


def data_changed(resource: str, action: str, id: int | None = None, source: str = "ui"):
    publish({"type": "data_changed", "resource": resource, "action": action, "id": id, "source": source})
