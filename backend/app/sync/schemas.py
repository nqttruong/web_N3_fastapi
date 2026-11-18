import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.core.schemas import APIModel, AwareDatetime


class PairRequest(APIModel):
    device_name: str = Field(min_length=1, max_length=100)

    @field_validator("device_name")
    @classmethod
    def device_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Device name must not be blank")
        return value


class PairingCodeCreate(APIModel):
    expires_in_minutes: int = Field(default=10, ge=1, le=15)


class PairingCodeRead(APIModel):
    pairing_code: str
    expires_at: datetime
    expires_in_minutes: int


class DeviceRead(APIModel):
    device_id: uuid.UUID
    device_name: str
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"


class SyncDeviceAdminRead(APIModel):
    device_id: uuid.UUID
    device_name: str
    paired_at: datetime
    last_seen_at: datetime | None
    last_pull_at: datetime | None
    last_push_at: datetime | None
    revoked_at: datetime | None


class ChangeRead(APIModel):
    cursor: int
    entity_type: str
    entity_id: uuid.UUID
    operation: Literal["insert", "update", "delete"]
    version: int
    changed_at: datetime
    schema_version: str
    data: dict[str, Any] | None = None


class ChangePage(APIModel):
    data: list[ChangeRead]
    next_cursor: int
    has_more: bool


class AndroidReviewEventIn(APIModel):
    request_id: uuid.UUID
    item_type: Literal["VOCABULARY", "KANJI", "GRAMMAR", "JLPT_REVIEW_ITEM"]
    item_id: str = Field(min_length=1, max_length=200)
    rating: Literal["AGAIN", "HARD", "GOOD", "EASY"]
    reviewed_at: AwareDatetime
    interval_before_minutes: int = Field(ge=0, le=100_000_000)
    interval_after_minutes: int = Field(ge=0, le=100_000_000)
    due_at_after: AwareDatetime


class PushRequest(APIModel):
    events: list[AndroidReviewEventIn] = Field(max_length=500)


class PushAck(APIModel):
    accepted: list[uuid.UUID]
    duplicates: list[uuid.UUID]
