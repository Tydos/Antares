from minio import Minio
from fastapi import UploadFile
from datetime import timedelta
import tempfile
import os
import logging


class MinioStorageBackend:
    def __init__(self, client: Minio, bucket_name: str) -> None:
        self._client = client
        self._bucket = bucket_name
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logging.debug(f"Created bucket: {self._bucket}")

    async def upload(self, file: UploadFile) -> str:
        """Validate, stream-upload to MinIO, return a 1-hour presigned URL."""
        if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
            raise ValueError("Not a PDF")
        if not file.filename:
            raise ValueError("Filename is required")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            while chunk := await file.read(10 * 1024 * 1024):
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            self._client.fput_object(self._bucket, file.filename, tmp_path, content_type="application/pdf")
        except Exception as e:
            raise RuntimeError(f"MinIO upload failed: {e}") from e
        finally:
            os.remove(tmp_path)

        url = self._client.presigned_get_object(
            bucket_name=self._bucket,
            object_name=file.filename,
            expires=timedelta(hours=1)
        )
        logging.debug(f"Presigned URL generated for: {file.filename}")
        return url

    def ping(self) -> bool:
        """Return True if the MinIO server is reachable."""
        try:
            self._client.list_buckets()
            return True
        except Exception:
            return False

    def download_to_tempfile(self, filename: str) -> str:
        """Download an object from MinIO to a local temp file, return the path."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        try:
            self._client.fget_object(self._bucket, filename, tmp.name)
        except Exception as e:
            os.remove(tmp.name)
            raise RuntimeError(f"MinIO download failed: {e}") from e
        return tmp.name
