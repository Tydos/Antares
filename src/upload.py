from minio import Minio
from fastapi import UploadFile
from fastapi.exceptions import HTTPException
from io import BytesIO
import uuid

# Read the file and upload to MinIO, returning the file URL
async def upload_pdf(file: UploadFile, minio_client: Minio, bucket_name: str) -> str:
    
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise ValueError("Not a PDF")
    
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)  # Create bucket if it doesn't exist
        
    file_data = await file.read()  # Read uploaded file content
    file_size = len(file_data)  # Get file size in bytes
    filename = file.filename or f"{uuid.uuid4()}.pdf"  # Use original filename or generate unique one
    
    minio_client.put_object(
        bucket_name=bucket_name,
        object_name=filename,  # Upload file with determined filename
        data=BytesIO(file_data),  # Wrap file bytes in a stream
        length=file_size,  # Specify file size
        content_type="application/pdf"  # Set content type as PDF
    )
    
    url = f"http://minio:9000/{bucket_name}/{filename}"  # Construct accessible file URL
    return url