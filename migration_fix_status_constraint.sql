-- Migration: Fix status constraint to allow new status values
-- This updates the bookings table to accept: Processing, Inquiry, Requested, Confirmed
-- Run this on production database to fix the issue

-- Drop the old constraint
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS valid_status;

-- Add the new constraint with all valid status values
ALTER TABLE bookings ADD CONSTRAINT valid_status
    CHECK (status IN ('Processing', 'Inquiry', 'Requested', 'Confirmed', 'provisional', 'confirmed', 'cancelled', 'completed'));
