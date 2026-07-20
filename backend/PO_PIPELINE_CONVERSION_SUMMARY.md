# PO Pipeline Conversion Summary

## Overview
The invoice processing pipeline has been successfully converted to handle Purchase Order (PO) documents. This conversion includes renaming all files/directories, updating field mappings, implementing robust error handling, and ensuring production-safe operation.

## File Structure Changes

### Directory Renaming
- `Invoice_*` → `PO_*` (all directories renamed)
- `Invoice_*.py` → `po_*.py` (all Python files renamed)

### Updated Directory Structure
```
backend/
├── PO_config/
│   └── po_settings.py
├── PO_data/
│   ├── input/
│   ├── images/
│   └── output/
├── PO_llm/
│   ├── po_extractor.py
│   ├── po_ollama_client.py
│   └── po_prompt_template.py
├── PO_ocr/
│   ├── po_pdf_to_image.py
│   ├── po_paddle_ocr.py
│   └── po_pdf_text_extractor.py
├── PO_processing/
│   ├── po_cleaner.py
│   ├── po_pdf_detector.py
│   ├── po_rule_based_extractor.py
│   ├── po_summary_generator.py
│   └── po_validator.py
├── PO_storage/
│   ├── po_faiss_store.py
│   ├── po_match_checker.py
│   └── po_postgres_writer.py
└── po_main.py
```

## PO Fields

### Structured Fields (Stored in PostgreSQL - `po_dataset` table)
- `po_number` (required)
- `po_date` (YYYY-MM-DD format)
- `vendor_name`
- `client_name`
- `payment_terms`
- `delivery_terms`
- `currency` (ISO code: USD, INR, EUR, GBP, JPY, CAD, AUD)
- `total_amount` (numeric)
- `start_date` (YYYY-MM-DD format)
- `end_date` (YYYY-MM-DD format)
- `reference_sow`
- `reference_msa`
- `quantity` (numeric)
- `unit_price` (numeric)
- `tax` (numeric)
- `tax_breakup`
- `service_code`
- `delivery_location`
- `grn_indicator`
- `po_status`

### Unstructured Field (Stored in FAISS)
- `description_of_goods_and_services` (not stored in DB)

## Key Changes

### 1. Rule-Based Extraction (`po_rule_based_extractor.py`)
- Updated field aliases for PO-specific terms
- Date normalization to YYYY-MM-DD format
- Dedicated extractors for: `po_date`, `total_amount`, `tax`, `currency`
- Validation logic updated for PO fields

### 2. Validation (`po_validator.py`)
- Validates `po_number` is required
- Validates `total_amount` is numeric
- Validates `currency` is valid ISO code
- Validates dates are in YYYY-MM-DD format

### 3. LLM Integration (`po_main.py`)
- **Rule-based extraction as PRIMARY**
- LLM used only as fallback for missing fields
- LLM data never overwrites rule-based data
- Robust error handling for LLM failures

### 4. Database Connectivity (`po_postgres_writer.py`)
- Added `check_db_connection()` function
- Validates connection before any DB operation
- Pipeline continues despite DB failures
- Does not crash on connection errors

### 5. FAISS Integration (`po_faiss_store.py`)
- Stores `description_of_goods_and_services` only
- Metadata includes: `po_number`, `vendor_name`, `file_id`
- Error handling prevents pipeline crashes
- Updated to use PO_data directory

### 6. Error Handling (Across all files)
- Try-catch blocks around all critical operations
- Pipeline always completes execution
- Rule-based data never lost on failures
- DB/FAISS/LLM failures logged but don't stop pipeline

## Example JSON Output

```json
{
  "structured": {
    "po_number": "PO-2024-001",
    "po_date": "2024-01-15",
    "vendor_name": "ABC Services Inc.",
    "client_name": "XYZ Corporation",
    "payment_terms": "Net 30",
    "delivery_terms": "FOB Destination",
    "currency": "USD",
    "total_amount": 15000.00,
    "start_date": "2024-01-20",
    "end_date": "2024-12-31",
    "reference_sow": "SOW-2024-001",
    "reference_msa": "MSA-2023-001",
    "quantity": 100,
    "unit_price": 150.00,
    "tax": 2700.00,
    "tax_breakup": "CGST: 1350.00, SGST: 1350.00",
    "service_code": "SVC-001",
    "delivery_location": "New York, NY",
    "grn_indicator": "Yes",
    "po_status": "Approved",
    "active_flag": 1,
    "file_id": 123
  },
  "unstructured": {
    "description_of_goods_and_services": "IT consulting services including software development, system integration, and technical support for the enterprise resource planning system implementation."
  }
}
```

