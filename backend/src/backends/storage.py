import os
import tempfile
import logging
from minio import Minio
from fastapi import UploadFile
from src.config import settings


class MinioStorageBackend:
    """Handles PDF storage in MinIO object storage.

    Wraps the MinIO client to provide upload, download, and delete operations.
    The bucket is created automatically on startup if it does not exist.
    """

    def __init__(self, client: Minio, bucket_name: str) -> None:
        """Connect to MinIO and ensure the target bucket exists."""
        self._client = client
        self._bucket = bucket_name
        
        # Ensure the bucket exists at startup.
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logging.debug(f"Created bucket: {self._bucket}")
            

    async def upload(self, file: UploadFile) -> str:
        """Validate and upload a PDF file to MinIO.

        Streams the file in chunks to avoid loading the entire file into memory.
        Raises ValueError for invalid input, RuntimeError if MinIO rejects the upload.
        Returns the stored filename.
        """
        if not file.filename:
            raise ValueError("Filename is required")
        if file.content_type != "application/pdf" or not file.filename.lower().endswith(".pdf"):
            raise ValueError("Not a PDF")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                while chunk := await file.read(settings.upload_chunk_size):
                    tmp.write(chunk)
                tmp_path = tmp.name
            self._client.fput_object(self._bucket, file.filename, tmp_path, content_type="application/pdf")
            logging.debug(f"Uploaded: {file.filename}")
            
        except Exception as e:
            raise RuntimeError(f"MinIO upload failed: {e}") from e
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
                
        return file.filename

    def delete(self, filename: str) -> None:
        """Permanently remove a file from the bucket."""
        self._client.remove_object(self._bucket, filename)
        logging.debug(f"Deleted: {filename}")

    def download(self, filename: str) -> str:
        """Download a file from MinIO to a local temp file.

        Returns the path to the temp file. The caller is responsible for
        deleting it after use (see IngestionPipeline).
        Raises RuntimeError if the download fails.
        """
        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = tmp.name
            self._client.fget_object(self._bucket, filename, tmp_path)
        except Exception as e:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise RuntimeError(f"MinIO download failed: {e}") from e
        return tmp_path

    def ping_minio(self) -> bool:
        """Return True if MinIO is reachable, False otherwise."""
        try:
            self._client.list_buckets()
            return True
        except Exception:
            return False
