"""Mint Vercel Blob client tokens; algorithm matches @vercel/blob generateClientTokenFromReadWriteToken."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any


def _json_compact(obj: dict[str, Any]) -> str:
    # Match JS JSON.stringify: no spaces, ASCII escapes for non-ASCII (ensure_ascii=True)
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True)


def _sign_payload_b64(payload_b64: str, read_write_token: str) -> str:
    key = read_write_token.encode("utf-8")
    msg = payload_b64.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def generate_client_token_from_read_write_token(
    *,
    read_write_token: str,
    pathname: str,
    valid_until_ms: int,
    allowed_content_types: list[str] | None = None,
    maximum_size_in_bytes: int | None = None,
    add_random_suffix: bool = False,
    allow_overwrite: bool | None = None,
    cache_control_max_age: int | None = None,
    on_upload_completed: dict[str, Any] | None = None,
) -> str:
    """
    Same wire format as @vercel/blob generateClientTokenFromReadWriteToken.
    Object key order matches the SDK's `{ ...tokenOptions, pathname, onUploadCompleted?, validUntil }`.
    """
    parts = read_write_token.split("_")
    if len(parts) < 4 or not parts[3]:
        raise ValueError("Invalid BLOB_READ_WRITE_TOKEN")

    store_id = parts[3]

    body: dict[str, Any] = {}
    if allowed_content_types is not None:
        body["allowedContentTypes"] = allowed_content_types
    if maximum_size_in_bytes is not None:
        body["maximumSizeInBytes"] = maximum_size_in_bytes
    if add_random_suffix:
        body["addRandomSuffix"] = True
    if allow_overwrite is not None:
        body["allowOverwrite"] = allow_overwrite
    if cache_control_max_age is not None:
        body["cacheControlMaxAge"] = cache_control_max_age
    body["pathname"] = pathname
    if on_upload_completed is not None:
        body["onUploadCompleted"] = on_upload_completed
    body["validUntil"] = valid_until_ms

    payload_b64 = base64.b64encode(_json_compact(body).encode("utf-8")).decode("ascii")
    secured_key = _sign_payload_b64(payload_b64, read_write_token)
    inner = f"{secured_key}.{payload_b64}"
    token_suffix = base64.b64encode(inner.encode("utf-8")).decode("ascii")
    return f"vercel_blob_client_{store_id}_{token_suffix}"
