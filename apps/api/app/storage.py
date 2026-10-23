"""S3-compatible evidence storage with a deterministic local adapter."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from pathlib import Path, PurePosixPath
from urllib.parse import quote


class LocalStorageProvider:
    def __init__(self, root: str = ".sda-storage", secret: str | None = None) -> None:
        self.root = Path(root)
        self.secret = (secret or os.getenv("SDA_STORAGE_SECRET", "local-demo-secret")).encode()

    def compute_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _safe_key(self, key: str) -> str:
        normalized = key.replace("\\", "/")
        if not normalized or normalized.startswith("/") or "//" in normalized:
            raise ValueError("Unsafe storage key")
        candidate = PurePosixPath(normalized)
        if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
            raise ValueError("Unsafe storage key")
        return "/".join(candidate.parts)

    def put_object(self, key: str, content: bytes, content_type: str) -> dict[str, str | int]:
        safe_key = self._safe_key(key)
        target = self.root / safe_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return {"key": safe_key, "bytes": len(content), "sha256": self.compute_hash(content), "content_type": content_type}

    def get_signed_url(self, key: str, expires_seconds: int = 900) -> str:
        safe_key = self._safe_key(key)
        expires_at = int(time.time()) + max(1, min(expires_seconds, 86_400))
        signature = hmac.new(self.secret, f"{safe_key}:{expires_at}".encode(), hashlib.sha256).hexdigest()
        return f"/api/v1/evidence/{quote(safe_key)}?expires={expires_at}&signature={signature}"

    def verify_signed_url(self, key: str, expires: int, signature: str) -> bool:
        if expires < int(time.time()):
            return False
        expected = hmac.new(self.secret, f"{self._safe_key(key)}:{expires}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def get_object(self, key: str) -> bytes:
        target = self.root / self._safe_key(key)
        if not target.is_file():
            raise FileNotFoundError(key)
        return target.read_bytes()

    def delete_object(self, key: str) -> None:
        target = self.root / self._safe_key(key)
        if target.is_file():
            target.unlink()


class S3StorageProvider:
    """Thin boto3 adapter for AWS S3, Cloudflare R2 and compatible stores."""

    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install boto3 to enable S3/R2 evidence storage") from exc
        self.bucket = os.environ["S3_BUCKET"]
        self.client = boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT") or None, aws_access_key_id=os.getenv("S3_ACCESS_KEY"), aws_secret_access_key=os.getenv("S3_SECRET_KEY"), region_name=os.getenv("S3_REGION", "auto"))

    def compute_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def put_object(self, key: str, content: bytes, content_type: str) -> dict[str, str | int]:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type, Metadata={"sha256": self.compute_hash(content)})
        return {"key": key, "bytes": len(content), "sha256": self.compute_hash(content), "content_type": content_type}

    def get_signed_url(self, key: str, expires_seconds: int = 900) -> str:
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=max(1, min(expires_seconds, 86_400)))

    def delete_object(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)
