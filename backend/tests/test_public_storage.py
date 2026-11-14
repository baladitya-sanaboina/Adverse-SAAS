import asyncio
import unittest
from typing import Any

from main import PUBLIC_STORAGE, app


def _status(path: str) -> int:
    """Send one GET through the full app (middleware included) and return the status code."""
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
    }
    asyncio.run(app(scope, receive, send))
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


class PublicStorageTest(unittest.TestCase):
    def test_missing_public_image_is_not_found_not_a_server_error(self) -> None:
        self.assertTrue(PUBLIC_STORAGE.is_dir())
        for path in (
            "/storage/profile-images/missing.png",
            "/storage/company-branding/x/missing.png",
        ):
            self.assertEqual(_status(path), 404, path)


if __name__ == "__main__":
    unittest.main()
