from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BlobNotConfigured(RuntimeError):
    pass


def blob_configured() -> bool:
    return bool(os.getenv("BLOB_READ_WRITE_TOKEN", "").strip())


def require_blob_token() -> str:
    token = os.getenv("BLOB_READ_WRITE_TOKEN", "").strip()
    if not token:
        raise BlobNotConfigured("BLOB_READ_WRITE_TOKEN nao configurado.")
    return token


def safe_blob_name(name: str) -> str:
    cleaned = Path(name or "arquivo").name.replace("\\", "_").replace("/", "_").strip()
    return cleaned or "arquivo"


def blob_path(*parts: str) -> str:
    return "/".join(part.strip("/").replace("\\", "/") for part in parts if part and part.strip("/"))


@dataclass(frozen=True)
class BlobUpload:
    pathname: str
    url: str = ""
    download_url: str = ""
    content_type: str = ""
    etag: str = ""
    size: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "pathname": self.pathname,
            "url": self.url,
            "downloadUrl": self.download_url,
            "contentType": self.content_type,
            "etag": self.etag,
            "size": self.size,
        }


def _client():
    try:
        from vercel.blob import BlobClient
    except ImportError as exc:
        raise BlobNotConfigured("Dependencia vercel nao instalada.") from exc
    require_blob_token()
    return BlobClient()


def _value(data: Any, *names: str, default: Any = "") -> Any:
    for name in names:
        if isinstance(data, dict) and name in data:
            return data[name]
        if hasattr(data, name):
            return getattr(data, name)
    return default


def upload_bytes(pathname: str, data: bytes, content_type: str | None = None) -> BlobUpload:
    guessed = content_type or mimetypes.guess_type(pathname)[0] or "application/octet-stream"
    client = _client()
    result = client.put(pathname, data, access="private", content_type=guessed, add_random_suffix=False)
    return BlobUpload(
        pathname=str(_value(result, "pathname", default=pathname)),
        url=str(_value(result, "url", default="")),
        download_url=str(_value(result, "download_url", "downloadUrl", default="")),
        content_type=str(_value(result, "content_type", "contentType", default=guessed)),
        etag=str(_value(result, "etag", default="")),
        size=len(data),
    )


def upload_path(path: Path, pathname: str, content_type: str | None = None) -> BlobUpload:
    return upload_bytes(pathname, path.read_bytes(), content_type=content_type)


def download_bytes(url_or_pathname: str) -> bytes:
    client = _client()
    result = client.get(url_or_pathname)
    if isinstance(result, bytes):
        return result
    if hasattr(result, "read"):
        return result.read()
    if isinstance(result, str):
        return result.encode("utf-8")
    body = _value(result, "body", "content", default=None)
    if hasattr(body, "read"):
        return body.read()
    if isinstance(body, bytes):
        return body
    raise RuntimeError("Resposta inesperada do Vercel Blob.")


def delete_blob(url_or_pathname: str) -> None:
    _client().delete(url_or_pathname)


def check_blob() -> dict[str, Any]:
    configured = blob_configured()
    if not configured:
        return {"configured": False, "ok": False, "error": "BLOB_READ_WRITE_TOKEN nao configurado."}
    try:
        _client()
        return {"configured": True, "ok": True, "error": None}
    except Exception as exc:
        return {"configured": True, "ok": False, "error": str(exc)}
