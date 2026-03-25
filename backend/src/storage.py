from minio import Minio
from fastapi import UploadFile
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
        """Validate and stream-upload a PDF. Returns the object filename."""
        
        # basic validation
        if not file.filename:
            raise ValueError("Filename is required")
        if file.content_type != "application/pdf" or not file.filename.lower().endswith(".pdf"):
            raise ValueError("Not a PDF")

        # stream to a temp file and upload
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            while chunk := await file.read(10 * 1024 * 1024):
                tmp.write(chunk)
            tmp_path = tmp.name
        try:
            self._client.fput_object(self._bucket, file.filename, tmp_path, content_type="application/pdf")
            logging.debug(f"Uploaded: {file.filename}")
        except Exception as e:
            raise RuntimeError(f"MinIO upload failed: {e}") from e
        finally:
            os.remove(tmp_path)
        return file.filename

    def delete(self, filename: str) -> None:
        """Remove an object from the bucket."""
        self._client.remove_object(self._bucket, filename)
        logging.debug(f"Deleted: {filename}")

    def download_to_tempfile(self, filename: str) -> str:
        """Download an object to a local temp file. Caller must delete it."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        try:
            self._client.fget_object(self._bucket, filename, tmp.name)
        except Exception as e:
            os.remove(tmp.name)
            raise RuntimeError(f"MinIO download failed: {e}") from e
        return tmp.name

    def ping(self) -> bool:
        try:
            self._client.list_buckets()
            return True
        except Exception:
            return False
