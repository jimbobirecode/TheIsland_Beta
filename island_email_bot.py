#!/usr/bin/env python3
"""
The Island Golf Club - Email Bot with Inquiry → Requested Flow
================================================================

Email Flow:
1. Customer Inquiry → Database (Status: 'Inquiry' ✅)
2. Customer Clicks "Book Now" → Database (Status: 'Inquiry' → 'Requested' ✅)
   Note: "Customer sent booking request on [timestamp]"
3. Bot Sends Acknowledgment → Database (Status: 'Requested' maintained)
   Note: "Acknowledgment email sent on [timestamp]"
4. Customer Replies Again → Database (Status: 'Requested' maintained)
   Note: "Customer replied again on [timestamp]"
"""

from flask import Flask, request, jsonify
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

app = Flask(__name__)

# --- CONFIG ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "bookings@theislandgolfclub.ie")
FROM_NAME = os.getenv("FROM_NAME", "The Island Golf Club")
PER_PLAYER_FEE = float(os.getenv("PER_PLAYER_FEE", "325.00"))
BOOKINGS_FILE = os.getenv("BOOKINGS_FILE", "provisional_bookings.jsonl")

# PostgreSQL Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Core API endpoint (for availability checking)
CORE_API_URL = os.getenv("CORE_API_URL", "https://core-new-aku3.onrender.com")

# Dashboard API endpoint
DASHBOARD_API_URL = os.getenv("DASHBOARD_API_URL", "https://theisland-dashboard.onrender.com")

# Default course for bookings
DEFAULT_COURSE_ID = os.getenv("DEFAULT_COURSE_ID", "theisland")

# Tracking email for confirmation webhooks
TRACKING_EMAIL_PREFIX = os.getenv("TRACKING_EMAIL_PREFIX", "theisland")

# Club booking email (appears in mailto links)
CLUB_BOOKING_EMAIL = os.getenv("CLUB_BOOKING_EMAIL", "bookings@theislandgolfclub.ie")

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- DATABASE CONNECTION POOL ---
db_pool = None


# ============================================================================
# THE ISLAND BRAND COLORS
# ============================================================================

