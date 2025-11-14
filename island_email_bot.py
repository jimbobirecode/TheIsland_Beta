#!/usr/bin/env python3
"""
TeeMail Email Bot - The Island Golf Club Edition
================================================

Enhanced with The Island branded HTML email templates
"""

from flask import Flask, request, jsonify
import logging
import json
import os
import requests
from datetime import datetime, timedelta
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

# Core API endpoint
CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:5001")

# External Dashboard API endpoint
DASHBOARD_API_URL = os.getenv("DASHBOARD_API_URL", "https://theisland-dashboard.onrender.com")

# Default course for bookings
DEFAULT_COURSE_ID = os.getenv("DEFAULT_COURSE_ID", "theisland")

# Tracking email for confirmation webhooks
TRACKING_EMAIL_PREFIX = os.getenv("TRACKING_EMAIL_PREFIX", "theisland")

# Club booking email (appears in mailto links for staff copy)
CLUB_BOOKING_EMAIL = os.getenv("CLUB_BOOKING_EMAIL", "bookings@theislandgolfclub.ie")

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- DATABASE CONNECTION POOL ---
db_pool = None

def get_db_pool():
    global db_pool
    if db_pool is None and DATABASE_URL:
        db_pool = SimpleConnectionPool(1, 10, DATABASE_URL)
    return db_pool

def get_db_connection():
    pool = get_db_pool()
    if pool:
        return pool.getconn()
    return None

def release_db_connection(conn):
    pool = get_db_pool()
    if pool and conn:
        pool.putconn(conn)


# --- THE ISLAND BRAND COLORS ---
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
}


# --- HTML EMAIL TEMPLATES ---

def get_email_header():
    """The Island branded email header"""
    return f"""
    <div style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%); padding: 40px 20px; text-align: center; border-radius: 12px 12px 0 0;">
        <h1 style="color: {THE_ISLAND_COLORS['white']}; font-size: 32px; margin: 0 0 10px 0; font-weight: 700; text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);">
            ⛳ The Island Golf Club
        </h1>
        <p style="color: {THE_ISLAND_COLORS['white']}; font-size: 16px; margin: 0; opacity: 0.95;">
            Visitor Tee Time Booking
        </p>
    </div>
    """

def get_email_footer():
    """The Island branded email footer"""
    return f"""
    <div style="background-color: {THE_ISLAND_COLORS['charcoal']}; padding: 30px 20px; text-align: center; border-radius: 0 0 12px 12px; margin-top: 20px;">
        <p style="color: {THE_ISLAND_COLORS['text_light']}; font-size: 14px; margin: 0 0 10px 0;">
            The Island Golf Club
        </p>
        <p style="color: {THE_ISLAND_COLORS['text_light']}; font-size: 12px; margin: 0;">
            Corballis, Donabate, Co. Dublin, K36 KH85, Ireland
        </p>
        <p style="color: {THE_ISLAND_COLORS['text_light']}; font-size: 12px; margin: 10px 0 0 0;">
            📞 +353 1 843 6205 | 📧 bookings@theislandgolfclub.ie
        </p>
    </div>
    """

