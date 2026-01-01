-- Migration: Add booking form fields
-- Description: Adds fields for lead name, caddie requirements, and F&B requirements
-- Date: 2026-01-01

-- Add new columns to bookings table
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS lead_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS caddie_requirements TEXT,
ADD COLUMN IF NOT EXISTS fb_requirements TEXT,
ADD COLUMN IF NOT EXISTS special_requests TEXT;

-- Create index for lead_name for searching
CREATE INDEX IF NOT EXISTS idx_bookings_lead_name ON bookings(lead_name);

-- Add comment to table documenting the new fields
COMMENT ON COLUMN bookings.lead_name IS 'Name of the lead guest for the booking';
COMMENT ON COLUMN bookings.caddie_requirements IS 'Caddie requirements and preferences for the booking';
COMMENT ON COLUMN bookings.fb_requirements IS 'Food and beverage requirements and preferences';
COMMENT ON COLUMN bookings.special_requests IS 'Any special requests or notes from the customer';