THE_ISLAND_COLORS = {
    'navy_primary': '#24388f',
    'royal_blue': '#1923c2',
    'powder_blue': '#b8c1da',
    'charcoal': '#2e303d',
    'black': '#000000',
    'white': '#ffffff',
    'light_grey': '#f8f9fa',
    'border_grey': '#e5e7eb',
    'text_dark': '#1f2937',
    'text_medium': '#4b5563',
    'text_light': '#6b7280',
    'gradient_start': '#24388f',
    'gradient_end': '#1923c2',
    'gold_accent': '#D4AF37',
    'green_success': '#2D5F3F',
    'bg_light': '#f3f4f6',
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
    """The Island Golf Club branded email header"""
    return f"""
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <title>The Island Golf Club - Booking</title>
        <style type="text/css">
            body {{
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
                font-family: Georgia, 'Times New Roman', serif;
                background-color: {THE_ISLAND_COLORS['bg_light']};
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
                border-bottom: 2px solid {THE_ISLAND_COLORS['border_grey']};
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
                border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']};
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
            }}
            .button-link {{
                background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%);
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
                border: 1px solid {THE_ISLAND_COLORS['border_grey']};
            }}
            .tee-table thead {{
                background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%);
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
                border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};
            }}
            .footer {{
                background: linear-gradient(135deg, {THE_ISLAND_COLORS['gradient_start']} 0%, {THE_ISLAND_COLORS['gradient_end']} 100%);
                padding: 30px;
                text-align: center;
                color: #ffffff;
            }}
        </style>
    </head>
    <body>
        <table role="presentation" width="100%" style="background-color: {THE_ISLAND_COLORS['bg_light']};">
            <tr>
                <td style="padding: 20px;">
                    <table class="email-container" align="center" width="800">
                        <tr>
                            <td class="header">
                                <img src="https://raw.githubusercontent.com/jimbobirecode/TeeMail-Assests/main/images.png" alt="The Island Golf Club" class="header-logo" />
                                <hr style="border: 0; height: 3px; background-color: {THE_ISLAND_COLORS['royal_blue']}; margin: 20px auto; width: 100%;" />
                                <p style="margin: 0; color: {THE_ISLAND_COLORS['text_medium']}; font-size: 16px; font-weight: 600;">
                                    Visitor Tee Time Booking
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td class="content">
    """


def get_email_footer():
    """The Island Golf Club branded email footer"""
    return f"""
                            </td>
                        </tr>
                        <tr>
                            <td class="footer">
                                <strong style="color: {THE_ISLAND_COLORS['gold_accent']}; font-size: 18px;">
                                    The Island Golf Club
                                </strong>
                                <p style="margin: 10px 0; color: #ffffff; font-size: 14px;">
                                    Corballis, Donabate, Co. Dublin, K36 KH85, Ireland
                                </p>
                                <p style="margin: 0; color: {THE_ISLAND_COLORS['powder_blue']}; font-size: 13px;">
                                    📞 <a href="tel:+35318436205" style="color: {THE_ISLAND_COLORS['gold_accent']}; text-decoration: none;">+353 1 843 6205</a>
                                    <span style="margin: 0 8px;">|</span>
                                    📧 <a href="mailto:{CLUB_BOOKING_EMAIL}" style="color: {THE_ISLAND_COLORS['gold_accent']}; text-decoration: none;">{CLUB_BOOKING_EMAIL}</a>
                                </p>
                                <p style="margin-top: 15px; color: {THE_ISLAND_COLORS['powder_blue']}; font-size: 12px;">
                                    Championship Links Golf Course
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
                <td style="border-radius: 8px; background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%);">
                    <a href="{booking_link}" style="background: transparent; color: #ffffff !important; padding: 10px 20px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; display: inline-block;">
                        {button_text}
                    </a>
                </td>
            </tr>
        </table>
    """


def build_booking_link(date: str, time: str, players: int, guest_email: str, booking_id: str = None) -> str:
    """Generate mailto link for Reserve Now button"""
    tracking_email = f"{TRACKING_EMAIL_PREFIX}@bookings.teemail.io"
    club_email = CLUB_BOOKING_EMAIL

    subject = quote(f"BOOKING REQUEST - {date} at {time}")

    body_lines = [
        f"BOOKING REQUEST",
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

    mailto_link = f"mailto:{club_email}?cc={tracking_email}&subject={subject}&body={body}"
    return mailto_link


def format_inquiry_email(results: list, player_count: int, guest_email: str, booking_id: str = None) -> str:
    """Generate inquiry email with available tee times"""
    html = get_email_header()

    html += f"""
        <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8; margin: 0 0 20px 0;">
            Thank you for your enquiry. We are delighted to present the following available tee times at <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club</strong>:
        </p>

        <div class="info-box">
            <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 15px 0;">
                👥 Booking Details
            </h3>
            <p style="margin: 5px 0;"><strong>Players:</strong> {player_count}</p>
            <p style="margin: 5px 0;"><strong>Green Fee:</strong> €{PER_PLAYER_FEE:.0f} per player</p>
            <p style="margin: 5px 0;"><strong>Status:</strong> <span style="background: #ecfdf5; color: {THE_ISLAND_COLORS['green_success']}; padding: 4px 10px; border-radius: 15px; font-size: 13px;">✓ Available Times Found</span></p>
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
            <h2 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 22px; font-weight: 700; margin: 0 0 15px 0; padding-bottom: 10px; border-bottom: 3px solid {THE_ISLAND_COLORS['gold_accent']};">
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
                    <td><strong style="font-size: 16px; color: {THE_ISLAND_COLORS['navy_primary']};">{time}</strong></td>
                    <td style="text-align: center;"><span style="background: #ecfdf5; color: {THE_ISLAND_COLORS['green_success']}; padding: 4px 10px; border-radius: 15px; font-size: 13px;">✓ Available</span></td>
                    <td><span style="color: {THE_ISLAND_COLORS['royal_blue']}; font-weight: 700;">€{PER_PLAYER_FEE:.0f} pp</span></td>
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

    html += f"""
        <div class="info-box" style="margin-top: 30px;">
            <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0;">
                💡 How to Book Your Tee Time
            </h3>
            <p style="margin: 5px 0;"><strong>Step 1:</strong> Click "Book Now" for your preferred time</p>
            <p style="margin: 5px 0;"><strong>Step 2:</strong> Your email client will open with booking details</p>
            <p style="margin: 5px 0;"><strong>Step 3:</strong> Send the email to request your tee time</p>
            <p style="margin-top: 12px; font-style: italic; font-size: 14px;">Or call us at <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">+353 1 843 6205</strong></p>
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
        <div style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['powder_blue']} 0%, #a3b9d9 100%); color: {THE_ISLAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
            <h2 style="margin: 0; font-size: 28px; font-weight: 700;">📬 Booking Request Received</h2>
        </div>

        <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8;">
            Thank you for your booking request at <strong>The Island Golf Club</strong>. We have received your request and will review it shortly.
        </p>

        <div class="info-box">
            <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 20px; margin: 0 0 20px 0;">
                📋 Your Booking Request
            </h3>
            <table width="100%" cellpadding="12" cellspacing="0" style="border-collapse: collapse; border: 1px solid {THE_ISLAND_COLORS['border_grey']}; border-radius: 8px;">
                <tr style="background-color: {THE_ISLAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; font-weight: 600; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        Booking ID
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 600; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        {booking_id}
                    </td>
                </tr>
                <tr style="background-color: #ffffff;">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        <strong>📅 Date</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        {date}
                    </td>
                </tr>
                <tr style="background-color: {THE_ISLAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        <strong>🕐 Time</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        {time}
                    </td>
                </tr>
                <tr style="background-color: #ffffff;">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        <strong>👥 Players</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        {players}
                    </td>
                </tr>
                <tr style="background-color: #fffbeb;">
                    <td style="padding: 18px 12px; font-weight: 700;">
                        <strong>💶 Total Fee</strong>
                    </td>
                    <td style="padding: 18px 12px; text-align: right; color: {THE_ISLAND_COLORS['green_success']}; font-size: 22px; font-weight: 700;">
                        €{total_fee:.2f}
                    </td>
                </tr>
            </table>
        </div>

        <div style="background: #e0f2fe; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; margin: 30px 0;">
            <p style="margin: 0; font-size: 15px; line-height: 1.7;">
                <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">📞 Next Steps:</strong>
            </p>
            <p style="margin: 10px 0 0 0; font-size: 14px; line-height: 1.7;">
                Our team is reviewing your request and will confirm availability shortly. You may receive additional communication from us via email or phone.
            </p>
        </div>

        <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 15px; line-height: 1.8; margin: 30px 0 0 0;">
            Thank you for choosing The Island Golf Club.
        </p>

        <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; margin: 20px 0 0 0;">
            Best regards,<br>
            <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club Team</strong>
        </p>
    """

    html += get_email_footer()
    return html


def format_no_availability_email(player_count: int) -> str:
    """Generate email when no availability found"""
    html = get_email_header()

    html += f"""
        <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8;">
            Thank you for your enquiry regarding tee times at <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club</strong>.
        </p>

        <div style="background: #fef2f2; border-left: 4px solid #dc2626; border-radius: 8px; padding: 20px; margin: 25px 0;">
            <h3 style="color: #dc2626; font-size: 18px; margin: 0 0 12px 0;">
                ⚠️ No Availability Found
            </h3>
            <p style="margin: 0;">
                Unfortunately, we do not have availability for <strong>{player_count} player(s)</strong> on your requested dates.
            </p>
        </div>

        <div class="info-box">
            <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0;">
                📞 Please Contact Us
            </h3>
            <p style="margin: 5px 0;">We would be delighted to assist you in finding alternative dates:</p>
            <p style="margin: 8px 0;"><strong>Email:</strong> <a href="mailto:{CLUB_BOOKING_EMAIL}" style="color: {THE_ISLAND_COLORS['navy_primary']};">{CLUB_BOOKING_EMAIL}</a></p>
            <p style="margin: 8px 0;"><strong>Telephone:</strong> <a href="tel:+35318436205" style="color: {THE_ISLAND_COLORS['navy_primary']};">+353 1 843 6205</a></p>
        </div>

        <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 15px; line-height: 1.8; margin: 20px 0 0 0;">
            We look forward to welcoming you to our championship links course.
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
        <div style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['powder_blue']} 0%, #a3b9d9 100%); color: {THE_ISLAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
            <h2 style="margin: 0; font-size: 28px; font-weight: 700;">📧 Inquiry Received</h2>
        </div>

        <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8;">
            Thank you for your tee time inquiry at <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club</strong>.
        </p>

        <div class="info-box">
            <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 20px; margin: 0 0 20px 0;">
                📋 Your Inquiry Details
            </h3>
            <table width="100%" cellpadding="12" cellspacing="0" style="border-collapse: collapse; border: 1px solid {THE_ISLAND_COLORS['border_grey']}; border-radius: 8px;">
    """

    if booking_id:
        html += f"""
                <tr style="background-color: {THE_ISLAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; font-weight: 600; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        Inquiry ID
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 600; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        {booking_id}
                    </td>
                </tr>
        """

    if dates:
        dates_str = ', '.join(dates)
        html += f"""
                <tr style="background-color: #ffffff;">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        <strong>📅 Requested Dates</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        {dates_str}
                    </td>
                </tr>
        """

    html += f"""
                <tr style="background-color: {THE_ISLAND_COLORS['light_grey']};">
                    <td style="padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        <strong>👥 Players</strong>
                    </td>
                    <td style="padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                        {player_count}
                    </td>
                </tr>
                <tr style="background-color: #fffbeb;">
                    <td style="padding: 18px 12px; font-weight: 700;">
                        <strong>💶 Estimated Green Fee</strong>
                    </td>
                    <td style="padding: 18px 12px; text-align: right; color: {THE_ISLAND_COLORS['royal_blue']}; font-size: 22px; font-weight: 700;">
                        €{player_count * PER_PLAYER_FEE:.2f}
                    </td>
                </tr>
            </table>
        </div>

        <div style="background: #e0f2fe; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; margin: 30px 0;">
            <p style="margin: 0; font-size: 15px; line-height: 1.7;">
                <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">📞 What Happens Next:</strong>
            </p>
            <p style="margin: 10px 0 0 0; font-size: 14px; line-height: 1.7;">
                Our team has received your inquiry and will check availability for your requested dates. We'll respond within 24 hours with available tee times and booking options.
            </p>
        </div>

        <div class="info-box">
            <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0;">
                📞 Contact Us Directly
            </h3>
            <p style="margin: 5px 0;">For immediate assistance, please contact us:</p>
            <p style="margin: 8px 0;"><strong>Email:</strong> <a href="mailto:{CLUB_BOOKING_EMAIL}" style="color: {THE_ISLAND_COLORS['navy_primary']};">{CLUB_BOOKING_EMAIL}</a></p>
            <p style="margin: 8px 0;"><strong>Telephone:</strong> <a href="tel:+35318436205" style="color: {THE_ISLAND_COLORS['navy_primary']};">+353 1 843 6205</a></p>
        </div>

        <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 15px; line-height: 1.8; margin: 30px 0 0 0;">
            Thank you for choosing The Island Golf Club.
        </p>

        <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; margin: 20px 0 0 0;">
            Best regards,<br>
            <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club Team</strong>
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


