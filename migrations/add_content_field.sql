-- Migration: Add content field to bookings
-- Description: Adds content field to store additional booking information
-- Date: 2026-02-07

-- Add content column to bookings table
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS content TEXT;

-- Add comment to document the new field
COMMENT ON COLUMN bookings.content IS 'Additional content or details about the booking from the form';
