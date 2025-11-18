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
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

app = Flask(__name__)

# --- CONFIG ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "theisland@bookings.teemail.io")
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
    'gold_accent': '#D4AF37',
    'green_success': '#2D5F3F',
    'bg_light': '#f3f4f6',
}


# --- HTML EMAIL TEMPLATES ---

def get_email_header():
    """The Island Golf Club branded email header with Outlook compatibility"""
    return f"""
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title>The Island Golf Club - Booking</title>

        <!--[if mso]>
        <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:AllowPNG/>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
        </noscript>
        <style type="text/css">
            body, table, td, p, div, span, a {{
                font-family: Georgia, 'Times New Roman', serif !important;
            }}
            table {{
                border-collapse: collapse !important;
                mso-table-lspace: 0pt !important;
                mso-table-rspace: 0pt !important;
            }}
        </style>
        <![endif]-->

        <style type="text/css">
            body {{
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
                font-family: Georgia, 'Times New Roman', serif;
                background-color: {THE_ISLAND_COLORS['bg_light']};
            }}

            table {{
                border-collapse: collapse;
                mso-table-lspace: 0pt;
                mso-table-rspace: 0pt;
            }}

            .email-wrapper {{
                background-color: {THE_ISLAND_COLORS['bg_light']};
                padding: 20px;
            }}

            .email-container {{
                background: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}

            .header {{
                background: linear-gradient(135deg, {THE_ISLAND_COLORS['gradient_start']} 0%, {THE_ISLAND_COLORS['gradient_end']} 100%);
                background-color: {THE_ISLAND_COLORS['navy_primary']};
                padding: 40px 30px;
                text-align: center;
                color: #ffffff;
                position: relative;
            }}

            .header::before {{
                content: '';
                position: absolute;
                top: -50px;
                right: -50px;
                width: 200px;
                height: 200px;
                background: radial-gradient(circle, rgba(212, 175, 55, 0.2) 0%, transparent 70%);
                border-radius: 50%;
            }}

            .header h1 {{
                margin: 0 0 10px 0;
                font-size: 32px;
                font-weight: 700;
                color: #ffffff;
                letter-spacing: -0.5px;
                position: relative;
                z-index: 1;
            }}

            .header p {{
                margin: 0;
                color: {THE_ISLAND_COLORS['gold_accent']};
                font-size: 16px;
                font-weight: 600;
                position: relative;
                z-index: 1;
            }}

            .est-badge {{
                display: inline-block;
                margin-top: 8px;
                padding: 4px 12px;
                background: rgba(212, 175, 55, 0.2);
                border: 1px solid {THE_ISLAND_COLORS['gold_accent']};
                border-radius: 20px;
                color: {THE_ISLAND_COLORS['gold_accent']};
                font-size: 12px;
                letter-spacing: 1px;
            }}

            .content {{
                padding: 40px 30px;
            }}

            .info-box {{
                background: linear-gradient(to right, #f0f9ff 0%, #e0f2fe 100%);
                background-color: #f0f9ff;
                border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']};
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
            }}

            .booking-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 25px 0;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                border: 1px solid {THE_ISLAND_COLORS['border_grey']};
            }}

            .booking-table tr {{
                border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};
            }}

            .booking-table td {{
                padding: 15px 12px;
                color: {THE_ISLAND_COLORS['text_dark']};
            }}

            .button-link {{
                background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%);
                background-color: {THE_ISLAND_COLORS['navy_primary']};
                color: #ffffff !important;
                padding: 15px 40px;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 16px;
                display: inline-block;
                box-shadow: 0 4px 15px rgba(36, 56, 143, 0.3);
            }}

            .footer {{
                background: linear-gradient(135deg, {THE_ISLAND_COLORS['gradient_start']} 0%, {THE_ISLAND_COLORS['gradient_end']} 100%);
                background-color: {THE_ISLAND_COLORS['navy_primary']};
                padding: 30px;
                text-align: center;
                color: #ffffff;
            }}

            .footer strong {{
                color: {THE_ISLAND_COLORS['gold_accent']};
                font-size: 18px;
            }}

            .footer a {{
                color: {THE_ISLAND_COLORS['gold_accent']};
                text-decoration: none;
                font-weight: 600;
            }}

            @media only screen and (max-width: 600px) {{
                .header h1 {{ font-size: 24px !important; }}
                .content {{ padding: 20px 15px !important; }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; background-color: {THE_ISLAND_COLORS['bg_light']};">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" class="email-wrapper" style="border-collapse: collapse;">
            <tr>
                <td style="padding: 20px; background-color: {THE_ISLAND_COLORS['bg_light']};">
                    <table role="presentation" class="email-container" align="center" border="0" cellpadding="0" cellspacing="0" width="800" style="max-width: 800px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <tr>
                            <td class="header" style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['gradient_start']} 0%, {THE_ISLAND_COLORS['gradient_end']} 100%); background-color: {THE_ISLAND_COLORS['navy_primary']}; padding: 40px 30px; text-align: center; color: #ffffff; position: relative;">
                                <!--[if gte mso 9]>
                                <v:rect xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false" style="width:800px;height:150px;">
                                <v:fill type="gradient" color="{THE_ISLAND_COLORS['gradient_end']}" color2="{THE_ISLAND_COLORS['gradient_start']}" angle="135" />
                                <v:textbox inset="40px,40px,40px,40px">
                                <![endif]-->
                                <div style="color: #ffffff;">
                                    <h1 style="margin: 0 0 10px 0; font-size: 32px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">
                                        ⛳ The Island Golf Club
                                    </h1>
                                    <p style="margin: 0; color: {THE_ISLAND_COLORS['gold_accent']}; font-size: 16px; font-weight: 600;">
                                        Visitor Tee Time Booking
                                    </p>
                                    <div class="est-badge" style="display: inline-block; margin-top: 8px; padding: 4px 12px; background: rgba(212, 175, 55, 0.2); border: 1px solid {THE_ISLAND_COLORS['gold_accent']}; border-radius: 20px; color: {THE_ISLAND_COLORS['gold_accent']}; font-size: 12px; letter-spacing: 1px;">
                                        CHAMPIONSHIP LINKS
                                    </div>
                                </div>
                                <!--[if gte mso 9]>
                                </v:textbox>
                                </v:rect>
                                <![endif]-->
                            </td>
                        </tr>
                        <tr>
                            <td class="content" style="padding: 40px 30px;">
    """

