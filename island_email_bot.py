#!/usr/bin/env python3
"""
Golf Club Booking System - Email Bot with Clear Customer Journey
=================================================================

CUSTOMER JOURNEY - CLEAR TERMINOLOGY
=====================================

Stage 1: Inquiry
----------------
- Customer sends initial email asking about availability
- Status: 'Inquiry'
- Email shows: "Status: Inquiry - Awaiting Your Request"
- System sends available tee times with "Book Now" buttons

Stage 2: Request
----------------
- Customer clicks "Book Now" button
- Customer REQUESTS a booking via mailto link
- Status: 'Inquiry' → 'Requested'
- Acknowledgment: "Booking Request Received"
- System sends acknowledgment email
- Note: "Customer sent booking request on [timestamp]"

Stage 3: Confirmation (Manual by Team)
---------------------------------------
- Booking team reviews and CONFIRMS the booking
- Status: 'Requested' → 'Confirmed'
- Team sends confirmation with payment details
- Email shows: "✅ Booking Confirmed"
- Includes payment instructions and important information
- Note: "Booking confirmed by team on [timestamp]"

Additional Flow:
- Customer Replies to Acknowledgment → Status maintained as 'Requested'
  Note: "Customer replied again on [timestamp]"
"""

from flask import Flask, request, jsonify, redirect
import logging
import json
import os
import requests
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool
from typing import List, Dict, Optional
import uuid
import hashlib
import re
from urllib.parse import quote
from threading import Thread
import time
import stripe
from email_storage import save_inbound_email, update_email_processing_status

app = Flask(__name__)

# --- CONFIG ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "clubname@bookings.teemail.io")
FROM_NAME = os.getenv("FROM_NAME", "Golf Club Bookings")
PER_PLAYER_FEE = float(os.getenv("PER_PLAYER_FEE", "325.00"))
BOOKINGS_FILE = os.getenv("BOOKINGS_FILE", "provisional_bookings.jsonl")

# PostgreSQL Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Core API endpoint (for availability checking)
CORE_API_URL = os.getenv("CORE_API_URL", "https://core-new-aku3.onrender.com")

# Dashboard API endpoint
DASHBOARD_API_URL = os.getenv("DASHBOARD_API_URL", "https://theisland-dashboard.onrender.com")

# Default course for bookings (used for API calls to fetch tee times)
DEFAULT_COURSE_ID = os.getenv("DEFAULT_COURSE_ID", "theisland")

# Database club ID (used for dashboard filtering - should match dashboard user's customer_id)
DATABASE_CLUB_ID = os.getenv("DATABASE_CLUB_ID", "demo")

# Tracking email for confirmation webhooks
TRACKING_EMAIL_PREFIX = os.getenv("TRACKING_EMAIL_PREFIX", "clubname")

# Club booking email (appears in mailto links)
CLUB_BOOKING_EMAIL = os.getenv("CLUB_BOOKING_EMAIL", "clubname@bookings.teemail.io")

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
# Success/Cancel URLs now point to app endpoints (can be overridden via env vars)
BOOKING_APP_URL = os.getenv("BOOKING_APP_URL", "https://theisland-email-bot.onrender.com")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", f"{BOOKING_APP_URL}/booking-success")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", f"{BOOKING_APP_URL}/booking-cancelled")

# Initialize Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- DATABASE CONNECTION POOL ---
db_pool = None


# ============================================================================
# BRAND COLORS
# ============================================================================

BRAND_COLORS = {
    'navy_primary': '#10b981',      # Emerald Green (primary brand)
    'royal_blue': '#059669',        # Dark Emerald (gradients, cards)
    'powder_blue': '#3b82f6',       # Bright Blue (accent)
    'charcoal': '#1f2937',          # Text Dark
    'black': '#000000',
    'white': '#ffffff',             # Pure White
    'light_grey': '#f9fafb',        # Background Gray (light)
    'border_grey': '#e5e7eb',
    'text_dark': '#1f2937',         # Text Dark (dark text)
    'text_medium': '#4b5563',
    'text_light': '#6b7280',
    'gradient_start': '#059669',    # Dark Emerald (gradients)
    'gradient_end': '#10b981',      # Emerald Green (primary brand)
    'gold_accent': '#fbbf24',       # Golden Yellow
    'green_success': '#10b981',     # Emerald Green (primary brand)
    'bg_light': '#f9fafb',          # Background Gray (light)
}


# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    try:
        if not DATABASE_URL:
            logging.error("❌ DATABASE_URL not set!")
            return False

        db_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL
        )

        logging.info("✅ Database connection pool created")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to create DB pool: {e}")
        return False


def get_db_connection():
    """Get a connection from the pool"""
    if db_pool:
        return db_pool.getconn()
    return None


def release_db_connection(conn):
    """Release connection back to pool"""
    if db_pool and conn:
        db_pool.putconn(conn)


def generate_booking_id(guest_email: str, timestamp: str = None) -> str:
    """Generate a unique booking ID in format: ISL-YYYYMMDD-XXXX"""
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    date_str = datetime.now().strftime("%Y%m%d")
    hash_input = f"{guest_email}{timestamp}".encode('utf-8')
    hash_digest = hashlib.md5(hash_input).hexdigest()[:8].upper()

    return f"ISL-{date_str}-{hash_digest}"


def save_booking_to_db(booking_data: dict):
    """Save booking to PostgreSQL"""
    conn = None
    try:
        logging.info("💾 SAVING NEW BOOKING TO DATABASE")
        logging.info(f"   Customer: {booking_data.get('guest_email')}")
        logging.info(f"   Players: {booking_data.get('players')}")
        logging.info(f"   Status: {booking_data.get('status')}")
        logging.info(f"   Club: {booking_data.get('club')}")

        conn = get_db_connection()
        if not conn:
            logging.error("❌ No database connection")
            return False

        cursor = conn.cursor()

        if 'booking_id' not in booking_data or not booking_data['booking_id']:
            booking_id = generate_booking_id(
                booking_data['guest_email'],
                booking_data['timestamp']
            )
            booking_data['booking_id'] = booking_id
            logging.info(f"   Generated booking_id: {booking_id}")
        else:
            booking_id = booking_data['booking_id']
            logging.info(f"   Using provided booking_id: {booking_id}")

        cursor.execute("""
            INSERT INTO bookings (
                booking_id, message_id, timestamp, guest_email, dates, date, tee_time,
                players, total, status, note,
                club, club_name
            ) VALUES (
                %(booking_id)s, %(message_id)s, %(timestamp)s, %(guest_email)s, %(dates)s, %(date)s, %(tee_time)s,
                %(players)s, %(total)s, %(status)s, %(note)s,
                %(club)s, %(club_name)s
            )
            ON CONFLICT (booking_id) DO UPDATE SET
                status = EXCLUDED.status,
                note = EXCLUDED.note,
                updated_at = CURRENT_TIMESTAMP
        """, {
            'booking_id': booking_id,
            'message_id': booking_data.get('message_id'),
            'timestamp': booking_data['timestamp'],
            'guest_email': booking_data['guest_email'],
            'dates': Json(booking_data.get('dates', [])),
            'date': booking_data.get('date'),
            'tee_time': booking_data.get('tee_time'),
            'players': booking_data['players'],
            'total': booking_data['total'],
            'status': booking_data['status'],
            'note': booking_data.get('note'),
            'club': booking_data.get('club'),
            'club_name': booking_data.get('club_name')
        })

        rows_affected = cursor.rowcount
        conn.commit()
        cursor.close()

        logging.info(f"✅ BOOKING SAVED - ID: {booking_id}")
        return booking_id

    except Exception as e:
        logging.error(f"❌ FAILED TO SAVE BOOKING: {e}")
        import traceback
        logging.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_db_connection(conn)


def get_booking_by_id(booking_id: str):
    """Get a specific booking by booking_id"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                booking_id as id,
                timestamp,
                guest_email,
                dates,
                date,
                tee_time,
                players,
                total,
                status,
                note,
                club,
                club_name,
                customer_confirmed_at,
                created_at,
                updated_at,
                message_id,
                confirmation_message_id
            FROM bookings
            WHERE booking_id = %s
        """, (booking_id,))

        booking = cursor.fetchone()
        cursor.close()

        if booking:
            booking_dict = dict(booking)

            # Convert datetime objects to strings
            for field in ['timestamp', 'customer_confirmed_at', 'created_at', 'updated_at']:
                if booking_dict.get(field) and hasattr(booking_dict[field], 'strftime'):
                    booking_dict[field] = booking_dict[field].strftime('%Y-%m-%d %H:%M:%S')

            if booking_dict.get('date') and hasattr(booking_dict['date'], 'strftime'):
                booking_dict['date'] = booking_dict['date'].strftime('%Y-%m-%d')

            return booking_dict

        return None

    except Exception as e:
        logging.error(f"❌ Failed to fetch booking {booking_id}: {e}")
        return None
    finally:
        if conn:
            release_db_connection(conn)


