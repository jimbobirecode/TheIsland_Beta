-- Diagnostic: Check what status values currently exist in the database
-- Run this FIRST to see what needs to be migrated

SELECT 'Current status values in database:' as info;
SELECT DISTINCT status, COUNT(*) as count
FROM bookings
GROUP BY status
ORDER BY status;

-- Also show some example rows to understand the data
SELECT 'Sample bookings with each status:' as info;
SELECT status, booking_id, guest_email, created_at
FROM bookings
ORDER BY status, created_at DESC
LIMIT 20;
