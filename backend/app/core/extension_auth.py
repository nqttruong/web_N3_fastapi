"""Bearer authentication for the explicitly configured local browser extension."""

import hmac
import ipaddress

from fastapi import Request, status

from app.core.config import Settings
from app.core.errors import AppError


class ExtensionCaptureUnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "extension_unauthorized"


class ExtensionCaptureDisabledError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "extension_capture_disabled"


def verify_extension_request(
    request: Request, settings: Settings, authorization: str | None
) -> None:
    """Require a configured secret and a loopback TCP peer; Origin is never authentication."""
    if settings.extension_import_token is None:
        raise ExtensionCaptureDisabledError(
            "Extension import chưa được bật. Hãy cấu hình EXTENSION_IMPORT_TOKEN ở backend local."
        )
    peer = request.client.host if request.client else ""
    try:
        is_loopback = ipaddress.ip_address(peer.split("%", 1)[0]).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise ExtensionCaptureUnauthorizedError("Chỉ chấp nhận kết nối từ máy local.")

    scheme, _, supplied = (authorization or "").partition(" ")
    expected = settings.extension_import_token.get_secret_value()
    if scheme.lower() != "bearer" or not supplied or not hmac.compare_digest(supplied, expected):
        raise ExtensionCaptureUnauthorizedError("Token extension không hợp lệ.")
