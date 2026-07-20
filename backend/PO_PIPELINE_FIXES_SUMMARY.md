# PO Processing Pipeline - End-to-End Fixes Summary

## Overview
Fixed the PO data extraction pipeline to ensure LLM output accuracy is preserved in final stored data, and eliminated PostgreSQL schema errors.

---

## 1. Merge Logic Fix (CRITICAL)

### Problem
Rule-based extraction was overwriting correct LLM values, causing data corruption:
- LLM output: `po_number: "PO-STC-IT-2024-0047"`
- Final output: `po_number: "stc tcs data migration project"` (corrupted)

### Solution
**File: `backend/po_main.py`**

Changed extraction order and merge priority:

**Before:**
- STEP 2: Rule-based extraction (PRIMARY)
- STEP 3: LLM extraction (FALLBACK only for missing fields)
- Merge: Rule-based data takes priority

**After:**
- STEP 2: LLM extraction (PRIMARY)
- STEP 3: Rule-based extraction (FALLBACK)
- Merge: LLM data takes priority, rule-based only fills missing fields

**Key Changes:**
- LLM extraction runs first with full text context
- Rule-based extraction runs as fallback
- Merge logic starts with LLM data, only adds rule-based values for missing fields
- LLM priority fields explicitly protected: `po_number`, `reference_sow`, `reference_msa`, `total_amount`, `service_code`, `quantity`, `unit_price`

---

## 2. Clean Amount Parsing

### Problem
Amount strings like `"USD 1,092,500.00 (@ 15% VAT)"` were parsed incorrectly:
- Mixed value and tax: `1092500.0015` instead of `1092500.00`
- Tax not extracted separately

### Solution
**File: `backend/PO_processing/po_amount_parser.py` (NEW)**

Created dedicated amount parsing module with functions:

- `parse_amount_and_tax(amount_str)` - Extracts amount and tax percentage from formatted strings
- `clean_numeric_value(value)` - Removes currency symbols, text, commas
- `extract_po_amount(text)` - Field-aware amount extraction with labels
- `extract_tax_amount(text)` - Field-aware tax percentage extraction

**Example:**
```python
amount_str = "USD 1,092,500.00 (@ 15% VAT)"
total_amount, tax = parse_amount_and_tax(amount_str)
# Returns: (1092500.0, 15)
```

---

## 3. Regex Extraction Fixes

### Problem
Rule-based extractor was picking wrong values:
- PR numbers extracted as quantity
- Random sentences extracted as unit_price

### Solution
**File: `backend/PO_processing/po_rule_based_extractor.py`**

Improved dedicated extractors:

**a) `_extract_total_amount()`**
- Field-aware patterns with labels (Total Amount, Grand Total, etc.)
- Excludes tax lines from amount extraction
- Fallback to largest monetary value if labeled amount not found

**b) `_extract_tax()`**
- Extracts percentage first (e.g., "15% VAT")
- Falls back to tax amount if percentage not found

**c) `_extract_quantity()`**
- Field-aware patterns with labels (Quantity, Qty, Units, etc.)
- Validates range: `0 < quantity < 10000` (prevents extracting years like 2024)
- Prevents extracting PR numbers as quantity

**d) `_extract_unit_price()`**
- Field-aware patterns with labels (Unit Price, Rate, etc.)
- Validates numeric format
- Prevents extracting random sentences

**e) Updated `_SKIP_IN_GENERIC` set**
- Added `quantity` and `unit_price` to skip generic extraction
- Ensures dedicated extractors are always used

---

## 4. Data Validation Layer

### Problem
No validation before DB insert, allowing corrupted data to be stored.

### Solution
**File: `backend/PO_processing/po_data_validator.py` (NEW)**

Created comprehensive validation module with field-specific validators:

**Validators:**
- `validate_po_number()` - Must start with "PO-" or contain "PO" pattern
- `validate_reference_sow()` - Must contain "SOW-" or "SOW" pattern
- `validate_reference_msa()` - Must contain "MSA-" or "MSA" pattern
- `validate_amount_field()` - Extracts numeric value, handles formatted strings
- `validate_tax_field()` - Extracts percentage from strings
- `validate_quantity()` - Validates numeric and reasonable range
- `validate_unit_price()` - Validates numeric and positive
- `validate_service_code()` - Validates alphanumeric format

**Main Function:**
- `validate_structured_data(structured_data)` - Validates all fields before DB insert
- Returns cleaned data and validation errors
- Fixes corrupted fields by returning cleaned values

---

## 5. PostgreSQL Schema Fix

### Problem
Database schema mismatches causing errors:
- Column "document_type" does not exist in files_dataset
- Text fields (reference_sow, reference_msa, service_code, po_number) defined as numeric columns
- Invalid input syntax for bigint when inserting text values

### Solution
**File: `backend/PO_storage/po_schema_migration.sql` (NEW)**

Generated SQL migration script that:

**a) Adds missing columns to files_dataset:**
```sql
ALTER TABLE files_dataset ADD COLUMN document_type TEXT;
ALTER TABLE files_dataset ADD COLUMN field_name TEXT;
ALTER TABLE files_dataset ADD COLUMN field_value TEXT;
ALTER TABLE files_dataset ADD COLUMN field_status TEXT;
```

**b) Converts incorrect numeric columns to TEXT:**
```sql
ALTER TABLE po_dataset ALTER COLUMN po_number TYPE TEXT;
ALTER TABLE po_dataset ALTER COLUMN reference_sow TYPE TEXT;
ALTER TABLE po_dataset ALTER COLUMN reference_msa TYPE TEXT;
ALTER TABLE po_dataset ALTER COLUMN service_code TYPE TEXT;
```

**c) Ensures numeric columns are properly typed:**
```sql
ALTER TABLE po_dataset ALTER COLUMN total_amount TYPE NUMERIC(15,2);
ALTER TABLE po_dataset ALTER COLUMN quantity TYPE NUMERIC(10,2);
ALTER TABLE po_dataset ALTER COLUMN unit_price TYPE NUMERIC(15,2);
ALTER TABLE po_dataset ALTER COLUMN tax TYPE NUMERIC(5,2);
```

**d) Includes verification query** to check all column types after migration.

---

## 6. Postgres Writer Update

### Problem
Postgres writer wasn't using the new amount parsing module.

### Solution
**File: `backend/PO_storage/po_postgres_writer.py`**

Updated `clean_numeric()` function:
- Now uses `parse_amount_and_tax()` from the new module
- Handles formatted strings like "USD 1,092,500.00 (@ 15% VAT)"
- Falls back to simple cleaning if amount parser fails

---

## 7. Pipeline Integration

### Problem
Validation layer not integrated into main pipeline.

### Solution
**File: `backend/po_main.py`**

Added validation layer as STEP 5:
- Import `validate_structured_data` from new module
- Validate merged structured data after merge step
- Clean and fix corrupted fields before DB insert
- Log validation errors for review
- Continue with cleaned data even if errors exist

**Updated Pipeline Steps:**
1. Text Extraction
2. LLM Extraction (PRIMARY)
3. Rule-based Extraction (FALLBACK)
4. Merge Data (LLM Priority)
5. **Data Validation Layer** (NEW)
6. Existing Validation
7. Summary Generation
8. Structured Data Preparation
9. Combined Match Check
10. Save to PostgreSQL
11. Save to FAISS

---

## Files Modified/Created

### Modified Files:
1. `backend/po_main.py` - Merge logic, pipeline integration
2. `backend/PO_processing/po_rule_based_extractor.py` - Regex fixes
3. `backend/PO_storage/po_postgres_writer.py` - Amount parser integration

### New Files Created:
1. `backend/PO_processing/po_amount_parser.py` - Amount parsing module
2. `backend/PO_processing/po_data_validator.py` - Validation layer
3. `backend/PO_storage/po_schema_migration.sql` - SQL migration script

---

## Deployment Steps

### 1. Run SQL Migration
```bash
# Connect to PostgreSQL database
psql -h 10.1.1.53 -U postgres -d clrvw_db

# Run migration script
\i backend/PO_storage/po_schema_migration.sql
```

### 2. Restart Pipeline
The changes are already integrated into the code. Simply restart the frontend server:
```bash
cd frontend
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 3. Test Upload
Upload a PO file and verify:
- LLM output is preserved in final data
- Amounts are parsed correctly (1092500.00, not 1092500.0015)
- Tax is extracted separately
- No PostgreSQL schema errors
- Validation errors are logged for review

---

## Expected Results

### Before Fix:
- po_number: "stc tcs data migration project" (corrupted)
- reference_sow: "SOW-TCS-STC-DM-" (truncated)
- quantity: "2024-0023" (PR number)
- unit_price: "ly at 15 and shall be borne by stc" (random text)
- total_amount: 1092500.0015 (mixed with tax)
- DB errors: column "document_type" does not exist, invalid bigint syntax

### After Fix:
- po_number: "PO-STC-IT-2024-0047" (from LLM)
- reference_sow: "SOW-TCS-STC-DM-2024-001" (from LLM)
- quantity: None or valid numeric value
- unit_price: None or valid numeric value
- total_amount: 1092500.00 (clean float)
- tax: 15 (separate field)
- No DB errors

---

## Notes

- **LLM Priority**: LLM extraction now runs first and takes priority for all critical fields
- **Rule-based Fallback**: Rule-based extraction only fills missing fields, never overwrites LLM data
- **Field Protection**: Critical fields (po_number, reference_sow, reference_msa, total_amount, service_code, quantity, unit_price) are explicitly protected
- **Validation Layer**: All data is validated before DB insert, with errors logged for review
- **Schema Compatibility**: SQL migration fixes all schema mismatches
- **Backward Compatible**: Changes don't break existing pipeline structure
