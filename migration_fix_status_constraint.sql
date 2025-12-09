-- Migration: Fix status constraint to allow new status values
-- This updates the bookings table to accept: Processing, Inquiry, Requested, Confirmed
-- Run this on production database to fix the issue

-- Step 1: Check current status values in the database
SELECT 'Current status values in database:' as info;
SELECT DISTINCT status, COUNT(*) as count
FROM bookings
GROUP BY status
ORDER BY status;

-- Step 2: No updates needed!
-- The new constraint accepts BOTH uppercase AND lowercase for backwards compatibility
-- This means existing code using lowercase values will continue to work

-- Step 3: Drop the old constraint (if it exists)
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS valid_status;

-- Step 4: Add the new constraint with all valid status values
-- Includes BOTH uppercase and lowercase for backwards compatibility
ALTER TABLE bookings ADD CONSTRAINT valid_status
    CHECK (status IN (
        -- Current flow (uppercase - preferred)
        'Processing',   -- Temporary status while checking availability
        'Inquiry',      -- Initial inquiry received, available times sent
        'Requested',    -- Customer clicked "Book Now" and requested specific time
        'Confirmed',    -- Staff manually confirmed the booking
        'Booked',       -- Legacy: Booked status
        'Pending',      -- Legacy: Pending confirmation
        'Rejected',     -- Legacy: Rejected booking
        'Provisional',  -- Legacy: Provisional booking
        'Cancelled',    -- Booking was cancelled
        'Completed',    -- Booking is complete
        -- Lowercase versions (for backwards compatibility)
        'confirmed', 'provisional', 'cancelled', 'completed', 'booked', 'pending', 'rejected'
    ));

-- Step 5: Verify the constraint was added successfully
SELECT 'Migration complete! Current status values:' as info;
SELECT DISTINCT status, COUNT(*) as count
FROM bookings
GROUP BY status
ORDER BY status;
