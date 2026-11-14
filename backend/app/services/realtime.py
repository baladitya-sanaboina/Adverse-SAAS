"""Per-user live events over Redis pub/sub, streamed to browsers as Server-Sent Events.

Every event is `{"type": "...", "data": {...}}`. Notifications use type "notification"; chat
(Phase 14) adds its own types on the same per-user channel. Publishing never raises: a Redis
outage must not break the action that produced the event (the notification row is still stored).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import Any
from uuid import UUID

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.settings import settings

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 20
_client: Redis | None = None


def channel(user_id: UUID | str) -> str:
    return f"realtime:user:{user_id}"


def _redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
    return _client


def publish(user_ids: Iterable[UUID], event_type: str, data: dict[str, Any]) -> None:
    payload = json.dumps({"type": event_type, "data": data}, default=str)
    try:
        client = _redis()
        for user_id in set(user_ids):
            client.publish(channel(user_id), payload)
    except Exception:  # noqa: BLE001 - live delivery is best effort
        logger.warning("Realtime publish failed for %s", event_type, exc_info=True)


PRESENCE_SECONDS = HEARTBEAT_SECONDS * 3


def presence_key(user_id: UUID | str) -> str:
    return f"presence:user:{user_id}"


def online(user_ids: Iterable[UUID]) -> set[UUID]:
    """Who has the app open right now (a live stream refreshes the key every heartbeat)."""
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return set()
    try:
        values = _redis().mget([presence_key(user_id) for user_id in ids])
    except Exception:  # noqa: BLE001 - presence is best effort
        logger.debug("Presence lookup failed", exc_info=True)
        return set()
    return {user_id for user_id, value in zip(ids, values, strict=True) if value}


async def stream(
    user_id: UUID, is_disconnected: Callable[[], Awaitable[bool]]
) -> AsyncIterator[str]:
    """Yield SSE frames for one user until the browser disconnects. While the stream is open the
    user counts as online (chat presence, Phase 14)."""
    client = AsyncRedis.from_url(settings.redis_url)
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(channel(user_id))
        yield 'event: ready\ndata: {"type":"ready"}\n\n'
        while True:
            try:
                await client.set(presence_key(user_id), "1", ex=PRESENCE_SECONDS)
            except Exception:  # noqa: BLE001
                logger.debug("Presence update failed", exc_info=True)
            if await is_disconnected():
                break
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=HEARTBEAT_SECONDS
            )
            if message and message.get("type") == "message":
                data = message["data"]
                text = data.decode() if isinstance(data, bytes) else str(data)
                yield f"data: {text}\n\n"
            else:
                # Comment line keeps proxies from closing an idle connection.
                yield ": ping\n\n"
            await asyncio.sleep(0)
    finally:
        try:
            await pubsub.unsubscribe(channel(user_id))
            await pubsub.aclose()  # type: ignore[no-untyped-call]
            await client.aclose()
        except Exception:  # noqa: BLE001
            logger.debug("Realtime stream cleanup failed", exc_info=True)
