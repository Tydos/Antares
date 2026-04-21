from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
from typing import Any
from src.config import settings


class BlobTokenError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def create_client_upload_token(
    event_body: dict[str, Any],
    read_write_token: str,
    *,
    allowed_content_types: list[str],
    maximum_size_in_bytes: int,
) -> dict[str, Any]:
    if not read_write_token:
        raise BlobTokenError("BLOB_READ_WRITE_TOKEN is not configured.", 503)
    if event_body.get("type") != "blob.generate-client-token":
        raise BlobTokenError(f"Unsupported event type: {event_body.get('type')!r}", 400)

    pathname = (event_body.get("payload") or {}).get("pathname")
    if not isinstance(pathname, str) or not pathname:
        raise BlobTokenError("Missing payload.pathname", 400)

    parts = read_write_token.split("_")
    if len(parts) < 4 or not parts[3]:
        raise BlobTokenError("Invalid BLOB_READ_WRITE_TOKEN format", 503)

    body = {
        "allowedContentTypes": allowed_content_types,
        "maximumSizeInBytes": maximum_size_in_bytes,
        "addRandomSuffix": True,
        "pathname": pathname,
        "validUntil": int(time.time() * 1000) + settings.blob_token_ttl_ms,
    }
    # Must match JS JSON.stringify: no spaces, ASCII-safe
    payload_b64 = base64.b64encode(
        json.dumps(body, separators=(",", ":"), ensure_ascii=True).encode()
    ).decode("ascii")
    signature = hmac.new(read_write_token.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    token_suffix = base64.b64encode(f"{signature}.{payload_b64}".encode()).decode("ascii")
    client_token = f"vercel_blob_client_{parts[3]}_{token_suffix}"

    return {"type": "blob.generate-client-token", "clientToken": client_token}