def update_booking_in_db(booking_id: str, updates: dict):
    """Update booking in PostgreSQL"""
    conn = None
    try:
        logging.info("="*60)
        logging.info(f"💾 DATABASE UPDATE INITIATED")
        logging.info("="*60)
        logging.info(f"📋 Booking ID: {booking_id}")
        logging.info(f"📝 Updates to apply:")
        for key, value in updates.items():
            logging.info(f"   • {key}: {value}")

        conn = get_db_connection()
        if not conn:
            logging.error("❌ No database connection available")
            return False

        cursor = conn.cursor()

        set_clauses = []
        params = {'booking_id': booking_id}

        # Build update query
        for key, value in updates.items():
            if key in ['status', 'note', 'players', 'total', 'customer_confirmed_at',
                      'confirmation_message_id', 'date', 'tee_time']:
                set_clauses.append(f"{key} = %({key})s")
                params[key] = value

        if not set_clauses:
            logging.warning("⚠️  No valid update fields found")
            cursor.close()
            release_db_connection(conn)
            return False

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        query = f"""
            UPDATE bookings
            SET {', '.join(set_clauses)}
            WHERE booking_id = %(booking_id)s
        """

        cursor.execute(query, params)
        rows_affected = cursor.rowcount
        conn.commit()
        cursor.close()

        if rows_affected == 0:
            logging.error(f"❌ No rows updated! Booking ID may not exist: {booking_id}")
            release_db_connection(conn)
            return False

        logging.info(f"✅ Database updated successfully - {rows_affected} row(s) affected")
        logging.info("="*60)
        return True

    except Exception as e:
        logging.error("="*60)
        logging.error(f"❌ DATABASE UPDATE FAILED")
        logging.error("="*60)
        logging.error(f"❌ Error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_db_connection(conn)


def extract_booking_id(text: str) -> Optional[str]:
    """Extract booking ID from email text"""
    pattern = r'ISL-\d{8}-[A-F0-9]{8}'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None


def extract_message_id(headers: str) -> Optional[str]:
    """Extract Message-ID from email headers string"""
    if not headers:
        return None
    pattern = r'Message-I[Dd]:\s*<?([^>\s]+)>?'
    match = re.search(pattern, headers, re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def is_duplicate_message(message_id: str) -> bool:
    """Check if this message_id has already been processed"""
    if not message_id:
        return False

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logging.warning("⚠️  Cannot check for duplicates - no DB connection")
            return False

        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM bookings
            WHERE message_id = %s OR confirmation_message_id = %s
        """, (message_id, message_id))

        count = cursor.fetchone()[0]
        cursor.close()

        return count > 0

    except Exception as e:
        logging.error(f"❌ Error checking for duplicate message: {e}")
        return False
    finally:
        if conn:
            release_db_connection(conn)


def was_acknowledgment_sent(booking_id: str) -> bool:
    """Check if acknowledgment email was already sent for this booking"""
    booking = get_booking_by_id(booking_id)
    if not booking:
        return False

    note = booking.get('note', '')
    status = booking.get('status', '')

    # Check if status is already 'Requested' or beyond AND acknowledgment was sent
    if status in ['Requested', 'Confirmed']:
        if 'Acknowledgment email sent' in note or 'acknowledgment email sent' in note.lower():
            return True

    return False


def was_confirmation_sent(booking_id: str) -> bool:
    """Check if confirmation email was already sent for this booking"""
    booking = get_booking_by_id(booking_id)
    if not booking:
        return False

    note = booking.get('note', '')
    status = booking.get('status', '')

    # Check if status is 'Confirmed' AND confirmation email was sent
    if status == 'Confirmed':
        if 'Confirmation email sent' in note or 'confirmation email sent' in note.lower():
            return True

    return False


def was_inquiry_email_sent_recently(guest_email: str, dates: list, hours: int = 1) -> Optional[str]:
    """
    Check if we sent an inquiry email to this customer for similar dates recently
    Returns booking_id if found, None otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Look for bookings from same email created within last N hours
        cursor.execute("""
            SELECT booking_id, dates, note, created_at
            FROM bookings
            WHERE guest_email = %s
            AND status = 'Inquiry'
            AND created_at >= NOW() - INTERVAL '%s hours'
            ORDER BY created_at DESC
            LIMIT 1
        """, (guest_email, hours))

        result = cursor.fetchone()
        cursor.close()

        if result:
            # Check if dates are similar
            existing_dates = result.get('dates', [])
            note = result.get('note', '')

            # If dates match or are very similar, consider it a duplicate
            if existing_dates and dates:
                # Simple check: if any date matches
                for date in dates:
                    if date in existing_dates:
                        logging.info(f"   Found recent inquiry for same email and date: {result['booking_id']}")
                        return result['booking_id']

        return None

    except Exception as e:
        logging.error(f"❌ Error checking for recent inquiry: {e}")
        return None
    finally:
        if conn:
            release_db_connection(conn)


def init_database():
    """Create bookings table if it doesn't exist"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logging.error("❌ No database connection available")
            return False

        cursor = conn.cursor()

        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'bookings'
            );
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            logging.info("📋 Creating new bookings table...")
            cursor.execute("""
                CREATE TABLE bookings (
                    id SERIAL PRIMARY KEY,
                    booking_id VARCHAR(255) UNIQUE NOT NULL,
                    message_id VARCHAR(500),
                    confirmation_message_id VARCHAR(500),
                    timestamp TIMESTAMP NOT NULL,
                    guest_email VARCHAR(255) NOT NULL,
                    dates JSONB,
                    date DATE,
                    tee_time VARCHAR(10),
                    players INTEGER NOT NULL,
                    total DECIMAL(10, 2) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'Inquiry',
                    note TEXT,
                    club VARCHAR(100),
                    club_name VARCHAR(255),
                    customer_confirmed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logging.info("✅ Bookings table created")
        else:
            logging.info("📋 Bookings table exists")

            # Check and update status constraint for Direct Debit payments
            logging.info("🔍 Checking status constraint for Direct Debit support...")
            try:
                # Check if constraint exists and get its definition
                cursor.execute("""
                    SELECT pg_get_constraintdef(oid)
                    FROM pg_constraint
                    WHERE conname = 'valid_status' AND conrelid = 'bookings'::regclass;
                """)
                constraint_def = cursor.fetchone()

                # Check if Direct Debit statuses are already in the constraint
                needs_update = False
                if constraint_def:
                    constraint_text = constraint_def[0]
                    if 'Pending SEPA' not in constraint_text or 'Pending BACS' not in constraint_text:
                        needs_update = True
                        logging.info("⚙️  Updating status constraint to add Direct Debit statuses...")
                else:
                    # No constraint exists, add it
                    needs_update = True
                    logging.info("⚙️  Adding status constraint with Direct Debit statuses...")

                if needs_update:
                    # Drop old constraint if it exists
                    cursor.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS valid_status;")

                    # Add updated constraint with Direct Debit statuses
                    cursor.execute("""
                        ALTER TABLE bookings ADD CONSTRAINT valid_status CHECK (status IN (
                            'Processing', 'Inquiry', 'Requested', 'Confirmed', 'Booked', 'Pending',
                            'Rejected', 'Provisional', 'Cancelled', 'Completed',
                            'confirmed', 'provisional', 'cancelled', 'completed', 'booked',
                            'pending', 'rejected',
                            'Pending SEPA', 'Pending BACS'
                        ));
                    """)
                    logging.info("✅ Status constraint updated with Direct Debit statuses")
                else:
                    logging.info("✅ Status constraint already includes Direct Debit statuses")

            except Exception as e:
                logging.warning(f"⚠️  Could not update status constraint: {e}")
                # Continue anyway - constraint might not exist on all deployments

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_email ON bookings(guest_email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_message_id ON bookings(message_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_booking_id ON bookings(booking_id);")

        conn.commit()
        cursor.close()

        logging.info("✅ Database schema ready")
        return True

    except Exception as e:
        logging.error(f"❌ Database initialization error: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_db_connection(conn)


# ============================================================================
# HTML EMAIL TEMPLATE FUNCTIONS
# ============================================================================

def get_email_header():
    """Golf Club branded email header"""
    return f"""
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <title>Golf Club - Booking</title>
        <style type="text/css">
            body {{
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
                font-family: Georgia, 'Times New Roman', serif;
                background-color: {BRAND_COLORS['bg_light']};
            }}
            .email-container {{
                background: #ffffff;
                border-radius: 12px;
                max-width: 800px;
                margin: 20px auto;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background: #ffffff;
                padding: 40px 30px;
                text-align: center;
                border-bottom: 2px solid {BRAND_COLORS['border_grey']};
            }}
            .header-logo {{
                max-width: 200px;
                height: auto;
                margin: 0 auto 20px auto;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .info-box {{
                background: linear-gradient(to right, #f0f9ff 0%, #e0f2fe 100%);
                border-left: 4px solid {BRAND_COLORS['navy_primary']};
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
            }}
            .button-link {{
                background: linear-gradient(135deg, {BRAND_COLORS['navy_primary']} 0%, {BRAND_COLORS['royal_blue']} 100%);
                color: #ffffff !important;
                padding: 15px 40px;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 16px;
                display: inline-block;
                box-shadow: 0 4px 15px rgba(36, 56, 143, 0.3);
            }}
            .tee-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 25px 0;
                border-radius: 8px;
                overflow: hidden;
                border: 1px solid {BRAND_COLORS['border_grey']};
            }}
            .tee-table thead {{
                background: linear-gradient(135deg, {BRAND_COLORS['navy_primary']} 0%, {BRAND_COLORS['royal_blue']} 100%);
                color: #ffffff;
            }}
            .tee-table th {{
                padding: 15px 12px;
                color: #ffffff;
                font-weight: 600;
                text-align: left;
            }}
            .tee-table td {{
                padding: 15px 12px;
                border-bottom: 1px solid {BRAND_COLORS['border_grey']};
            }}
            .footer {{
                background: linear-gradient(135deg, {BRAND_COLORS['gradient_start']} 0%, {BRAND_COLORS['gradient_end']} 100%);
                padding: 30px;
                text-align: center;
                color: #ffffff;
            }}
        </style>
    </head>
    <body>
        <table role="presentation" width="100%" style="background-color: {BRAND_COLORS['bg_light']};">
            <tr>
                <td style="padding: 20px;">
                    <table class="email-container" align="center" width="800">
                        <tr>
                            <td class="header">
                                <img src="https://raw.githubusercontent.com/jimbobirecode/TeeMail-Assests/main/output-onlinepngtools.png" alt="Golf Club" class="header-logo" />
                                <hr style="border: 0; height: 3px; background-color: {BRAND_COLORS['royal_blue']}; margin: 20px auto; width: 100%;" />
                                <p style="margin: 0; color: {BRAND_COLORS['text_medium']}; font-size: 16px; font-weight: 600;">
                                    Visitor Tee Time Booking
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td class="content">
    """


def get_email_footer():
    """Golf Club branded email footer"""
    return f"""
                            </td>
                        </tr>
                        <tr>
                            <td class="footer">
                                <strong style="color: {BRAND_COLORS['gold_accent']}; font-size: 18px;">
                                    Golf Club Bookings
                                </strong>
                                <p style="margin: 10px 0; color: #ffffff; font-size: 14px;">
                                    Tee Time Booking System
                                </p>
                                <p style="margin: 0; color: {BRAND_COLORS['powder_blue']}; font-size: 13px;">
                                    📧 <a href="mailto:{CLUB_BOOKING_EMAIL}" style="color: {BRAND_COLORS['gold_accent']}; text-decoration: none;">{CLUB_BOOKING_EMAIL}</a>
                                </p>
                                <p style="margin-top: 15px; color: {BRAND_COLORS['powder_blue']}; font-size: 12px;">
                                    Powered by TeeMail
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


def create_book_button(booking_link: str, button_text: str = "Reserve Now") -> str:
    """Create HTML for Reserve Now button"""
    return f"""
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin: 0 auto;">
            <tr>
                <td style="border-radius: 8px; background: linear-gradient(135deg, {BRAND_COLORS['navy_primary']} 0%, {BRAND_COLORS['royal_blue']} 100%);">
                    <a href="{booking_link}" style="background: transparent; color: #ffffff !important; padding: 10px 20px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; display: inline-block;">
                        {button_text}
                    </a>
                </td>
            </tr>
        </table>
    """


def build_booking_link(date: str, time: str, players: int, guest_email: str, booking_id: str = None) -> str:
    """
    Generate booking link for Book Now button

    If Stripe is configured, creates a link to /book endpoint that redirects to Stripe checkout
    Otherwise, falls back to mailto link
    """
    if STRIPE_SECRET_KEY:
        # Build Stripe checkout link
        params = {
            'booking_id': booking_id or generate_booking_id(guest_email, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            'date': date,
            'time': time,
            'players': players,
            'email': guest_email
        }

        # URL encode parameters
        query_string = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
        return f"{BOOKING_APP_URL}/book?{query_string}"
    else:
        # Fallback to mailto link if Stripe not configured
        tracking_email = f"{TRACKING_EMAIL_PREFIX}@bookings.teemail.io"

        subject = quote(f"BOOKING REQUEST - {date} at {time}")

        body_lines = [
            f"I would like to book the following tee time:",
            f"",
            f"Booking Details:",
            f"- Date: {date}",
            f"- Time: {time}",
            f"- Players: {players}",
            f"- Green Fee: €{PER_PLAYER_FEE:.0f} per player",
            f"- Total: €{players * PER_PLAYER_FEE:.0f}",
            f"",
            f"Guest Email: {guest_email}",
        ]

        if booking_id:
            body_lines.insert(3, f"- Booking ID: {booking_id}")

        body = quote("\n".join(body_lines))

        # Email goes ONLY to the bot tracking email for processing
        mailto_link = f"mailto:{tracking_email}?subject={subject}&body={body}"
        return mailto_link


def format_inquiry_email(results: list, player_count: int, guest_email: str, booking_id: str = None) -> str:
    """Generate inquiry email with available tee times"""
    html = get_email_header()

    html += f"""
        <p style="color: {BRAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8; margin: 0 0 20px 0;">
            Thank you for your enquiry. We are delighted to present the following available tee times:
        </p>

        <div class="info-box">
            <h3 style="color: {BRAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 15px 0;">
                👥 Booking Details
            </h3>
            <p style="margin: 5px 0;"><strong>Players:</strong> {player_count}</p>
            <p style="margin: 5px 0;"><strong>Green Fee:</strong> €{PER_PLAYER_FEE:.0f} per player</p>
            <p style="margin: 5px 0;"><strong>Status:</strong> <span style="background: #e0f2fe; color: {BRAND_COLORS['navy_primary']}; padding: 4px 10px; border-radius: 15px; font-size: 13px;">Inquiry - Awaiting Your Request</span></p>
        </div>
    """

    # Group results by date
    dates_list = sorted(list(set([r["date"] for r in results])))

    for date in dates_list:
        date_results = [r for r in results if r["date"] == date]

        if not date_results:
            continue

        html += f"""
        <div style="margin: 30px 0;">
            <h2 style="color: {BRAND_COLORS['navy_primary']}; font-size: 22px; font-weight: 700; margin: 0 0 15px 0; padding-bottom: 10px; border-bottom: 3px solid {BRAND_COLORS['gold_accent']};">
                🗓️ {date}
            </h2>
            <table class="tee-table">
                <thead>
                    <tr>
                        <th>Tee Time</th>
                        <th style="text-align: center;">Availability</th>
                        <th>Green Fee</th>
                        <th style="text-align: center;">Booking</th>
                    </tr>
                </thead>
                <tbody>
        """

        for result in date_results:
            time = result["time"]
            booking_link = build_booking_link(date, time, player_count, guest_email, booking_id)
            button_html = create_book_button(booking_link, "Book Now")

            html += f"""
                <tr style="background-color: #f9fafb;">
                    <td><strong style="font-size: 16px; color: {BRAND_COLORS['navy_primary']};">{time}</strong></td>
                    <td style="text-align: center;"><span style="background: #ecfdf5; color: {BRAND_COLORS['green_success']}; padding: 4px 10px; border-radius: 15px; font-size: 13px;">✓ Available</span></td>
                    <td><span style="color: {BRAND_COLORS['royal_blue']}; font-weight: 700;">€{PER_PLAYER_FEE:.0f} pp</span></td>
                    <td style="text-align: center;">
                        {button_html}
                    </td>
                </tr>
            """

        html += """
                </tbody>
            </table>
        </div>
        """

    # Update instructions based on whether Stripe is enabled
    if STRIPE_SECRET_KEY:
        html += f"""
        <div class="info-box" style="margin-top: 30px;">
            <h3 style="color: {BRAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0;">
                💡 How to Book Your Tee Time
            </h3>
            <p style="margin: 5px 0;"><strong>Step 1:</strong> Click "Book Now" for your preferred time</p>
            <p style="margin: 5px 0;"><strong>Step 2:</strong> Complete your payment securely via Stripe</p>
            <p style="margin: 5px 0;"><strong>Step 3:</strong> Receive instant confirmation via email</p>
            <p style="margin-top: 12px; font-style: italic; font-size: 14px;">✅ Secure payment processing • 💳 All major cards accepted • 🔒 SSL encrypted</p>
            <p style="margin-top: 8px; font-style: italic; font-size: 14px;">Questions? Reply to this email and we'll be happy to help.</p>
        </div>
    """
    else:
        html += f"""
        <div class="info-box" style="margin-top: 30px;">
            <h3 style="color: {BRAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0;">
                💡 How to Book Your Tee Time
            </h3>
            <p style="margin: 5px 0;"><strong>Step 1:</strong> Click "Book Now" for your preferred time</p>
            <p style="margin: 5px 0;"><strong>Step 2:</strong> Your email client will open with booking details</p>
            <p style="margin: 5px 0;"><strong>Step 3:</strong> Send the email to request your tee time</p>
            <p style="margin-top: 12px; font-style: italic; font-size: 14px;">Questions? Reply to this email and we'll be happy to help.</p>
        </div>
    """

    html += get_email_footer()
    return html


def format_acknowledgment_email(booking_data: Dict) -> str:
    """Generate acknowledgment email when customer clicks Book Now"""
    booking_id = booking_data.get('id') or booking_data.get('booking_id', 'N/A')
    date = booking_data.get('date', 'TBD')
    time = booking_data.get('tee_time', 'TBD')
    players = booking_data.get('players', booking_data.get('num_players', 0))
    total_fee = players * PER_PLAYER_FEE

    html = get_email_header()

    html += f"""
        <div style="background: linear-gradient(135deg, {BRAND_COLORS['powder_blue']} 0%, #a3b9d9 100%); color: {BRAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
            <h2 style="margin: 0; font-size: 28px; font-weight: 700;">📬 Booking Request Received</h2>
        </div>

        <p style="color: {BRAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8;">
            Thank you for your booking request. We have received your request and will review it shortly.
        </p>

        <div class="info-box">
            <h3 style="color: {BRAND_COLORS['navy_primary']}; font-size: 20px; margin: 0 0 20px 0;">
                📋 Your Booking Request
            </h3>
            <table width="100%" cellpadding="12" cellspacing="0" style="border-collapse: collapse; border: 1px solid {BRAND_COLORS['border_grey']}; border-radius: 8px;">
                <tr style="background-color: {BRAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; font-weight: 600; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        Booking ID
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 600; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {booking_id}
                    </td>
                </tr>
                <tr style="background-color: #ffffff;">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        <strong>📅 Date</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {date}
                    </td>
                </tr>
                <tr style="background-color: {BRAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        <strong>🕐 Time</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {time}
                    </td>
                </tr>
                <tr style="background-color: #ffffff;">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        <strong>👥 Players</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {players}
                    </td>
                </tr>
                <tr style="background-color: #fffbeb;">
                    <td style="padding: 18px 12px; font-weight: 700;">
                        <strong>💶 Total Fee</strong>
                    </td>
                    <td style="padding: 18px 12px; text-align: right; color: {BRAND_COLORS['green_success']}; font-size: 22px; font-weight: 700;">
                        €{total_fee:.2f}
                    </td>
                </tr>
            </table>
        </div>

        <div style="background: #e0f2fe; border-left: 4px solid {BRAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; margin: 30px 0;">
            <p style="margin: 0; font-size: 15px; line-height: 1.7;">
                <strong style="color: {BRAND_COLORS['navy_primary']};">✅ Request Received</strong>
            </p>
            <p style="margin: 10px 0 0 0; font-size: 14px; line-height: 1.7;">
                We have received your booking request and our team will be in touch shortly to confirm your tee time. We'll contact you via email or phone within 24 hours.
            </p>
        </div>

        <p style="color: {BRAND_COLORS['text_medium']}; font-size: 15px; line-height: 1.8; margin: 30px 0 0 0;">
            Thank you for choosing our golf club.
        </p>

        <p style="color: {BRAND_COLORS['text_medium']}; font-size: 14px; margin: 20px 0 0 0;">
            Best regards,<br>
            <strong style="color: {BRAND_COLORS['navy_primary']};">Golf Club Bookings Team</strong>
        </p>
    """

    html += get_email_footer()
    return html


def format_confirmation_email(booking_data: Dict) -> str:
    """Generate confirmation email when booking team confirms the booking (Stage 3)"""
    booking_id = booking_data.get('id') or booking_data.get('booking_id', 'N/A')
    date = booking_data.get('date', 'TBD')
    time = booking_data.get('tee_time', 'TBD')
    players = booking_data.get('players', booking_data.get('num_players', 0))
    total_fee = players * PER_PLAYER_FEE

    html = get_email_header()

    html += f"""
        <div style="background: linear-gradient(135deg, {BRAND_COLORS['green_success']} 0%, #1f4d31 100%); color: {BRAND_COLORS['white']}; padding: 25px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
            <h2 style="margin: 0; font-size: 28px; font-weight: 700;">✅ Booking Confirmed</h2>
        </div>

        <p style="color: {BRAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8;">
            Congratulations! Your booking has been confirmed.
        </p>

        <div class="info-box" style="border: 2px solid {BRAND_COLORS['green_success']};">
            <h3 style="color: {BRAND_COLORS['navy_primary']}; font-size: 20px; margin: 0 0 20px 0;">
                📋 Confirmed Booking Details
            </h3>
            <table width="100%" cellpadding="12" cellspacing="0" style="border-collapse: collapse; border: 1px solid {BRAND_COLORS['border_grey']}; border-radius: 8px;">
                <tr style="background-color: {BRAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; font-weight: 600; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        Booking ID
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 600; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {booking_id}
                    </td>
                </tr>
                <tr style="background-color: #ffffff;">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        <strong>📅 Date</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; color: {BRAND_COLORS['navy_primary']}; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {date}
                    </td>
                </tr>
                <tr style="background-color: {BRAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        <strong>🕐 Tee Time</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; color: {BRAND_COLORS['navy_primary']}; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {time}
                    </td>
                </tr>
                <tr style="background-color: #ffffff;">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        <strong>👥 Number of Players</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {players}
                    </td>
                </tr>
                <tr style="background-color: #fffbeb; border: 2px solid {BRAND_COLORS['gold_accent']};">
                    <td style="padding: 18px 12px; font-weight: 700;">
                        <strong style="font-size: 16px;">💶 Total Amount Due</strong>
                    </td>
                    <td style="padding: 18px 12px; text-align: right; color: {BRAND_COLORS['green_success']}; font-size: 24px; font-weight: 700;">
                        €{total_fee:.2f}
                    </td>
                </tr>
            </table>
        </div>

        <div style="background: linear-gradient(to right, #fffbeb 0%, #fef3c7 100%); border-left: 4px solid {BRAND_COLORS['gold_accent']}; padding: 20px; border-radius: 8px; margin: 30px 0;">
            <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>💳 Payment Details</strong></h3>
            <p style="margin: 0 0 10px 0; font-size: 15px; line-height: 1.7;">
                <strong>Payment Method:</strong> Bank Transfer or Card Payment
            </p>
            <p style="margin: 0 0 10px 0; font-size: 15px; line-height: 1.7;">
                <strong>When:</strong> Payment is required to secure your booking
            </p>
            <p style="margin: 0 0 10px 0; font-size: 15px; line-height: 1.7;">
                <strong>Bank Details:</strong> Please contact us for bank transfer details
            </p>
            <p style="margin: 10px 0 0 0; font-size: 14px; color: {BRAND_COLORS['text_medium']}; font-style: italic;">
                💡 For card payment or bank transfer details, please reply to this email.
            </p>
        </div>

        <div style="background: #e0f2fe; border-left: 4px solid {BRAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; margin: 30px 0;">
            <h3 style="margin: 0 0 10px 0; color: {BRAND_COLORS['navy_primary']};">📍 Important Information</h3>
            <ul style="margin: 10px 0 0 0; padding-left: 20px; font-size: 14px; line-height: 1.8;">
                <li>Please arrive <strong>30 minutes before</strong> your tee time</li>
                <li>Please bring proof of handicap (if applicable)</li>
                <li>Cancellations must be made at least 48 hours in advance</li>
                <li>Weather permitting - we'll contact you if conditions are unsuitable</li>
            </ul>
        </div>

        <p style="color: {BRAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8; margin: 30px 0;">
            We look forward to welcoming you to our golf club. If you have any questions, please don't hesitate to contact us.
        </p>

        <div style="text-align: center; margin: 30px 0; padding: 20px; background-color: {BRAND_COLORS['light_grey']}; border-radius: 8px;">
            <p style="margin: 0 0 10px 0; color: {BRAND_COLORS['text_medium']}; font-size: 14px;">Contact Us</p>
            <p style="margin: 5px 0;"><strong style="color: {BRAND_COLORS['navy_primary']};">📧 Email:</strong> {FROM_EMAIL}</p>
        </div>

        <p style="color: {BRAND_COLORS['text_medium']}; font-size: 14px; margin: 20px 0 0 0;">
            Best regards,<br>
            <strong style="color: {BRAND_COLORS['navy_primary']};">Golf Club Bookings Team</strong>
        </p>
    """

    html += get_email_footer()
    return html


def format_no_availability_email(player_count: int, guest_email: str = None, dates: list = None, preferred_time: str = None) -> str:
    """Generate email when no availability found - includes waitlist opt-in"""
    from urllib.parse import quote

    html = get_email_header()

    html += f"""
        <p style="color: {BRAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8;">
            Thank you for your enquiry regarding tee times at <strong style="color: {BRAND_COLORS['navy_primary']};">Golf Club</strong>.
        </p>

        <div style="background: #fef2f2; border-left: 4px solid #dc2626; border-radius: 8px; padding: 20px; margin: 25px 0;">
            <h3 style="color: #dc2626; font-size: 18px; margin: 0 0 12px 0;">
                ⚠️ No Availability Found
            </h3>
            <p style="margin: 0;">
                Unfortunately, we do not have availability for <strong>{player_count} player(s)</strong> on your requested dates.
            </p>
        </div>
    """

    # Add Waitlist Opt-In Section
    if dates and guest_email:
        dates_str = ', '.join(dates) if isinstance(dates, list) else str(dates)
        time_str = preferred_time or "Flexible"

        # Create mailto link for waitlist opt-in
        waitlist_subject = quote(f"JOIN WAITLIST - {dates_str} - {time_str} - {player_count} players")
        waitlist_body = quote(f"""I would like to join the waitlist for:

Date(s): {dates_str}
Preferred Time: {time_str}
Players: {player_count}

Please notify me if availability becomes available.

Thank you.""")

        waitlist_mailto = f"mailto:{FROM_EMAIL}?subject={waitlist_subject}&body={waitlist_body}"

        html += f"""
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); border-radius: 12px; padding: 25px; margin: 25px 0; text-align: center;">
            <h3 style="color: #ffffff; margin: 0 0 15px 0; font-size: 20px;">
                <span style="margin-right: 8px;">📋</span>Join Our Waitlist
            </h3>
            <p style="color: #dbeafe; margin: 0 0 20px 0; font-size: 15px;">
                Click below to be notified if availability opens up for your requested date.
                We'll automatically check every few hours and email you as soon as a tee time becomes available.
            </p>
            <div style="background: #ffffff; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                <p style="color: #1e3a8a; margin: 0; font-size: 14px;">
                    <strong>Date:</strong> {dates_str}<br>
                    <strong>Time:</strong> {time_str}<br>
                    <strong>Players:</strong> {player_count}
                </p>
            </div>
            <a href="{waitlist_mailto}"
               style="display: inline-block; background: #10b981; color: white; padding: 14px 35px;
                      border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 16px;
                      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);">
                Join Waitlist - Get Notified
            </a>
            <p style="color: #93c5fd; margin: 15px 0 0 0; font-size: 12px;">
                You'll receive an email as soon as we find availability
            </p>
        </div>
        """

    html += f"""
        <div class="info-box">
            <h3 style="color: {BRAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0;">
                📞 Please Contact Us
            </h3>
            <p style="margin: 5px 0;">We would be delighted to assist you in finding alternative dates:</p>
            <p style="margin: 8px 0;"><strong>Email:</strong> <a href="mailto:{CLUB_BOOKING_EMAIL}" style="color: {BRAND_COLORS['navy_primary']};">{CLUB_BOOKING_EMAIL}</a></p>
        </div>

        <p style="color: {BRAND_COLORS['text_medium']}; font-size: 15px; line-height: 1.8; margin: 20px 0 0 0;">
            We look forward to welcoming you to our golf club.
        </p>
    """

    html += get_email_footer()
    return html


def format_inquiry_received_email(parsed: Dict, guest_email: str, booking_id: str = None) -> str:
    """Generate fallback email when API unavailable or no dates provided"""
    html = get_email_header()

    player_count = parsed.get('players', 4)
    dates = parsed.get('dates', [])

    html += f"""
        <div style="background: linear-gradient(135deg, {BRAND_COLORS['powder_blue']} 0%, #a3b9d9 100%); color: {BRAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
            <h2 style="margin: 0; font-size: 28px; font-weight: 700;">📧 Inquiry Received</h2>
        </div>

        <p style="color: {BRAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8;">
            Thank you for your tee time inquiry at <strong style="color: {BRAND_COLORS['navy_primary']};">Golf Club</strong>.
        </p>

        <div class="info-box">
            <h3 style="color: {BRAND_COLORS['navy_primary']}; font-size: 20px; margin: 0 0 20px 0;">
                📋 Your Inquiry Details
            </h3>
            <table width="100%" cellpadding="12" cellspacing="0" style="border-collapse: collapse; border: 1px solid {BRAND_COLORS['border_grey']}; border-radius: 8px;">
    """

    if booking_id:
        html += f"""
                <tr style="background-color: {BRAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; font-weight: 600; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        Inquiry ID
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 600; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {booking_id}
                    </td>
                </tr>
        """

    if dates:
        dates_str = ', '.join(dates)
        html += f"""
                <tr style="background-color: #ffffff;">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        <strong>📅 Requested Dates</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {dates_str}
                    </td>
                </tr>
        """

    html += f"""
                <tr style="background-color: {BRAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        <strong>👥 Players</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {BRAND_COLORS['border_grey']};">
                        {player_count}
                    </td>
                </tr>
                <tr style="background-color: #fffbeb;">
                    <td style="padding: 18px 12px; font-weight: 700;">
                        <strong>💶 Estimated Green Fee</strong>
                    </td>
                    <td style="padding: 18px 12px; text-align: right; color: {BRAND_COLORS['royal_blue']}; font-size: 22px; font-weight: 700;">
                        €{player_count * PER_PLAYER_FEE:.2f}
                    </td>
                </tr>
            </table>
        </div>

        <div style="background: #e0f2fe; border-left: 4px solid {BRAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; margin: 30px 0;">
            <p style="margin: 0; font-size: 15px; line-height: 1.7;">
                <strong style="color: {BRAND_COLORS['navy_primary']};">📞 What Happens Next:</strong>
            </p>
            <p style="margin: 10px 0 0 0; font-size: 14px; line-height: 1.7;">
                Our team has received your inquiry and will check availability for your requested dates. We'll respond within 24 hours with available tee times and booking options.
            </p>
        </div>

        <div class="info-box">
            <h3 style="color: {BRAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0;">
                📞 Contact Us Directly
            </h3>
            <p style="margin: 5px 0;">For immediate assistance, please contact us:</p>
            <p style="margin: 8px 0;"><strong>Email:</strong> <a href="mailto:{CLUB_BOOKING_EMAIL}" style="color: {BRAND_COLORS['navy_primary']};">{CLUB_BOOKING_EMAIL}</a></p>
        </div>

        <p style="color: {BRAND_COLORS['text_medium']}; font-size: 15px; line-height: 1.8; margin: 30px 0 0 0;">
            Thank you for choosing our golf club.
        </p>

        <p style="color: {BRAND_COLORS['text_medium']}; font-size: 14px; margin: 20px 0 0 0;">
            Best regards,<br>
            <strong style="color: {BRAND_COLORS['navy_primary']};">Golf Club Bookings Team</strong>
        </p>
    """

    html += get_email_footer()
    return html


# ============================================================================
# EMAIL SENDING FUNCTION
# ============================================================================

def send_email_sendgrid(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via SendGrid"""
    try:
        logging.info(f"📧 Sending email to: {to_email}")
        logging.info(f"   Subject: {subject}")

        message = Mail(
            from_email=Email(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_body)
        )

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        logging.info(f"✅ Email sent successfully")
        logging.info(f"   Status code: {response.status_code}")
        return True

    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False


# ============================================================================
# BACKGROUND PROCESSING FUNCTIONS
# ============================================================================

def process_staff_confirmation_async(booking_id: str, booking: Dict):
    """
    Process staff confirmation in background thread - sends confirmation email
    This runs AFTER we've already returned 200 to the webhook
    """
    try:
        logging.info(f"🔄 Background processing started for staff confirmation {booking_id}")

        customer_email = booking.get('guest_email')

        if customer_email:
            if not was_confirmation_sent(booking_id):
                # Send confirmation email with payment details
                logging.info(f"   Sending confirmation email to {customer_email}...")
                html_email = format_confirmation_email(booking)
                subject_line = "Booking Confirmed - Golf Club"
                send_email_sendgrid(customer_email, subject_line, html_email)

                # Update note to reflect confirmation email sent
                conf_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                existing_note = booking.get('note', '')
                update_booking_in_db(booking_id, {
                    'note': f"{existing_note}\nConfirmation email sent on {conf_timestamp}"
                })

                logging.info(f"✅ Confirmation email sent successfully for {booking_id}")
            else:
                logging.warning(f"   ⚠️  Confirmation email already sent for {booking_id} - skipping")
        else:
            logging.warning(f"   ⚠️  No customer email found for {booking_id}")

        logging.info(f"✅ Background processing completed for staff confirmation {booking_id}")

    except Exception as e:
        logging.error(f"❌ Background processing error for staff confirmation {booking_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())

        try:
            existing_note = booking.get('note', '')
            update_booking_in_db(booking_id, {
                'note': f"{existing_note}\nError sending confirmation email: {str(e)}"
            })
        except:
            pass


def process_booking_request_async(booking_id: str, sender_email: str, timestamp: str):
    """
    Process booking request in background thread - sends acknowledgment email
    This runs AFTER we've already returned 200 to the webhook
    """
    try:
        logging.info(f"🔄 Background processing started for booking request {booking_id}")

        if not was_acknowledgment_sent(booking_id):
            # Get fresh booking data
            booking_data = get_booking_by_id(booking_id)

            if booking_data:
                # Send acknowledgment email
                logging.info(f"   Sending acknowledgment email to {sender_email}...")
                html_email = format_acknowledgment_email(booking_data)
                subject_line = "Your Booking Request - Golf Club"
                send_email_sendgrid(sender_email, subject_line, html_email)

                # Update note to reflect acknowledgment sent
                ack_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                update_booking_in_db(booking_id, {
                    'note': f"Customer sent booking request on {timestamp}\nAcknowledgment email sent on {ack_timestamp}"
                })

                logging.info(f"✅ Acknowledgment email sent successfully for {booking_id}")
            else:
                logging.error(f"   ❌ Could not retrieve booking data for {booking_id}")
        else:
            logging.warning(f"   ⚠️  Acknowledgment email already sent for {booking_id} - skipping")

        logging.info(f"✅ Background processing completed for booking request {booking_id}")

    except Exception as e:
        logging.error(f"❌ Background processing error for booking request {booking_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())

        try:
            existing_note = f"Customer sent booking request on {timestamp}"
            update_booking_in_db(booking_id, {
                'note': f"{existing_note}\nError sending acknowledgment email: {str(e)}"
            })
        except:
            pass


def process_inquiry_async(sender_email: str, parsed: Dict, booking_id: str, dates: list, players: int):
    """
    Process inquiry in background thread - checks availability and sends email
    This runs AFTER we've already returned 200 to the webhook
    """
    try:
        logging.info(f"🔄 Background processing started for booking {booking_id}")

        if dates:
            try:
                # Make the API call (can take up to 120 seconds)
                api_url = f"{CORE_API_URL}/check_availability"
                payload = {
                    'course_id': DEFAULT_COURSE_ID,
                    'dates': dates,
                    'players': players
                }

                logging.info(f"   🔗 Calling Core API: {api_url}")
                logging.info(f"   📦 Payload: {payload}")

                # Make the API call with retry logic
                max_retries = 2
                for attempt in range(max_retries + 1):
                    try:
                        logging.info(f"   🔄 Attempt {attempt + 1}/{max_retries + 1}")
                        response = requests.post(
                            api_url,
                            json=payload,
                            timeout=120
                        )

                        logging.info(f"   ✅ Core API responded with status: {response.status_code}")

                        # If successful or not a 502, break the retry loop
                        if response.status_code != 502:
                            break

                        # If 502 and we have retries left, wait and try again
                        if attempt < max_retries:
                            logging.warning(f"   ⚠️  Got 502, retrying (attempt {attempt + 2}/{max_retries + 1})...")
                            time.sleep(10)  # Increased delay from 5s to 10s
                    except requests.Timeout:
                        logging.error(f"   ❌ Timeout on attempt {attempt + 1}")
                        if attempt == max_retries:
                            raise
                        logging.info(f"   ⏳ Waiting 10 seconds before retry...")
                        time.sleep(10)

                # Log response details for debugging
                if response.status_code != 200:
                    logging.error(f"   ❌ API Error Response:")
                    logging.error(f"      Status: {response.status_code}")
                    try:
                        logging.error(f"      Body: {response.text[:500]}")
                    except:
                        pass

                if response.status_code == 200:
                    api_data = response.json()
                    results = api_data.get('results', [])
                    logging.info(f"   📊 API returned {len(results)} results")

                    if results:
                        # Send inquiry email with available times
                        logging.info(f"   ✅ Found {len(results)} available times")
                        html_email = format_inquiry_email(results, players, sender_email, booking_id)
                        subject_line = "Available Tee Times at Golf Club"
                        send_email_sendgrid(sender_email, subject_line, html_email)

                        # Update status
                        update_booking_in_db(booking_id, {
                            'status': 'Inquiry',
                            'note': 'Initial inquiry received. Available times sent.'
                        })
                    else:
                        # No availability
                        logging.info(f"   ⚠️  No availability found")
                        html_email = format_no_availability_email(players, guest_email=sender_email, dates=dates)
                        subject_line = "Tee Time Availability - Golf Club"
                        send_email_sendgrid(sender_email, subject_line, html_email)

                        update_booking_in_db(booking_id, {
                            'status': 'Inquiry',
                            'note': 'Initial inquiry received. No availability found.'
                        })
                else:
                    logging.warning(f"   API returned non-200 status: {response.status_code}")
                    # Send fallback email
                    html_email = format_inquiry_received_email(parsed, sender_email, booking_id)
                    subject_line = "Tee Time Inquiry - Golf Club"
                    send_email_sendgrid(sender_email, subject_line, html_email)

                    update_booking_in_db(booking_id, {
                        'status': 'Inquiry',
                        'note': 'Initial inquiry received. API unavailable - manual follow-up needed.'
                    })

            except requests.RequestException as e:
                logging.error(f"   ❌ API error: {e}")
                # Send fallback email
                html_email = format_inquiry_received_email(parsed, sender_email, booking_id)
                subject_line = "Tee Time Inquiry - Golf Club"
                send_email_sendgrid(sender_email, subject_line, html_email)

                update_booking_in_db(booking_id, {
                    'status': 'Inquiry',
                    'note': f'Initial inquiry received. API error: {str(e)}'
                })
        else:
            # No dates found - send "please provide dates" email
            logging.info(f"   ℹ️  No dates provided")
            html_email = format_inquiry_received_email(parsed, sender_email, booking_id)
            subject_line = "Tee Time Inquiry - Golf Club"
            send_email_sendgrid(sender_email, subject_line, html_email)

            update_booking_in_db(booking_id, {
                'status': 'Inquiry',
                'note': 'Initial inquiry received. No dates provided - awaiting customer response.'
            })

        logging.info(f"✅ Background processing completed for booking {booking_id}")

    except Exception as e:
        logging.error(f"❌ Background processing error for {booking_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())

        # Try to update booking with error status
        try:
            update_booking_in_db(booking_id, {
                'status': 'Inquiry',
                'note': f'Error during processing: {str(e)}'
            })
        except:
            pass


# ============================================================================
# EMAIL DETECTION FUNCTIONS
# ============================================================================

def is_booking_request(subject: str, body: str) -> bool:
    """Detect if this is a booking request (customer clicked Book Now)"""
    subject_lower = subject.lower() if subject else ""
    body_lower = body.lower() if body else ""

    # Check for "BOOKING REQUEST" in subject
    if "booking request" in subject_lower:
        logging.info("🎯 Detected 'BOOKING REQUEST' in subject")
        return True

    # Check if it contains a booking ID (means it's a reply/request)
    has_booking_ref = extract_booking_id(body) or extract_booking_id(subject)
    booking_keywords = ['booking request', 'book now', 'reserve', 'confirm booking']
    has_booking_keyword = any(keyword in body_lower or keyword in subject_lower for keyword in booking_keywords)

    if has_booking_ref and has_booking_keyword:
        logging.info("🎯 Detected booking reference + booking keywords")
        return True

    return False


def is_customer_reply(subject: str, body: str) -> bool:
    """Detect if this is a customer replying to an acknowledgment"""
    subject_lower = subject.lower() if subject else ""

    # Check if it's a reply (Re:)
    if subject_lower.startswith('re:'):
        logging.info("🎯 Detected 'Re:' in subject (customer reply)")
        return True

    return False


def is_staff_confirmation(subject: str, body: str, from_email: str) -> bool:
    """Detect if this is a staff member manually confirming a booking (Stage 3)"""
    subject_lower = subject.lower() if subject else ""
    body_lower = body.lower() if body else ""

    # Check if email is from staff domain (bookings@bookings.teemail.io or similar)
    # For now, we'll detect based on keywords since staff will manually trigger this
    confirmation_keywords = ['confirm booking', 'confirmed', 'approve booking', 'booking confirmed']

    # Check for CONFIRM keyword and booking ID
    has_confirm = any(keyword in subject_lower or keyword in body_lower for keyword in confirmation_keywords)
    has_booking_ref = extract_booking_id(body) or extract_booking_id(subject)

    if has_confirm and has_booking_ref:
        logging.info("🎯 Detected staff confirmation request")
        return True

    return False


# ============================================================================
# ENHANCED EMAIL PARSING WITH NLP
# ============================================================================

try:
    from enhanced_nlp import parse_booking_email, IntentType, UrgencyLevel
    ENHANCED_NLP_AVAILABLE = True
except ImportError:
    ENHANCED_NLP_AVAILABLE = False
    logging.warning("Enhanced NLP module not available, using legacy parsing")


def parse_email_enhanced(subject: str, body: str, from_email: str = "", from_name: str = "") -> Dict:
    """
    Enhanced email parsing using comprehensive NLP
    Returns enriched data including tee times, lodging, and more
    """
    if not ENHANCED_NLP_AVAILABLE:
        # Fallback to simple parsing
        return parse_email_simple(subject, body)

    try:
        # Use enhanced NLP parser
        entity = parse_booking_email(body, subject, from_email, from_name)

        # Convert to backward-compatible format
        result = {
            'players': entity.player_count or 4,  # Default to 4
            'dates': entity.booking_dates,
            'preferred_date': entity.preferred_date,
            'tee_times': entity.tee_times,
            'preferred_time': entity.preferred_time,
            'flexible_dates': entity.flexible_dates,
            'flexible_times': entity.flexible_times,

            # Lodging information (NEW)
            'lodging_requested': entity.lodging_requested,
            'check_in_date': entity.check_in_date,
            'check_out_date': entity.check_out_date,
            'num_nights': entity.num_nights,
            'num_rooms': entity.num_rooms,
            'room_type': entity.room_type,

            # Contact information
            'contact_name': entity.contact_name,
            'contact_email': entity.contact_email,
            'contact_phone': entity.contact_phone,

            # Additional details
            'special_requests': entity.special_requests,
            'dietary_requirements': entity.dietary_requirements,
            'golf_experience': entity.golf_experience,

            # Intent and urgency
            'intent': entity.intent.value if entity.intent else 'unknown',
            'urgency': entity.urgency.value if entity.urgency else 'unknown',

            # Confidence scores
            'date_confidence': entity.date_confidence,
            'time_confidence': entity.time_confidence,
            'lodging_confidence': entity.lodging_confidence,

            # Raw data for debugging
            'raw_dates': entity.raw_dates,
            'raw_times': entity.raw_times,
            'extracted_entities': entity.extracted_entities,
        }

        logging.info(f"✨ Enhanced NLP parsing: {len(entity.booking_dates)} dates, "
                    f"{len(entity.tee_times)} times, "
                    f"lodging: {entity.lodging_requested}, "
                    f"intent: {entity.intent.value}, "
                    f"urgency: {entity.urgency.value}")

        return result

    except Exception as e:
        logging.error(f"Enhanced NLP parsing failed: {e}", exc_info=True)
        # Fallback to simple parsing
        return parse_email_simple(subject, body)


# ============================================================================
# SIMPLE EMAIL PARSING (Legacy - Fallback)
# ============================================================================

def parse_email_simple(subject: str, body: str) -> Dict:
    """Enhanced parsing to extract dates, players, etc. with flexible date formats"""
    full_text = f"{subject}\n{body}".lower()
    result = {
        'players': 4,  # default
        'dates': []
    }

    # Extract number of players
    player_patterns = [
        r'(\d+)\s*(?:players?|people|persons?|golfers?)',
        r'(?:party|group)\s*(?:of|size)?\s*(\d+)',
        r'(?:foursome|4some)',  # Special case for 4
        r'(?:twosome|2some)',   # Special case for 2
        r'(?:threesome|3some)', # Special case for 3
    ]

    for pattern in player_patterns:
        match = re.search(pattern, full_text)
        if match:
            if 'foursome' in pattern or '4some' in pattern:
                result['players'] = 4
            elif 'twosome' in pattern or '2some' in pattern:
                result['players'] = 2
            elif 'threesome' in pattern or '3some' in pattern:
                result['players'] = 3
            else:
                try:
                    num = int(match.group(1))
                    if 1 <= num <= 20:
                        result['players'] = num
                except (ValueError, IndexError):
                    pass
            if result['players']:
                break

    # Enhanced date extraction - multiple formats
    date_patterns = [
        # ISO date format (YYYY-MM-DD or YYYY/MM/DD)
        r'(?:on|for|date[:\s]*)\s*(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})',
        r'(?<!\d)(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})(?!\d)',
        # Dates with keywords
        r'(?:on|for|date[:\s]*)\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        # Month name + day
        r'(?:on|for|date[:\s]*)\s*(\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{2,4})',
        r'(?:on|for|date[:\s]*)\s*((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{2,4})?)',
        # Month name without keyword
        r'\b((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{2,4})?)\b',
        r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)\b',
        # Numeric dates without keywords
        r'\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b',
        # Relative dates
        r'\b(tomorrow)\b',
        r'\b(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
    ]

    dates_found = []
    for pattern in date_patterns:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            date_str = match.group(1).strip()
            try:
                parsed_date = None

                if 'tomorrow' in date_str.lower():
                    parsed_date = datetime.now() + timedelta(days=1)
                elif 'next' in date_str.lower():
                    # Handle "next Friday" etc
                    days = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                           'friday': 4, 'saturday': 5, 'sunday': 6}
                    for day, offset in days.items():
                        if day in date_str.lower():
                            today = datetime.now()
                            current_day = today.weekday()
                            days_ahead = (offset - current_day + 7) % 7
                            if days_ahead == 0:
                                days_ahead = 7
                            parsed_date = today + timedelta(days=days_ahead)
                            break
                else:
                    # Check if this is ISO format (YYYY-MM-DD or YYYY/MM/DD)
                    is_iso_format = re.match(r'^\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}$', date_str)

                    if is_iso_format:
                        # Parse ISO format with yearfirst=True
                        parsed_date = date_parser.parse(date_str, yearfirst=True, default=datetime.now().replace(day=1))
                    else:
                        # Use dateutil parser for flexible date parsing with dayfirst for European format
                        parsed_date = date_parser.parse(date_str, fuzzy=True, dayfirst=True, default=datetime.now().replace(day=1))

                    # If no year was specified and date is in the past, assume next year
                    if parsed_date and not re.search(r'\d{4}', date_str):
                        if parsed_date.date() < datetime.now().date():
                            parsed_date = parsed_date.replace(year=parsed_date.year + 1)

                if parsed_date:
                    # Only accept future dates (or today)
                    if parsed_date.date() >= datetime.now().date():
                        formatted_date = parsed_date.strftime('%Y-%m-%d')
                        if formatted_date not in dates_found:
                            dates_found.append(formatted_date)
            except (ValueError, TypeError):
                continue

    result['dates'] = dates_found

    return result


# ============================================================================
# WAITLIST FUNCTIONS
# ============================================================================

def is_waitlist_optin_email(subject: str) -> bool:
    """Detect if this is a waitlist opt-in email"""
    subject_upper = subject.upper() if subject else ""
    return "JOIN WAITLIST" in subject_upper


def parse_waitlist_optin_subject(subject: str) -> dict:
    """Parse waitlist details from subject line
    Expected format: JOIN WAITLIST - 2025-12-15 - 10:00 AM - 4 players
    """
    result = {
        'dates': [],
        'preferred_time': None,
        'players': 4
    }

    if not subject:
        return result

    # Extract dates (YYYY-MM-DD format)
    date_matches = re.findall(r'(\d{4}-\d{2}-\d{2})', subject)
    if date_matches:
        result['dates'] = date_matches

    # Extract time (various formats)
    time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)', subject, re.IGNORECASE)
    if time_match:
        result['preferred_time'] = time_match.group(1)

    # Extract players count
    players_match = re.search(r'(\d+)\s*players?', subject, re.IGNORECASE)
    if players_match:
        result['players'] = int(players_match.group(1))

    return result


def generate_waitlist_id(guest_email: str, timestamp: str) -> str:
    """Generate unique waitlist ID"""
    import hashlib
    hash_input = f"{guest_email}{timestamp}"
    hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8].upper()
    date_str = datetime.now().strftime('%Y%m%d')
    return f"WL-{date_str}-{hash_value}"


def add_to_waitlist(guest_email: str, dates: list, preferred_time: str, players: int, waitlist_id: str) -> bool:
    """Add customer to waitlist database"""
    try:
        logging.info(f"🔄 Adding to waitlist: {waitlist_id} | Email: {guest_email} | Dates: {dates} | Players: {players}")

        conn = get_db_connection()
        if not conn:
            logging.error("❌ No database connection for waitlist")
            return False

        cursor = conn.cursor()

        # Get guest name from email or previous bookings
        guest_name = guest_email.split('@')[0].replace('.', ' ').replace('_', ' ').title()

        # Use first date as requested_date
        requested_date = dates[0] if dates else datetime.now().strftime('%Y-%m-%d')

        logging.info(f"   Inserting into waitlist table: date={requested_date}, time={preferred_time or 'Flexible'}, players={players}")

        cursor.execute("""
            INSERT INTO waitlist (
                waitlist_id, guest_email, guest_name, requested_date,
                preferred_time, time_flexibility, players, golf_course,
                status, priority, club, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            ON CONFLICT (waitlist_id) DO NOTHING
            RETURNING id
        """, (
            waitlist_id,
            guest_email,
            guest_name,
            requested_date,
            preferred_time or 'Flexible',
            'Flexible',
            players,
            'Golf Club',
            'Waiting',
            5,
            DATABASE_CLUB_ID
        ))

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        release_db_connection(conn)

        if result:
            logging.info(f"✅ Added to waitlist: {waitlist_id} (DB id: {result[0]}) for {guest_email}")
        else:
            logging.warning(f"⚠️  Waitlist entry already exists: {waitlist_id}")

        return True

    except Exception as e:
        logging.error(f"❌ Error adding to waitlist: {e}")
        logging.exception("Full error:")
        return False


def send_waitlist_confirmation_email(guest_email: str, waitlist_id: str, dates: list, preferred_time: str, players: int):
    """Send confirmation email to customer after they opt into waitlist"""
    dates_str = ', '.join(dates) if dates else 'Your requested dates'
    time_str = preferred_time or 'Flexible'

    html = get_email_header()

    html += f"""
        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 25px; border-radius: 12px; text-align: center; margin-bottom: 30px;">
            <h2 style="margin: 0; font-size: 28px; font-weight: 700;">✅ Added to Waitlist</h2>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Waitlist ID: {waitlist_id}</p>
        </div>

        <p style="color: {BRAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8;">
            Thank you for joining our waitlist at <strong style="color: {BRAND_COLORS['navy_primary']};">Golf Club</strong>.
        </p>

        <div style="background: {BRAND_COLORS['light_grey']}; border-radius: 8px; padding: 20px; margin: 25px 0;">
            <h3 style="color: {BRAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 15px 0;">
                📋 Your Waitlist Details
            </h3>
            <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
                <tr>
                    <td style="font-weight: 600; width: 40%;">Date(s):</td>
                    <td>{dates_str}</td>
                </tr>
                <tr>
                    <td style="font-weight: 600;">Preferred Time:</td>
                    <td>{time_str}</td>
                </tr>
                <tr>
                    <td style="font-weight: 600;">Players:</td>
                    <td>{players}</td>
                </tr>
                <tr>
                    <td style="font-weight: 600;">Status:</td>
                    <td><span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 4px; font-size: 13px;">Active - Waiting</span></td>
                </tr>
            </table>
        </div>

        <div style="background: #eff6ff; border-radius: 8px; padding: 20px; margin: 25px 0;">
            <h3 style="color: #1e40af; font-size: 16px; margin: 0 0 10px 0;">
                🔔 What happens next?
            </h3>
            <ul style="margin: 0; padding-left: 20px; color: #1e40af;">
                <li style="margin-bottom: 8px;">We'll check for availability every few hours</li>
                <li style="margin-bottom: 8px;">As soon as a tee time opens up, we'll email you immediately</li>
                <li style="margin-bottom: 8px;">You can then book your preferred time through our normal booking process</li>
            </ul>
        </div>

        <p style="color: {BRAND_COLORS['text_medium']}; font-size: 15px; line-height: 1.8;">
            If you have any questions or need to update your waitlist request, please contact us at
            <a href="mailto:{CLUB_BOOKING_EMAIL}" style="color: {BRAND_COLORS['navy_primary']};">{CLUB_BOOKING_EMAIL}</a>.
        </p>
    """

    html += get_email_footer()

    send_email_sendgrid(guest_email, "Waitlist Confirmation - Golf Club", html)
    logging.info(f"✅ Waitlist confirmation email sent to {guest_email}")


def process_waitlist_optin(from_email: str, subject: str, body: str, message_id: str) -> tuple:
    """Process a waitlist opt-in email and add customer to waitlist"""

    # Extract clean email
    if '<' in from_email:
        guest_email = from_email.split('<')[1].strip('>')
    else:
        guest_email = from_email

    # Parse waitlist details from subject
    parsed = parse_waitlist_optin_subject(subject)

    # Also try to extract from body if subject doesn't have dates
    if not parsed['dates']:
        body_dates = re.findall(r'(\d{4}-\d{2}-\d{2})', body)
        if body_dates:
            parsed['dates'] = body_dates

    if not parsed['preferred_time']:
        body_time = re.search(r'Preferred Time:\s*(.+)', body)
        if body_time:
            parsed['preferred_time'] = body_time.group(1).strip()

    # Generate waitlist ID
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    waitlist_id = generate_waitlist_id(guest_email, timestamp)

    # Add to waitlist
    success = add_to_waitlist(
        guest_email,
        parsed['dates'],
        parsed['preferred_time'],
        parsed['players'],
        waitlist_id
    )

    if success:
        # Send confirmation email in background
        thread = Thread(
            target=send_waitlist_confirmation_email,
            args=(guest_email, waitlist_id, parsed['dates'], parsed['preferred_time'], parsed['players'])
        )
        thread.daemon = True
        thread.start()

        return ('waitlist_added', waitlist_id)
    else:
        return ('waitlist_error', None)


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    db_status = "connected" if db_pool else "disconnected"

    return jsonify({
        'status': 'healthy',
        'service': 'Golf Club Email Bot - Inquiry → Requested Flow',
        'database': db_status,
        'flow': 'Inquiry → Requested'
    })


@app.route('/webhook/inbound', methods=['POST'])
def handle_inbound_email():
    """
    Handle incoming emails with the three-stage customer journey

    CRITICAL: This endpoint MUST respond within 10 seconds to prevent webhook retries
    All slow processing (API calls, email sending) happens in background threads

    Stage 1 - Inquiry:
        Customer sends initial email → Status: 'Inquiry'
        System responds with available times and "Book Now" buttons

    Stage 2 - Request:
        Customer clicks "Book Now" → Status: 'Inquiry' → 'Requested'
        System sends acknowledgment: "Booking Request Received"

    Stage 3 - Confirmation:
        Staff manually confirms booking → Status: 'Requested' → 'Confirmed'
        System sends confirmation with payment details

    Additional:
        Customer replies to acknowledgment → Status maintained as 'Requested'
    """
    start_time = time.time()

    try:
        from_email = request.form.get('from', '')
        to_email = request.form.get('to', '')
        subject = request.form.get('subject', '')
        text_body = request.form.get('text', '')
        html_body = request.form.get('html', '')
        headers = request.form.get('headers', '')

        body = text_body if text_body else html_body
        message_id = extract_message_id(headers)

        logging.info("="*80)
        logging.info(f"📨 INBOUND WEBHOOK")
        logging.info(f"From: {from_email}")
        logging.info(f"To: {to_email}")
        logging.info(f"Subject: {subject}")
        logging.info(f"Body (first 200 chars): {body[:200] if body else 'EMPTY'}")
        logging.info(f"Message-ID: {message_id}")
        logging.info("="*80)

        # Save email to database immediately
        try:
            save_inbound_email(
                message_id=message_id,
                from_email=from_email,
                to_email=to_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                headers=headers
            )
            logging.info(f"✅ Email saved to database (message_id: {message_id})")
        except Exception as e:
            logging.error(f"❌ Failed to save email to database: {e}")

        # CRITICAL: Check for duplicate FIRST (prevents retries from processing)
        if message_id and is_duplicate_message(message_id):
            elapsed = time.time() - start_time
            logging.warning(f"⚠️  DUPLICATE MESSAGE - SKIPPING (responded in {elapsed:.2f}s)")
            return jsonify({'status': 'duplicate', 'message_id': message_id}), 200

        # Extract clean email
        if '<' in from_email:
            sender_email = from_email.split('<')[1].strip('>')
        else:
            sender_email = from_email

        if not sender_email or '@' not in sender_email:
            elapsed = time.time() - start_time
            logging.warning(f"⚠️  Invalid email (responded in {elapsed:.2f}s)")
            return jsonify({'status': 'invalid_email'}), 400

        if not body or len(body.strip()) < 10:
            elapsed = time.time() - start_time
            logging.warning(f"⚠️  Empty body (responded in {elapsed:.2f}s)")
            return jsonify({'status': 'empty_body'}), 200

        # Parse basic info with enhanced NLP
        sender_name = from_email.split('<')[0].strip() if '<' in from_email else ""
        parsed = parse_email_enhanced(subject, body, sender_email, sender_name)

        # FLOW DETECTION
        # ==============

        # Case 0: STAFF CONFIRMATION (manual confirmation by booking team - Stage 3)
        if is_staff_confirmation(subject, body, sender_email):
            start_time = time.time()
            logging.info("✅ DETECTED: STAFF CONFIRMATION (Manual confirmation by team)")

            # Extract booking ID from email
            booking_id = extract_booking_id(subject) or extract_booking_id(body)

            if booking_id:
                # Get existing booking to check status
                booking = get_booking_by_id(booking_id)

                if booking and booking.get('status') == 'Requested':
                    # Update booking to "Confirmed" IMMEDIATELY
                    logging.info(f"   Updating booking {booking_id} to 'Confirmed'")

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    existing_note = booking.get('note', '')
                    new_note = f"{existing_note}\nBooking confirmed by team on {timestamp}"

                    updates = {
                        'status': 'Confirmed',
                        'note': new_note
                    }

                    update_booking_in_db(booking_id, updates)

                    # Update email processing status
                    try:
                        update_email_processing_status(
                            message_id=message_id,
                            status='processed',
                            booking_id=booking_id
                        )
                    except Exception as e:
                        logging.error(f"❌ Failed to update email processing status: {e}")

                    elapsed = time.time() - start_time
                    logging.info(f"✅ Booking confirmed in DB (responded in {elapsed:.2f}s)")

                    # Start background thread for email sending
                    # Refresh booking data after status update
                    updated_booking = get_booking_by_id(booking_id)
                    if updated_booking:
                        thread = Thread(
                            target=process_staff_confirmation_async,
                            args=(booking_id, updated_booking)
                        )
                        thread.daemon = True
                        thread.start()
                        logging.info(f"🔄 Background thread started for confirmation email {booking_id}")

                    # Return 200 immediately (before email is sent)
                    return jsonify({'status': 'confirmed', 'booking_id': booking_id}), 200
                else:
                    elapsed = time.time() - start_time
                    status = booking.get('status') if booking else 'not found'
                    logging.warning(f"   Booking {booking_id} cannot be confirmed (current status: {status}) (responded in {elapsed:.2f}s)")
                    return jsonify({'status': 'invalid_status', 'current_status': status}), 200
            else:
                elapsed = time.time() - start_time
                logging.warning(f"   Confirmation request but no booking ID found (responded in {elapsed:.2f}s)")
                return jsonify({'status': 'no_booking_id'}), 200

        # Case 1: BOOKING REQUEST (customer clicked "Book Now")
        elif is_booking_request(subject, body):
            start_time = time.time()
            logging.info("📝 DETECTED: BOOKING REQUEST (Customer clicked Book Now)")

            # Extract booking ID from email
            booking_id = extract_booking_id(subject) or extract_booking_id(body)

            if booking_id:
                # Check if already processed (prevent duplicate processing)
                booking = get_booking_by_id(booking_id)
                if booking and booking.get('status') == 'Requested' and booking.get('confirmation_message_id'):
                    elapsed = time.time() - start_time
                    logging.warning(f"   ⚠️  Already processed (responded in {elapsed:.2f}s)")
                    return jsonify({'status': 'already_requested', 'booking_id': booking_id}), 200

                # Update existing booking to "Requested" IMMEDIATELY
                logging.info(f"   Updating booking {booking_id} to 'Requested'")

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updates = {
                    'status': 'Requested',
                    'note': f"Customer sent booking request on {timestamp}",
                    'confirmation_message_id': message_id
                }

                # Extract date and time if present
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', subject + body)
                time_match = re.search(r'(\d{1,2}:\d{2})', subject + body)

                if date_match:
                    updates['date'] = date_match.group(1)
                if time_match:
                    updates['tee_time'] = time_match.group(1)

                update_booking_in_db(booking_id, updates)

                # Update email processing status
                try:
                    update_email_processing_status(
                        message_id=message_id,
                        status='processed',
                        booking_id=booking_id
                    )
                except Exception as e:
                    logging.error(f"❌ Failed to update email processing status: {e}")

                elapsed = time.time() - start_time
                logging.info(f"✅ Booking request saved to DB (responded in {elapsed:.2f}s)")

                # Start background thread for email sending
                thread = Thread(
                    target=process_booking_request_async,
                    args=(booking_id, sender_email, timestamp)
                )
                thread.daemon = True
                thread.start()
                logging.info(f"🔄 Background thread started for acknowledgment email {booking_id}")

                # Return 200 immediately (before email is sent)
                return jsonify({'status': 'requested', 'booking_id': booking_id}), 200
            else:
                elapsed = time.time() - start_time
                logging.warning(f"   Booking request but no booking ID found (responded in {elapsed:.2f}s)")
                return jsonify({'status': 'no_booking_id'}), 200

        # Case 2: CUSTOMER REPLY (replying to acknowledgment)
        elif is_customer_reply(subject, body):
            start_time = time.time()
            logging.info("💬 DETECTED: CUSTOMER REPLY")

            booking_id = extract_booking_id(subject) or extract_booking_id(body)

            if booking_id:
                logging.info(f"   Updating notes for booking {booking_id}")

                booking = get_booking_by_id(booking_id)
                if booking and booking.get('status') == 'Requested':
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    existing_note = booking.get('note', '')
                    new_note = f"{existing_note}\nCustomer replied again on {timestamp}"

                    update_booking_in_db(booking_id, {
                        'note': new_note
                    })

                    # Update email processing status
                    try:
                        update_email_processing_status(
                            message_id=message_id,
                            status='processed',
                            booking_id=booking_id
                        )
                    except Exception as e:
                        logging.error(f"❌ Failed to update email processing status: {e}")

                    elapsed = time.time() - start_time
                    logging.info(f"✅ Reply processed (responded in {elapsed:.2f}s)")
                    return jsonify({'status': 'reply_received', 'booking_id': booking_id}), 200

            logging.info("   Reply but no matching booking found - treating as new inquiry")

        # Case 2.5: WAITLIST OPT-IN (customer clicked "Join Waitlist" button)
        if is_waitlist_optin_email(subject):
            start_time = time.time()
            logging.info("📋 DETECTED: WAITLIST OPT-IN")

            status, waitlist_id = process_waitlist_optin(sender_email, subject, body, message_id)

            # Update email processing status with waitlist_id
            if status == 'waitlist_added' and waitlist_id:
                try:
                    update_email_processing_status(
                        message_id=message_id,
                        status='processed',
                        booking_id=waitlist_id  # Store waitlist_id as booking_id for tracking
                    )

                    # Also update inbound_emails with email_type='waitlist'
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE inbound_emails
                            SET email_type = 'waitlist',
                                waitlist_id = %s
                            WHERE message_id = %s
                        """, (waitlist_id, message_id))
                        conn.commit()
                        cursor.close()
                        release_db_connection(conn)
                        logging.info(f"✅ Email linked to waitlist entry: {waitlist_id}")
                except Exception as e:
                    logging.error(f"❌ Failed to update email for waitlist: {e}")

            elapsed = time.time() - start_time
            if status == 'waitlist_added':
                logging.info(f"✅ Customer added to waitlist: {waitlist_id} (responded in {elapsed:.2f}s)")
                return jsonify({'status': 'waitlist_added', 'waitlist_id': waitlist_id}), 200
            else:
                logging.error(f"❌ Failed to add to waitlist (responded in {elapsed:.2f}s)")
                return jsonify({'status': 'waitlist_error'}), 500

        # Case 3: NEW INQUIRY (default)
        logging.info("📧 DETECTED: NEW INQUIRY")

        # Check for recent duplicate inquiry
        existing_booking_id = was_inquiry_email_sent_recently(sender_email, parsed['dates'], hours=1)
        if existing_booking_id:
            elapsed = time.time() - start_time
            logging.warning(f"⚠️  Duplicate inquiry (responded in {elapsed:.2f}s)")
            return jsonify({'status': 'duplicate_inquiry', 'existing_booking_id': existing_booking_id}), 200

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        booking_id = generate_booking_id(sender_email, timestamp)

        # Create booking with "Processing" status initially
        new_entry = {
            "booking_id": booking_id,
            "timestamp": timestamp,
            "guest_email": sender_email,
            "message_id": message_id,
            "dates": parsed['dates'],
            "date": parsed['dates'][0] if parsed['dates'] else None,
            "tee_time": None,
            "players": parsed['players'],
            "total": PER_PLAYER_FEE * parsed['players'],
            "status": "Processing",  # ← Temporary status while we check availability
            "note": "Webhook received, checking availability...",
            "club": DATABASE_CLUB_ID,
            "club_name": FROM_NAME
        }

        # Save to database IMMEDIATELY
        save_booking_to_db(new_entry)

        # Update email processing status
        try:
            update_email_processing_status(
                message_id=message_id,
                status='processed',
                booking_id=booking_id,
                parsed_data=parsed
            )
        except Exception as e:
            logging.error(f"❌ Failed to update email processing status: {e}")

        elapsed = time.time() - start_time
        logging.info(f"✅ Inquiry saved to DB (responded in {elapsed:.2f}s)")

        # Start background processing thread (API call + email sending)
        thread = Thread(
            target=process_inquiry_async,
            args=(sender_email, parsed, booking_id, parsed['dates'], parsed['players'])
        )
        thread.daemon = True
        thread.start()

        logging.info(f"🔄 Background thread started for booking {booking_id}")

        # Return 200 immediately (before API call completes)
        return jsonify({
            'status': 'inquiry_accepted',
            'booking_id': booking_id,
            'processing': 'background'
        }), 200

    except Exception as e:
        elapsed = time.time() - start_time
        logging.exception(f"❌ ERROR (responded in {elapsed:.2f}s):")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        # Always log response time
        elapsed = time.time() - start_time
        if elapsed > 10:
            logging.error(f"🚨 SLOW RESPONSE: {elapsed:.2f}s - WEBHOOK MAY RETRY!")
        else:
            logging.info(f"⏱️  Response time: {elapsed:.2f}s")


@app.route('/api/bookings', methods=['GET'])
def api_get_bookings():
    """API endpoint for dashboard to read bookings"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'No database connection'}), 500

        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM bookings
            WHERE club = %s
            ORDER BY timestamp DESC
        """, (DATABASE_CLUB_ID,))

        bookings = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)

        return jsonify({
            'success': True,
            'bookings': [dict(b) for b in bookings],
            'count': len(bookings)
        })

    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bookings/<booking_id>', methods=['PUT'])
def api_update_booking(booking_id):
    """API endpoint for dashboard updates"""
    try:
        data = request.json

        if update_booking_in_db(booking_id, data):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# STRIPE PAYMENT ENDPOINTS
# ============================================================================

@app.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """
    Create a Stripe checkout session for a booking

    Expected JSON payload:
    {
        "booking_id": "ISL-20251209-8C9409B7",
        "date": "2025-12-15",
        "tee_time": "10:30",
        "players": 4,
        "total": 1300.00,
        "guest_email": "customer@example.com"
    }
    """
    try:
        if not STRIPE_SECRET_KEY:
            return jsonify({'error': 'Stripe not configured'}), 500

        data = request.json
        booking_id = data.get('booking_id')
        date = data.get('date')
        tee_time = data.get('tee_time')
        players = data.get('players')
        total = data.get('total')
        guest_email = data.get('guest_email')

        if not all([booking_id, date, players, total, guest_email]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Create Stripe checkout session with BACS and SEPA Direct Debit support
        session = stripe.checkout.Session.create(
            payment_method_types=['card', 'bacs_debit', 'sepa_debit'],  # Support card, BACS, and SEPA
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f'Golf Booking - {FROM_NAME}',
                        'description': f'Date: {date}{f", Tee Time: {tee_time}" if tee_time else ""}\nPlayers: {players}',
                        'images': ['https://theisland.ie/wp-content/uploads/2024/01/island-logo.png'],
                    },
                    'unit_amount': int(float(total) * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=STRIPE_SUCCESS_URL + f'?booking_id={booking_id}',
            cancel_url=STRIPE_CANCEL_URL + f'?booking_id={booking_id}',
            customer_email=guest_email,
            metadata={
                'booking_id': booking_id,
                'date': date,
                'tee_time': tee_time or '',
                'players': str(players),
                'club': DATABASE_CLUB_ID,
            },
        )

        logging.info(f"✅ Created Stripe checkout session for booking {booking_id}: {session.id}")

        return jsonify({
            'sessionId': session.id,
            'url': session.url
        })

    except Exception as e:
        logging.error(f"❌ Error creating Stripe checkout session: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/book', methods=['GET'])
def book_redirect():
    """
    Simple redirect endpoint for email Book Now buttons
    Accepts GET parameters and redirects to Stripe checkout

    Parameters:
    - booking_id: ISL-20251209-8C9409B7
    - date: 2025-12-15
    - time: 10:30
    - players: 4
    - email: customer@example.com
    """
    try:
        if not STRIPE_SECRET_KEY:
            return "Stripe payment system is not configured. Please contact us directly.", 500

        # Get parameters from query string
        booking_id = request.args.get('booking_id')
        date = request.args.get('date')
        tee_time = request.args.get('time')
        players = request.args.get('players')
        guest_email = request.args.get('email')

        if not all([booking_id, date, tee_time, players, guest_email]):
            return "Missing required booking information. Please contact us directly.", 400

        # Convert players to int and calculate total
        players = int(players)
        total = players * PER_PLAYER_FEE

        # Create Stripe checkout session with BACS and SEPA Direct Debit support
        # Note: BACS and SEPA must be enabled in Stripe dashboard first
        # If not enabled, will automatically try different combinations

        # Common session parameters
        session_params = {
            'line_items': [{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f'Golf Booking - {FROM_NAME}',
                        'description': f'Date: {date}, Tee Time: {tee_time}\nPlayers: {players}',
                        'images': ['https://theisland.ie/wp-content/uploads/2024/01/island-logo.png'],
                    },
                    'unit_amount': int(total * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            'mode': 'payment',
            'success_url': STRIPE_SUCCESS_URL + f'?booking_id={booking_id}',
            'cancel_url': STRIPE_CANCEL_URL + f'?booking_id={booking_id}',
            'customer_email': guest_email,
            'metadata': {
                'booking_id': booking_id,
                'date': date,
                'tee_time': tee_time,
                'players': str(players),
                'club': DATABASE_CLUB_ID,
            },
            'payment_intent_data': {
                'metadata': {
                    'booking_id': booking_id,
                    'date': date,
                    'tee_time': tee_time,
                    'players': str(players),
                }
            }
        }

        # Try payment methods in order of preference
        payment_method_attempts = [
            (['card', 'sepa_debit', 'bacs_debit'], 'Card + SEPA + BACS'),
            (['card', 'sepa_debit'], 'Card + SEPA only'),
            (['card', 'bacs_debit'], 'Card + BACS only'),
            (['card'], 'Card only'),
        ]

        session = None
        for payment_methods, description in payment_method_attempts:
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=payment_methods,
                    **session_params
                )
                # Success! Log which payment methods are active
                if len(payment_methods) < 3:
                    disabled = []
                    if 'sepa_debit' not in payment_methods:
                        disabled.append('SEPA')
                    if 'bacs_debit' not in payment_methods:
                        disabled.append('BACS')
                    logging.warning(f"⚠️ Using {description} ({', '.join(disabled)} not enabled)")
                    logging.warning(f"   Enable at: https://dashboard.stripe.com/account/payments/settings")
                else:
                    logging.info(f"✅ Using {description}")
                break
            except stripe.error.InvalidRequestError as e:
                # This payment method combination didn't work, try next
                if 'payment method type' in str(e).lower():
                    if payment_methods == ['card']:
                        # Even card-only failed, re-raise the error
                        logging.error(f"❌ All payment methods failed: {str(e)}")
                        raise
                    # Try next combination
                    continue
                else:
                    # Different error, re-raise it
                    raise

        if not session:
            raise Exception("Failed to create Stripe checkout session with any payment method combination")

        logging.info(f"✅ Created Stripe checkout session for booking {booking_id}: {session.id}")

        # Redirect to Stripe checkout
        return redirect(session.url, code=303)

    except Exception as e:
        logging.error(f"❌ Error creating Stripe checkout: {str(e)}")
        return f"Unable to process payment. Please contact us directly. Error: {str(e)}", 500


@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """
    Handle Stripe webhook events
    Primary event: checkout.session.completed
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        if STRIPE_WEBHOOK_SECRET:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        else:
            # No signature verification (not recommended for production)
            event = json.loads(payload)

        logging.info(f"📨 Received Stripe webhook: {event['type']}")

        # Handle successful payment checkout
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']

            # Extract booking information from metadata
            booking_id = session['metadata'].get('booking_id')
            date = session['metadata'].get('date')
            tee_time = session['metadata'].get('tee_time')
            players = session['metadata'].get('players')
            guest_email = session['customer_email']
            amount_paid = session['amount_total'] / 100  # Convert from cents
            payment_method_types = session.get('payment_method_types', [])

            logging.info(f"💳 Payment checkout completed for booking {booking_id}")
            logging.info(f"   Amount: €{amount_paid}")
            logging.info(f"   Customer: {guest_email}")
            logging.info(f"   Payment methods: {payment_method_types}")

            # Check if Direct Debit (BACS or SEPA) was used
            if 'bacs_debit' in payment_method_types or 'sepa_debit' in payment_method_types:
                payment_type = 'SEPA' if 'sepa_debit' in payment_method_types else 'BACS'

                # Detect test mode (session ID starts with cs_test_ or sk_test_)
                is_test_mode = session['id'].startswith('cs_test_') or (STRIPE_SECRET_KEY and STRIPE_SECRET_KEY.startswith('sk_test_'))

                if is_test_mode:
                    # TEST MODE: Instant confirmation for easier testing
                    logging.info(f"🧪 TEST MODE: {payment_type} Direct Debit - marking as confirmed immediately")

                    update_data = {
                        'status': 'Confirmed',
                        'tee_time': tee_time,
                        'note': f"Payment confirmed via Stripe ({payment_type} Direct Debit - TEST MODE) on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nAmount paid: €{amount_paid}\nStripe Session ID: {session['id']}"
                    }

                    if update_booking_in_db(booking_id, update_data):
                        logging.info(f"✅ Updated booking {booking_id} to Confirmed status (test mode)")

                        # Send instant confirmation email (same as card payment)
                        Thread(
                            target=send_payment_confirmation_email,
                            args=(booking_id, guest_email, date, tee_time, players, amount_paid)
                        ).start()
                    else:
                        logging.error(f"❌ Failed to update booking {booking_id}")

                else:
                    # LIVE MODE: Mark as pending - payment will clear in 3-5 days
                    logging.info(f"⏳ {payment_type} Direct Debit payment pending for booking {booking_id}")

                    update_data = {
                        'status': f'Pending {payment_type}',
                        'tee_time': tee_time,
                        'note': f"{payment_type} Direct Debit payment initiated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nAmount: €{amount_paid}\nStatus: Pending (clears in 3-5 business days)\nStripe Session ID: {session['id']}"
                    }

                    if update_booking_in_db(booking_id, update_data):
                        logging.info(f"✅ Updated booking {booking_id} to Pending {payment_type} status")

                        # Send "pending confirmation" email
                        Thread(
                            target=send_direct_debit_pending_email,
                            args=(booking_id, guest_email, date, tee_time, players, amount_paid, payment_type)
                        ).start()
                    else:
                        logging.error(f"❌ Failed to update booking {booking_id}")

            else:
                # Card payment: Instant confirmation
                logging.info(f"✅ Card payment confirmed for booking {booking_id}")

                update_data = {
                    'status': 'Confirmed',
                    'tee_time': tee_time,  # Save the tee time to database
                    'note': f"Payment confirmed via Stripe (Card) on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nAmount paid: €{amount_paid}\nStripe Session ID: {session['id']}"
                }

                if update_booking_in_db(booking_id, update_data):
                    logging.info(f"✅ Updated booking {booking_id} to Confirmed status")

                    # Send confirmation email in background
                    Thread(
                        target=send_payment_confirmation_email,
                        args=(booking_id, guest_email, date, tee_time, players, amount_paid)
                    ).start()

                else:
                    logging.error(f"❌ Failed to update booking {booking_id}")

        # Handle Direct Debit payment clearing (3-5 days after checkout)
        elif event['type'] == 'charge.succeeded':
            charge = event['data']['object']
            payment_method_details = charge.get('payment_method_details', {})
            payment_method_type = payment_method_details.get('type')

            # Only process if this is a Direct Debit payment (BACS or SEPA)
            if payment_method_type in ['bacs_debit', 'sepa_debit']:
                payment_type = 'SEPA' if payment_method_type == 'sepa_debit' else 'BACS'

                # Get the payment intent to access metadata
                payment_intent_id = charge.get('payment_intent')

                if payment_intent_id:
                    try:
                        # Retrieve payment intent which has our booking metadata
                        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

                        # Extract booking details from payment intent metadata
                        booking_id = payment_intent.metadata.get('booking_id')
                        date = payment_intent.metadata.get('date')
                        tee_time = payment_intent.metadata.get('tee_time')
                        players = payment_intent.metadata.get('players')
                        amount_paid = charge['amount'] / 100

                        if booking_id:
                            logging.info(f"✅ {payment_type} Direct Debit payment cleared for booking {booking_id}")

                            # Get customer email from charge
                            receipt_email = charge.get('receipt_email') or charge.get('billing_details', {}).get('email')

                            # Update booking to "Confirmed" status
                            update_data = {
                                'status': 'Confirmed',
                                'note': f"{payment_type} Direct Debit payment cleared on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nAmount paid: €{amount_paid}\nStripe Charge ID: {charge['id']}"
                            }

                            if update_booking_in_db(booking_id, update_data):
                                logging.info(f"✅ Updated booking {booking_id} to Confirmed status ({payment_type} cleared)")

                                # Send final confirmation email if we have customer email
                                if receipt_email:
                                    Thread(
                                        target=send_direct_debit_confirmed_email,
                                        args=(booking_id, receipt_email, date, tee_time, players, amount_paid, payment_type)
                                    ).start()
                                else:
                                    logging.warning(f"⚠️ No customer email found for {payment_type} confirmation (booking {booking_id})")
                            else:
                                logging.error(f"❌ Failed to update booking {booking_id} after {payment_type} clearing")
                        else:
                            logging.warning(f"⚠️ No booking_id found in payment intent metadata for charge {charge['id']}")
                    except Exception as e:
                        logging.error(f"❌ Error processing {payment_type} clearing: {str(e)}")

        # Handle failed charges (optional)
        elif event['type'] == 'charge.failed':
            charge = event['data']['object']
            payment_method_details = charge.get('payment_method_details', {})
            payment_method_type = payment_method_details.get('type')

            if payment_method_type in ['bacs_debit', 'sepa_debit']:
                payment_type = 'SEPA' if payment_method_type == 'sepa_debit' else 'BACS'
                logging.warning(f"⚠️ {payment_type} Direct Debit payment failed: {charge.get('id')}")

        return jsonify({'status': 'success'}), 200

    except ValueError as e:
        logging.error(f"❌ Invalid Stripe webhook payload: {str(e)}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        logging.error(f"❌ Invalid Stripe webhook signature: {str(e)}")
        return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        logging.error(f"❌ Error processing Stripe webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/booking-success', methods=['GET'])
def booking_success():
    """
    Success page after Stripe payment completion
    Shows confirmation message and booking details
    """
    booking_id = request.args.get('booking_id', 'Unknown')

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Booking Confirmed - {FROM_NAME}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .container {{
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 600px;
                padding: 50px 40px;
                text-align: center;
            }}
            .success-icon {{
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 30px;
                animation: scaleIn 0.5s ease-out;
            }}
            @keyframes scaleIn {{
                from {{ transform: scale(0); }}
                to {{ transform: scale(1); }}
            }}
            .checkmark {{
                color: white;
                font-size: 48px;
                font-weight: bold;
            }}
            h1 {{
                color: #1f2937;
                margin: 0 0 15px 0;
                font-size: 32px;
            }}
            p {{
                color: #6b7280;
                font-size: 16px;
                line-height: 1.6;
                margin: 0 0 30px 0;
            }}
            .booking-id {{
                background: #f3f4f6;
                border-radius: 8px;
                padding: 20px;
                margin: 30px 0;
            }}
            .booking-id strong {{
                color: #1f2937;
                font-size: 18px;
            }}
            .booking-id code {{
                display: block;
                font-size: 20px;
                color: #667eea;
                font-weight: bold;
                margin-top: 10px;
                font-family: 'Courier New', monospace;
            }}
            .info-box {{
                background: #eff6ff;
                border-left: 4px solid #3b82f6;
                border-radius: 8px;
                padding: 20px;
                text-align: left;
                margin: 20px 0;
            }}
            .info-box h3 {{
                margin: 0 0 15px 0;
                color: #1f2937;
                font-size: 18px;
            }}
            .info-box ul {{
                margin: 0;
                padding-left: 20px;
            }}
            .info-box li {{
                margin: 8px 0;
                color: #374151;
            }}
            .button {{
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                padding: 14px 32px;
                border-radius: 8px;
                font-weight: 600;
                margin-top: 20px;
                transition: transform 0.2s;
            }}
            .button:hover {{
                transform: translateY(-2px);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">
                <div class="checkmark">✓</div>
            </div>

            <h1>Payment Confirmed!</h1>
            <p>Thank you for your booking. Your payment has been successfully processed.</p>

            <div class="booking-id">
                <strong>Your Booking Reference:</strong>
                <code>{booking_id}</code>
            </div>

            <div class="info-box">
                <h3>📧 What's Next?</h3>
                <ul>
                    <li>Check your email for confirmation details</li>
                    <li>Save your booking reference for your records</li>
                    <li>Arrive 30 minutes before your tee time</li>
                    <li>Bring this confirmation with you</li>
                </ul>
            </div>

            <p style="margin-top: 30px; font-size: 14px;">
                If you have any questions, please reply to your confirmation email.
            </p>

            <a href="https://theisland.ie" class="button">Return to Homepage</a>
        </div>
    </body>
    </html>
    """

    return html


@app.route('/booking-cancelled', methods=['GET'])
def booking_cancelled():
    """
    Cancellation page when user cancels Stripe payment
    """
    booking_id = request.args.get('booking_id', 'Unknown')

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Booking Cancelled - {FROM_NAME}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                margin: 0;
                padding: 20px;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .container {{
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 600px;
                padding: 50px 40px;
                text-align: center;
            }}
            .icon {{
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 30px;
            }}
            .icon-text {{
                color: white;
                font-size: 48px;
            }}
            h1 {{
                color: #1f2937;
                margin: 0 0 15px 0;
                font-size: 32px;
            }}
            p {{
                color: #6b7280;
                font-size: 16px;
                line-height: 1.6;
                margin: 0 0 30px 0;
            }}
            .info-box {{
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                border-radius: 8px;
                padding: 20px;
                text-align: left;
                margin: 20px 0;
            }}
            .info-box p {{
                margin: 8px 0;
                color: #374151;
            }}
            .button {{
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                padding: 14px 32px;
                border-radius: 8px;
                font-weight: 600;
                margin: 10px;
                transition: transform 0.2s;
            }}
            .button:hover {{
                transform: translateY(-2px);
            }}
            .button-secondary {{
                background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">
                <div class="icon-text">⚠</div>
            </div>

            <h1>Booking Cancelled</h1>
            <p>Your payment was cancelled and no charges were made to your card.</p>

            <div class="info-box">
                <p><strong>📋 What happened?</strong></p>
                <p>You clicked the back button or closed the payment page before completing your booking.</p>
                <p style="margin-top: 15px;"><strong>💡 Want to try again?</strong></p>
                <p>Check your email for available tee times and click "Book Now" to complete your booking.</p>
            </div>

            <p style="margin-top: 30px;">
                If you're experiencing issues or have questions, please reply to your inquiry email and we'll be happy to help.
            </p>

            <div style="margin-top: 30px;">
                <a href="mailto:{CLUB_BOOKING_EMAIL}" class="button">Contact Us</a>
                <a href="https://theisland.ie" class="button button-secondary">Return to Homepage</a>
            </div>
        </div>
    </body>
    </html>
    """

    return html


def send_payment_confirmation_email(booking_id: str, guest_email: str, date: str, tee_time: str, players: int, amount_paid: float):
    """
    Send confirmation email after successful payment
    """
    try:
        # Format tee time display
        tee_time_display = f" at {tee_time}" if tee_time else ""

        # Create email body
        subject = f"✅ Payment Confirmed - Booking {booking_id}"

        html_body = f"""
        {get_email_header()}

        <div style="max-width: 600px; margin: 0 auto; background: white; padding: 40px 30px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                            color: white; padding: 15px 30px; border-radius: 50px; font-size: 24px; font-weight: bold;">
                    ✅ Payment Confirmed!
                </div>
            </div>

            <h2 style="color: {BRAND_COLORS['navy_primary']}; margin-bottom: 20px;">Thank you for your payment!</h2>

            <p>We're delighted to confirm that your payment has been received and your booking is now confirmed.</p>

            <div style="background: linear-gradient(to right, #f0fdf4 0%, #dcfce7 100%);
                        border-left: 4px solid #10b981; padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>📅 Booking Details</strong></h3>
                <p style="margin: 5px 0;"><strong>Booking ID:</strong> {booking_id}</p>
                <p style="margin: 5px 0;"><strong>Date:</strong> {date}{tee_time_display}</p>
                <p style="margin: 5px 0;"><strong>Players:</strong> {players}</p>
                <p style="margin: 5px 0;"><strong>Amount Paid:</strong> €{amount_paid:.2f}</p>
            </div>

            <div style="background: linear-gradient(to right, #eff6ff 0%, #dbeafe 100%);
                        border-left: 4px solid {BRAND_COLORS['royal_blue']};
                        padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>📋 What's Next?</strong></h3>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li style="margin: 8px 0;">You'll receive a detailed confirmation email with all the information you need</li>
                    <li style="margin: 8px 0;">Please arrive 30 minutes before your tee time</li>
                    <li style="margin: 8px 0;">Bring your booking confirmation (this email)</li>
                    <li style="margin: 8px 0;">Don't forget your golf clubs and suitable attire</li>
                </ul>
            </div>

            <div style="background: linear-gradient(to right, #fef3c7 0%, #fde68a 100%);
                        border-left: 4px solid {BRAND_COLORS['gold_accent']};
                        padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>ℹ️ Important Information</strong></h3>
                <p style="margin: 5px 0;">If you need to modify or cancel your booking, please contact us as soon as possible.</p>
                <p style="margin: 5px 0;">Our cancellation policy: Cancellations must be made at least 48 hours in advance for a full refund.</p>
            </div>

            <p style="margin-top: 30px;">We look forward to welcoming you to {FROM_NAME}!</p>

            <p style="margin-top: 20px;">If you have any questions, please don't hesitate to reply to this email.</p>
        </div>

        {get_email_footer()}
        """

        # Send email
        if send_email_sendgrid(guest_email, subject, html_body):
            logging.info(f"✅ Sent payment confirmation email to {guest_email}")
        else:
            logging.error(f"❌ Failed to send payment confirmation email to {guest_email}")

    except Exception as e:
        logging.error(f"❌ Error sending payment confirmation email: {str(e)}")


def send_direct_debit_pending_email(booking_id: str, guest_email: str, date: str, tee_time: str, players: int, amount: float, payment_type: str = 'SEPA'):
    """
    Send email for Direct Debit pending confirmation
    Direct Debit payments (BACS/SEPA) take 3-5 business days to clear

    Args:
        payment_type: Either 'BACS' (UK) or 'SEPA' (Europe)
    """
    try:
        # Format tee time display
        tee_time_display = f" at {tee_time}" if tee_time else ""

        # Payment method description
        payment_desc = "UK bank transfer" if payment_type == 'BACS' else "European bank transfer"

        # Create email body
        subject = f"⏳ Booking Request Received - {booking_id}"

        html_body = f"""
        {get_email_header()}

        <div style="max-width: 600px; margin: 0 auto; background: white; padding: 40px 30px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="display: inline-block; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                            color: white; padding: 15px 30px; border-radius: 50px; font-size: 24px; font-weight: bold;">
                    ⏳ Payment Pending
                </div>
            </div>

            <h2 style="color: {BRAND_COLORS['navy_primary']}; margin-bottom: 20px;">Thank you for your booking!</h2>

            <p>We've received your booking request and your {payment_type} Direct Debit payment is being processed.</p>

            <div style="background: #fff3cd; padding: 20px; margin: 25px 0; border-left: 4px solid #ffc107; border-radius: 8px;">
                <h3 style="margin: 0 0 10px 0; color: {BRAND_COLORS['navy_primary']};"><strong>⏳ Payment Processing</strong></h3>
                <p style="margin: 5px 0;">Your {payment_type} Direct Debit payment is being processed. This typically takes <strong>3-5 business days</strong> to clear.</p>
                <p style="margin: 5px 0;">We'll send you a confirmation email once your payment clears.</p>
            </div>

            <div style="background: linear-gradient(to right, #f0fdf4 0%, #dcfce7 100%);
                        border-left: 4px solid #10b981; padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>📅 Booking Details</strong></h3>
                <p style="margin: 5px 0;"><strong>Booking ID:</strong> {booking_id}</p>
                <p style="margin: 5px 0;"><strong>Date:</strong> {date}{tee_time_display}</p>
                <p style="margin: 5px 0;"><strong>Players:</strong> {players}</p>
                <p style="margin: 5px 0;"><strong>Amount:</strong> €{amount:.2f}</p>
                <p style="margin: 5px 0;"><strong>Status:</strong> Pending ({payment_type} clearing)</p>
            </div>

            <div style="background: linear-gradient(to right, #eff6ff 0%, #dbeafe 100%);
                        border-left: 4px solid {BRAND_COLORS['royal_blue']};
                        padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>📋 What Happens Next?</strong></h3>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li style="margin: 8px 0;">Your payment will clear in 3-5 business days</li>
                    <li style="margin: 8px 0;">We'll send you a confirmation email once payment is confirmed</li>
                    <li style="margin: 8px 0;">Your tee time is reserved pending payment confirmation</li>
                    <li style="margin: 8px 0;">No further action is required from you</li>
                </ul>
            </div>

            <div style="background: linear-gradient(to right, #fef3c7 0%, #fde68a 100%);
                        border-left: 4px solid {BRAND_COLORS['gold_accent']};
                        padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>ℹ️ {payment_type} Direct Debit Information</strong></h3>
                <p style="margin: 5px 0;">{payment_type} Direct Debit is a secure and cost-effective payment method for {payment_desc}s.</p>
                <p style="margin: 5px 0;">Your payment is protected by the Direct Debit Guarantee.</p>
            </div>

            <p style="margin-top: 30px;">Thank you for choosing {FROM_NAME}. We look forward to welcoming you!</p>

            <p style="margin-top: 20px;">If you have any questions, please don't hesitate to reply to this email.</p>
        </div>

        {get_email_footer()}
        """

        # Send email
        if send_email_sendgrid(guest_email, subject, html_body):
            logging.info(f"✅ Sent {payment_type} Direct Debit pending email to {guest_email}")
        else:
            logging.error(f"❌ Failed to send {payment_type} Direct Debit pending email to {guest_email}")

    except Exception as e:
        logging.error(f"❌ Error sending {payment_type} Direct Debit pending email: {str(e)}")


def send_direct_debit_confirmed_email(booking_id: str, guest_email: str, date: str, tee_time: str, players: int, amount_paid: float, payment_type: str = 'SEPA'):
    """
    Send final confirmation email after Direct Debit payment clears (3-5 days after checkout)

    Args:
        payment_type: Either 'BACS' (UK) or 'SEPA' (Europe)
    """
    try:
        # Format tee time display
        tee_time_display = f" at {tee_time}" if tee_time else ""

        # Create email body
        subject = f"✅ Payment Confirmed ({payment_type} Cleared) - {booking_id}"

        html_body = f"""
        {get_email_header()}

        <div style="max-width: 600px; margin: 0 auto; background: white; padding: 40px 30px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                            color: white; padding: 15px 30px; border-radius: 50px; font-size: 24px; font-weight: bold;">
                    ✅ {payment_type} Payment Cleared!
                </div>
            </div>

            <h2 style="color: {BRAND_COLORS['navy_primary']}; margin-bottom: 20px;">Your payment has been confirmed!</h2>

            <p>Great news! Your {payment_type} Direct Debit payment has cleared and your booking is now fully confirmed.</p>

            <div style="background: linear-gradient(to right, #f0fdf4 0%, #dcfce7 100%);
                        border-left: 4px solid #10b981; padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>📅 Confirmed Booking Details</strong></h3>
                <p style="margin: 5px 0;"><strong>Booking ID:</strong> {booking_id}</p>
                <p style="margin: 5px 0;"><strong>Date:</strong> {date}{tee_time_display}</p>
                <p style="margin: 5px 0;"><strong>Players:</strong> {players}</p>
                <p style="margin: 5px 0;"><strong>Amount Paid:</strong> €{amount_paid:.2f} ({payment_type} Direct Debit)</p>
                <p style="margin: 5px 0;"><strong>Status:</strong> ✅ Confirmed</p>
            </div>

            <div style="background: linear-gradient(to right, #eff6ff 0%, #dbeafe 100%);
                        border-left: 4px solid {BRAND_COLORS['royal_blue']};
                        padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>📋 What's Next?</strong></h3>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li style="margin: 8px 0;">Your tee time is now fully confirmed</li>
                    <li style="margin: 8px 0;">Please arrive 30 minutes before your tee time</li>
                    <li style="margin: 8px 0;">Bring your booking confirmation (this email)</li>
                    <li style="margin: 8px 0;">Don't forget your golf clubs and suitable attire</li>
                </ul>
            </div>

            <div style="background: linear-gradient(to right, #fef3c7 0%, #fde68a 100%);
                        border-left: 4px solid {BRAND_COLORS['gold_accent']};
                        padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3 style="margin: 0 0 15px 0; color: {BRAND_COLORS['navy_primary']};"><strong>ℹ️ Important Information</strong></h3>
                <p style="margin: 5px 0;">If you need to modify or cancel your booking, please contact us as soon as possible.</p>
                <p style="margin: 5px 0;">Our cancellation policy: Cancellations must be made at least 48 hours in advance for a full refund.</p>
            </div>

            <p style="margin-top: 30px;">We look forward to welcoming you to {FROM_NAME}!</p>

            <p style="margin-top: 20px;">If you have any questions, please don't hesitate to reply to this email.</p>
        </div>

        {get_email_footer()}
        """

        # Send email
        if send_email_sendgrid(guest_email, subject, html_body):
            logging.info(f"✅ Sent {payment_type} Direct Debit confirmed email to {guest_email}")
        else:
            logging.error(f"❌ Failed to send {payment_type} Direct Debit confirmed email to {guest_email}")

    except Exception as e:
        logging.error(f"❌ Error sending {payment_type} Direct Debit confirmed email: {str(e)}")


# ============================================================================
# INITIALIZE
# ============================================================================
logging.info("="*80)
logging.info("🌐 Golf Club - Email Bot")
logging.info("="*80)
logging.info("📧 Email Flow: Inquiry → Requested")
logging.info("✅ Step 1: Customer Inquiry → Status: 'Inquiry'")
logging.info("✅ Step 2: Customer Clicks 'Book Now' → Status: 'Requested'")
logging.info("✅ Step 3: Bot Sends Acknowledgment → Status: 'Requested' (maintained)")
logging.info("✅ Step 4: Customer Replies → Status: 'Requested' (maintained)")
logging.info("="*80)

if init_db_pool():
    init_database()
    logging.info("✅ Database ready")

logging.info(f"📧 SendGrid: {FROM_EMAIL}")
logging.info(f"📬 Club Booking Email: {CLUB_BOOKING_EMAIL}")
logging.info(f"📮 Tracking Email: {TRACKING_EMAIL_PREFIX}@bookings.teemail.io")
logging.info(f"🏌️  Database Club ID: {DATABASE_CLUB_ID}")
logging.info(f"🏌️  Default Course ID: {DEFAULT_COURSE_ID}")
logging.info(f"🔗 Core API: {CORE_API_URL}")
if STRIPE_SECRET_KEY:
    logging.info(f"💳 Stripe: ENABLED (key: {STRIPE_SECRET_KEY[:7]}...)")
    logging.info(f"📍 Success URL: {STRIPE_SUCCESS_URL}")
    logging.info(f"📍 Cancel URL: {STRIPE_CANCEL_URL}")
    logging.info(f"🔗 Book URL: {BOOKING_APP_URL}/book")
else:
    logging.info(f"💳 Stripe: DISABLED - Using mailto fallback")
logging.info("="*80)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