def format_confirmation_email(booking_data: Dict) -> str:
    """Generate The Island branded HTML confirmation email"""
    
    booking_id = booking_data.get('id', 'N/A')
    player_name = booking_data.get('name', 'N/A')
    email = booking_data.get('email', 'N/A')
    phone = booking_data.get('phone', 'N/A')
    num_players = booking_data.get('num_players', 0)
    preferred_date = booking_data.get('preferred_date', 'N/A')
    preferred_time = booking_data.get('preferred_time', 'N/A')
    total_fee = num_players * PER_PLAYER_FEE
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background-color: {THE_ISLAND_COLORS['light_grey']};">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: {THE_ISLAND_COLORS['light_grey']}; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); overflow: hidden; max-width: 100%;">
                        <tr>
                            <td>
                                {get_email_header()}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px 30px;">
                                <div style="background-color: {THE_ISLAND_COLORS['royal_blue']}; color: white; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
                                    <h2 style="margin: 0; font-size: 24px; font-weight: 600;">✅ Booking Confirmed!</h2>
                                </div>
                                
                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.6; margin: 0 0 25px 0;">
                                    Dear <strong>{player_name}</strong>,
                                </p>
                                
                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.6; margin: 0 0 25px 0;">
                                    We're delighted to confirm your tee time booking at The Island Golf Club, one of Ireland's premier links courses.
                                </p>
                                
                                <div style="background-color: {THE_ISLAND_COLORS['light_grey']}; border-left: 4px solid {THE_ISLAND_COLORS['royal_blue']}; padding: 20px; border-radius: 8px; margin: 25px 0;">
                                    <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 15px 0; font-weight: 600;">
                                        📋 Booking Details
                                    </h3>
                                    
                                    <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>Booking ID:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 8px 0; text-align: right; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {booking_id}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>📅 Date:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 8px 0; text-align: right; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {preferred_date}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>🕐 Time:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 8px 0; text-align: right; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {preferred_time}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>👥 Players:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 8px 0; text-align: right; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {num_players}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0;">
                                                <strong>💶 Total Fee:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['royal_blue']}; font-size: 18px; font-weight: 700; padding: 8px 0; text-align: right;">
                                                €{total_fee:.2f}
                                            </td>
                                        </tr>
                                    </table>
                                </div>
                                
                                <div style="background-color: #e8f0fe; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; padding: 15px; border-radius: 8px; margin: 25px 0;">
                                    <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; margin: 0; line-height: 1.6;">
                                        <strong>ℹ️ Important:</strong> Please arrive 30 minutes before your tee time. Payment is required upon arrival. We accept all major credit cards and cash.
                                    </p>
                                </div>
                                
                                <div style="text-align: center; margin: 30px 0;">
                                    <a href="mailto:{CLUB_BOOKING_EMAIL}" style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; box-shadow: 0 4px 15px rgba(36, 56, 143, 0.3);">
                                        📧 Contact Us
                                    </a>
                                </div>
                                
                                <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; line-height: 1.6; margin: 25px 0 0 0;">
                                    We look forward to welcoming you to The Island Golf Club!
                                </p>
                                
                                <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; line-height: 1.6; margin: 15px 0 0 0;">
                                    Best regards,<br>
                                    <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club Team</strong>
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td>
                                {get_email_footer()}
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    return html_content


