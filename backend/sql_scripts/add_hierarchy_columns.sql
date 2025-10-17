-- Add POD Lead and Calibrator hierarchy columns to pull_requests table
-- Run this SQL script on your PostgreSQL database

ALTER TABLE pull_requests 
ADD COLUMN IF NOT EXISTS pod_lead_email VARCHAR;

ALTER TABLE pull_requests 
ADD COLUMN IF NOT EXISTS calibrator_email VARCHAR;

-- Create indices for faster queries
CREATE INDEX IF NOT EXISTS idx_pr_pod_lead ON pull_requests(pod_lead_email);
CREATE INDEX IF NOT EXISTS idx_pr_calibrator ON pull_requests(calibrator_email);

-- Verify columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'pull_requests' 
AND column_name IN ('pod_lead_email', 'calibrator_email');

