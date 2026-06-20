import boto3
from deltalake import DeltaTable, write_deltalake
import pyarrow as pa
from datetime import datetime, timezone

# S3 bucket name
BUCKET = "nppi-storage-ap-south-1-590183973586-ap-south-1-an"

# S3 paths for each Delta table
BRONZE_PATH = f"s3://{BUCKET}/bronze"
SILVER_PATH = f"s3://{BUCKET}/silver"
GOLD_PATH = f"s3://{BUCKET}/gold"
CORRUPTION_LOG_PATH = f"s3://{BUCKET}/corruption_log"

# AWS storage options - uses credentials from aws configure
STORAGE_OPTIONS = {
    "AWS_REGION": "ap-south-1",
}

# Bronze table schema
bronze_schema = pa.schema([
    pa.field("doc_id", pa.string()),
    pa.field("sha256_fingerprint", pa.string()),
    pa.field("source", pa.string()),
    pa.field("origin", pa.string()),
    pa.field("arrival_timestamp", pa.timestamp("us", tz="UTC")),
    pa.field("document_type", pa.string()),
    pa.field("document_category", pa.string()),
    pa.field("file_size_bytes", pa.int64()),
    pa.field("s3_path", pa.string()),
    pa.field("processing_status", pa.string()),
])

# Corruption log schema
corruption_log_schema = pa.schema([
    pa.field("log_id", pa.string()),
    pa.field("doc_id", pa.string()),
    pa.field("detected_at", pa.timestamp("us", tz="UTC")),
    pa.field("stored_fingerprint", pa.string()),
    pa.field("actual_fingerprint", pa.string()),
    pa.field("severity", pa.string()),
])

# Silver schema - empty for now, Layer 3 defines it
silver_schema = pa.schema([
    pa.field("doc_id", pa.string()),
])

# Gold schema - empty for now, Layer 4 defines it
gold_schema = pa.schema([
    pa.field("doc_id", pa.string()),
])

def create_empty_table(path, schema, name):
    empty_table = pa.table({field.name: pa.array([], type=field.type) for field in schema})
    write_deltalake(path, empty_table, mode="overwrite", storage_options=STORAGE_OPTIONS)
    print(f"[OK] {name} table created at {path}")

if __name__ == "__main__":
    print("Creating NPPI Delta tables on S3...\n")
    create_empty_table(BRONZE_PATH, bronze_schema, "bronze")
    create_empty_table(SILVER_PATH, silver_schema, "silver")
    create_empty_table(GOLD_PATH, gold_schema, "gold")
    create_empty_table(CORRUPTION_LOG_PATH, corruption_log_schema, "corruption_log")
    print("\nAll tables created successfully.")