def format_provisional_email(booking_data: Dict) -> str:
    """Generate The Island branded provisional booking email"""
    
    booking_id = booking_data.get('id', 'N/A')
    player_name = booking_data.get('name', 'N/A')
    email = booking_data.get('email', 'N/A')
    phone = booking_data.get('phone', 'N/A')
    num_players = booking_data.get('num_players', 0)
    preferred_date = booking_data.get('preferred_date', 'N/A')
    preferred_time = booking_data.get('preferred_time', 'N/A')
    total_fee = num_players * PER_PLAYER_FEE
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background-color: {THE_ISLAND_COLORS['light_grey']};">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: {THE_ISLAND_COLORS['light_grey']}; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); overflow: hidden; max-width: 100%;">
                        <tr>
                            <td>
                                {get_email_header()}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px 30px;">
                                <div style="background-color: {THE_ISLAND_COLORS['powder_blue']}; color: {THE_ISLAND_COLORS['navy_primary']}; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
                                    <h2 style="margin: 0; font-size: 24px; font-weight: 600;">⏳ Booking Request Received</h2>
                                </div>
                                
                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.6; margin: 0 0 25px 0;">
                                    Dear <strong>{player_name}</strong>,
                                </p>
                                
                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.6; margin: 0 0 25px 0;">
                                    Thank you for your tee time request at The Island Golf Club. We have received your booking and our team is reviewing availability.
                                </p>
                                
                                <div style="background-color: {THE_ISLAND_COLORS['light_grey']}; border-left: 4px solid {THE_ISLAND_COLORS['powder_blue']}; padding: 20px; border-radius: 8px; margin: 25px 0;">
                                    <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 15px 0; font-weight: 600;">
                                        📋 Your Request
                                    </h3>
                                    
                                    <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>Booking ID:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 8px 0; text-align: right; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {booking_id}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>📅 Requested Date:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 8px 0; text-align: right; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {preferred_date}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>🕐 Requested Time:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 8px 0; text-align: right; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {preferred_time}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>👥 Players:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 8px 0; text-align: right; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {num_players}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 8px 0;">
                                                <strong>💶 Estimated Fee:</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['royal_blue']}; font-size: 18px; font-weight: 700; padding: 8px 0; text-align: right;">
                                                €{total_fee:.2f}
                                            </td>
                                        </tr>
                                    </table>
                                </div>
                                
                                <div style="background-color: #e8f0fe; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; padding: 15px; border-radius: 8px; margin: 25px 0;">
                                    <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; margin: 0; line-height: 1.6;">
                                        <strong>ℹ️ What's Next?</strong><br>
                                        Our team will confirm availability and send you a confirmation email within 24 hours. If you have any questions, please don't hesitate to contact us.
                                    </p>
                                </div>
                                
                                <div style="text-align: center; margin: 30px 0;">
                                    <a href="mailto:{CLUB_BOOKING_EMAIL}" style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; box-shadow: 0 4px 15px rgba(36, 56, 143, 0.3);">
                                        📧 Contact Us
                                    </a>
                                </div>
                                
                                <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; line-height: 1.6; margin: 25px 0 0 0;">
                                    Thank you for choosing The Island Golf Club.
                                </p>
                                
                                <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; line-height: 1.6; margin: 15px 0 0 0;">
                                    Best regards,<br>
                                    <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club Team</strong>
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td>
                                {get_email_footer()}
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    return html_content


# --- EMAIL SENDING FUNCTION ---