def get_email_footer():
    """The Island Golf Club branded email footer with Outlook compatibility"""
    return f"""
                            </td>
                        </tr>
                        <tr>
                            <td class="footer" style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['gradient_start']} 0%, {THE_ISLAND_COLORS['gradient_end']} 100%); background-color: {THE_ISLAND_COLORS['navy_primary']}; padding: 30px; text-align: center; color: #ffffff; position: relative;">
                                <!--[if gte mso 9]>
                                <v:rect xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false" style="width:800px;height:180px;">
                                <v:fill type="gradient" color="{THE_ISLAND_COLORS['gradient_end']}" color2="{THE_ISLAND_COLORS['gradient_start']}" angle="135" />
                                <v:textbox inset="30px,30px,30px,30px">
                                <![endif]-->
                                <div style="color: #ffffff;">
                                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">
                                        <tr>
                                            <td style="padding: 0 0 15px 0; text-align: center;">
                                                <strong style="color: {THE_ISLAND_COLORS['gold_accent']}; font-size: 18px; letter-spacing: 0.5px;">
                                                    The Island Golf Club
                                                </strong>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 0 0 10px 0; text-align: center;">
                                                <p style="margin: 0; color: #ffffff; font-size: 14px; line-height: 1.6;">
                                                    Corballis, Donabate, Co. Dublin, K36 KH85, Ireland
                                                </p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 0 0 15px 0; text-align: center;">
                                                <p style="margin: 0; color: {THE_ISLAND_COLORS['powder_blue']}; font-size: 13px;">
                                                    <a href="tel:+35318436205" style="color: {THE_ISLAND_COLORS['gold_accent']}; text-decoration: none; font-weight: 600;">📞 +353 1 843 6205</a>
                                                    <span style="color: {THE_ISLAND_COLORS['powder_blue']}; margin: 0 8px;">|</span>
                                                    <a href="mailto:{CLUB_BOOKING_EMAIL}" style="color: {THE_ISLAND_COLORS['gold_accent']}; text-decoration: none; font-weight: 600;">📧 bookings@theislandgolfclub.ie</a>
                                                </p>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td style="padding: 15px 0 0 0; text-align: center; border-top: 1px solid rgba(212, 175, 55, 0.3);">
                                                <p style="margin: 0; color: {THE_ISLAND_COLORS['powder_blue']}; font-size: 12px; line-height: 1.5;">
                                                    Championship Links Golf Course
                                                </p>
                                            </td>
                                        </tr>
                                    </table>
                                </div>
                                <!--[if gte mso 9]>
                                </v:textbox>
                                </v:rect>
                                <![endif]-->
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

def build_booking_link(date: str, time: str, players: int, guest_email: str, booking_id: str = None) -> str:
    """Generate mailto link for Reserve Now button"""

    tracking_email = f"{TRACKING_EMAIL_PREFIX}@bookings.teemail.io"
    club_email = CLUB_BOOKING_EMAIL

    # Format booking details
    subject = quote(f"CONFIRM BOOKING - {date} at {time}")

    body_lines = [
        f"CONFIRM BOOKING",
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

    # Create mailto link with both tracking and club email
    mailto_link = f"mailto:{club_email}?cc={tracking_email}&subject={subject}&body={body}"

    return mailto_link


def create_book_button(booking_link: str, button_text: str = "Reserve Now") -> str:
    """Create HTML for Reserve Now button"""
    return f"""
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin: 0 auto;">
            <tr>
                <td style="border-radius: 6px; background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%);">
                    <a href="{booking_link}" style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%); background-color: {THE_ISLAND_COLORS['navy_primary']}; color: #ffffff !important; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; display: inline-block;">
                        {button_text}
                    </a>
                </td>
            </tr>
        </table>
    """


def format_availability_email(results: list, player_count: int, guest_email: str, booking_id: str = None,
                             used_alternatives: bool = False, original_dates: list = None) -> str:
    """Generate The Island Golf Club branded HTML email with available tee times"""

    html = get_email_header()

    # Opening greeting
    html += f"""
                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8; margin: 0 0 20px 0;">
                                    Thank you for your enquiry. We are delighted to present the following available tee times at <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club</strong>, one of Ireland's finest championship links courses:
                                </p>

                                <div style="background: linear-gradient(to right, #f0f9ff 0%, #e0f2fe 100%); background-color: #f0f9ff; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; border-radius: 8px; padding: 20px; margin: 25px 0;">
                                    <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 15px 0; font-weight: 700;">
                                        👥 Booking Details
                                    </h3>
                                    <p style="margin: 5px 0; color: {THE_ISLAND_COLORS['text_dark']};"><strong>Players:</strong> {player_count}</p>
                                    <p style="margin: 5px 0; color: {THE_ISLAND_COLORS['text_dark']};"><strong>Green Fee:</strong> €{PER_PLAYER_FEE:.0f} per player</p>
                                    <p style="margin: 5px 0; color: {THE_ISLAND_COLORS['text_dark']};"><strong>Status:</strong> <span style="display: inline-block; padding: 4px 10px; background: #ecfdf5; color: {THE_ISLAND_COLORS['green_success']}; border: 1px solid {THE_ISLAND_COLORS['green_success']}; border-radius: 15px; font-size: 13px; font-weight: 600;">{'✓ Alternative Dates Found' if used_alternatives else '✓ Available Times Found'}</span></p>
                                </div>
    """

    # Add alternative dates notice if applicable
    if used_alternatives and original_dates:
        original_dates_str = ', '.join(original_dates)
        plural = 's' if len(original_dates) > 1 else ''
        were_was = 'were' if len(original_dates) > 1 else 'was'

        html += f"""
                                <div style="background: linear-gradient(to right, #FFFEF7 0%, #FFF9E6 100%); background-color: #FFFEF7; border: 2px solid {THE_ISLAND_COLORS['gold_accent']}; border-radius: 8px; padding: 20px; margin: 25px 0;">
                                    <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0; font-weight: 700;">
                                        🎯 Alternative Dates Found!
                                    </h3>
                                    <p style="font-size: 15px; margin: 0 0 12px 0; line-height: 1.6; color: {THE_ISLAND_COLORS['text_dark']};">
                                        Your requested date{plural} <strong style="color: #8B7355;">({original_dates_str})</strong> {were_was} fully booked.
                                    </p>
                                    <div style="background: rgba(212, 175, 55, 0.15); padding: 12px; border-radius: 6px; border-left: 3px solid {THE_ISLAND_COLORS['gold_accent']};">
                                        <p style="margin: 0; font-weight: 600; color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 15px;">
                                            ✅ Great news! We found available tee times within the same week
                                        </p>
                                        <p style="margin: 8px 0 0 0; color: {THE_ISLAND_COLORS['text_medium']}; line-height: 1.6; font-size: 14px;">
                                            These alternative dates offer the same championship golf experience and are clearly marked below with <strong style="color: {THE_ISLAND_COLORS['gold_accent']};">gold badges</strong>.
                                        </p>
                                    </div>
                                </div>
        """

    # Group results by date
    dates_list = sorted(list(set([r["date"] for r in results])))

    for date in dates_list:
        date_results = [r for r in results if r["date"] == date]

        if not date_results:
            continue

        # Check if this is an alternative date
        is_alt_date = date_results[0].get('is_alternative_date', False)

        # Start alternative date wrapper if needed
        if is_alt_date:
            html += f"""
                                <div style="background: linear-gradient(to right, #FFFEF7 0%, #FFF9E6 100%); background-color: #FFFEF7; border: 2px solid {THE_ISLAND_COLORS['gold_accent']}; padding: 20px; margin: 30px 0; border-radius: 8px;">
            """

        gold_color = THE_ISLAND_COLORS['gold_accent']
        date_badge = f'<span style="display: inline-block; padding: 4px 12px; background: #fef3c7; color: #92400e; border: 1px solid {gold_color}; border-radius: 15px; font-size: 13px; font-weight: 600; margin-left: 10px;">📅 Alternative Date</span>' if is_alt_date else ''

        html += f"""
                                <div style="margin: 30px 0;">
                                    <h2 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 22px; font-weight: 700; margin: 0 0 15px 0; padding-bottom: 10px; border-bottom: 3px solid {THE_ISLAND_COLORS['gold_accent']};">
                                        🗓️ {date} {date_badge}
                                    </h2>
                                    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; margin: 20px 0; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05); border: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                        <thead>
                                            <tr style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%); background-color: {THE_ISLAND_COLORS['navy_primary']}; color: #ffffff;">
                                                <th style="padding: 15px 12px; color: #ffffff; font-weight: 600; text-align: left; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Tee Time</th>
                                                <th style="padding: 15px 12px; color: #ffffff; font-weight: 600; text-align: center; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Availability</th>
                                                <th style="padding: 15px 12px; color: #ffffff; font-weight: 600; text-align: left; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Green Fee</th>
                                                <th style="padding: 15px 12px; color: #ffffff; font-weight: 600; text-align: center; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Booking</th>
                                            </tr>
                                        </thead>
                                        <tbody>
        """

        row_count = 0
        for result in date_results:
            time = result["time"]
            row_bg = '#f9fafb' if row_count % 2 == 0 else '#ffffff'
            if is_alt_date:
                row_bg = '#FFFEF7'

            booking_link = build_booking_link(date, time, player_count, guest_email, booking_id)
            button_html = create_book_button(booking_link, "Reserve Now")

            html += f"""
                                            <tr style="background-color: {row_bg}{'; border-left: 3px solid ' + THE_ISLAND_COLORS['gold_accent'] if is_alt_date else ''};">
                                                <td style="padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};"><strong style="font-size: 16px; color: {THE_ISLAND_COLORS['navy_primary']};">{time}</strong></td>
                                                <td style="padding: 15px 12px; text-align: center; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};"><span style="display: inline-block; padding: 4px 10px; background: #ecfdf5; color: {THE_ISLAND_COLORS['green_success']}; border: 1px solid {THE_ISLAND_COLORS['green_success']}; border-radius: 15px; font-size: 13px; font-weight: 600;">✓ Available</span></td>
                                                <td style="padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};"><span style="color: {THE_ISLAND_COLORS['royal_blue']}; font-weight: 700; font-size: 15px;">€{PER_PLAYER_FEE:.0f} pp</span></td>
                                                <td style="padding: 15px 12px; text-align: center; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                    {button_html}
                                                </td>
                                            </tr>
            """
            row_count += 1

        html += """
                                        </tbody>
                                    </table>
                                </div>
        """

        # Close alternative date wrapper if needed
        if is_alt_date:
            html += "</div>"

    # Add championship links description
    html += f"""
                                <div style="background: linear-gradient(to right, #f0f9ff 0%, #e0f2fe 100%); background-color: #f0f9ff; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; border-radius: 8px; padding: 20px; margin: 30px 0;">
                                    <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0; font-weight: 700;">
                                        ⛳ Championship Links Experience
                                    </h3>
                                    <p style="margin: 0; color: {THE_ISLAND_COLORS['text_dark']}; line-height: 1.7;">
                                        The Island Golf Club features a classic links layout offering stunning views and an authentic Irish golfing experience. Our championship course provides golfers with a memorable round of links golf.
                                    </p>
                                </div>

                                <div style="background: linear-gradient(to right, #e8f0fe 0%, #dbeafe 100%); background-color: #e8f0fe; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; border-radius: 8px; padding: 20px; margin: 30px 0;">
                                    <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 18px; margin: 0 0 12px 0; font-weight: 700;">
                                        💡 How to Confirm Your Booking
                                    </h3>
                                    <p style="margin: 5px 0; color: {THE_ISLAND_COLORS['text_dark']};"><strong>Step 1:</strong> Click any "Reserve Now" button above for your preferred tee time</p>
                                    <p style="margin: 5px 0; color: {THE_ISLAND_COLORS['text_dark']};"><strong>Step 2:</strong> Your email client will open with a pre-filled booking request</p>
                                    <p style="margin: 5px 0; color: {THE_ISLAND_COLORS['text_dark']};"><strong>Step 3:</strong> Simply send the email - we'll confirm within 30 minutes</p>
                                    <p style="margin-top: 12px; font-style: italic; color: {THE_ISLAND_COLORS['text_medium']};font-size: 14px;">Alternatively, you may telephone us at <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">+353 1 843 6205</strong></p>
                                </div>
    """

    html += get_email_footer()

    return html


def format_no_availability_email(player_count: int, original_dates: list = None, checked_alternatives: bool = False) -> str:
    """Generate HTML email when no availability found"""

    html = get_email_header()

    html += f"""
                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8; margin: 0 0 20px 0;">
                                    Thank you for your enquiry regarding tee times at <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club</strong>.
                                </p>

                                <div style="background: linear-gradient(to right, #fef2f2 0%, #fee2e2 100%); background-color: #fef2f2; border-left: 4px solid #dc2626; border-radius: 8px; padding: 20px; margin: 25px 0;">
                                    <h3 style="color: #dc2626; font-size: 18px; margin: 0 0 12px 0; font-weight: 700;">
                                        ⚠️ No Availability Found
                                    </h3>
                                    <p style="margin: 0; color: {THE_ISLAND_COLORS['text_dark']}; line-height: 1.6;">
                                        Unfortunately, we do not have availability for <strong>{player_count} player(s)</strong> on your requested dates.
                                    </p>
    """

    if checked_alternatives:
        html += f"""
                                    <p style="margin: 10px 0 0 0; color: {THE_ISLAND_COLORS['text_medium']}; line-height: 1.6;">
                                        We have checked dates within a week of your request, but were unable to find suitable availability.
                                    </p>
        """

    html += """
                                </div>

                                <div style="background: linear-gradient(to right, #f0f9ff 0%, #e0f2fe 100%); background-color: #f0f9ff; border-left: 4px solid """ + THE_ISLAND_COLORS['navy_primary'] + """; border-radius: 8px; padding: 20px; margin: 30px 0;">
                                    <h3 style="color: """ + THE_ISLAND_COLORS['navy_primary'] + """; font-size: 18px; margin: 0 0 12px 0; font-weight: 700;">
                                        📞 Please Contact Us
                                    </h3>
                                    <p style="margin: 5px 0; color: """ + THE_ISLAND_COLORS['text_dark'] + """;">We would be delighted to assist you in finding alternative dates or discuss other options:</p>
                                    <p style="margin: 8px 0; color: """ + THE_ISLAND_COLORS['text_dark'] + """;"><strong>Email:</strong> <a href="mailto:""" + CLUB_BOOKING_EMAIL + """" style="color: """ + THE_ISLAND_COLORS['navy_primary'] + """;">""" + CLUB_BOOKING_EMAIL + """</a></p>
                                    <p style="margin: 8px 0; color: """ + THE_ISLAND_COLORS['text_dark'] + """;"><strong>Telephone:</strong> <a href="tel:+35318436205" style="color: """ + THE_ISLAND_COLORS['navy_primary'] + """;">+353 1 843 6205</a></p>
                                </div>

                                <p style="color: """ + THE_ISLAND_COLORS['text_medium'] + """; font-size: 15px; line-height: 1.8; margin: 20px 0 0 0;">
                                    We look forward to welcoming you to our championship links course.
                                </p>
    """

    html += get_email_footer()

    return html


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
{get_email_header()}
                                <div style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['green_success']} 0%, #1e4d2e 100%); background-color: {THE_ISLAND_COLORS['green_success']}; color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 30px; box-shadow: 0 4px 12px rgba(45, 95, 63, 0.3);">
                                    <h2 style="margin: 0; font-size: 28px; font-weight: 700; color: #ffffff;">✅ Booking Confirmed!</h2>
                                </div>

                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8; margin: 0 0 20px 0;">
                                    Dear <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">{player_name}</strong>,
                                </p>

                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8; margin: 0 0 30px 0;">
                                    We're delighted to confirm your tee time booking at <strong>The Island Golf Club</strong>, one of Ireland's premier championship links courses.
                                </p>

                                <div class="info-box" style="background: linear-gradient(to right, #f0f9ff 0%, #e0f2fe 100%); background-color: #f0f9ff; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; border-radius: 8px; padding: 25px; margin: 30px 0;">
                                    <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 20px; margin: 0 0 20px 0; font-weight: 700;">
                                        📋 Confirmed Booking Details
                                    </h3>

                                    <table class="booking-table" width="100%" cellpadding="12" cellspacing="0" style="border-collapse: collapse; border-radius: 8px; overflow: hidden; border: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                        <tr style="background-color: {THE_ISLAND_COLORS['light_grey']};">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 15px 12px; font-weight: 600; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                Booking ID
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 15px 12px; text-align: right; font-weight: 600; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {booking_id}
                                            </td>
                                        </tr>
                                        <tr style="background-color: #ffffff;">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>📅 Date</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 15px; padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {preferred_date}
                                            </td>
                                        </tr>
                                        <tr style="background-color: {THE_ISLAND_COLORS['light_grey']};">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>🕐 Tee Time</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 15px; padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {preferred_time}
                                            </td>
                                        </tr>
                                        <tr style="background-color: #ffffff;">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>👥 Number of Players</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 15px; padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {num_players}
                                            </td>
                                        </tr>
                                        <tr style="background-color: #fffbeb;">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 15px; padding: 18px 12px; font-weight: 700;">
                                                <strong>💶 Total Fee</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['green_success']}; font-size: 22px; font-weight: 700; padding: 18px 12px; text-align: right;">
                                                €{total_fee:.2f}
                                            </td>
                                        </tr>
                                    </table>
                                </div>

                                <div style="background: linear-gradient(to right, #e8f0fe 0%, #dbeafe 100%); background-color: #e8f0fe; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; margin: 30px 0;">
                                    <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 15px; margin: 0 0 12px 0; line-height: 1.7;">
                                        <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">ℹ️ Important Information:</strong>
                                    </p>
                                    <ul style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; margin: 0; padding-left: 20px; line-height: 1.8;">
                                        <li>Please arrive <strong>30 minutes before</strong> your tee time</li>
                                        <li>Payment is required upon arrival</li>
                                        <li>We accept all major credit cards and cash</li>
                                        <li>Please contact us immediately if you need to make changes</li>
                                    </ul>
                                </div>

                                <div style="text-align: center; margin: 35px 0;">
                                    <a href="mailto:{CLUB_BOOKING_EMAIL}" class="button-link" style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%); background-color: {THE_ISLAND_COLORS['navy_primary']}; color: #ffffff !important; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; box-shadow: 0 4px 15px rgba(36, 56, 143, 0.3);">
                                        📧 Contact Club Office
                                    </a>
                                </div>

                                <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 15px; line-height: 1.8; margin: 30px 0 0 0;">
                                    We look forward to welcoming you to The Island Golf Club and hope you enjoy your round on our championship links course.
                                </p>

                                <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; line-height: 1.6; margin: 20px 0 0 0;">
                                    Best regards,<br>
                                    <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club Team</strong>
                                </p>
{get_email_footer()}
    """

    return html_content


def format_provisional_email(booking_data: Dict) -> str:
    """Generate The Island branded provisional booking email with reply-to-confirm workflow"""

    booking_id = booking_data.get('id', 'N/A')
    player_name = booking_data.get('name', 'N/A')
    email = booking_data.get('email', 'N/A')
    phone = booking_data.get('phone', 'N/A')
    num_players = booking_data.get('num_players', 0)
    preferred_date = booking_data.get('preferred_date', 'N/A')
    preferred_time = booking_data.get('preferred_time', 'N/A')
    alternate_date = booking_data.get('alternate_date')
    total_fee = num_players * PER_PLAYER_FEE

    # Build alternate date row if provided (with highlighted styling)
    alternate_row = ""
    if alternate_date:
        alternate_row = f"""
                                        <tr style="background-color: #fef3c7;">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>📅 Alternate Date</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 15px; padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {alternate_date}
                                            </td>
                                        </tr>
        """

    # URL-encode mailto parameters for proper link handling
    mailto_subject = quote(f"Re: Booking {booking_id}")
    mailto_body = quote(f"CONFIRM {booking_id}")

    html_content = f"""
{get_email_header()}
                                <div style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['powder_blue']} 0%, #a3b9d9 100%); background-color: {THE_ISLAND_COLORS['powder_blue']}; color: {THE_ISLAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 30px; box-shadow: 0 4px 12px rgba(184, 193, 218, 0.4);">
                                    <h2 style="margin: 0; font-size: 28px; font-weight: 700; color: {THE_ISLAND_COLORS['navy_primary']};">⏳ Booking Request Received</h2>
                                </div>

                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8; margin: 0 0 20px 0;">
                                    Dear <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">{player_name}</strong>,
                                </p>

                                <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; line-height: 1.8; margin: 0 0 30px 0;">
                                    Thank you for your tee time request at <strong>The Island Golf Club</strong>. We have received your booking request and are reviewing availability for your preferred date and time.
                                </p>

                                <div class="info-box" style="background: linear-gradient(to right, #f0f9ff 0%, #e0f2fe 100%); background-color: #f0f9ff; border-left: 4px solid {THE_ISLAND_COLORS['powder_blue']}; border-radius: 8px; padding: 25px; margin: 30px 0;">
                                    <h3 style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 20px; margin: 0 0 20px 0; font-weight: 700;">
                                        📋 Your Booking Request
                                    </h3>

                                    <table class="booking-table" width="100%" cellpadding="12" cellspacing="0" style="border-collapse: collapse; border-radius: 8px; overflow: hidden; border: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                        <tr style="background-color: {THE_ISLAND_COLORS['light_grey']};">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 15px 12px; font-weight: 600; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                Booking ID
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 14px; padding: 15px 12px; text-align: right; font-weight: 600; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {booking_id}
                                            </td>
                                        </tr>
                                        <tr style="background-color: #ffffff;">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>📅 Requested Date</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 15px; padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {preferred_date}
                                            </td>
                                        </tr>
                                        {alternate_row}
                                        <tr style="background-color: {THE_ISLAND_COLORS['light_grey']};">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>🕐 Requested Time</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 15px; padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {preferred_time}
                                            </td>
                                        </tr>
                                        <tr style="background-color: #ffffff;">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; padding: 15px 12px; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                <strong>👥 Number of Players</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 15px; padding: 15px 12px; text-align: right; font-weight: 700; border-bottom: 1px solid {THE_ISLAND_COLORS['border_grey']};">
                                                {num_players}
                                            </td>
                                        </tr>
                                        <tr style="background-color: #fffbeb;">
                                            <td style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 15px; padding: 18px 12px; font-weight: 700;">
                                                <strong>💶 Estimated Fee</strong>
                                            </td>
                                            <td style="color: {THE_ISLAND_COLORS['royal_blue']}; font-size: 22px; font-weight: 700; padding: 18px 12px; text-align: right;">
                                                €{total_fee:.2f}
                                            </td>
                                        </tr>
                                    </table>
                                </div>

                                <div style="background: linear-gradient(to right, #e0f2fe 0%, #bae6fd 100%); background-color: #e0f2fe; border-left: 4px solid {THE_ISLAND_COLORS['navy_primary']}; padding: 20px; border-radius: 8px; margin: 30px 0;">
                                    <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 16px; margin: 0 0 15px 0; line-height: 1.7;">
                                        <strong style="color: {THE_ISLAND_COLORS['navy_primary']}; font-size: 17px;">✉️ How to Confirm Your Booking</strong>
                                    </p>
                                    <p style="color: {THE_ISLAND_COLORS['text_dark']}; font-size: 15px; margin: 0 0 12px 0; line-height: 1.7;">
                                        Simply reply to this email with: <strong style="background-color: {THE_ISLAND_COLORS['gold_accent']}; color: {THE_ISLAND_COLORS['navy_primary']}; padding: 4px 8px; border-radius: 4px;">CONFIRM {booking_id}</strong>
                                    </p>
                                    <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; margin: 0; line-height: 1.7;">
                                        Or click the button below to send a pre-filled confirmation email.
                                    </p>
                                </div>

                                <div style="text-align: center; margin: 35px 0;">
                                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin: 0 auto;">
                                        <tr>
                                            <td style="border-radius: 8px; background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%);">
                                                <a href="mailto:{CLUB_BOOKING_EMAIL}?subject={mailto_subject}&body={mailto_body}" class="button-link" style="background: linear-gradient(135deg, {THE_ISLAND_COLORS['navy_primary']} 0%, {THE_ISLAND_COLORS['royal_blue']} 100%); background-color: {THE_ISLAND_COLORS['navy_primary']}; color: #ffffff !important; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; box-shadow: 0 4px 15px rgba(36, 56, 143, 0.3);">
                                                    📧 Confirm Booking Now
                                                </a>
                                            </td>
                                        </tr>
                                    </table>
                                </div>

                                <div style="background-color: {THE_ISLAND_COLORS['light_grey']}; border-left: 3px solid {THE_ISLAND_COLORS['gold_accent']}; padding: 15px; border-radius: 6px; margin: 30px 0;">
                                    <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 13px; margin: 0; line-height: 1.6; font-style: italic;">
                                        💡 <strong>Need to make changes?</strong> Simply reply to this email with your updated requirements (date, time, or number of players).
                                    </p>
                                </div>

                                <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 15px; line-height: 1.8; margin: 30px 0 0 0;">
                                    Thank you for choosing The Island Golf Club. We look forward to welcoming you to our championship links course.
                                </p>

                                <p style="color: {THE_ISLAND_COLORS['text_medium']}; font-size: 14px; line-height: 1.6; margin: 20px 0 0 0;">
                                    Best regards,<br>
                                    <strong style="color: {THE_ISLAND_COLORS['navy_primary']};">The Island Golf Club Team</strong>
                                </p>
{get_email_footer()}
    """

    return html_content


# --- EMAIL PARSING FUNCTION ---

def parse_booking_from_email(text: str, subject: str = "") -> Dict:
    """
    Parse booking details from email content using intelligent pattern matching.
    Returns a dictionary with extracted booking information.
    """
    full_text = f"{subject}\n{text}".lower()
    result = {
        'num_players': None,
        'preferred_date': None,
        'preferred_time': None,
        'phone': None,
        'alternate_date': None
    }

    # --- EXTRACT NUMBER OF PLAYERS ---
    player_patterns = [
        r'(\d+)\s*(?:players?|people|persons?|golfers?|guests?)',
        r'(?:party|group)\s*(?:of|size)?\s*(\d+)',
        r'(?:foursome|4some)',  # Special case for 4
        r'(?:twosome|2some)',   # Special case for 2
        r'(?:threesome|3some)', # Special case for 3
        r'for\s*(\d+)',
        r'(\d+)\s*(?:ball|person)'
    ]

    for pattern in player_patterns:
        match = re.search(pattern, full_text)
        if match:
            if 'foursome' in pattern or '4some' in pattern:
                result['num_players'] = 4
            elif 'twosome' in pattern or '2some' in pattern:
                result['num_players'] = 2
            elif 'threesome' in pattern or '3some' in pattern:
                result['num_players'] = 3
            else:
                try:
                    num = int(match.group(1))
                    if 1 <= num <= 4:  # Valid golf group size
                        result['num_players'] = num
                except (ValueError, IndexError):
                    pass
            if result['num_players']:
                break

    # Default to 4 if not found
    if not result['num_players']:
        result['num_players'] = 4

    # --- EXTRACT PHONE NUMBER ---
    phone_patterns = [
        r'(?:phone|tel|mobile|cell|contact)\s*:?\s*([+]?[\d\s\-\(\)]{9,})',
        r'([+]?\d{1,4}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4})',
        r'(\d{3}[\s\-]\d{3,4}[\s\-]\d{4})',
    ]

    for pattern in phone_patterns:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            phone = match.group(1).strip()
            # Clean up phone number - keep only digits, +, (), -, and spaces
            phone = re.sub(r'[^\d+\(\)\-\s]', '', phone).strip()
            # Count digits only
            digit_count = len(re.sub(r'[^\d]', '', phone))
            if digit_count >= 7:  # At least 7 digits for a valid phone
                result['phone'] = phone
                break

    # --- EXTRACT DATES ---
    # Common date patterns - ordered from most specific to least specific
    date_patterns = [
        # Dates with keywords
        r'(?:on|for|date[:\s]*)\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        r'(?:on|for|date[:\s]*)\s*(\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{2,4})',
        r'(?:on|for|date[:\s]*)\s*((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{2,4})?)',
        r'(?:on|for|date[:\s]*)\s*(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))',
        r'(?:on|for|date[:\s]*)\s*(tomorrow)',
        # Month name + day (with or without year) - no keyword required
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
                # Try to parse the date
                parsed_date = None

                if 'tomorrow' in date_str:
                    parsed_date = datetime.now() + timedelta(days=1)
                elif 'next' in date_str:
                    # Handle "next Friday" etc
                    days = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                           'friday': 4, 'saturday': 5, 'sunday': 6}
                    for day, offset in days.items():
                        if day in date_str:
                            today = datetime.now()
                            current_day = today.weekday()
                            days_ahead = (offset - current_day + 7) % 7
                            if days_ahead == 0:
                                days_ahead = 7
                            parsed_date = today + timedelta(days=days_ahead)
                            break
                else:
                    # Use dateutil parser for flexible date parsing
                    parsed_date = date_parser.parse(date_str, fuzzy=True, dayfirst=True, default=datetime.now().replace(day=1))

                    # If no year was specified and date is in the past, assume next year
                    if parsed_date and not re.search(r'\d{4}', date_str):
                        if parsed_date.date() < datetime.now().date():
                            parsed_date = parsed_date.replace(year=parsed_date.year + 1)

                if parsed_date:
                    # Only accept future dates (or today)
                    if parsed_date.date() >= datetime.now().date():
                        dates_found.append(parsed_date.strftime('%Y-%m-%d'))
            except (ValueError, TypeError):
                continue

    # Assign first two unique dates found
    unique_dates = list(dict.fromkeys(dates_found))  # Remove duplicates while preserving order
    if unique_dates:
        result['preferred_date'] = unique_dates[0]
        if len(unique_dates) > 1:
            result['alternate_date'] = unique_dates[1]

    # --- EXTRACT TIME ---
    # First check for specific times with context
    time_patterns = [
        # Specific times with keywords
        r'(?:time|tee\s*time)[:\s]+(\d{1,2}:\d{2}\s*(?:am|pm)?)',
        r'(?:time|tee\s*time)[:\s]+(\d{1,2}\s*(?:am|pm))',
        r'(?:at|around|about)\s+(\d{1,2}:\d{2}\s*(?:am|pm)?)',
        r'(?:at|around|about)\s+(\d{1,2}\s*(?:am|pm))',
        # Standalone times
        r'\b(\d{1,2}:\d{2}\s*(?:am|pm))\b',
        r'\b(\d{1,2}\s*(?:am|pm))\b',
        # General time periods
        r'\b(morning)\b',
        r'\b(afternoon)\b',
        r'\b(evening)\b',
        r'\b(early|late)\s+(morning|afternoon)\b',
    ]

    for pattern in time_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            time_str = match.group(1).strip().lower()

            # Convert general times to specific ranges
            if 'morning' in time_str:
                if 'early' in time_str:
                    result['preferred_time'] = '8:00 AM'
                elif 'late' in time_str:
                    result['preferred_time'] = '11:00 AM'
                else:
                    result['preferred_time'] = '9:00 AM'
            elif 'afternoon' in time_str:
                if 'early' in time_str:
                    result['preferred_time'] = '1:00 PM'
                elif 'late' in time_str:
                    result['preferred_time'] = '4:00 PM'
                else:
                    result['preferred_time'] = '2:00 PM'
            elif 'evening' in time_str:
                result['preferred_time'] = '5:00 PM'
            else:
                # Normalize time format
                try:
                    # Add AM/PM if missing and hour is ambiguous
                    if not re.search(r'am|pm', time_str, re.IGNORECASE):
                        hour_match = re.match(r'(\d{1,2})', time_str)
                        if hour_match:
                            hour = int(hour_match.group(1))
                            if hour >= 7 and hour <= 11:
                                time_str += ' AM'
                            elif hour >= 12:
                                time_str += ' PM'
                            elif hour >= 1 and hour <= 6:
                                time_str += ' PM'

                    result['preferred_time'] = time_str.upper()
                except:
                    result['preferred_time'] = time_str.upper()
            break

    # If no specific time found but "tee times" (plural) mentioned, default to morning preference
    if not result['preferred_time']:
        if re.search(r'\b(?:looking for|need|want|requesting|seeking)\s+(?:tee\s*)?times?\b', full_text, re.IGNORECASE):
            result['preferred_time'] = 'Morning (flexible)'
        elif re.search(r'\btee\s*times?\b', full_text, re.IGNORECASE):
            result['preferred_time'] = 'Flexible'

    return result


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
        
        # Parse booking details from email content
        logging.info("")
        logging.info("🔍 Parsing email content for booking details...")
        parsed_data = parse_booking_from_email(text_body, subject)

        logging.info(f"   📊 Parsed Results:")
        logging.info(f"      Players: {parsed_data.get('num_players', 'Not found')}")
        logging.info(f"      Date: {parsed_data.get('preferred_date', 'Not found')}")
        logging.info(f"      Time: {parsed_data.get('preferred_time', 'Not found')}")
        logging.info(f"      Phone: {parsed_data.get('phone', 'Not found')}")
        if parsed_data.get('alternate_date'):
            logging.info(f"      Alternate Date: {parsed_data.get('alternate_date')}")

        # Create booking with received data
        booking_id = str(uuid.uuid4())[:8]

        booking_data = {
            'id': booking_id,
            'name': sender_name,
            'email': sender_email,
            'phone': parsed_data.get('phone') or 'N/A',
            'num_players': parsed_data.get('num_players', 4),
            'preferred_date': parsed_data.get('preferred_date') or 'TBD',
            'preferred_time': parsed_data.get('preferred_time') or 'TBD',
            'alternate_date': parsed_data.get('alternate_date'),
            'special_requests': text_body[:500] if text_body else subject,
            'status': 'provisional',
            'course_id': DEFAULT_COURSE_ID
        }

        logging.info("")
        logging.info(f"📋 Creating Booking:")
        logging.info(f"   ID: {booking_id}")
        logging.info(f"   Name: {sender_name}")
        logging.info(f"   Email: {sender_email}")
        logging.info(f"   Phone: {booking_data['phone']}")
        logging.info(f"   Players: {booking_data['num_players']}")
        logging.info(f"   Date: {booking_data['preferred_date']}")
        logging.info(f"   Time: {booking_data['preferred_time']}")
        if booking_data.get('alternate_date'):
            logging.info(f"   Alternate Date: {booking_data['alternate_date']}")
        
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
        
        # Send provisional confirmation email with requested times
        logging.info("")
        logging.info("📧 Preparing confirmation email with requested times...")
        email_sent = False

        # Build results from parsed booking data (not from API - this is self-contained)
        results = []
        dates_to_show = []

        if booking_data.get('preferred_date') and booking_data['preferred_date'] != 'TBD':
            dates_to_show.append(booking_data['preferred_date'])

        if booking_data.get('alternate_date'):
            dates_to_show.append(booking_data['alternate_date'])

        # Create time slots from parsed time or default common times
        times_to_show = []
        if booking_data.get('preferred_time') and booking_data['preferred_time'] != 'TBD':
            times_to_show.append(booking_data['preferred_time'])
        else:
            # Default to common tee times if no specific time requested
            times_to_show = ['08:00', '10:00', '12:00', '14:00', '16:00']

        # Build results for email template
        for date in dates_to_show:
            for time in times_to_show:
                results.append({
                    'date': date,
                    'time': time
                })

        try:
            if not SENDGRID_API_KEY:
                logging.error("❌ SENDGRID_API_KEY not set!")
                logging.error("   Cannot send confirmation email")
            else:
                if results:
                    # We have dates to show - use the fancy availability email
                    logging.info(f"   Showing {len(results)} time slots for requested dates")
                    html_email = format_availability_email(
                        results=results,
                        player_count=booking_data['num_players'],
                        guest_email=sender_email,
                        booking_id=booking_id,
                        used_alternatives=False,
                        original_dates=None
                    )
                    subject = "Available Tee Times at The Island Golf Club"
                else:
                    # No valid dates - send provisional email
                    logging.info("   No valid dates found - sending provisional confirmation")
                    html_email = format_provisional_email(booking_data)
                    subject = "Your Island Golf Club Booking Request"

                email_sent = send_email(
                    sender_email,
                    subject,
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
