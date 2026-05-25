import os
import boto3
from botocore.config import Config
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# ==========================================
# S3 / MinIO Client Factory
# ==========================================
def get_s3_client():
    """
    Returns a boto3 S3 client.
    - If S3_ENDPOINT_URL is set in .env, connects to local MinIO.
    - Otherwise, connects to official AWS S3 using IAM credentials.
    """
    endpoint_url = os.getenv("S3_ENDPOINT_URL", None)

    return boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        endpoint_url=endpoint_url,  # None = real AWS, set = MinIO
        config=Config(signature_version="s3v4")
    )

BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "terminator-datasets")

# ==========================================
# Request/Response Schemas
# ==========================================
class InitiateUploadRequest(BaseModel):
    filename: str

class PresignPartsRequest(BaseModel):
    upload_id: str
    key: str
    part_numbers: List[int]

class CompletedPart(BaseModel):
    PartNumber: int
    ETag: str

class CompleteUploadRequest(BaseModel):
    upload_id: str
    key: str
    parts: List[CompletedPart]

# ==========================================
# Router
# ==========================================
router = APIRouter(prefix="/api/v1/dataset", tags=["Dataset Upload"])


@router.post("/upload/initiate")
async def initiate_multipart_upload(req: InitiateUploadRequest):
    """
    Step 1: Creates a multipart upload session in S3.
    Returns an upload_id and S3 key to coordinate subsequent part uploads.
    """
    try:
        s3 = get_s3_client()
        key = f"datasets/{req.filename}"
        response = s3.create_multipart_upload(
            Bucket=BUCKET_NAME,
            Key=key,
            ContentType="text/csv"
        )
        return {
            "upload_id": response["UploadId"],
            "key": key,
            "bucket": BUCKET_NAME
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate upload: {str(e)}")


@router.post("/upload/presign-parts")
async def presign_upload_parts(req: PresignPartsRequest):
    """
    Step 2: Generates a unique pre-signed PUT URL for each file chunk.
    The frontend browser uses these URLs to upload directly to S3.
    Each URL expires in 15 minutes.
    """
    try:
        s3 = get_s3_client()
        presigned_parts = []

        for part_number in req.part_numbers:
            url = s3.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": BUCKET_NAME,
                    "Key": req.key,
                    "UploadId": req.upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=900  # 15 minutes
            )
            presigned_parts.append({
                "part_number": part_number,
                "url": url
            })

        return {"parts": presigned_parts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate pre-signed URLs: {str(e)}")


@router.post("/upload/complete")
async def complete_multipart_upload(req: CompleteUploadRequest):
    """
    Step 3: Finalizes the multipart upload by assembling all uploaded chunks.
    S3 stitches together all parts into the final file object.
    """
    try:
        s3 = get_s3_client()
        parts_payload = [
            {"PartNumber": p.PartNumber, "ETag": p.ETag}
            for p in req.parts
        ]
        s3.complete_multipart_upload(
            Bucket=BUCKET_NAME,
            Key=req.key,
            UploadId=req.upload_id,
            MultipartUpload={"Parts": parts_payload}
        )
        return {
            "status": "success",
            "s3_uri": f"s3://{BUCKET_NAME}/{req.key}",
            "key": req.key
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete upload: {str(e)}")


@router.delete("/upload/abort")
async def abort_multipart_upload(upload_id: str, key: str):
    """
    Safety endpoint: Aborts and cleans up an incomplete multipart upload
    to avoid paying for partial/orphaned file chunks in S3.
    """
    try:
        s3 = get_s3_client()
        s3.abort_multipart_upload(
            Bucket=BUCKET_NAME,
            Key=key,
            UploadId=upload_id
        )
        return {"status": "aborted", "upload_id": upload_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to abort upload: {str(e)}")


@router.get("/list")
async def list_uploaded_datasets():
    """
    Lists all datasets currently stored in the S3 bucket.
    Used by the frontend to display previously uploaded files.
    """
    try:
        s3 = get_s3_client()
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix="datasets/")
        files = []
        for obj in response.get("Contents", []):
            files.append({
                "key": obj["Key"],
                "filename": obj["Key"].replace("datasets/", ""),
                "size_mb": round(obj["Size"] / (1024 * 1024), 2),
                "last_modified": obj["LastModified"].isoformat()
            })
        return {"datasets": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list datasets: {str(e)}")

import pandas as pd
import io

@router.get("/load")
async def load_dataset(key: str):
    """
    Downloads a CSV file from S3 and parses it into JSON for the frontend applicant queue.
    """
    try:
        s3 = get_s3_client()
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        
        # Read the file stream into pandas
        csv_data = response['Body'].read()
        df = pd.read_csv(io.BytesIO(csv_data))
        
        # Clean data: Replace NaNs with empty strings or nulls to prevent JSON errors
        df = df.fillna("")
        
        # Convert to list of dictionaries
        records = df.to_dict(orient="records")
        return records
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")