# ============================================================================
# SIMPLE EMAIL PARSING
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
# WEBHOOK ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    db_status = "connected" if db_pool else "disconnected"

    return jsonify({
        'status': 'healthy',
        'service': 'The Island Email Bot - Inquiry → Requested Flow',
        'database': db_status,
        'flow': 'Inquiry → Requested'
    })


@app.route('/webhook/inbound', methods=['POST'])
def handle_inbound_email():
    """
    Handle incoming emails with the following flow:
    1. Customer Inquiry → Database (Status: 'Inquiry')
    2. Customer Clicks "Book Now" → Database (Status: 'Inquiry' → 'Requested')
    3. Bot Sends Acknowledgment → Database (Status: 'Requested' maintained)
    4. Customer Replies Again → Database (Status: 'Requested' maintained)
    """
    try:
        from_email = request.form.get('from', '')
        subject = request.form.get('subject', '')
        text_body = request.form.get('text', '')
        html_body = request.form.get('html', '')
        headers = request.form.get('headers', '')

        body = text_body if text_body else html_body
        message_id = extract_message_id(headers)

        logging.info("="*80)
        logging.info(f"📨 INBOUND WEBHOOK")
        logging.info(f"From: {from_email}")
        logging.info(f"Subject: {subject}")
        logging.info("="*80)

        # Check for duplicate
        if message_id and is_duplicate_message(message_id):
            logging.warning(f"⚠️  DUPLICATE - SKIPPING")
            return jsonify({'status': 'duplicate'}), 200

        # Extract clean email
        if '<' in from_email:
            sender_email = from_email.split('<')[1].strip('>')
        else:
            sender_email = from_email

        if not sender_email or '@' not in sender_email:
            return jsonify({'status': 'invalid_email'}), 400

        if not body or len(body.strip()) < 10:
            return jsonify({'status': 'empty_body'}), 200

        # Parse basic info
        parsed = parse_email_simple(subject, body)

        # FLOW DETECTION
        # ==============

        # Case 1: BOOKING REQUEST (customer clicked "Book Now")
        if is_booking_request(subject, body):
            logging.info("📝 DETECTED: BOOKING REQUEST (Customer clicked Book Now)")

            # Extract booking ID from email
            booking_id = extract_booking_id(subject) or extract_booking_id(body)

            if booking_id:
                # Update existing booking to "Requested"
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

                # Send ACKNOWLEDGMENT email
                logging.info("   Sending acknowledgment email...")
                booking_data = get_booking_by_id(booking_id)
                if booking_data:
                    html_email = format_acknowledgment_email(booking_data)
                    subject_line = "Your Booking Request - The Island Golf Club"
                    send_email_sendgrid(sender_email, subject_line, html_email)

                    # Update note to reflect acknowledgment sent
                    ack_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    update_booking_in_db(booking_id, {
                        'note': f"Customer sent booking request on {timestamp}\nAcknowledgment email sent on {ack_timestamp}"
                    })

                return jsonify({'status': 'requested', 'booking_id': booking_id}), 200
            else:
                logging.warning("   Booking request but no booking ID found")
                return jsonify({'status': 'no_booking_id'}), 200

        # Case 2: CUSTOMER REPLY (replying to acknowledgment)
        elif is_customer_reply(subject, body):
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

                    return jsonify({'status': 'reply_received', 'booking_id': booking_id}), 200

            logging.info("   Reply but no matching booking found - treating as new inquiry")

        # Case 3: NEW INQUIRY (default)
        logging.info("📧 DETECTED: NEW INQUIRY")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create new booking with status 'Inquiry'
        booking_id = generate_booking_id(sender_email, timestamp)

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
            "status": "Inquiry",  # ← KEY: Initial status is "Inquiry"
            "note": "Initial inquiry received",
            "club": DEFAULT_COURSE_ID,
            "club_name": FROM_NAME
        }

        save_booking_to_db(new_entry)

        # Check availability and send inquiry email with time offers
        if parsed['dates']:
            try:
                response = requests.post(
                    f"{CORE_API_URL}/api/availability/check",
                    json={
                        'course_id': DEFAULT_COURSE_ID,
                        'dates': parsed['dates'],
                        'players': parsed['players']
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    api_data = response.json()
                    results = api_data.get('results', [])

                    if results:
                        # Send inquiry email with available times
                        html_email = format_inquiry_email(results, parsed['players'], sender_email, booking_id)
                        subject_line = "Available Tee Times at The Island Golf Club"
                        send_email_sendgrid(sender_email, subject_line, html_email)
                    else:
                        # No availability
                        html_email = format_no_availability_email(parsed['players'])
                        subject_line = "Tee Time Availability - The Island Golf Club"
                        send_email_sendgrid(sender_email, subject_line, html_email)
                else:
                    logging.warning(f"API returned non-200 status: {response.status_code}")
                    # Send fallback "we received your inquiry" email
                    html_email = format_inquiry_received_email(parsed, sender_email, booking_id)
                    subject_line = "Tee Time Inquiry - The Island Golf Club"
                    send_email_sendgrid(sender_email, subject_line, html_email)

            except requests.RequestException as e:
                logging.error(f"API error: {e}")
                # Send fallback "we received your inquiry" email
                html_email = format_inquiry_received_email(parsed, sender_email, booking_id)
                subject_line = "Tee Time Inquiry - The Island Golf Club"
                send_email_sendgrid(sender_email, subject_line, html_email)
        else:
            # No dates found - send "please provide dates" email
            html_email = format_inquiry_received_email(parsed, sender_email, booking_id)
            subject_line = "Tee Time Inquiry - The Island Golf Club"
            send_email_sendgrid(sender_email, subject_line, html_email)

        return jsonify({'status': 'inquiry_created', 'booking_id': booking_id}), 200

    except Exception as e:
        logging.exception(f"❌ ERROR:")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
        """, (DEFAULT_COURSE_ID,))

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
# INITIALIZE
# ============================================================================
logging.info("="*80)
logging.info("🌐 The Island Golf Club - Email Bot")
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
logging.info(f"🔗 Core API: {CORE_API_URL}")
logging.info("="*80)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
