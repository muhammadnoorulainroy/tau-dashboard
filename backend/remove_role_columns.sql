-- Remove role-based columns from pull_requests table
-- Run this if you had previously added these columns

ALTER TABLE pull_requests DROP COLUMN IF EXISTS calibrator_email;
ALTER TABLE pull_requests DROP COLUMN IF EXISTS pod_lead_email;

-- Drop indices if they exist
DROP INDEX IF EXISTS idx_pr_calibrator;
DROP INDEX IF EXISTS idx_pr_pod_lead;

