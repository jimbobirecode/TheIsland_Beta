-- Migration: Add Direct Debit Payment Statuses
-- Date: 2025-12-11
-- Description: Add "Pending SEPA" and "Pending BACS" to valid booking statuses for Direct Debit payments

-- Drop the existing constraint
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS valid_status;

-- Add the constraint with new Direct Debit statuses
ALTER TABLE bookings ADD CONSTRAINT valid_status CHECK (status IN (
    'Processing', 'Inquiry', 'Requested', 'Confirmed', 'Booked', 'Pending', 'Rejected', 'Provisional', 'Cancelled', 'Completed',
    'confirmed', 'provisional', 'cancelled', 'completed', 'booked', 'pending', 'rejected',
    'Pending SEPA', 'Pending BACS'
));

-- Verify the constraint was added
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'valid_status';
