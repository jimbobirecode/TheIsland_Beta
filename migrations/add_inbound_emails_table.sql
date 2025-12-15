-- Migration: Add inbound_emails table for full email storage
-- Date: 2025-12-15
-- Purpose: Store complete email content for learning system and debugging

CREATE TABLE IF NOT EXISTS inbound_emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE,
    from_email VARCHAR(255) NOT NULL,
    to_email VARCHAR(255),
    subject TEXT,
    text_body TEXT,
    html_body TEXT,
    headers TEXT,
    attachments JSONB,
    booking_id VARCHAR(255),
    parsed_data JSONB,
    processing_status VARCHAR(50) DEFAULT 'received',
    error_message TEXT,
    received_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,
    club VARCHAR(100) NOT NULL DEFAULT 'demo'
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_inbound_emails_message_id ON inbound_emails(message_id);
CREATE INDEX IF NOT EXISTS idx_inbound_emails_from_email ON inbound_emails(from_email);
CREATE INDEX IF NOT EXISTS idx_inbound_emails_booking_id ON inbound_emails(booking_id);
CREATE INDEX IF NOT EXISTS idx_inbound_emails_received_at ON inbound_emails(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbound_emails_status ON inbound_emails(processing_status);
CREATE INDEX IF NOT EXISTS idx_inbound_emails_club ON inbound_emails(club);

-- Add comment
COMMENT ON TABLE inbound_emails IS 'Stores complete inbound email content for learning system and debugging';
COMMENT ON COLUMN inbound_emails.parsed_data IS 'JSON of parsed booking data (dates, players, intent, etc)';
COMMENT ON COLUMN inbound_emails.processing_status IS 'Status: received, processed, error, duplicate';
