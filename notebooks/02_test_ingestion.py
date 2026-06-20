import sys
sys.path.append(".")

from pipeline.ingest import ingest_document
from pipeline.integrity import verify_document

TEST_FILE = r"C:\users\user\desktop\govt projects\PHARMACEUTICAL PRICING INTELLIGENCE\Real docs from NPPA\nppa_ceiling_prices_2008.csv"

print("=== NPPI Layer 1 — End-to-End Test ===\n")

# Test 1: Ingest a real NPPA document
print("--- Test 1: Ingest document ---")
result = ingest_document(
    file_path=TEST_FILE,
    source="https://nppa.gov.in",
    origin="NPPA",
    document_type="CSV",
    document_category="Ceiling Price Schedule",
)
print(f"Result: {result}\n")

# Test 2: Verify integrity of the ingested document
if result["status"] == "STORED":
    print("--- Test 2: Verify integrity ---")
    verify_document(result["doc_id"])
    print()

# Test 3: Try to ingest the same document again — should be rejected as duplicate
print("--- Test 3: Duplicate detection ---")
result2 = ingest_document(
    file_path=TEST_FILE,
    source="https://nppa.gov.in",
    origin="NPPA",
    document_type="CSV",
    document_category="Ceiling Price Schedule",
)
print(f"Result: {result2}\n")

print("=== All tests complete ===")
