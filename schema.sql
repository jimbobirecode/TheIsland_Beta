-- Island Golf Club Booking System Database Schema
-- This schema defines the database structure for the email booking bot

CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    booking_id VARCHAR(255) UNIQUE NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    guest_email VARCHAR(255) NOT NULL,
    dates TEXT,
    date DATE,
    players INTEGER NOT NULL DEFAULT 4,
    total DECIMAL(10, 2),
    status VARCHAR(50) NOT NULL DEFAULT 'provisional',
    intent VARCHAR(255),
    urgency VARCHAR(50),
    confidence DECIMAL(3, 2),
    is_corporate BOOLEAN DEFAULT FALSE,
    company_name VARCHAR(255),
    note TEXT,
    club VARCHAR(255),
    club_name VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    customer_confirmed_at TIMESTAMP,
    message_id VARCHAR(255),
    confirmation_message_id VARCHAR(255),
    tee_time TIME,
    updated_by VARCHAR(255),
    created_by VARCHAR(255),
    hotel_checkin DATE,
    hotel_checkout DATE,
    hotel_nights INTEGER,
    hotel_rooms INTEGER,
    hotel_cost DECIMAL(10, 2),
    lodging_intent VARCHAR(255),
    golf_dates TEXT[],
    golf_courses TEXT[],
    selected_tee_times TEXT[],
    CONSTRAINT valid_status CHECK (status IN ('provisional', 'confirmed', 'cancelled', 'completed'))
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_bookings_booking_id ON bookings(booking_id);
CREATE INDEX IF NOT EXISTS idx_bookings_guest_email ON bookings(guest_email);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_created_at ON bookings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date);
CREATE INDEX IF NOT EXISTS idx_bookings_message_id ON bookings(message_id);

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

-- Waitlist table for tee time requests
CREATE TABLE IF NOT EXISTS waitlist (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(255) UNIQUE NOT NULL,
    guest_email VARCHAR(255) NOT NULL,
    guest_name VARCHAR(255),
    requested_date DATE NOT NULL,
    preferred_time_start TIME,
    preferred_time_end TIME,
    players INTEGER NOT NULL DEFAULT 4,
    flexibility VARCHAR(50) DEFAULT 'flexible', -- strict, flexible, very_flexible
    priority INTEGER DEFAULT 0, -- higher = more priority
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, notified, converted, expired, cancelled
    notes TEXT,
    notified_at TIMESTAMP,
    converted_booking_id VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    club VARCHAR(255),
    CONSTRAINT valid_waitlist_status CHECK (status IN ('pending', 'notified', 'converted', 'expired', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_waitlist_email ON waitlist(guest_email);
CREATE INDEX IF NOT EXISTS idx_waitlist_date ON waitlist(requested_date);
CREATE INDEX IF NOT EXISTS idx_waitlist_status ON waitlist(status);
CREATE INDEX IF NOT EXISTS idx_waitlist_created_at ON waitlist(created_at DESC);

CREATE TRIGGER update_waitlist_updated_at BEFORE UPDATE ON waitlist
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Export logs for notify platform integration
CREATE TABLE IF NOT EXISTS export_logs (
    id SERIAL PRIMARY KEY,
    export_id VARCHAR(255) UNIQUE NOT NULL,
    export_type VARCHAR(50) NOT NULL, -- json, csv, api
    destination VARCHAR(500),
    records_exported INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, completed, failed
    error_message TEXT,
    filters JSONB, -- store filter criteria used
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_export_logs_type ON export_logs(export_type);
CREATE INDEX IF NOT EXISTS idx_export_logs_created_at ON export_logs(created_at DESC);
