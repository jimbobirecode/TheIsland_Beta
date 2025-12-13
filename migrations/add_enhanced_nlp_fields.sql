-- Migration: Add enhanced NLP fields to bookings table
-- Date: 2025-12-13
-- Purpose: Support comprehensive email parsing with spaCy + dateparser

-- Add room type for lodging requests
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS room_type VARCHAR(50);

-- Add contact information fields
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50);

-- Add special requests and preferences
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS special_requests TEXT[],
ADD COLUMN IF NOT EXISTS dietary_requirements TEXT[];

-- Add golf experience level
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS golf_experience VARCHAR(50);

-- Add flexibility flags
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS flexible_dates BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS flexible_times BOOLEAN DEFAULT FALSE;

-- Add preferred/alternative time slots
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS preferred_time VARCHAR(50),
ADD COLUMN IF NOT EXISTS alternative_times TEXT[];

-- Add confidence scores for better tracking
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS date_confidence DECIMAL(3, 2),
ADD COLUMN IF NOT EXISTS time_confidence DECIMAL(3, 2),
ADD COLUMN IF NOT EXISTS lodging_confidence DECIMAL(3, 2);

-- Create index for quick lodging request lookups
CREATE INDEX IF NOT EXISTS idx_bookings_hotel_checkin ON bookings(hotel_checkin)
WHERE hotel_checkin IS NOT NULL;

-- Create index for special requests
CREATE INDEX IF NOT EXISTS idx_bookings_golf_experience ON bookings(golf_experience)
WHERE golf_experience IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN bookings.room_type IS 'Type of room requested: single, double, suite';
COMMENT ON COLUMN bookings.special_requests IS 'Array of special requests from guest';
COMMENT ON COLUMN bookings.dietary_requirements IS 'Array of dietary requirements (vegetarian, gluten-free, etc.)';
COMMENT ON COLUMN bookings.golf_experience IS 'Golf skill level: beginner, intermediate, advanced, professional';
COMMENT ON COLUMN bookings.flexible_dates IS 'Whether guest is flexible with dates';
COMMENT ON COLUMN bookings.flexible_times IS 'Whether guest is flexible with tee times';
COMMENT ON COLUMN bookings.date_confidence IS 'Confidence score for extracted date (0.0-1.0)';
COMMENT ON COLUMN bookings.time_confidence IS 'Confidence score for extracted time (0.0-1.0)';
COMMENT ON COLUMN bookings.lodging_confidence IS 'Confidence score for lodging detection (0.0-1.0)';
