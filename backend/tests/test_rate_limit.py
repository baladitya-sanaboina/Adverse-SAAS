"""Write rate limit per signed-in session (security checklist, 2026-11-15), without Redis."""

import asyncio
import json
import unittest
from collections.abc import MutableMapping
from typing import Any

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.middleware.rate_limit import RateLimitMiddleware


class FakeRedis:
    def __init__(self, broken: bool = False) -> None:
        self.counts: dict[str, int] = {}
        self.broken = broken

    async def incr(self, key: str) -> int:
        if self.broken:
            raise ConnectionError("redis down")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return True


class Api:
    """Sends requests straight through the ASGI app (no test client package needed)."""

    def __init__(self, redis: FakeRedis, limit: int = 3) -> None:
        async def ok(_: Any) -> PlainTextResponse:
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/thing", ok, methods=["GET", "POST"])])
        app.add_middleware(RateLimitMiddleware, limit=limit, redis=redis)  # type: ignore[arg-type]
        self.app = app

    def call(self, method: str, token: str | None = None) -> tuple[int, dict[str, str], bytes]:
        sent: list[MutableMapping[str, Any]] = []

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: MutableMapping[str, Any]) -> None:
            sent.append(message)

        headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": "/thing",
            "raw_path": b"/thing",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        }
        asyncio.run(self.app(scope, receive, send))
        start = next(m for m in sent if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        found = {k.decode().lower(): v.decode() for k, v in start["headers"]}
        return start["status"], found, body


class RateLimitTest(unittest.TestCase):
    def test_writes_over_the_limit_get_429(self) -> None:
        api = Api(FakeRedis())
        codes = [api.call("POST", "session-a")[0] for _ in range(3)]
        status, headers, body = api.call("POST", "session-a")
        self.assertEqual(codes + [status], [200, 200, 200, 429])
        self.assertEqual(json.loads(body)["code"], "RATE_LIMITED")
        self.assertIn("retry-after", headers)
        # Another session has its own count; reads are never limited.
        self.assertEqual(api.call("POST", "session-b")[0], 200)
        self.assertEqual(api.call("GET", "session-a")[0], 200)

    def test_requests_without_a_token_are_left_to_the_flow_limits(self) -> None:
        api = Api(FakeRedis(), limit=1)
        self.assertEqual([api.call("POST")[0] for _ in range(3)], [200, 200, 200])

    def test_redis_down_lets_requests_through(self) -> None:
        api = Api(FakeRedis(broken=True), limit=1)
        self.assertEqual([api.call("POST", "session-a")[0] for _ in range(3)], [200] * 3)


if __name__ == "__main__":
    unittest.main()
