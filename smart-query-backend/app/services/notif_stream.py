import asyncio
import json
from typing import Optional

_queues: dict[int, list[asyncio.Queue]] = {}


def subscribe(user_id: int) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    if user_id not in _queues:
        _queues[user_id] = []
    _queues[user_id].append(q)
    return q


def unsubscribe(user_id: int, q: asyncio.Queue):
    if user_id not in _queues:
        return
    try:
        _queues[user_id].remove(q)
    except ValueError:
        pass
    if not _queues[user_id]:
        del _queues[user_id]


async def push(user_id: int, notification: dict):
    for q in _queues.get(user_id, []):
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await q.put(notification)


def push_sync(user_id: int, notification: dict):
    for q in _queues.get(user_id, []):
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        q.put_nowait(notification)