def send_email(to_email: str, subject: str, html_content: str):
    """Send HTML email via SendGrid"""
    try:
        message = Mail(
            from_email=Email(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        logging.info(f"Email sent to {to_email}: {response.status_code}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {e}")
        return False


# --- DATABASE FUNCTIONS ---

def store_booking_in_db(booking_data: Dict) -> bool:
    """Store booking in PostgreSQL database"""
    conn = get_db_connection()
    if not conn:
        logging.warning("No database connection available")
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bookings (
                    id, name, email, phone, num_players,
                    preferred_date, preferred_time, alternate_date,
                    special_requests, status, total_fee, created_at,
                    course_id, raw_email_data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    updated_at = NOW()
            """, (
                booking_data['id'],
                booking_data.get('name'),
                booking_data.get('email'),
                booking_data.get('phone'),
                booking_data.get('num_players'),
                booking_data.get('preferred_date'),
                booking_data.get('preferred_time'),
                booking_data.get('alternate_date'),
                booking_data.get('special_requests'),
                booking_data.get('status', 'provisional'),
                booking_data.get('num_players', 0) * PER_PLAYER_FEE,
                datetime.utcnow(),
                DEFAULT_COURSE_ID,
                Json(booking_data)
            ))
        conn.commit()
        logging.info(f"Stored booking {booking_data['id']} in database")
        return True
    except Exception as e:
        conn.rollback()
        logging.error(f"Failed to store booking in database: {e}")
        return False
    finally:
        release_db_connection(conn)


def update_booking_status(booking_id: str, status: str, notes: str = None) -> bool:
    """Update booking status in database"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            if notes:
                cur.execute("""
                    UPDATE bookings
                    SET status = %s, internal_notes = %s, updated_at = NOW()
                    WHERE id = %s
                """, (status, notes, booking_id))
            else:
                cur.execute("""
                    UPDATE bookings
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s
                """, (status, booking_id))
        conn.commit()
        logging.info(f"Updated booking {booking_id} to status: {status}")
        return True
    except Exception as e:
        conn.rollback()
        logging.error(f"Failed to update booking status: {e}")
        return False
    finally:
        release_db_connection(conn)


# --- WEBHOOK ENDPOINTS ---

@app.route('/webhook/inbound', methods=['POST'])
def inbound_webhook():
    """Handle incoming emails from Email Relay (bookings.teemail.io)"""
    request_id = datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f')[:20]
    
    try:
        logging.info("=" * 80)
        logging.info(f"📨 WEBHOOK TRIGGERED [{request_id}]")
        logging.info("=" * 80)
        
        # Parse incoming email data
        data = request.form
        
        # Log what we received
        logging.info(f"📦 Received {len(data)} form fields:")
        for key in data.keys():
            value = data.get(key, '')
            if key in ['text', 'html', 'email']:
                logging.info(f"   {key}: {len(value)} chars")
            else:
                logging.info(f"   {key}: {value[:100]}")
        
        # Extract email fields
        from_email = data.get('from', '')
        to_email = data.get('to', '')
        subject = data.get('subject', '')
        text_body = data.get('text', '')
        html_body = data.get('html', '')
        
        logging.info("")
        logging.info("📧 Email Details:")
        logging.info(f"   From: {from_email}")
        logging.info(f"   To: {to_email}")
        logging.info(f"   Subject: {subject}")
        logging.info(f"   Text Body: {len(text_body)} chars")
        logging.info(f"   HTML Body: {len(html_body)} chars")
        
        if text_body:
            logging.info("")
            logging.info("📄 Text Body Preview (first 500 chars):")
            logging.info(text_body[:500])
        
        # Validate required fields
        if not from_email:
            logging.error("❌ Missing required field: from")
            return jsonify({
                'status': 'error',
                'message': 'Missing from field',
                'request_id': request_id
            }), 400
        
        if not subject and not text_body:
            logging.error("❌ Missing both subject and text body")
            return jsonify({
                'status': 'error',
                'message': 'Missing subject and text body',
                'request_id': request_id
            }), 400
        
        # Extract clean email address
        sender_email = from_email
        sender_name = "Visitor"
        
        if '<' in from_email:
            # Format: "John Doe <john@example.com>"
            parts = from_email.split('<')
            sender_name = parts[0].strip().strip('"')
            sender_email = parts[1].strip('>')
            logging.info(f"   Extracted name: {sender_name}")
            logging.info(f"   Extracted email: {sender_email}")
        else:
            # Use email username as name
            sender_name = sender_email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
            logging.info(f"   Generated name from email: {sender_name}")
        
        # Create booking with received data
        booking_id = str(uuid.uuid4())[:8]
        
        booking_data = {
            'id': booking_id,
            'name': sender_name,
            'email': sender_email,
            'phone': 'N/A',
            'num_players': 4,  # Default - TODO: parse from email body
            'preferred_date': 'TBD',  # TODO: parse from email body
            'preferred_time': 'TBD',  # TODO: parse from email body
            'alternate_date': None,
            'special_requests': text_body[:500] if text_body else subject,
            'status': 'provisional',
            'course_id': DEFAULT_COURSE_ID
        }
        
        logging.info("")
        logging.info(f"📋 Creating Booking:")
        logging.info(f"   ID: {booking_id}")
        logging.info(f"   Name: {sender_name}")
        logging.info(f"   Email: {sender_email}")
        logging.info(f"   Players: {booking_data['num_players']}")
        logging.info(f"   Date: {booking_data['preferred_date']}")
        logging.info(f"   Time: {booking_data['preferred_time']}")
        
        # Store in database
        logging.info("")
        logging.info("💾 Storing in database...")
        db_stored = store_booking_in_db(booking_data)
        
        if db_stored:
            logging.info("✅ Database: SUCCESS")
        else:
            logging.error("❌ Database: FAILED")
            logging.error("   Check DATABASE_URL environment variable")
            logging.error("   Check database connection and schema")
        
        # Send provisional confirmation email
        logging.info("")
        logging.info("📧 Sending confirmation email...")
        email_sent = False
        
        try:
            if not SENDGRID_API_KEY:
                logging.error("❌ SENDGRID_API_KEY not set!")
                logging.error("   Cannot send confirmation email")
            else:
                html_email = format_provisional_email(booking_data)
                email_sent = send_email(
                    sender_email,
                    "Your Island Golf Club Booking Request",
                    html_email
                )
                
                if email_sent:
                    logging.info("✅ Email: SUCCESS")
                    logging.info(f"   Sent to: {sender_email}")
                else:
                    logging.error("❌ Email: FAILED")
                    logging.error("   Check SendGrid API key and configuration")
                    
        except Exception as email_error:
            logging.error(f"❌ Email Error: {email_error}")
            logging.error(f"   Type: {type(email_error).__name__}")
            import traceback
            logging.error(f"   Traceback: {traceback.format_exc()}")
        
        logging.info("")
        logging.info("=" * 80)
        logging.info(f"✅ WEBHOOK COMPLETE [{request_id}]")
        logging.info(f"   Booking ID: {booking_id}")
        logging.info(f"   Database: {'✅' if db_stored else '❌'}")
        logging.info(f"   Email: {'✅' if email_sent else '❌'}")
        logging.info("=" * 80)
        
        return jsonify({
            'status': 'success',
            'booking_id': booking_id,
            'database_stored': db_stored,
            'email_sent': email_sent,
            'from': sender_email,
            'subject': subject,
            'request_id': request_id
        }), 200
        
    except Exception as e:
        logging.error("=" * 80)
        logging.error(f"❌ WEBHOOK ERROR [{request_id}]")
        logging.error("=" * 80)
        logging.error(f"   Error Type: {type(e).__name__}")
        logging.error(f"   Error Message: {str(e)}")
        
        import traceback
        logging.error("")
        logging.error("📋 Full Traceback:")
        logging.error(traceback.format_exc())
        logging.error("=" * 80)
        
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_type': type(e).__name__,
            'request_id': request_id
        }), 500


@app.route('/webhook/events', methods=['POST'])
def event_webhook():
    """Handle email events (opens, clicks, etc.)"""
    try:
        events = request.json
        for event in events:
            event_type = event.get('event')
            email = event.get('email')
            logging.info(f"Email event: {event_type} for {email}")
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logging.error(f"Error processing event: {e}")
        return jsonify({'status': 'error'}), 500


@app.route('/api/confirm/<booking_id>', methods=['POST'])
def confirm_booking(booking_id):
    """Confirm a booking and send confirmation email"""
    try:
        # Get booking from database
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Database unavailable'}), 500
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,))
                booking = cur.fetchone()
            
            if not booking:
                return jsonify({'status': 'error', 'message': 'Booking not found'}), 404
            
            # Update status
            update_booking_status(booking_id, 'confirmed')
            
            # Send confirmation email
            html_email = format_confirmation_email(dict(booking))
            send_email(booking['email'], "✅ Your Island Golf Club Booking is Confirmed!", html_email)
            
            return jsonify({'status': 'success', 'booking_id': booking_id}), 200
            
        finally:
            release_db_connection(conn)
            
    except Exception as e:
        logging.error(f"Error confirming booking: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    """Get all bookings"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database unavailable'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM bookings
                WHERE course_id = %s
                ORDER BY created_at DESC
            """, (DEFAULT_COURSE_ID,))
            bookings = cur.fetchall()
        
        return jsonify({'status': 'success', 'bookings': bookings}), 200
    finally:
        release_db_connection(conn)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'The Island Email Bot',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
