-- ============================================
-- PO Dataset Schema Migration Script
-- Fixes column name mismatches to match actual schema
-- ============================================

-- Run this script on your PostgreSQL database (clrvw_db)

-- ============================================
-- ACTUAL SCHEMA REFERENCE
-- po_dataset columns:
--   id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
--   file_id INT
--   po_id VARCHAR(50)              <-- NOT po_number
--   po_date DATE
--   vendor_name VARCHAR(255)
--   client_name VARCHAR(255)
--   payment_terms TEXT
--   delivery_terms TEXT
--   currency VARCHAR(10)
--   total_amount NUMERIC(18,2)
--   start_date DATE
--   end_date DATE
--   reference_sow VARCHAR(255)
--   reference_msa VARCHAR(255)
--   quantity NUMERIC(18,2)
--   unit_price NUMERIC(18,2)
--   tax NUMERIC(18,2)
--   tax_breakup JSONB              <-- Not TEXT
--   service_code VARCHAR(100)
--   delivery_location VARCHAR(255)
--   grn_indicator BOOLEAN DEFAULT FALSE  <-- Not TEXT
--   po_status VARCHAR(50)
-- ============================================

-- ============================================
-- NO CHANGES NEEDED
-- ============================================
-- The actual schema already matches the expected types:
-- - po_id is VARCHAR(50) ✓
-- - grn_indicator is BOOLEAN ✓
-- - tax_breakup is JSONB ✓
-- - No active_flag column (correct) ✓
-- - Numeric columns are properly typed ✓

-- ============================================
-- OPTIONAL: Add summary columns to files_dataset
-- Only run if you want to store field-level summaries
-- ============================================

-- Uncomment the following block to add summary columns to files_dataset
/*
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'files_dataset' 
        AND column_name = 'document_type'
    ) THEN
        ALTER TABLE files_dataset ADD COLUMN document_type TEXT;
        RAISE NOTICE 'Added document_type column to files_dataset';
    ELSE
        RAISE NOTICE 'document_type column already exists in files_dataset';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'files_dataset' 
        AND column_name = 'field_name'
    ) THEN
        ALTER TABLE files_dataset ADD COLUMN field_name TEXT;
        RAISE NOTICE 'Added field_name column to files_dataset';
    ELSE
        RAISE NOTICE 'field_name column already exists in files_dataset';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'files_dataset' 
        AND column_name = 'field_value'
    ) THEN
        ALTER TABLE files_dataset ADD COLUMN field_value TEXT;
        RAISE NOTICE 'Added field_value column to files_dataset';
    ELSE
        RAISE NOTICE 'field_value column already exists in files_dataset';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'files_dataset' 
        AND column_name = 'field_status'
    ) THEN
        ALTER TABLE files_dataset ADD COLUMN field_status TEXT;
        RAISE NOTICE 'Added field_status column to files_dataset';
    ELSE
        RAISE NOTICE 'field_status column already exists in files_dataset';
    END IF;
END $$;
*/

-- ============================================
-- Verify current schema
-- ============================================
SELECT 
    table_name,
    column_name,
    data_type,
    character_maximum_length,
    numeric_precision,
    numeric_scale
FROM information_schema.columns
WHERE table_name IN ('po_dataset', 'files_dataset')
ORDER BY table_name, ordinal_position;

-- ============================================
-- Migration Complete
-- ============================================
-- No schema changes needed - code has been updated to match actual schema
-- ============================================
