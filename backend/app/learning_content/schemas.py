from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SyncRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    trigger: str
    source_commit_sha: str | None
    source_manifest_hash: str | None
    counts: dict[str, int]
    error: str | None
    attempts: int
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class LearningPackRead(BaseModel):
    id: str
    title: str
    jlpt_level: str
    source_version: int
    source_commit_sha: str | None
    license_blocked_count: int
    active_item_count: int
    synced_at: datetime
    is_archived: bool


class LearningSyncStatus(BaseModel):
    source_configured: bool
    source_available: bool
    source_description: str
    interval_minutes: int
    last_checked_at: datetime | None
    last_success_at: datetime | None
    current_versions: list[LearningPackRead]
    active_counts: dict[str, int]
    last_run: SyncRunRead | None


class LearningItemRead(BaseModel):
    id: UUID
    stable_source_id: str
    item_type: str
    jlpt_level: str
    pack_id: str
    pack_title: str
    source_version: int
    lesson_id: str
    lesson_number: int
    lesson_title: str
    order_index: int
    source_name: str
    source_license: str
    payload: dict[str, Any]
    examples: list[dict[str, Any]]


class LearningItemPage(BaseModel):
    items: list[LearningItemRead]
    total: int
    page: int
    page_size: int


class SyncQueued(BaseModel):
    run_id: UUID
    status: str
    message: str
