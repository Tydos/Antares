"""
Sign Vercel Blob client-upload tokens.

When the browser calls @vercel/blob's client upload API it first hits our
/blob-upload endpoint to get a short-lived signed token.  We generate that
token here using the same algorithm as the official @vercel/blob JS SDK.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class BlobTokenError(Exception):
    """Raised when a client token cannot be minted; `status_code` maps to an HTTP response."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


_TOKEN_TTL_MS = 60 * 60 * 1000  # tokens are valid for 1 hour


def _json_compact(obj: dict[str, Any]) -> str:
    # Must match JS JSON.stringify: no spaces, ASCII-safe
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True)


def _sign(payload_b64: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()


def _build_client_token(
    *,
    read_write_token: str,
    pathname: str,
    valid_until_ms: int,
    allowed_content_types: list[str] | None = None,
    maximum_size_in_bytes: int | None = None,
) -> str:
    parts = read_write_token.split("_")
    if len(parts) < 4 or not parts[3]:
        raise ValueError("Invalid BLOB_READ_WRITE_TOKEN format")

    store_id = parts[3]

    body: dict[str, Any] = {}
    if allowed_content_types is not None:
        body["allowedContentTypes"] = allowed_content_types
    if maximum_size_in_bytes is not None:
        body["maximumSizeInBytes"] = maximum_size_in_bytes
    body["addRandomSuffix"] = True
    body["pathname"] = pathname
    body["validUntil"] = valid_until_ms

    payload_b64 = base64.b64encode(_json_compact(body).encode()).decode("ascii")
    signature = _sign(payload_b64, read_write_token)
    token_suffix = base64.b64encode(f"{signature}.{payload_b64}".encode()).decode("ascii")
    return f"vercel_blob_client_{store_id}_{token_suffix}"


def handle_upload_event(
    event_body: dict[str, Any],
    read_write_token: str,
    *,
    allowed_content_types: list[str],
    maximum_size_in_bytes: int,
) -> dict[str, Any]:
    """Validate a @vercel/blob handleUpload event and return the signed client token."""
    if not read_write_token:
        raise BlobTokenError("BLOB_READ_WRITE_TOKEN is not configured.", 503)

    if event_body.get("type") != "blob.generate-client-token":
        raise BlobTokenError(f"Unsupported event type: {event_body.get('type')!r}", 400)

    pathname = (event_body.get("payload") or {}).get("pathname")
    if not isinstance(pathname, str) or not pathname:
        raise BlobTokenError("Missing payload.pathname", 400)

    try:
        client_token = _build_client_token(
            read_write_token=read_write_token,
            pathname=pathname,
            valid_until_ms=int(time.time() * 1000) + _TOKEN_TTL_MS,
            allowed_content_types=allowed_content_types,
            maximum_size_in_bytes=maximum_size_in_bytes,
        )
    except ValueError as e:
        raise BlobTokenError(str(e), 503) from e

    return {"type": "blob.generate-client-token", "clientToken": client_token}
