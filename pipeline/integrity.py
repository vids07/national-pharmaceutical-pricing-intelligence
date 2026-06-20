import uuid
import tempfile
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


def verify_document(doc_id: str) -> dict:
    # Fetch stored record from bronze
    dt = DeltaTable(BRONZE_PATH, storage_options=STORAGE_OPTIONS)
    df = dt.to_pyarrow_table(filters=[("doc_id", "=", doc_id)])

    if len(df) == 0:
        print(f"[ERROR] doc_id={doc_id} not found in bronze table")
        return {"status": "NOT_FOUND", "doc_id": doc_id}

    stored_fingerprint = df["sha256_fingerprint"][0].as_py()
    s3_path = df["s3_path"][0].as_py()

    # s3_path is like s3://bucket/bronze/raw/xxx.csv — extract the key
    s3_key = s3_path.replace(f"s3://{BUCKET}/", "")

    # Download file to a temp location and recalculate fingerprint
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name

    s3_client.download_file(BUCKET, s3_key, tmp_path)
    actual_fingerprint = generate_sha256(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    if actual_fingerprint == stored_fingerprint:
        print(f"[INTACT] doc_id={doc_id} fingerprint matches — document is uncorrupted")
        return {"status": "INTACT", "doc_id": doc_id}

    # Mismatch — log to corruption_log
    print(f"[CORRUPTION DETECTED] doc_id={doc_id}")
    print(f"  stored:   {stored_fingerprint}")
    print(f"  actual:   {actual_fingerprint}")

    log_record = pa.table({
        "log_id": pa.array([str(uuid.uuid4())], pa.string()),
        "doc_id": pa.array([doc_id], pa.string()),
        "detected_at": pa.array([datetime.now(timezone.utc)], pa.timestamp("us", tz="UTC")),
        "stored_fingerprint": pa.array([stored_fingerprint], pa.string()),
        "actual_fingerprint": pa.array([actual_fingerprint], pa.string()),
        "severity": pa.array(["HIGH"], pa.string()),
    })

    write_deltalake(CORRUPTION_LOG_PATH, log_record, mode="append", storage_options=STORAGE_OPTIONS)
    print(f"[LOGGED] Corruption event written to corruption_log")

    return {"status": "CORRUPTED", "doc_id": doc_id}
