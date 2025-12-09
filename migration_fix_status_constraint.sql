-- Migration: Fix status constraint to allow new status values
-- This updates the bookings table to accept: Processing, Inquiry, Requested, Confirmed
-- Run this on production database to fix the issue

-- Step 1: Check current status values in the database
SELECT 'Current status values in database:' as info;
SELECT DISTINCT status, COUNT(*) as count
FROM bookings
GROUP BY status
ORDER BY status;

-- Step 2: Update any invalid status values to their correct equivalents
-- Map old lowercase values to new capitalized values
UPDATE bookings SET status = 'Confirmed' WHERE status = 'confirmed';
UPDATE bookings SET status = 'Provisional' WHERE LOWER(status) = 'provisional';
UPDATE bookings SET status = 'Cancelled' WHERE LOWER(status) = 'cancelled';
UPDATE bookings SET status = 'Completed' WHERE LOWER(status) = 'completed';

-- Handle any other unexpected values (if any exist)
-- You can check what values need to be updated by running the SELECT above first

-- Step 3: Drop the old constraint (if it exists)
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS valid_status;

-- Step 4: Add the new constraint with all valid status values
ALTER TABLE bookings ADD CONSTRAINT valid_status
    CHECK (status IN (
        'Processing',   -- Temporary status while checking availability
        'Inquiry',      -- Initial inquiry received, available times sent
        'Requested',    -- Customer clicked "Book Now" and requested specific time
        'Confirmed',    -- Staff manually confirmed the booking
        'Provisional',  -- Legacy: Provisional booking
        'Cancelled',    -- Booking was cancelled
        'Completed'     -- Booking is complete
    ));

-- Step 5: Verify the constraint was added successfully
SELECT 'Migration complete! Current status values:' as info;
SELECT DISTINCT status, COUNT(*) as count
FROM bookings
GROUP BY status
ORDER BY status;
