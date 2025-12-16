"""
Email Storage Module
Saves complete inbound emails to database for learning system and debugging
"""

import os
import json
import logging
import psycopg2
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL not set")
            return None
        return psycopg2.connect(database_url)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None


def save_inbound_email(
    message_id: str,
    from_email: str,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str = None,
    headers: str = None,
    attachments: list = None,
    booking_id: str = None,
    parsed_data: dict = None,
    club: str = None
) -> bool:
    """
    Save complete inbound email to database

    Args:
        message_id: Unique Message-ID from email headers
        from_email: Sender email address
        to_email: Recipient email address
        subject: Email subject line
        text_body: Plain text email body
        html_body: HTML email body (optional)
        headers: Raw email headers (optional)
        attachments: List of attachment metadata (optional)
        booking_id: Associated booking ID (optional)
        parsed_data: Parsed booking data from enhanced_nlp (optional)
        club: Club identifier (optional)

    Returns:
        bool: True if saved successfully, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Use club from environment if not provided
        if not club:
            club = os.getenv('DATABASE_CLUB_ID', 'demo')

        # Convert attachments and parsed_data to JSON
        attachments_json = json.dumps(attachments) if attachments else None
        parsed_json = json.dumps(parsed_data) if parsed_data else None

        cursor.execute("""
            INSERT INTO inbound_emails (
                message_id, from_email, to_email, subject,
                body_text, body_html, headers, attachments,
                booking_id, parsed_data, processing_status,
                received_at, club
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s::jsonb,
                %s, %s::jsonb, %s,
                %s, %s
            )
            ON CONFLICT (message_id) DO UPDATE SET
                processed_at = EXCLUDED.processed_at,
                booking_id = EXCLUDED.booking_id,
                parsed_data = EXCLUDED.parsed_data,
                processing_status = EXCLUDED.processing_status
            RETURNING id
        """, (
            message_id, from_email, to_email, subject,
            text_body, html_body, headers, attachments_json,
            booking_id, parsed_json, 'received',
            datetime.now(), club
        ))

        email_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()

        logger.info(f"✅ Saved inbound email to database: {message_id} (id={email_id})")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to save inbound email: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            conn.close()


def update_email_processing_status(
    message_id: str,
    status: str,
    booking_id: str = None,
    error_message: str = None
) -> bool:
    """
    Update the processing status of an inbound email

    Args:
        message_id: Email Message-ID
        status: New status (processed, error, duplicate)
        booking_id: Associated booking ID (optional)
        error_message: Error message if status is 'error' (optional)

    Returns:
        bool: True if updated successfully
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        cursor.execute("""
            UPDATE inbound_emails
            SET processing_status = %s,
                processed_at = %s,
                booking_id = COALESCE(%s, booking_id),
                error_message = %s
            WHERE message_id = %s
        """, (status, datetime.now(), booking_id, error_message, message_id))

        conn.commit()
        cursor.close()

        logger.info(f"✅ Updated email processing status: {message_id} → {status}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to update email status: {e}")
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            conn.close()


def get_inbound_email(message_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve an inbound email by Message-ID

    Args:
        message_id: Email Message-ID

    Returns:
        dict: Email data or None if not found
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id, message_id, from_email, to_email, subject,
                body_text, body_html, headers, attachments,
                booking_id, parsed_data, processing_status,
                error_message, received_at, processed_at, club
            FROM inbound_emails
            WHERE message_id = %s
        """, (message_id,))

        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return {
            'id': row[0],
            'message_id': row[1],
            'from_email': row[2],
            'to_email': row[3],
            'subject': row[4],
            'text_body': row[5],
            'html_body': row[6],
            'headers': row[7],
            'attachments': row[8],
            'booking_id': row[9],
            'parsed_data': row[10],
            'processing_status': row[11],
            'error_message': row[12],
            'received_at': row[13],
            'processed_at': row[14],
            'club': row[15],
        }

    except Exception as e:
        logger.error(f"❌ Failed to retrieve email: {e}")
        return None

    finally:
        if conn:
            conn.close()


def get_emails_by_booking_id(booking_id: str) -> list:
    """
    Get all emails associated with a booking

    Args:
        booking_id: Booking ID

    Returns:
        list: List of email records
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id, message_id, from_email, subject,
                body_text, processing_status, received_at
            FROM inbound_emails
            WHERE booking_id = %s
            ORDER BY received_at DESC
        """, (booking_id,))

        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                'id': row[0],
                'message_id': row[1],
                'from_email': row[2],
                'subject': row[3],
                'text_body': row[4],
                'processing_status': row[5],
                'received_at': row[6],
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"❌ Failed to retrieve emails by booking: {e}")
        return []

    finally:
        if conn:
            conn.close()


def get_recent_emails(limit: int = 50, status: str = None) -> list:
    """
    Get recent inbound emails

    Args:
        limit: Maximum number of emails to return
        status: Filter by processing status (optional)

    Returns:
        list: List of email records
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT
                    id, message_id, from_email, subject,
                    processing_status, received_at, booking_id
                FROM inbound_emails
                WHERE processing_status = %s
                ORDER BY received_at DESC
                LIMIT %s
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT
                    id, message_id, from_email, subject,
                    processing_status, received_at, booking_id
                FROM inbound_emails
                ORDER BY received_at DESC
                LIMIT %s
            """, (limit,))

        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                'id': row[0],
                'message_id': row[1],
                'from_email': row[2],
                'subject': row[3],
                'processing_status': row[4],
                'received_at': row[5],
                'booking_id': row[6],
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"❌ Failed to retrieve recent emails: {e}")
        return []

    finally:
        if conn:
            conn.close()
