"""Local single-user Web access and sync-management authorization."""

import ipaddress
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from app.core.config import Settings, get_settings


def _is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def require_local_web_access(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Keep personal Web APIs local; Android uses its separate device-token routes."""
    if settings.app_env == "test" or _is_loopback(request):
        return
    raise HTTPException(
        status_code=403,
        detail="Web API chỉ khả dụng từ máy chạy ứng dụng. Android cần dùng device sync API.",
    )


def require_https_for_remote_sync(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    if settings.app_env == "test" or _is_loopback(request) or request.url.scheme == "https":
        return
    raise HTTPException(
        status_code=400,
        detail="Đồng bộ từ thiết bị qua mạng chỉ chấp nhận HTTPS.",
    )


def require_sync_admin(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    admin_key: Annotated[str | None, Header(alias="X-Sync-Admin-Key")] = None,
) -> None:
    configured = settings.sync_admin_key
    if configured is not None:
        if not secrets.compare_digest(admin_key or "", configured.get_secret_value()):
            raise HTTPException(status_code=401, detail="Thiếu hoặc sai khóa quản trị đồng bộ.")
        return
    if settings.app_env == "test":
        return
    if settings.app_env == "development" and _is_loopback(request):
        return
    raise HTTPException(
        status_code=503,
        detail="Quản lý ghép nối bị tắt; hãy cấu hình SYNC_ADMIN_KEY tối thiểu 32 ký tự.",
    )
