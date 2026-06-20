import uuid
import boto3
from datetime import datetime, timezone
from pathlib import Path
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake
from pipeline.fingerprint import generate_sha256

BUCKET = "nppi-storage-ap-south-1-590183973586-ap-south-1-an"
BRONZE_PATH = f"s3://{BUCKET}/bronze"
CORRUPTION_LOG_PATH = f"s3://{BUCKET}/corruption_log"

STORAGE_OPTIONS = {
    "AWS_REGION": "ap-south-1",
}

s3_client = boto3.client("s3", region_name="ap-south-1")


def _fingerprint_exists(fingerprint: str) -> bool:
    try:
        dt = DeltaTable(BRONZE_PATH, storage_options=STORAGE_OPTIONS)
        df = dt.to_pyarrow_table(
            filters=[("sha256_fingerprint", "=", fingerprint)]
        )
        return len(df) > 0
    except Exception:
        return False


def _upload_to_s3(file_path: str, doc_id: str) -> str:
    suffix = Path(file_path).suffix
    s3_key = f"bronze/raw/{doc_id}{suffix}"
    s3_client.upload_file(file_path, BUCKET, s3_key)
    return f"s3://{BUCKET}/{s3_key}"


def ingest_document(
    file_path: str,
    source: str,
    origin: str,
    document_type: str,
    document_category: str,
) -> dict:
    # Generate fingerprint
    fingerprint = generate_sha256(file_path)

    # Duplicate check
    if _fingerprint_exists(fingerprint):
        print(f"[DUPLICATE] Document already exists. Fingerprint: {fingerprint}")
        return {"status": "DUPLICATE_REJECTED", "fingerprint": fingerprint}

    # Upload raw file to S3
    doc_id = str(uuid.uuid4())
    s3_path = _upload_to_s3(file_path, doc_id)
    file_size = Path(file_path).stat().st_size

    # Write metadata to bronze Delta table
    record = pa.table({
        "doc_id": pa.array([doc_id], pa.string()),
        "sha256_fingerprint": pa.array([fingerprint], pa.string()),
        "source": pa.array([source], pa.string()),
        "origin": pa.array([origin], pa.string()),
        "arrival_timestamp": pa.array([datetime.now(timezone.utc)], pa.timestamp("us", tz="UTC")),
        "document_type": pa.array([document_type], pa.string()),
        "document_category": pa.array([document_category], pa.string()),
        "file_size_bytes": pa.array([file_size], pa.int64()),
        "s3_path": pa.array([s3_path], pa.string()),
        "processing_status": pa.array(["STORED"], pa.string()),
    })

    write_deltalake(BRONZE_PATH, record, mode="append", storage_options=STORAGE_OPTIONS)

    print(f"[STORED] doc_id={doc_id} fingerprint={fingerprint}")
    return {"status": "STORED", "doc_id": doc_id, "fingerprint": fingerprint}
