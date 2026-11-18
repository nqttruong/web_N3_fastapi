"""Contracts for the future sync module (not implemented in PR1)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.database.enums import SyncOperation


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    cursor: int
    entity_type: str
    entity_id: uuid.UUID
    operation: SyncOperation
    version: int
    changed_at: datetime


class ChangeFeed(Protocol):
    def changes_since(self, cursor: int, limit: int) -> list[ChangeRecord]:
        """Changes with ``cursor > given cursor``, ascending."""
        ...
