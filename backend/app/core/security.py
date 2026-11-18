"""Single-user Web API access boundary; Android has a separate device bearer credential."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.sync.admin import require_local_web_access


@dataclass(frozen=True, slots=True)
class Principal:
    """Who is making the request. ``user_id`` will become a real UUID once auth exists."""

    user_id: str | None
    is_local: bool


LOCAL_PRINCIPAL = Principal(user_id=None, is_local=True)


def get_principal(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> Principal:
    require_local_web_access(request, settings)
    return LOCAL_PRINCIPAL
