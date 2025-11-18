-- Island Golf Club Booking System Database Schema
-- This schema defines the database structure for the email booking bot

CREATE TABLE IF NOT EXISTS bookings (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    num_players INTEGER NOT NULL DEFAULT 4,
    preferred_date VARCHAR(50),
    preferred_time VARCHAR(50),
    alternate_date VARCHAR(50),
    special_requests TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'provisional',
    total_fee DECIMAL(10, 2),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    course_id VARCHAR(255) NOT NULL DEFAULT 'theisland',
    internal_notes TEXT,
    raw_email_data JSONB,
    CONSTRAINT valid_status CHECK (status IN ('provisional', 'confirmed', 'cancelled', 'completed'))
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_bookings_email ON bookings(email);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_created_at ON bookings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bookings_course_id ON bookings(course_id);
CREATE INDEX IF NOT EXISTS idx_bookings_preferred_date ON bookings(preferred_date);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_bookings_updated_at BEFORE UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
