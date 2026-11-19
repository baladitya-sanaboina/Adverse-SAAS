"""Automatic client codes (owner request 2026-11-19), without a database."""

import unittest
from typing import Any
from uuid import uuid4

from app.repositories.client_repository import ClientRepository
from app.schemas.client import ClientCreate


class FakeCursor:
    """Answers the two queries _next_code makes: the highest CLT number, then 'is it taken'."""

    def __init__(self, highest: int, taken: set[str]) -> None:
        self.highest = highest
        self.taken = taken
        self.last: Any = None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        if "advisory" in sql:
            self.last = None
        elif "MAX(" in sql:
            self.last = (self.highest,)
        else:
            self.last = (1,) if params[1] in self.taken else None

    def fetchone(self) -> Any:
        return self.last


class ClientCodeTest(unittest.TestCase):
    def test_code_is_optional_and_blank_means_automatic(self) -> None:
        self.assertIsNone(ClientCreate(name="Kalpana Studio").code)
        self.assertIsNone(ClientCreate(name="Kalpana Studio", code="  ").code)
        self.assertEqual(ClientCreate(name="Kalpana Studio", code=" ks-01 ").code, "KS-01")

    def test_next_code_counts_up_and_skips_codes_in_use(self) -> None:
        company = uuid4()
        self.assertEqual(ClientRepository._next_code(FakeCursor(0, set()), company), "CLT-0001")
        self.assertEqual(ClientRepository._next_code(FakeCursor(6, set()), company), "CLT-0007")
        # Someone typed CLT-0007 by hand for another client: the next free one is used.
        self.assertEqual(
            ClientRepository._next_code(FakeCursor(6, {"CLT-0007"}), company), "CLT-0008"
        )


if __name__ == "__main__":
    unittest.main()
