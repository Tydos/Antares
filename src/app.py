from fastapi import FastAPI, File, UploadFile
from fastapi.exceptions import HTTPException
from minio import Minio
from src.upload import upload_pdf

#start services
app = FastAPI()
minio_client = Minio(
    "minio:9000",
    access_key="admin",
    secret_key="admin123",
    secure=False
)
BUCKET_NAME = "pdf-files"
    
@app.get("/")
def home():
    return {"message": "FastAPI server running"}

#tryna upload file
@app.post("/upload")
async def upload(file: UploadFile = File(...,description="attach a pdf file")):
    try:
        url = await upload_pdf(file,minio_client,BUCKET_NAME)
        return{"url":url}
    except ValueError as ve:
        raise HTTPException(status_code=400,detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

