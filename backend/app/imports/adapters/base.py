"""Adapter contract: raw user input → ``DraftContent`` + draft-level notes.

Adapters are pure functions of their input. They never fetch URLs, never touch the database
and never mark an answer as confirmed.
"""

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.imports.schemas import DraftContent, Issue


def new_key() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class ParseResult:
    adapter: str
    content: DraftContent
    notes: list[Issue] = field(default_factory=list)


class UnsupportedInputError(Exception):
    """The adapter recognises it cannot handle this input (do not pretend to parse it)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Adapter(Protocol):
    name: str

    def parse(self, raw: str) -> ParseResult: ...
