-- ============================================================
--  SOW Pipeline v3 — DB Migration
--  Run this ONCE in pgAdmin before running the pipeline.
-- ============================================================

-- 1. Add active_flag column to sow_dataset (if not already present)
--    active_flag = 1 → current/active record
--    active_flag = 0 → old/historical record (overwritten by update)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='sow_dataset' AND column_name='active_flag'
    ) THEN
        ALTER TABLE sow_dataset ADD COLUMN active_flag INT DEFAULT 1;
        COMMENT ON COLUMN sow_dataset.active_flag IS
            '1 = current active record | 0 = historical (replaced by update)';
    END IF;
END$$;

-- 2. Set all existing rows to active_flag = 1 (they are current)
UPDATE sow_dataset SET active_flag = 1 WHERE active_flag IS NULL;

-- 3. Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'sow_dataset'
ORDER BY ordinal_position;

-- Optional: view current data
-- SELECT * FROM sow_dataset ORDER BY active_flag DESC;
