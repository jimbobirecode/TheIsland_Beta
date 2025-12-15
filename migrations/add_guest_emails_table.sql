-- Migration: Add guest_emails table for logging all inbound emails
-- Date: 2025-12-15
-- Purpose: Track all inbound emails with full content and metadata

-- Guest emails log for all inbound emails
CREATE TABLE IF NOT EXISTS guest_emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    from_email VARCHAR(255) NOT NULL,
    to_email VARCHAR(255),
    subject TEXT,
    body_text TEXT,
    body_html TEXT,
    details JSONB, -- Full email metadata (headers, attachments info, etc)
    received_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    booking_id VARCHAR(255), -- Link to bookings table if applicable
    waitlist_id VARCHAR(50), -- Link to waitlist table if applicable
    email_type VARCHAR(50), -- inquiry, booking_request, staff_confirmation, waitlist_optin, customer_reply, etc
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_guest_emails_message_id ON guest_emails(message_id);
CREATE INDEX IF NOT EXISTS idx_guest_emails_from_email ON guest_emails(from_email);
CREATE INDEX IF NOT EXISTS idx_guest_emails_booking_id ON guest_emails(booking_id);
CREATE INDEX IF NOT EXISTS idx_guest_emails_waitlist_id ON guest_emails(waitlist_id);
CREATE INDEX IF NOT EXISTS idx_guest_emails_received_at ON guest_emails(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_guest_emails_email_type ON guest_emails(email_type);
CREATE INDEX IF NOT EXISTS idx_guest_emails_processed ON guest_emails(processed);