## Example Summary Output

| Field Name | Field Value | Status |
|------------|-------------|--------|
| po_number | PO-2024-001 | Valid |
| po_date | 2024-01-15 | Valid |
| vendor_name | ABC Services Inc. | Valid |
| client_name | XYZ Corporation | Valid |
| total_amount | 15000.00 | Valid |
| description_of_goods_and_services | IT consulting services... | Valid |

## Example DB Insert (PostgreSQL)

```sql
INSERT INTO po_dataset (
  po_number, po_date, vendor_name, client_name, payment_terms,
  delivery_terms, currency, total_amount, start_date, end_date,
  reference_sow, reference_msa, quantity, unit_price, tax,
  tax_breakup, service_code, delivery_location, grn_indicator,
  po_status, active_flag, file_id
) VALUES (
  'PO-2024-001', '2024-01-15', 'ABC Services Inc.', 'XYZ Corporation',
  'Net 30', 'FOB Destination', 'USD', 15000.00, '2024-01-20',
  '2024-12-31', 'SOW-2024-001', 'MSA-2023-001', 100, 150.00,
  2700.00, 'CGST: 1350.00, SGST: 1350.00', 'SVC-001',
  'New York, NY', 'Yes', 'Approved', 1, 123
);
```

## Example FAISS Metadata

```python
{
  "po_number": "PO-2024-001",
  "vendor_name": "ABC Services Inc.",
  "file_id": 123,
  "texts": [
    "Description of Goods and Services: IT consulting services including software development, system integration, and technical support for the enterprise resource planning system implementation."
  ]
}
```

## DB Connectivity Handling

```python
def check_db_connection():
    """
    Validate database connection before operations.
    Returns (conn, cursor) if successful, (None, None) if failed.
    """
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")  # Lightweight query
        cursor.fetchone()
        print("[DB] Connection successful")
        return conn, cursor
    except Exception as e:
        print(f"[ERROR] DB CONNECTION FAILED: {e}")
        if conn:
            conn.close()
        return None, None
```

## Production Safety Features

1. **No Pipeline Crashes**: LLM, DB, or FAISS failures do not stop the pipeline
2. **Rule-Based Data Preservation**: LLM never overwrites rule-based extracted data
3. **DB Connectivity Checks**: Connection validated before any DB operation
4. **Comprehensive Error Handling**: Try-catch blocks around all critical operations
5. **Graceful Degradation**: Pipeline continues with partial data if components fail
6. **Logging**: All errors logged with context for debugging

## Configuration

### Database Config (`po_settings.py`)
```python
DB_CONFIG = {
    "host": "10.1.1.53",
    "database": "clrvw_db",
    "user": "postgres",
    "password": "postgres",
    "port": "5432"
}
```

### FAISS Config
```python
FAISS_INDEX_PATH = "po.index"
FAISS_MODEL = "all-MiniLM-L6-v2"
```

### LLM Config
```python
MODEL_NAME = "llama3"
API_URL = "http://10.1.1.219:8080/ollama/api/generate"
API_KEY = "sk-b2fec1202df44aec868c8eab5b767ba6"
```

## Usage

```bash
python po_main.py <file_path> [file_id]
```

Example:
```bash
python po_main.py PO_data/input/po.pdf 123
```

## Validation Rules

- `po_number`: Required, must contain alphanumeric characters
- `total_amount`: Must be numeric
- `currency`: Must be valid ISO code (USD, INR, EUR, GBP, JPY, CAD, AUD)
- Dates (`po_date`, `start_date`, `end_date`): Must be in YYYY-MM-DD format

## Completion Status

All conversion tasks completed:
- ✅ Directories renamed
- ✅ Python files renamed
- ✅ Configuration updated
- ✅ Rule-based extractor updated
- ✅ Validator updated
- ✅ LLM prompt template updated
- ✅ Main pipeline updated with error handling
- ✅ Postgres writer updated with DB connectivity checks
- ✅ FAISS store updated for PO fields
- ✅ Summary generator updated
- ✅ Match checker updated
- ✅ All imports updated
- ✅ __pycache__ cleaned
- ✅ Documentation generated
