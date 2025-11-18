#!/usr/bin/env python3
"""
TeeMail Email Bot - COMPLETE WORKING VERSION WITH ENHANCED ALTERNATIVE DATE MARKING
====================================================================================

This is the COMPLETE version with all functions included.
Enhanced with automatic alternative date checking and IMPROVED VISUAL MARKING.
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

# Enhanced NLP for parsing
from enhanced_nlp import parse_booking_email, IntentType, UrgencyLevel

app = Flask(__name__)

# --- CONFIG ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "teetimes@countylouthgolfclub.com")
FROM_NAME = os.getenv("FROM_NAME", "County Louth Golf Club")
PER_PLAYER_FEE = float(os.getenv("PER_PLAYER_FEE", "325.00"))
BOOKINGS_FILE = os.getenv("BOOKINGS_FILE", "provisional_bookings.jsonl")

# PostgreSQL Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Core API endpoint
CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:5001")

# External Dashboard API endpoint
DASHBOARD_API_URL = os.getenv("DASHBOARD_API_URL", "https://teemailsg-1.onrender.com")

# Default course for bookings
DEFAULT_COURSE_ID = os.getenv("DEFAULT_COURSE_ID", "baltray")

# Tracking email for confirmation webhooks (separate from course ID)
TRACKING_EMAIL_PREFIX = os.getenv("TRACKING_EMAIL_PREFIX", "countylouth")

# Club booking email (appears in mailto links for staff copy)
CLUB_BOOKING_EMAIL = os.getenv("CLUB_BOOKING_EMAIL", "teetimes@countylouthgolfclub.com")

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- DATABASE CONNECTION POOL ---
db_pool = None


# ============================================================================
# HTML EMAIL TEMPLATE FUNCTIONS - ENHANCED WITH IMPROVED ALTERNATIVE DATE STYLING
# ============================================================================

def get_email_header(course_name: str) -> str:
    """Generate modern, polished email header with soft rounded corners"""
    return f"""
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title>{course_name} - Tee Time Availability</title>

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
                background-color: #f3f4f6;
            }}

            table {{
                border-collapse: collapse;
                mso-table-lspace: 0pt;
                mso-table-rspace: 0pt;
            }}

            .email-wrapper {{
                background-color: #f3f4f6;
                padding: 20px;
            }}

            .email-container {{
                background: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}

            .header {{
                background: linear-gradient(135deg, #003B7C 0%, #001F3F 100%);
                background-color: #003B7C;
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
                color: #D4AF37;
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
                border: 1px solid #D4AF37;
                border-radius: 20px;
                color: #D4AF37;
                font-size: 12px;
                letter-spacing: 1px;
            }}

            .content {{
                padding: 40px 30px;
            }}

            .greeting {{
                font-size: 18px;
                margin-bottom: 20px;
                color: #1f2937;
                line-height: 1.6;
            }}

            .tee-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 25px 0;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                border: 1px solid #e5e7eb;
            }}

            .tee-table thead {{
                background: linear-gradient(135deg, #003B7C 0%, #001F3F 100%);
                background-color: #003B7C;
                color: #ffffff;
            }}

            .tee-table th {{
                padding: 15px 12px;
                color: #ffffff;
                font-weight: 600;
                text-align: left;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border: none;
            }}

            .tee-table td {{
                padding: 15px 12px;
                border-bottom: 1px solid #e5e7eb;
                border-left: none;
                border-right: none;
            }}

            .tee-table tbody tr {{
                background-color: #f9fafb;
                transition: background 0.2s;
            }}

            .tee-table tbody tr:nth-child(even) {{
                background-color: #ffffff;
            }}

            .tee-table tbody tr:hover {{
                background-color: #f0f9ff;
            }}

            .button-cell {{
                background: linear-gradient(135deg, #B91C2E 0%, #8B1420 100%);
                background-color: #B91C2E;
                padding: 10px 20px;
                border-radius: 6px;
            }}

            .button-link {{
                color: #ffffff !important;
                text-decoration: none;
                font-weight: 600;
                font-size: 14px;
            }}

            .date-section {{
                margin: 30px 0;
            }}

            .date-header {{
                color: #003B7C;
                font-size: 24px;
                font-weight: 700;
                margin: 25px 0 15px 0;
                padding-bottom: 10px;
                border-bottom: 3px solid #D4AF37;
            }}

            .status-badge {{
                display: inline-block;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 600;
                background: #ecfdf5;
                color: #2D5F3F;
                border: 1px solid #2D5F3F;
            }}

            .alternative-badge {{
                display: inline-block;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 600;
                background: #fef3c7;
                color: #92400e;
                border: 1px solid #D4AF37;
            }}

            .alternative-date-section {{
                border: 2px solid #D4AF37;
                padding: 20px;
                background: linear-gradient(to right, #FFFEF7 0%, #FFF9E6 100%);
                background-color: #FFFEF7;
                margin: 30px 0;
            }}

            .alt-date-row {{
                border-left: 3px solid #D4AF37 !important;
                background-color: #FFFEF7 !important;
            }}

            .info-box {{
                background: linear-gradient(to right, #f0f9ff 0%, #e0f2fe 100%);
                background-color: #f0f9ff;
                border-left: 4px solid #003B7C;
                border-radius: 4px;
                padding: 20px;
                margin: 20px 0;
            }}

            .info-box h3 {{
                margin: 0 0 10px 0;
                color: #003B7C;
                font-size: 18px;
            }}

            .info-box p {{
                margin: 5px 0;
                color: #374151;
            }}

            .alternative-box {{
                background: linear-gradient(to right, #fffbeb 0%, #fef3c7 100%);
                background-color: #fffbeb;
                border-left: 4px solid #D4AF37;
                border-radius: 4px;
                padding: 20px;
                margin: 20px 0;
            }}

            .alternative-box h3 {{
                margin: 0 0 10px 0;
                color: #92400e;
                font-size: 18px;
            }}

            .links-box {{
                background: linear-gradient(to right, #f0fdf4 0%, #dcfce7 100%);
                background-color: #f0fdf4;
                border-left: 4px solid #2D5F3F;
                border-radius: 4px;
                padding: 20px;
                margin: 20px 0;
            }}

            .links-box h3 {{
                margin: 0 0 10px 0;
                color: #2D5F3F;
                font-size: 18px;
            }}

            .group-box {{
                background-color: #f9fafb;
                border-left: 4px solid #003B7C;
                border-radius: 4px;
                padding: 20px;
                margin: 20px 0;
            }}

            .group-box h3 {{
                margin: 0 0 10px 0;
                color: #003B7C;
                font-size: 18px;
            }}

            .warning-box {{
                background-color: #fef3c7;
                border-left: 4px solid #D4AF37;
                border-radius: 4px;
                padding: 20px;
                margin: 20px 0;
            }}

            .warning-box h3 {{
                margin: 0 0 10px 0;
                color: #92400e;
                font-size: 18px;
            }}

            .footer {{
                background: linear-gradient(135deg, #003B7C 0%, #001F3F 100%);
                background-color: #003B7C;
                padding: 30px;
                text-align: center;
                color: #ffffff;
            }}

            .footer strong {{
                color: #D4AF37;
                font-size: 18px;
            }}

            .footer a {{
                color: #D4AF37;
                text-decoration: none;
                font-weight: 600;
            }}

            .footer .tagline {{
                color: rgba(255, 255, 255, 0.8);
                font-style: italic;
                margin-top: 5px;
            }}

            .price-highlight {{
                font-weight: 700;
                color: #003B7C;
                font-size: 16px;
            }}

            .emoji {{
                font-size: 20px;
                margin-right: 8px;
            }}

            @media only screen and (max-width: 600px) {{
                .header h1 {{ font-size: 24px !important; }}
                .content {{ padding: 20px 15px !important; }}
                .tee-table th, .tee-table td {{ padding: 10px 8px; font-size: 12px; }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f3f4f6;">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" class="email-wrapper" style="border-collapse: collapse;">
            <tr>
                <td style="padding: 20px; background-color: #f3f4f6;">
                    <table role="presentation" class="email-container" align="center" border="0" cellpadding="0" cellspacing="0" width="800" style="max-width: 800px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <tr>
                            <td class="header" style="background: linear-gradient(135deg, #003B7C 0%, #001F3F 100%); background-color: #003B7C; padding: 40px 30px; text-align: center; color: #ffffff; position: relative;">
                                <!--[if gte mso 9]>
                                <v:rect xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false" style="width:800px;height:150px;">
                                <v:fill type="gradient" color="#001F3F" color2="#003B7C" angle="135" />
                                <v:textbox inset="40px,40px,40px,40px">
                                <![endif]-->
                                <div style="color: #ffffff;">
                                    <h1 style="margin: 0 0 10px 0; font-size: 32px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">
                                        <span class="emoji"></span>{course_name}
                                    </h1>
                                    <p style="margin: 0; color: #D4AF37; font-size: 16px; font-weight: 600;">
                                        Available Tee Times for Your Round
                                    </p>
                                    <div class="est-badge" style="display: inline-block; margin-top: 8px; padding: 4px 12px; background: rgba(212, 175, 55, 0.2); border: 1px solid #D4AF37; border-radius: 20px; color: #D4AF37; font-size: 12px; letter-spacing: 1px;">
                                        EST. 1892
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


def get_email_footer(course_name: str, from_email: str = "teetimes@countylouthgolfclub.com") -> str:
    """Generate Outlook-compatible email footer"""
    return f"""
                            </td>
                        </tr>
                        <tr>
                            <td class="footer" style="background: linear-gradient(135deg, #003B7C 0%, #001F3F 100%); background-color: #003B7C; padding: 30px; text-align: center; color: #ffffff;">
                                <!--[if gte mso 9]>
                                <v:rect xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false" style="width:800px;height:180px;">
                                <v:fill type="gradient" color="#001F3F" color2="#003B7C" angle="135" />
                                <v:textbox inset="30px,30px,30px,30px">
                                <![endif]-->
                                <div style="color: #ffffff;">
                                    <p style="margin-bottom: 10px; font-size: 12px; letter-spacing: 1px;">
                                        CHAMPIONSHIP LINKS GOLF
                                    </p>
                                    <p style="margin: 0;">
                                        <strong style="color: #D4AF37; font-size: 18px;">{course_name}</strong>
                                    </p>
                                    <p class="tagline" style="color: rgba(255, 255, 255, 0.8); margin-top: 5px; font-style: italic;">
                                        Baltray, Co. Louth, Ireland • Est. 1892
                                    </p>
                                    <p style="margin-top: 25px; color: #ffffff;">
                                        <strong>Contact:</strong> <a href="mailto:{from_email}" style="color: #D4AF37; text-decoration: none; font-weight: 600;">{from_email}</a>
                                    </p>
                                    <p style="margin-top: 5px; color: #ffffff;">
                                        <strong>Telephone:</strong> <a href="tel:+353419881530" style="color: #D4AF37; text-decoration: none; font-weight: 600;">+353 41 988 1530</a>
                                    </p>
                                    <p style="margin-top: 20px; font-size: 11px; color: rgba(255, 255, 255, 0.6);">
                                        We look forward to welcoming you to our historic links
                                    </p>
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


def create_book_button(booking_link: str, button_text: str = "Reserve Now") -> str:
    """Create Outlook-compatible table-based button"""
    return f"""
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: collapse; margin: 0 auto;">
        <tr>
            <td class="button-cell" align="center" style="background: linear-gradient(135deg, #B91C2E 0%, #8B1420 100%); background-color: #B91C2E; padding: 10px 20px; border-radius: 6px; box-shadow: 0 2px 4px rgba(185, 28, 46, 0.3);">
                <a href="{booking_link}" class="button-link" style="color: #ffffff; text-decoration: none; font-weight: 600; font-size: 14px;">
                    <span class="emoji">🗓️</span>{button_text}
                </a>
            </td>
        </tr>
    </table>
    """


def format_standard_booking_email_html(
    course_name: str,
    results: list,
    player_count: int,
    guest_email: str,
    booking_link_func,
    booking_id: str = None,
    from_email: str = "teetimes@countylouthgolfclub.com",
    used_alternatives: bool = False,
    original_dates: list = None
) -> str:
    """Format beautiful HTML email for standard bookings (1-4 players) with enhanced alternative date marking"""
    
    html = get_email_header(course_name)
    
    html += f"""
        <p class="greeting">Thank you for your enquiry. We are delighted to present the following available tee times at <strong style="color: #003B7C;">{course_name}</strong>, one of Ireland's finest championship links courses:</p>
        
        <div class="info-box">
            <h3><span class="emoji">👥</span>Booking Details</h3>
            <p><strong>Players:</strong> {player_count}</p>
            <p><strong>Green Fee:</strong> €{PER_PLAYER_FEE:.0f} per player</p>
            <p><strong>Status:</strong> <span class="status-badge">{'✓ Alternative Dates Found' if used_alternatives else '✓ Available Times Found'}</span></p>
        </div>
    """
    
    # Add ENHANCED alternative dates notice if applicable
    if used_alternatives and original_dates:
        original_dates_str = ', '.join(original_dates)
        plural = 's' if len(original_dates) > 1 else ''
        were_was = 'were' if len(original_dates) > 1 else 'was'
        
        html += f"""
        <div class="alternative-box">
            <h3><span class="emoji">🎯</span>Alternative Dates Found!</h3>
            <p style="font-size: 16px; margin-bottom: 15px; line-height: 1.6;">
                Your requested date{plural} <strong style="color: #8B7355;">({original_dates_str})</strong> {were_was} fully booked.
            </p>
            <div class="highlight">
                <p style="margin: 0; font-weight: 600; color: #8B7355; font-size: 16px;">
                    <span class="emoji">✅</span>Great news! We found available tee times within the same week
                </p>
                <p style="margin: 10px 0 0 0; color: #666; line-height: 1.6;">
                    These alternative dates offer the same championship golf experience 
                    and are clearly marked below with <strong style="color: #D4AF37;">gold badges</strong>.
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
            html += '<div class="alternative-date-section">'
        
        date_badge = '<span class="alternative-badge">📅 Alternative Date</span>' if is_alt_date else ''
        
        html += f"""
        <div class="date-section">
            <h2 class="date-header"><span class="emoji">🗓️</span>{date} {date_badge}</h2>
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
            price = result.get("price", f"€{PER_PLAYER_FEE:.0f}")
            row_class = 'alt-date-row' if is_alt_date else ''
            
            booking_link = booking_link_func(
                date, time, player_count, guest_email, course_name, booking_id=booking_id
            )
            
            button_html = create_book_button(booking_link, "Reserve Now")
            html += f"""
                    <tr class="{row_class}">
                        <td><strong style="font-size: 16px; color: #003B7C;">{time}</strong></td>
                        <td style="text-align: center;"><span class="status-badge">✓ Available</span></td>
                        <td><span class="price-highlight">€{PER_PLAYER_FEE:.0f} pp</span></td>
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
        
        # Close alternative date wrapper if needed
        if is_alt_date:
            html += '</div>'
    
    # Add championship links description and helpful info box
    html += """
        <div class="links-box" style="margin-top: 30px;">
            <h3><span class="emoji">⛳</span>Championship Links Experience</h3>
            <p>County Louth Golf Club features a classic links layout on the Baltray peninsula, offering stunning views of the Boyne Estuary and Mourne Mountains. Our course has hosted numerous prestigious championships and provides an authentic Irish golfing experience.</p>
        </div>
        
        <div class="info-box">
            <h3><span class="emoji">💡</span>How to Confirm Your Booking</h3>
            <p><strong>Step 1:</strong> Click any "Reserve Now" button above for your preferred tee time</p>
            <p><strong>Step 2:</strong> Your email client will open with a pre-filled booking request</p>
            <p><strong>Step 3:</strong> Simply send the email - we'll confirm within 30 minutes</p>
            <p style="margin-top: 12px; font-style: italic; color: #6b7280;">Alternatively, you may telephone us at <strong style="color: #003B7C;">+353 41 988 1530</strong></p>
        </div>
    """
    
    html += get_email_footer(course_name, from_email)
    
    return html


def format_no_availability_email_html(
    course_name: str,
    player_count: int,
    from_email: str = "teetimes@countylouthgolfclub.com",
    original_dates: list = None,
    checked_alternatives: bool = False
) -> str:
    """Format HTML email when no availability found"""
    
    html = get_email_header(course_name)
    
    html += f"""
        <p class="greeting">Thank you for your enquiry regarding tee times at <strong style="color: #003B7C;">{course_name}</strong>.</p>
        
        <div class="warning-box">
            <h3><span class="emoji">⚠️</span>No Availability Found</h3>
            <p>Unfortunately, we do not have availability for <strong>{player_count} player(s)</strong> on your requested dates.</p>
    """
    
    if checked_alternatives:
        html += f"""
            <p style="margin-top: 10px;">We have checked dates within a week of your request, but were unable to find suitable availability.</p>
        """
    
    html += """
        </div>
        
        <div class="info-box">
            <h3><span class="emoji">📞</span>Please Contact Us</h3>
            <p>We would be delighted to assist you in finding alternative dates or discuss other options:</p>
            <p><strong>Email:</strong> <a href="mailto:{from_email}" style="color: #003B7C;">{from_email}</a></p>
            <p><strong>Telephone:</strong> <a href="tel:+353419881530" style="color: #003B7C;">+353 41 988 1530</a></p>
        </div>
        
        <p>We look forward to welcoming you to our championship links course.</p>
    """
    
    html += get_email_footer(course_name, from_email)
    
    return html


def format_error_email_html(
    course_name: str,
    error_message: str = None,
    from_email: str = "teetimes@countylouthgolfclub.com"
) -> str:
    """Format HTML email for errors"""
    
    html = get_email_header(course_name)
    
    html += f"""
        <p class="greeting">Thank you for your enquiry!</p>
        
        <div class="warning-box">
            <h3><span class="emoji">⚠️</span>Technical Issue</h3>
            <p>We encountered an issue checking availability for your request.</p>
            {f'<p style="font-size: 14px; color: #6b7280; margin-top: 10px;">Error: {error_message}</p>' if error_message else ''}
        </div>
        
        <div class="info-box">
            <h3><span class="emoji">📞</span>Please Contact Us</h3>
            <p>Our team is ready to help you book your tee time:</p>
            <p><strong>Email:</strong> <a href="mailto:{from_email}" style="color: #10b981;">{from_email}</a></p>
            <p><strong>Phone:</strong> +353 41 988 1530</p>
        </div>
    """
    
    html += get_email_footer(course_name, from_email)
    
    return html


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
    """Generate a unique booking ID in format: BOOK-YYYYMMDD-XXXX"""
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    date_str = datetime.now().strftime("%Y%m%d")
    hash_input = f"{guest_email}{timestamp}".encode('utf-8')
    hash_digest = hashlib.md5(hash_input).hexdigest()[:8].upper()

    return f"BOOK-{date_str}-{hash_digest}"


def save_booking_to_db(booking_data: dict):
    """Save booking to PostgreSQL"""
    conn = None
    try:
        logging.info("💾 SAVING NEW BOOKING TO DATABASE")
        logging.info(f"   Customer: {booking_data.get('guest_email')}")
        logging.info(f"   Players: {booking_data.get('players')}")
        logging.info(f"   Date: {booking_data.get('date')}")

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
                players, total, status, intent, urgency,
                confidence, is_corporate, company_name, note,
                club, club_name
            ) VALUES (
                %(booking_id)s, %(message_id)s, %(timestamp)s, %(guest_email)s, %(dates)s, %(date)s, %(tee_time)s,
                %(players)s, %(total)s, %(status)s, %(intent)s, %(urgency)s,
                %(confidence)s, %(is_corporate)s, %(company_name)s, %(note)s,
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
            'intent': booking_data.get('intent'),
            'urgency': booking_data.get('urgency'),
            'confidence': booking_data.get('confidence'),
            'is_corporate': booking_data.get('is_corporate', False),
            'company_name': booking_data.get('company_name'),
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


def post_booking_to_dashboard(booking_data: dict, booking_id: str = None):
    """
    Dashboard sync via shared database.
    The dashboard reads directly from PostgreSQL, so no API call is needed.
    All updates happen through save_booking_to_db() and update_booking_in_db().
    """
    booking_id = booking_id or booking_data.get('booking_id')
    logging.info(f"📊 Booking {booking_id} saved to database - dashboard will auto-sync")
    return True


def get_all_bookings_from_db():
    """Get all bookings from PostgreSQL"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logging.warning("⚠️  No database connection")
            return []

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
                intent,
                urgency,
                confidence,
                is_corporate,
                company_name,
                note,
                club,
                club_name,
                customer_confirmed_at,
                created_at,
                updated_at
            FROM bookings
            ORDER BY timestamp DESC
        """)

        bookings = cursor.fetchall()
        cursor.close()

        result = []
        for booking in bookings:
            booking_dict = dict(booking)

            # Convert datetime objects to strings
            for field in ['timestamp', 'customer_confirmed_at', 'created_at', 'updated_at']:
                if booking_dict.get(field) and hasattr(booking_dict[field], 'strftime'):
                    booking_dict[field] = booking_dict[field].strftime('%Y-%m-%d %H:%M:%S')

            if booking_dict.get('date') and hasattr(booking_dict['date'], 'strftime'):
                booking_dict['date'] = booking_dict['date'].strftime('%Y-%m-%d')

            result.append(booking_dict)

        return result

    except Exception as e:
        logging.error(f"❌ Failed to fetch bookings: {e}")
        return []
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
                intent,
                urgency,
                confidence,
                is_corporate,
                company_name,
                note,
                club,
                club_name,
                customer_confirmed_at,
                created_at,
                updated_at
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
    """Update booking in PostgreSQL - ENHANCED WITH DETAILED LOGGING"""
    conn = None
    try:
        logging.info("="*60)
        logging.info(f"💾 DATABASE UPDATE INITIATED")
        logging.info("="*60)
        logging.info(f"📋 Booking ID: {booking_id}")
        logging.info(f"📝 Updates to apply:")
        for key, value in updates.items():
            if key == 'tee_time':
                if value:
                    logging.info(f"   ✓ {key}: {value} (TIME WILL BE SET)")
                else:
                    logging.warning(f"   ⚠️  {key}: {value} (TIME WILL REMAIN NULL)")
            else:
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
                logging.debug(f"   Adding to query: {key} = {value}")

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

        logging.info(f"📊 Executing SQL query...")
        logging.debug(f"   Query: {query}")
        logging.debug(f"   Params: {params}")

        cursor.execute(query, params)
        rows_affected = cursor.rowcount
        conn.commit()
        cursor.close()

        if rows_affected == 0:
            logging.error(f"❌ No rows updated! Booking ID may not exist: {booking_id}")
            release_db_connection(conn)
            return False

        logging.info(f"✅ Database updated successfully - {rows_affected} row(s) affected")

        # Get updated booking for logging (dashboard will auto-sync from DB)
        if rows_affected > 0:
            logging.info("🔄 Fetching updated booking from database...")
            updated_booking = get_booking_by_id(booking_id)
            release_db_connection(conn)
            conn = None

            if updated_booking:
                logging.info("📊 Updated booking retrieved:")
                logging.info(f"   Status: {updated_booking.get('status')}")
                logging.info(f"   Date: {updated_booking.get('date')}")
                logging.info(f"   Tee Time: {updated_booking.get('tee_time', 'NULL')}")
                logging.info(f"   Players: {updated_booking.get('players')}")

                if not updated_booking.get('tee_time'):
                    logging.warning("⚠️  ⚠️  ⚠️  TEE_TIME IS STILL NULL AFTER UPDATE!")
                    logging.warning("⚠️  Customer will see 'not specified' for the time")

                logging.info("📊 Dashboard will auto-sync from database")
            else:
                logging.warning("⚠️  Could not retrieve updated booking")

        logging.info("="*60)
        return True

    except Exception as e:
        logging.error("="*60)
        logging.error(f"❌ ❌ ❌ DATABASE UPDATE FAILED ❌ ❌ ❌")
        logging.error("="*60)
        logging.error(f"❌ Error: {e}")
        logging.error(f"❌ Booking ID: {booking_id}")
        logging.error(f"❌ Updates attempted: {updates}")
        import traceback
        logging.error(f"❌ Traceback: {traceback.format_exc()}")
        logging.error("="*60)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_db_connection(conn)


def extract_booking_id(text: str) -> Optional[str]:
    """Extract booking ID from email text"""
    pattern = r'BOOK-\d{8}-[A-F0-9]{8}'
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


def is_confirmation_email(subject: str, body: str) -> bool:
    """
    Detect if this is a confirmation email (not a new booking request)
    """
    subject_lower = subject.lower() if subject else ""
    body_lower = body.lower() if body else ""
    
    # Check subject for confirmation patterns
    if "confirm booking" in subject_lower:
        logging.info("🎯 Detected 'CONFIRM BOOKING' in subject")
        return True
    
    if "confirm group booking" in subject_lower:
        logging.info("🎯 Detected 'CONFIRM GROUP BOOKING' in subject")
        return True
        
    # Check if it's a reply (Re:)
    if subject_lower.startswith('re:'):
        logging.info("🎯 Detected 'Re:' in subject (reply email)")
        return True
    
    # Check body for booking reference + confirmation keywords
    has_booking_ref = extract_booking_id(body) or extract_booking_id(subject)
    confirmation_keywords = ['confirm', 'yes', 'book', 'proceed', 'accept', 'ok', 'okay', 'sure', 'sounds good']
    has_confirmation_keyword = any(keyword in body_lower for keyword in confirmation_keywords)
    
    if has_booking_ref and has_confirmation_keyword:
        logging.info("🎯 Detected booking reference + confirmation keywords")
        return True
    
    return False


def extract_tee_time_from_email(subject: str, body: str) -> tuple:
    """
    Extract the TEE TIME date and time from confirmation email
    ENHANCED with comprehensive pattern matching and detailed logging
    """
    logging.info("="*60)
    logging.info("🔍 EXTRACTING TEE TIME FROM EMAIL")
    logging.info("="*60)
    logging.info(f"📧 Subject: {subject}")
    logging.info(f"📝 Body (first 200 chars): {body[:200] if body else 'None'}")

    tee_date = None
    tee_time = None

    # ============================================================
    # PATTERN 1: Try to extract from subject first (single bookings)
    # Format: "CONFIRM BOOKING - 2025-11-15 at 10:00 [Ref: BOOK-...]"
    # ============================================================
    logging.info("🔎 Trying PATTERN 1: Date and time from subject...")
    subject_patterns = [
        r'(\d{4}-\d{2}-\d{2})\s+at\s+(\d{1,2}:\d{2})',  # 2025-11-15 at 10:00
        r'(\d{4}-\d{2}-\d{2})\s+@\s+(\d{1,2}:\d{2})',   # 2025-11-15 @ 10:00
        r'(\d{4}/\d{2}/\d{2})\s+at\s+(\d{1,2}:\d{2})',  # 2025/11/15 at 10:00
        r'(\d{2}-\d{2}-\d{4})\s+at\s+(\d{1,2}:\d{2})',  # 15-11-2025 at 10:00
    ]

    for i, pattern in enumerate(subject_patterns, 1):
        subject_match = re.search(pattern, subject, re.IGNORECASE)
        if subject_match:
            tee_date = subject_match.group(1)
            tee_time = subject_match.group(2)
            # Normalize date format to YYYY-MM-DD
            if '/' in tee_date:
                tee_date = tee_date.replace('/', '-')
            # Handle DD-MM-YYYY format
            if re.match(r'\d{2}-\d{2}-\d{4}', tee_date):
                parts = tee_date.split('-')
                tee_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

            # Normalize time format to HH:MM (ensure 2 digits for hour)
            if ':' in tee_time:
                hour, minute = tee_time.split(':')
                tee_time = f"{hour.zfill(2)}:{minute}"

            logging.info(f"✅ Pattern {i} MATCHED in subject!")
            logging.info(f"✅ Extracted: {tee_date} at {tee_time}")
            return tee_date, tee_time
        else:
            logging.debug(f"   Pattern {i} did not match")

    logging.info("❌ No complete date+time found in subject, trying separate extraction...")

    # ============================================================
    # PATTERN 2: Extract date from subject (for group bookings)
    # ============================================================
    logging.info("🔎 Trying PATTERN 2: Date only from subject...")
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(\d{4}/\d{2}/\d{2})',  # YYYY/MM/DD
        r'(\d{2}-\d{2}-\d{4})',  # DD-MM-YYYY
        r'(\d{2}/\d{2}/\d{4})',  # DD/MM/YYYY
    ]

    for i, pattern in enumerate(date_patterns, 1):
        group_date_match = re.search(pattern, subject)
        if group_date_match:
            tee_date = group_date_match.group(1)
            # Normalize
            if '/' in tee_date:
                tee_date = tee_date.replace('/', '-')
            if re.match(r'\d{2}-\d{2}-\d{4}', tee_date):
                parts = tee_date.split('-')
                tee_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

            logging.info(f"✅ Date pattern {i} MATCHED in subject: {tee_date}")
            break
        else:
            logging.debug(f"   Date pattern {i} did not match")

    # ============================================================
    # PATTERN 3: Extract from body if not found in subject
    # ============================================================
    if not tee_date:
        logging.info("🔎 Trying PATTERN 3: Date from body...")
        body_date_patterns = [
            r'Date:\s*(\d{4}-\d{2}-\d{2})',
            r'Date:\s*(\d{4}/\d{2}/\d{2})',
            r'Date:\s*(\d{2}-\d{2}-\d{4})',
            r'Date:\s*(\d{2}/\d{2}/\d{4})',
        ]

        for i, pattern in enumerate(body_date_patterns, 1):
            date_match = re.search(pattern, body, re.IGNORECASE)
            if date_match:
                tee_date = date_match.group(1)
                # Normalize
                if '/' in tee_date:
                    tee_date = tee_date.replace('/', '-')
                if re.match(r'\d{2}-\d{2}-\d{4}', tee_date):
                    parts = tee_date.split('-')
                    tee_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

                logging.info(f"✅ Date pattern {i} MATCHED in body: {tee_date}")
                break
            else:
                logging.debug(f"   Date pattern {i} did not match in body")

    # ============================================================
    # PATTERN 4: Extract time from body
    # ============================================================
    if not tee_time:
        logging.info("🔎 Trying PATTERN 4: Time from body...")
        body_time_patterns = [
            r'Time:\s*(\d{1,2}:\d{2})',                    # Time: 10:00
            r'Tee Time:\s*(\d{1,2}:\d{2})',                # Tee Time: 10:00
            r'at\s+(\d{1,2}:\d{2})',                       # at 10:00
            r'@\s+(\d{1,2}:\d{2})',                        # @ 10:00
            r'(\d{1,2}:\d{2})\s*(?:am|pm|AM|PM)',          # 10:00 AM
        ]

        for i, pattern in enumerate(body_time_patterns, 1):
            time_match = re.search(pattern, body, re.IGNORECASE)
            if time_match:
                tee_time = time_match.group(1)
                # Normalize to HH:MM
                if ':' in tee_time:
                    hour, minute = tee_time.split(':')
                    tee_time = f"{hour.zfill(2)}:{minute}"

                logging.info(f"✅ Time pattern {i} MATCHED in body: {tee_time}")
                break
            else:
                logging.debug(f"   Time pattern {i} did not match in body")

    # ============================================================
    # PATTERN 5: Group booking format "Group 1: 10:00 - 4 players"
    # ============================================================
    if not tee_time:
        logging.info("🔎 Trying PATTERN 5: Group booking time from body...")
        group_time_patterns = [
            r'Group\s+1:\s*(\d{1,2}:\d{2})',               # Group 1: 10:00
            r'Group\s+1:\s*(\d{1,2}:\d{2})\s*-',           # Group 1: 10:00 -
            r'First group:\s*(\d{1,2}:\d{2})',             # First group: 10:00
            r'Starting at:\s*(\d{1,2}:\d{2})',             # Starting at: 10:00
        ]

        for i, pattern in enumerate(group_time_patterns, 1):
            group_time_match = re.search(pattern, body, re.IGNORECASE)
            if group_time_match:
                tee_time = group_time_match.group(1)
                # Normalize to HH:MM
                if ':' in tee_time:
                    hour, minute = tee_time.split(':')
                    tee_time = f"{hour.zfill(2)}:{minute}"

                logging.info(f"✅ Group time pattern {i} MATCHED in body: {tee_time}")
                break
            else:
                logging.debug(f"   Group time pattern {i} did not match in body")

    # ============================================================
    # FINAL RESULTS
    # ============================================================
    logging.info("="*60)
    if tee_date and tee_time:
        logging.info(f"✅ ✅ ✅ EXTRACTION SUCCESSFUL ✅ ✅ ✅")
        logging.info(f"📅 Date: {tee_date}")
        logging.info(f"⏰ Time: {tee_time}")
    elif tee_date and not tee_time:
        logging.warning(f"⚠️  PARTIAL EXTRACTION - Date found: {tee_date}, but TIME NOT FOUND")
        logging.warning(f"⚠️  This is likely a group booking - time should be in body")
    elif not tee_date and tee_time:
        logging.warning(f"⚠️  PARTIAL EXTRACTION - Time found: {tee_time}, but DATE NOT FOUND")
    else:
        logging.error("❌ ❌ ❌ EXTRACTION FAILED ❌ ❌ ❌")
        logging.error("❌ Could not find date or time in subject or body")
        logging.error(f"❌ Subject was: {subject}")
        logging.error(f"❌ Body (first 500 chars): {body[:500] if body else 'None'}")
    logging.info("="*60)

    return tee_date, tee_time


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


def process_confirmation(from_email: str, subject: str, body: str, message_id: str = None):
    """UNIFIED CONFIRMATION PROCESSING - ENHANCED WITH DETAILED LOGGING"""
    logging.info("="*80)
    logging.info(f"🎉 PROCESSING CONFIRMATION EMAIL")
    logging.info("="*80)
    logging.info(f"📧 From: {from_email}")
    logging.info(f"📧 Subject: {subject}")
    logging.info(f"📧 Message ID: {message_id}")
    logging.info(f"📧 Body length: {len(body) if body else 0} characters")

    # Step 1: Extract booking ID
    logging.info("🔍 Step 1: Looking for booking ID...")
    booking_id = extract_booking_id(subject) or extract_booking_id(body)

    if not booking_id:
        logging.error("❌ NO BOOKING ID FOUND in subject or body")
        logging.error(f"   Subject: {subject}")
        logging.error(f"   Body (first 300 chars): {body[:300] if body else 'None'}")
        return {'status': 'no_booking_id'}, 200

    logging.info(f"✅ Booking ID found: {booking_id}")

    # Step 2: Check for duplicates
    logging.info("🔍 Step 2: Checking for duplicate messages...")
    if message_id and is_duplicate_message(message_id):
        logging.warning(f"⚠️  DUPLICATE CONFIRMATION (message_id already processed)")
        logging.warning(f"   Message ID: {message_id}")
        return {'status': 'duplicate', 'booking_id': booking_id}, 200
    logging.info("✅ Not a duplicate message")

    # Step 3: Retrieve booking from database
    logging.info(f"🔍 Step 3: Retrieving booking from database...")
    booking = get_booking_by_id(booking_id)

    if not booking:
        logging.error(f"❌ BOOKING NOT FOUND IN DATABASE")
        logging.error(f"   Booking ID: {booking_id}")
        return {'status': 'booking_not_found', 'booking_id': booking_id}, 404

    logging.info(f"✅ Booking found in database")
    logging.info(f"   Current status: {booking.get('status')}")
    logging.info(f"   Guest email: {booking.get('guest_email')}")
    logging.info(f"   Players: {booking.get('players')}")
    logging.info(f"   Current tee_time: {booking.get('tee_time', 'None')}")

    # Step 4: Check if already confirmed
    if booking.get('status', '').lower() == 'confirmed':
        logging.info(f"ℹ️  Booking already confirmed - no action needed")
        logging.info(f"   Confirmed at: {booking.get('customer_confirmed_at')}")
        return {'status': 'already_confirmed', 'booking_id': booking_id}, 200

    # Step 5: Verify confirmation intent
    logging.info("🔍 Step 5: Checking for confirmation keywords...")
    confirmation_keywords = ['confirm', 'yes', 'book', 'proceed', 'accept', 'ok', 'okay', 'sure', 'sounds good']
    body_lower = body.lower() if body else ""
    is_confirmation = any(keyword in body_lower for keyword in confirmation_keywords)

    if not is_confirmation:
        logging.warning("⚠️  No confirmation keywords found - treating as general reply")
        logging.warning(f"   Body (first 200 chars): {body_lower[:200]}")
        return {'status': 'reply_received', 'booking_id': booking_id}, 200

    logging.info(f"✅ Confirmation intent detected")

    # Step 6: Extract tee time details
    logging.info("🔍 Step 6: Extracting tee time from email...")
    tee_date, tee_time = extract_tee_time_from_email(subject, body)

    # Step 7: Prepare updates
    logging.info("🔍 Step 7: Preparing database updates...")
    updates = {
        'status': 'Confirmed',
        'customer_confirmed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'confirmation_message_id': message_id,
        'note': f"Confirmed via email"
    }

    if tee_date:
        updates['date'] = tee_date
        logging.info(f"   ✓ Will update date to: {tee_date}")
    else:
        logging.warning(f"   ⚠️  No date extracted - keeping existing date: {booking.get('date')}")

    if tee_time:
        updates['tee_time'] = tee_time
        logging.info(f"   ✓ Will update tee_time to: {tee_time}")
    else:
        logging.warning(f"   ⚠️  No time extracted - tee_time will remain NULL")
        logging.warning(f"   ⚠️  This means customer will see 'not specified' for time!")

    # Step 8: Update database
    logging.info("🔍 Step 8: Updating database...")
    logging.info(f"   Updates to apply: {updates}")

    if update_booking_in_db(booking_id, updates):
        logging.info("="*80)
        logging.info(f"✅ ✅ ✅ BOOKING CONFIRMED SUCCESSFULLY ✅ ✅ ✅")
        logging.info("="*80)
        logging.info(f"📋 Booking ID: {booking_id}")
        logging.info(f"📅 Date: {tee_date or booking.get('date', 'Unknown')}")
        logging.info(f"⏰ Time: {tee_time or 'NOT SPECIFIED'}")
        logging.info(f"👤 Guest: {booking.get('guest_email')}")
        logging.info(f"👥 Players: {booking.get('players')}")
        logging.info("="*80)

        return {
            'status': 'confirmed',
            'booking_id': booking_id,
            'tee_date': tee_date,
            'tee_time': tee_time
        }, 200
    else:
        logging.error("❌ DATABASE UPDATE FAILED")
        return {'status': 'update_failed', 'booking_id': booking_id}, 500


def log_provisional_booking(guest_email: str, parsed, dates: list, message_id: str = None):
    """Log booking to database and JSONL"""
    total = PER_PLAYER_FEE * parsed.player_count
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_entry = {
        "timestamp": timestamp,
        "guest_email": guest_email,
        "message_id": message_id,
        "dates": dates,
        "date": dates[0] if dates else None,
        "tee_time": None,
        "players": parsed.player_count,
        "total": total,
        "status": "Pending",
        "intent": parsed.intent.value,
        "urgency": parsed.urgency.value,
        "confidence": parsed.confidence,
        "is_corporate": parsed.is_corporate,
        "company_name": parsed.company_name,
        "note": "Booking offer sent",
        "club": DEFAULT_COURSE_ID,
        "club_name": FROM_NAME
    }

    booking_id = save_booking_to_db(new_entry)

    if not booking_id:
        booking_id = generate_booking_id(guest_email, timestamp)
        new_entry['booking_id'] = booking_id
    else:
        new_entry['booking_id'] = booking_id

    post_booking_to_dashboard(new_entry, booking_id)

    # Also save to JSONL
    existing = []
    if os.path.exists(BOOKINGS_FILE):
        with open(BOOKINGS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        existing.append(json.loads(line))
                    except:
                        continue

    existing = [e for e in existing
                if not (e.get("guest_email") == guest_email and
                       e.get("dates", [None])[0] == dates[0] if dates else False)]
    existing.append(new_entry)

    with open(BOOKINGS_FILE, "w") as f:
        for e in existing:
            f.write(json.dumps(e) + "\n")

    return booking_id


def init_database():
    """Create bookings table with tee_time field"""
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
            logging.info("📋 Creating new bookings table with tee_time field...")
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
                    status VARCHAR(50) NOT NULL DEFAULT 'Pending',
                    intent VARCHAR(50),
                    urgency VARCHAR(50),
                    confidence DECIMAL(3, 2),
                    is_corporate BOOLEAN DEFAULT FALSE,
                    company_name VARCHAR(255),
                    note TEXT,
                    club VARCHAR(100),
                    club_name VARCHAR(255),
                    customer_confirmed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logging.info("✅ Bookings table created with tee_time field")
        else:
            logging.info("📋 Bookings table exists - checking for schema updates...")

            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'bookings';
            """)
            existing_columns = {row[0] for row in cursor.fetchall()}

            required_columns = {
                'tee_time': 'VARCHAR(10)',
            }

            for col_name, col_def in required_columns.items():
                if col_name not in existing_columns:
                    logging.info(f"  📌 Adding missing column: {col_name}")
                    cursor.execute(f"ALTER TABLE bookings ADD COLUMN IF NOT EXISTS {col_name} {col_def};")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_email ON bookings(guest_email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_message_id ON bookings(message_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_tee_time ON bookings(tee_time);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_booking_id ON bookings(booking_id);")

        conn.commit()
        cursor.close()

        logging.info("✅ Database schema ready with tee_time field")
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
# ALTERNATIVE DATE CHECKING - ENHANCED FEATURE
# ============================================================================

def generate_alternative_dates(original_dates: list, max_alternatives: int = 7) -> list:
    """
    🆕 Generate alternative dates to check if original dates have no availability
    Returns dates within +/- 7 days of the original request
    """
    alternative_dates = []
    
    if not original_dates:
        return alternative_dates
    
    try:
        # Parse the first requested date
        base_date = datetime.strptime(original_dates[0], '%Y-%m-%d').date()
        today = datetime.now().date()
        
        logging.info(f"📅 Generating alternatives around {base_date}")
        
        # Generate dates: +1, -1, +2, -2, +3, -3, +4, -4 days from original
        for offset in [1, -1, 2, -2, 3, -3, 4, -4]:
            alt_date = base_date + timedelta(days=offset)
            
            # Don't suggest dates in the past
            if alt_date >= today:
                alternative_dates.append(alt_date.strftime('%Y-%m-%d'))
            
            if len(alternative_dates) >= max_alternatives:
                break
        
        logging.info(f"✅ Generated {len(alternative_dates)} alternative dates")
        for i, date in enumerate(alternative_dates[:3], 1):
            logging.info(f"   {i}. {date}")
        
    except Exception as e:
        logging.error(f"❌ Error generating alternative dates: {e}")
    
    return alternative_dates


def check_availability_via_api(course_id: str, dates: list, players: int, parsed=None) -> dict:
    """Call Core API to check availability"""
    try:
        url = f"{CORE_API_URL}/check_availability"
        payload = {
            "course_id": course_id,
            "dates": dates,
            "players": players
        }

        # Add time preferences if available from parsed data
        if parsed and parsed.time_preference:
            time_pref = {}
            if parsed.time_preference.morning:
                time_pref['morning'] = True
            if parsed.time_preference.afternoon:
                time_pref['afternoon'] = True
            if parsed.time_preference.evening:
                time_pref['evening'] = True
            if parsed.time_preference.specific_time:
                time_pref['specific_time'] = parsed.time_preference.specific_time

            if time_pref:
                payload['time_preference'] = time_pref

        # Add special requests if available
        if parsed:
            if parsed.cart_requested:
                payload['cart_requested'] = True
            if parsed.caddie_requested:
                payload['caddie_requested'] = True
            if parsed.is_corporate:
                payload['is_corporate'] = True

        logging.info(f"🔗 Calling Core API: {url}")
        logging.info(f"   Dates: {dates}")
        logging.info(f"   Players: {players}")

        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        data = response.json()

        logging.info(f"✅ Core API responded - {len(data.get('results', []))} results")

        return data

    except requests.exceptions.Timeout:
        logging.error("❌ Core API timeout")
        return {"success": False, "error": "Core API timeout"}
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Core API error: {e}")
        return {"success": False, "error": str(e)}


def check_availability_with_alternatives(course_id: str, dates: list, players: int, parsed=None) -> dict:
    """
    🆕 NEW FEATURE: Check availability and automatically try alternative dates if none found
    
    This function dramatically improves booking conversion rates by automatically
    checking nearby dates (+/- 7 days) when the originally requested dates are full.
    
    Returns combined results with flags indicating if alternatives were used.
    """
    logging.info("="*80)
    logging.info("🔍 CHECKING AVAILABILITY WITH AUTO-ALTERNATIVES")
    logging.info("="*80)
    logging.info(f"📅 Original dates requested: {dates}")
    logging.info(f"👥 Players: {players}")
    
    # STEP 1: Try the originally requested dates
    logging.info("🔍 STEP 1: Checking originally requested dates...")
    original_response = check_availability_via_api(course_id, dates, players, parsed)
    
    # Check if we got results AND they match the requested dates
    if original_response.get("success") and original_response.get("results"):
        results = original_response.get("results", [])
        result_count = len(results)
        
        # CRITICAL: Check if results are actually for the requested dates
        result_dates = set([r.get('date') for r in results])
        requested_dates = set(dates)
        
        # If results match requested dates, we're done!
        if result_dates.intersection(requested_dates):
            matching_results = [r for r in results if r.get('date') in requested_dates]
            logging.info(f"✅ SUCCESS! Found {len(matching_results)} tee times on requested dates")
            logging.info("="*80)
            
            # Only return the results that match requested dates
            original_response['results'] = matching_results
            original_response['used_alternatives'] = False
            original_response['original_dates'] = dates
            original_response['checked_alternatives'] = False
            return original_response
        else:
            # Results are for different dates - API returned alternatives automatically
            logging.warning(f"⚠️  API returned {result_count} results but for different dates:")
            logging.warning(f"   Requested: {dates}")
            logging.warning(f"   Received: {sorted(result_dates)}")
            logging.info("   Treating as no availability on requested dates")
            # Fall through to alternative date checking
    
    # STEP 2: No availability on requested dates - try alternatives
    logging.info("⚠️  No availability found on requested dates")
    logging.info("="*80)
    logging.info("🔄 STEP 2: Generating and checking alternative dates...")
    logging.info("="*80)
    
    alternative_dates = generate_alternative_dates(dates, max_alternatives=7)
    
    if not alternative_dates:
        logging.warning("❌ Could not generate alternative dates")
        original_response['checked_alternatives'] = False
        return original_response
    
    logging.info(f"📅 Checking {len(alternative_dates)} alternative dates:")
    for i, date in enumerate(alternative_dates, 1):
        logging.info(f"   {i}. {date}")
    
    # Try alternative dates
    alternative_response = check_availability_via_api(course_id, alternative_dates, players, parsed)
    
    if alternative_response.get("success") and alternative_response.get("results"):
        result_count = len(alternative_response['results'])
        logging.info("="*80)
        logging.info(f"🎉 GREAT NEWS! Found {result_count} tee times on alternative dates!")
        logging.info("="*80)
        
        alternative_response['used_alternatives'] = True
        alternative_response['original_dates'] = dates
        alternative_response['searched_dates'] = alternative_dates
        alternative_response['checked_alternatives'] = True
        
        # Mark all results as alternative dates for UI display
        for result in alternative_response.get('results', []):
            result['is_alternative_date'] = True
        
        # Log which dates had availability
        available_dates = list(set([r['date'] for r in alternative_response['results']]))
        logging.info(f"📅 Available alternative dates found:")
        for date in sorted(available_dates):
            count = len([r for r in alternative_response['results'] if r['date'] == date])
            logging.info(f"   • {date}: {count} tee times")
        
        return alternative_response
    
    # STEP 3: Still no availability found
    logging.info("="*80)
    logging.warning("❌ No availability found on requested dates OR alternatives")
    logging.info("="*80)
    
    return {
        "success": False,
        "results": [],
        "error": "No availability found",
        "used_alternatives": False,
        "original_dates": dates,
        "searched_dates": alternative_dates,
        "checked_alternatives": True
    }


# ============================================================================
# BOOKING LOGIC FUNCTIONS
# ============================================================================

def analyze_group_size(player_count: int) -> dict:
    """Analyze group size and return booking strategy"""
    
    if player_count <= 4:
        return {
            'category': 'standard',
            'slots_needed': 1,
            'requires_consecutive': False,
            'suggest_contact': False
        }
    
    elif player_count <= 8:
        return {
            'category': 'medium',
            'slots_needed': 2,
            'requires_consecutive': True,
            'suggest_contact': False
        }
    
    elif player_count <= 12:
        return {
            'category': 'large',
            'slots_needed': 3,
            'requires_consecutive': True,
            'suggest_contact': False
        }
    
    else:
        # Even for very large groups, show available options
        # Calculate number of slots needed (4 players per slot)
        slots_needed = (player_count + 3) // 4
        return {
            'category': 'very_large',
            'slots_needed': slots_needed,
            'requires_consecutive': True,
            'suggest_contact': True,  # Still suggest contact for special arrangements
            'manual_only': False,  # Changed from True - show options anyway!
            'contact_reason': 'large_group_benefits',
            'message': f'For groups of {player_count}, we recommend contacting us for group rates and special arrangements. However, you can still book directly below.'
        }


def build_booking_link(date: str, time: str, players: int, guest_email: str, course_name: str,
                      slot_group: List[Dict] = None, player_distribution: List[int] = None,
                      booking_id: str = None) -> str:
    """Generate mailto link with CONFIRM BOOKING subject"""

    tracking_email = f"{TRACKING_EMAIL_PREFIX}@bookings.teemail.io"
    club_email = CLUB_BOOKING_EMAIL

    if slot_group and player_distribution:
        # GROUP BOOKING EMAIL
        total_players = sum(player_distribution)
        total_cost = PER_PLAYER_FEE * total_players

        if booking_id:
            subject = f"CONFIRM GROUP BOOKING - {total_players} Players - {date} [Ref: {booking_id}]"
        else:
            subject = f"Group Booking Request - {total_players} Players - {date}"

        body = f"""Hello,

Please CONFIRM consecutive tee times for our group:

Course: {course_name}
Date: {date}
Total Players: {total_players}"""

        if booking_id:
            body += f"\nBooking Reference: {booking_id}"

        body += "\n\nTee Time Details:\n"

        for i, (slot, slot_players) in enumerate(zip(slot_group, player_distribution), 1):
            slot_time = slot.get('time', '')
            slot_cost = PER_PLAYER_FEE * slot_players
            body += f"\nGroup {i}: {slot_time} - {slot_players} player{'s' if slot_players != 1 else ''} (€{slot_cost:.2f})"

        body += f"""

Total Cost: €{total_cost:.2f}

Guest Email: {guest_email}

Please confirm this group booking.

Thank you!"""

    else:
        # SINGLE BOOKING EMAIL
        total_cost = PER_PLAYER_FEE * players

        if booking_id:
            subject = f"CONFIRM BOOKING - {date} at {time} [Ref: {booking_id}]"
        else:
            subject = f"Tee Time Booking Request - {date} at {time}"

        body = f"""Hello,

Please CONFIRM my booking with the following details:

Course: {course_name}
Date: {date}
Time: {time}
Number of Players: {players}
Price per Player: €{PER_PLAYER_FEE:.2f}
Total Cost: €{total_cost:.2f}"""

        if booking_id:
            body += f"\nBooking Reference: {booking_id}"

        body += f"""

Guest Email: {guest_email}

Please confirm this booking.

Thank you!"""
    
    subject_encoded = quote(subject)
    body_encoded = quote(body)

    mailto_link = f"mailto:{club_email},{tracking_email}?subject={subject_encoded}&body={body_encoded}"

    return mailto_link


def find_consecutive_slots(results: list, slots_needed: int) -> list:
    """Find consecutive tee time slots for group bookings"""
    if slots_needed <= 1:
        return []
    
    # Group by date
    dates_dict = {}
    for result in results:
        date = result.get('date')
        if date not in dates_dict:
            dates_dict[date] = []
        dates_dict[date].append(result)
    
    consecutive_options = []
    
    for date, slots in dates_dict.items():
        # Sort by time
        sorted_slots = sorted(slots, key=lambda x: x.get('time', ''))
        
        # Look for consecutive slots (within 10 minutes of each other)
        for i in range(len(sorted_slots) - slots_needed + 1):
            potential_group = []
            
            for j in range(slots_needed):
                slot = sorted_slots[i + j]
                
                # Check if slots are within 10-12 minutes of each other
                if j > 0:
                    prev_time = potential_group[-1].get('time', '')
                    curr_time = slot.get('time', '')
                    
                    # Parse times and check difference
                    try:
                        prev_h, prev_m = map(int, prev_time.split(':'))
                        curr_h, curr_m = map(int, curr_time.split(':'))
                        
                        prev_total = prev_h * 60 + prev_m
                        curr_total = curr_h * 60 + curr_m
                        
                        diff = curr_total - prev_total
                        
                        # Must be 10-12 minutes apart (standard tee interval)
                        if diff < 8 or diff > 15:
                            break
                    except:
                        break
                
                potential_group.append(slot)
            
            if len(potential_group) == slots_needed:
                consecutive_options.append(potential_group)
    
    return consecutive_options


def distribute_players_across_slots(total_players: int, num_slots: int) -> list:
    """Distribute players across slots (e.g., 11 players → [4, 4, 3])"""
    base_per_slot = total_players // num_slots
    remainder = total_players % num_slots
    
    distribution = [base_per_slot] * num_slots
    
    # Add remainder players to first slots
    for i in range(remainder):
        distribution[i] += 1
    
    return distribution


def format_consecutive_slots_table(slot_group: list, player_distribution: list) -> str:
    """Format HTML table for consecutive group booking slots"""
    
    html = """
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
        <thead>
            <tr style="background: #003B7C; color: white;">
                <th style="padding: 10px; text-align: left;">Group</th>
                <th style="padding: 10px; text-align: left;">Tee Time</th>
                <th style="padding: 10px; text-align: center;">Players</th>
                <th style="padding: 10px; text-align: right;">Cost</th>
            </tr>
        </thead>
        <tbody>
    """
    
    total_cost = 0
    
    for i, (slot, slot_players) in enumerate(zip(slot_group, player_distribution), 1):
        slot_time = slot.get('time', '')
        slot_cost = PER_PLAYER_FEE * slot_players
        total_cost += slot_cost
        
        bg_color = '#f9fafb' if i % 2 == 0 else '#ffffff'
        
        html += f"""
            <tr style="background: {bg_color};">
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">Group {i}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{slot_time}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: center;">{slot_players}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: right;">€{slot_cost:.2f}</td>
            </tr>
        """
    
    html += f"""
            <tr style="background: #FFF8E1; font-weight: bold;">
                <td colspan="3" style="padding: 12px; text-align: right;">Total:</td>
                <td style="padding: 12px; text-align: right; color: #003B7C;">€{total_cost:.2f}</td>
            </tr>
        </tbody>
    </table>
    """
    
    return html


def format_group_booking_email_html(
    course_name: str,
    consecutive_options: list,
    player_count: int,
    guest_email: str,
    group_analysis: dict,
    booking_link_func,
    booking_id: str = None,
    from_email: str = "teetimes@countylouthgolfclub.com",
    used_alternatives: bool = False,
    original_dates: list = None
) -> str:
    """Format beautiful HTML email for group bookings (5+ players) with alternative date support"""
    
    html = get_email_header(course_name)
    
    slots_needed = group_analysis['slots_needed']
    player_distribution = distribute_players_across_slots(player_count, slots_needed)
    
    html += f"""
        <p class="greeting">Thank you for your group booking enquiry at <strong style="color: #003B7C;">{course_name}</strong>!</p>
        
        <div class="info-box">
            <h3><span class="emoji">👥</span>Group Booking Details</h3>
            <p><strong>Total Players:</strong> {player_count}</p>
            <p><strong>Tee Times Needed:</strong> {slots_needed} consecutive slots</p>
            <p><strong>Player Distribution:</strong> {' + '.join(map(str, player_distribution))} players per group</p>
            <p><strong>Green Fee:</strong> €{PER_PLAYER_FEE:.0f} per player</p>
            <p><strong>Total Cost:</strong> <span class="price-highlight">€{PER_PLAYER_FEE * player_count:.2f}</span></p>
            <p><strong>Status:</strong> <span class="status-badge">{'✓ Alternative Dates Found' if used_alternatives else '✓ Available Times Found'}</span></p>
        </div>
    """
    
    # Add special notice for very large groups (13+ players) suggesting contact but still showing options
    if group_analysis.get('category') == 'very_large':
        html += f"""
        <div class="links-box">
            <h3><span class="emoji">💎</span>Large Group Benefits Available</h3>
            <p>For groups of {player_count} players, we can offer:</p>
            <ul style="color: #374151; line-height: 1.8;">
                <li><strong>Group discounts</strong> on green fees</li>
                <li><strong>Catering arrangements</strong> for your group</li>
                <li><strong>Dedicated support</strong> from our events team</li>
                <li><strong>Flexible scheduling</strong> options</li>
            </ul>
            <p style="margin-top: 15px;">
                <strong>Contact us at <a href="tel:+353419881530" style="color: #2D5F3F;">+353 41 988 1530</a> to discuss these benefits!</strong>
            </p>
            <p style="margin-top: 10px; font-style: italic; color: #6b7280;">
                Or you can book directly using the options below:
            </p>
        </div>
        """
    
    # Add ENHANCED alternative dates notice if applicable
    if used_alternatives and original_dates:
        original_dates_str = ', '.join(original_dates)
        plural = 's' if len(original_dates) > 1 else ''
        were_was = 'were' if len(original_dates) > 1 else 'was'
        
        html += f"""
        <div class="alternative-box">
            <h3><span class="emoji">🎯</span>Alternative Dates Found!</h3>
            <p style="font-size: 16px; margin-bottom: 15px; line-height: 1.6;">
                Your requested date{plural} <strong style="color: #8B7355;">({original_dates_str})</strong> {were_was} fully booked 
                for groups of {player_count} players.
            </p>
            <div class="highlight">
                <p style="margin: 0; font-weight: 600; color: #8B7355; font-size: 16px;">
                    <span class="emoji">✅</span>Great news! We found consecutive tee times within the same week
                </p>
                <p style="margin: 10px 0 0 0; color: #666; line-height: 1.6;">
                    These alternative dates offer the same championship golf experience 
                    and are clearly marked below with <strong style="color: #D4AF37;">gold badges</strong>.
                </p>
            </div>
        </div>
        """
    
    # Group options by date
    options_by_date = {}
    for option in consecutive_options:
        # Handle both pre-grouped API results and locally found consecutive slots
        if isinstance(option, dict) and option.get('is_multi_slot'):
            # Pre-grouped from API
            date = option.get('date')
            is_alt = option.get('is_alternative_date', False)
            slot_details = option.get('slot_details', [])
            
            if date not in options_by_date:
                options_by_date[date] = {'options': [], 'is_alternative': is_alt}
            options_by_date[date]['options'].append({
                'type': 'pre_grouped',
                'date': date,
                'slot_details': slot_details,
                'time': slot_details[0].get('time') if slot_details else ''
            })
        elif isinstance(option, list):
            # Locally found consecutive slots
            date = option[0].get('date') if option else None
            is_alt = option[0].get('is_alternative_date', False) if option else False
            
            if date and date not in options_by_date:
                options_by_date[date] = {'options': [], 'is_alternative': is_alt}
            if date:
                options_by_date[date]['options'].append({
                    'type': 'local',
                    'slots': option
                })
    
    # Display options by date
    for date in sorted(options_by_date.keys()):
        date_info = options_by_date[date]
        is_alt_date = date_info['is_alternative']
        
        # Start alternative date wrapper if needed
        if is_alt_date:
            html += '<div class="alternative-date-section">'
        
        date_badge = '<span class="alternative-badge">📅 Alternative Date</span>' if is_alt_date else ''
        
        html += f"""
        <div class="date-section">
            <h2 class="date-header"><span class="emoji">🗓️</span>{date} {date_badge}</h2>
            <p style="margin-bottom: 20px; color: #666;">We found {len(date_info['options'])} option{'s' if len(date_info['options']) > 1 else ''} with {slots_needed} consecutive tee times:</p>
        """
        
        for option_num, option_data in enumerate(date_info['options'][:3], 1):
            if option_data['type'] == 'pre_grouped':
                # Handle pre-grouped API results
                slot_group = option_data['slot_details']
                start_time = option_data['time']
            else:
                # Handle locally found consecutive slots
                slot_group = option_data['slots']
                start_time = slot_group[0].get('time', '') if slot_group else ''
            
            slots_table = format_consecutive_slots_table(slot_group, player_distribution)
            
            booking_link = booking_link_func(
                date=date,
                time=start_time,
                players=player_count,
                guest_email=guest_email,
                course_name=course_name,
                slot_group=slot_group,
                player_distribution=player_distribution,
                booking_id=booking_id
            )
            
            row_class = 'alt-date-row' if is_alt_date else ''

            button_html = create_book_button(booking_link, f"Book All {slots_needed} Tee Times")
            html += f"""
            <div class="group-box" style="margin: 20px 0; padding: 20px; background: {'#FFFEF7' if is_alt_date else '#f9fafb'}; border-radius: 8px; border-left: 4px solid {'#D4AF37' if is_alt_date else '#003B7C'};">
                <h3 style="margin-top: 0; color: {'#8B7355' if is_alt_date else '#003B7C'};">
                    <span class="emoji">⛳</span>Option {option_num}: Starting at {start_time}
                </h3>
                {slots_table}
                <div style="text-align: center; margin-top: 20px;">
                    {button_html}
                </div>
            </div>
            """
        
        html += "</div>"
        
        # Close alternative date wrapper if needed
        if is_alt_date:
            html += '</div>'
    
    # Add helpful information
    html += """
        <div class="links-box" style="margin-top: 30;">
            <h3><span class="emoji">⛳</span>Group Golf at County Louth</h3>
            <p>Our championship links course is perfect for group outings. Each fourball will tee off at 10-minute intervals, allowing your entire group to enjoy a great day of golf together.</p>
        </div>
        
        <div class="info-box">
            <h3><span class="emoji">💡</span>How to Confirm Your Group Booking</h3>
            <p><strong>Step 1:</strong> Choose your preferred option and click "Book All X Tee Times"</p>
            <p><strong>Step 2:</strong> Your email client will open with all details pre-filled</p>
            <p><strong>Step 3:</strong> Send the email - we'll confirm all tee times within 30 minutes</p>
            <p style="margin-top: 12px; font-style: italic; color: #6b7280;">For groups over 12 players or special requirements, please call us at <strong style="color: #003B7C;">+353 41 988 1530</strong></p>
        </div>
    """
    
    html += get_email_footer(course_name, from_email)
    
    return html


def format_no_consecutive_slots_email_html(
    course_name: str,
    player_count: int,
    slots_needed: int,
    from_email: str = "teetimes@countylouthgolfclub.com",
    original_dates: list = None,
    checked_alternatives: bool = False
) -> str:
    """Format HTML email when consecutive slots not available for group"""
    
    html = get_email_header(course_name)
    
    html += f"""
        <p class="greeting">Thank you for your group booking enquiry at <strong style="color: #003B7C;">{course_name}</strong>.</p>
        
        <div class="warning-box">
            <h3><span class="emoji">⚠️</span>Limited Consecutive Availability</h3>
            <p>Unfortunately, we don't have <strong>{slots_needed} consecutive tee times</strong> available for your group of <strong>{player_count} players</strong> on your requested dates.</p>
    """
    
    if checked_alternatives:
        html += f"""
            <p style="margin-top: 10px;">We have checked dates within a week of your request, but were unable to find suitable consecutive slots for your group.</p>
        """
    
    html += """
        </div>
        
        <div class="info-box">
            <h3><span class="emoji">📞</span>Let Us Help You</h3>
            <p>Our team specializes in accommodating group bookings and can help you find the perfect solution:</p>
            <p><strong>Email:</strong> <a href="mailto:{from_email}" style="color: #003B7C;">{from_email}</a></p>
            <p><strong>Telephone:</strong> <a href="tel:+353419881530" style="color: #003B7C;">+353 41 988 1530</a></p>
            <p style="margin-top: 15px;">We can often:</p>
            <ul style="color: #374151;">
                <li>Find alternative dates with availability</li>
                <li>Split your group across non-consecutive times</li>
                <li>Offer group discounts for larger bookings</li>
                <li>Arrange catering and other services</li>
            </ul>
        </div>
        
        <p>We look forward to welcoming your group to our championship links course!</p>
    """
    
    html += get_email_footer(course_name, from_email)
    
    return html


def format_availability_response(parsed, api_response: dict, guest_email: str, booking_id: str = None, message_id: str = None) -> tuple[str, str]:
    """Format HTML email response from Core API data with enhanced alternative date support for both standard and group bookings"""

    group_analysis = analyze_group_size(parsed.player_count)
    
    # Extract metadata
    used_alternatives = api_response.get('used_alternatives', False)
    original_dates = api_response.get('original_dates', [])
    checked_alternatives = api_response.get('checked_alternatives', False)
    
    if not api_response.get("success"):
        subject = "Tee Time Availability Check"
        body = format_error_email_html(FROM_NAME, api_response.get("error"), FROM_EMAIL)
        return subject, body
    
    results = api_response.get("results", [])
    if not results:
        subject = "No Availability Found"
        
        # Use appropriate no-availability email based on group size
        if group_analysis['slots_needed'] > 1:
            body = format_no_consecutive_slots_email_html(
                FROM_NAME,
                parsed.player_count,
                group_analysis['slots_needed'],
                FROM_EMAIL,
                original_dates=original_dates,
                checked_alternatives=checked_alternatives
            )
        else:
            body = format_no_availability_email_html(
                FROM_NAME, 
                parsed.player_count, 
                FROM_EMAIL,
                original_dates=original_dates,
                checked_alternatives=checked_alternatives
            )
        return subject, body
    
    course_name = results[0].get("course_name", FROM_NAME)
    
    # Handle GROUP bookings (5+ players needing consecutive slots)
    if group_analysis['slots_needed'] > 1:
        logging.info(f"🎯 GROUP BOOKING: {parsed.player_count} players need {group_analysis['slots_needed']} consecutive slots")
        
        # Check if API already provided grouped slots
        multi_slot_results = [r for r in results if r.get('is_multi_slot')]
        
        if multi_slot_results:
            # API provided pre-grouped consecutive slots
            consecutive_options = multi_slot_results
            logging.info(f"   ✅ API provided {len(consecutive_options)} pre-grouped options")
        else:
            # Find consecutive slots from individual results
            consecutive_options = find_consecutive_slots(results, group_analysis['slots_needed'])
            logging.info(f"   🔍 Found {len(consecutive_options)} consecutive slot combinations")
        
        if not consecutive_options:
            logging.warning("   ❌ No consecutive slots available")
            subject = "Group Booking - Limited Availability"
            body = format_no_consecutive_slots_email_html(
                course_name,
                parsed.player_count,
                group_analysis['slots_needed'],
                FROM_EMAIL,
                original_dates=original_dates,
                checked_alternatives=checked_alternatives
            )
            return subject, body
        
        # Format group booking email with consecutive options
        subject = f"Group Booking Options - {course_name} ({parsed.player_count} Players)"
        body = format_group_booking_email_html(
            course_name=course_name,
            consecutive_options=consecutive_options,
            player_count=parsed.player_count,
            guest_email=guest_email,
            group_analysis=group_analysis,
            booking_link_func=build_booking_link,
            booking_id=booking_id,
            from_email=FROM_EMAIL,
            used_alternatives=used_alternatives,
            original_dates=original_dates
        )
        return subject, body
    
    # Handle STANDARD bookings (1-4 players)
    else:
        logging.info(f"✅ STANDARD BOOKING: {parsed.player_count} players")
        subject = f"Tee Time Availability - {course_name}"
        
        body = format_standard_booking_email_html(
            course_name=course_name,
            results=results,
            player_count=parsed.player_count,
            guest_email=guest_email,
            booking_link_func=build_booking_link,
            booking_id=booking_id,
            from_email=FROM_EMAIL,
            used_alternatives=used_alternatives,
            original_dates=original_dates
        )

        return subject, body


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
# WEBHOOK ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    db_status = "connected" if db_pool else "disconnected"
    
    return jsonify({
        'status': 'healthy',
        'service': 'TeeMail Email Bot - Enhanced with Alternative Date Checking & Improved Visual Marking',
        'database': db_status,
        'features': [
            'enhanced_html_templates', 
            'championship_branding', 
            'confirmation_detection',
            'alternative_date_checking',
            'improved_visual_marking'
        ]
    })


@app.route('/webhook/inbound', methods=['POST'])
def handle_inbound_email():
    """SendGrid Inbound Parse webhook with alternative date checking"""
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

        # Detect confirmation emails
        if is_confirmation_email(subject, body):
            logging.info("🎯 CONFIRMATION EMAIL DETECTED")
            result, status_code = process_confirmation(from_email, subject, body, message_id)
            return jsonify(result), status_code
        
        # Process as NEW booking
        logging.info("📝 NEW BOOKING REQUEST")

        if not from_email or '@' not in from_email:
            return jsonify({'status': 'invalid_email'}), 400

        if not body or len(body.strip()) < 10:
            return jsonify({'status': 'empty_body'}), 200
        
        parsed = parse_booking_email(body, subject)

        logging.info(f"   Players: {parsed.player_count}")
        logging.info(f"   Confidence: {parsed.confidence:.0%}")
        logging.info(f"   Intent: {parsed.intent.value}")
        
        if parsed.confidence < 0.3:
            return jsonify({'status': 'low_confidence'}), 200
        
        dates = []
        if parsed.dates.start_date:
            dates.append(parsed.dates.start_date.strftime('%Y-%m-%d'))
        if parsed.dates.end_date:
            dates.append(parsed.dates.end_date.strftime('%Y-%m-%d'))
        
        if not dates:
            return jsonify({'status': 'no_dates'}), 200
        
        booking_id = log_provisional_booking(from_email, parsed, dates, message_id)
        
        # 🆕 NEW: Use the enhanced availability checking with alternatives
        api_response = check_availability_with_alternatives(DEFAULT_COURSE_ID, dates, parsed.player_count, parsed)
        
        # Format and send email (now includes alternative date info with improved visual marking)
        subject_line, html_body = format_availability_response(parsed, api_response, from_email, booking_id, message_id)
        
        # SEND THE EMAIL!
        send_email_sendgrid(from_email, subject_line, html_body)
        
        return jsonify({'status': 'success', 'booking_id': booking_id}), 200
            
    except Exception as e:
        logging.exception(f"❌ ERROR:")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/bookings', methods=['GET'])
def api_get_bookings():
    """API endpoint for dashboard to read bookings"""
    try:
        bookings = get_all_bookings_from_db()
        
        return jsonify({
            'success': True,
            'bookings': bookings,
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
logging.info("🌐 TeeMail Email Bot - Enhanced with Alternative Date Checking & Improved Visual Marking")
logging.info("="*80)
logging.info("✅ Enhanced HTML templates enabled")
logging.info("✅ County Louth championship branding")
logging.info("✅ Beautiful responsive emails")
logging.info("🆕 AUTOMATIC ALTERNATIVE DATE CHECKING")
logging.info("✨ IMPROVED VISUAL MARKING - Gold badges & gradients")
logging.info("📊 Dashboard reads from shared PostgreSQL database")
logging.info("="*80)

if init_db_pool():
    init_database()
    logging.info("✅ Database ready")

logging.info(f"📧 SendGrid: {FROM_EMAIL}")
logging.info(f"📬 Club Booking Email: {CLUB_BOOKING_EMAIL}")
logging.info(f"📮 Tracking Email: {TRACKING_EMAIL_PREFIX}@bookings.teemail.io")
logging.info(f"🔗 Core API: {CORE_API_URL}")
logging.info(f"📊 Dashboard: {DASHBOARD_API_URL}")
logging.info("="*80)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
