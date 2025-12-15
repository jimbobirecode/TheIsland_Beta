# Email Storage Integration Guide

## Overview

Complete email content is now saved to the `inbound_emails` table for:
- ✅ Learning system training data
- ✅ Debugging parsing issues
- ✅ Audit trail of all communications
- ✅ Customer service history

---

## Database Setup

### 1. Run Migration

```bash
psql $DATABASE_URL < migrations/add_inbound_emails_table.sql
```

This creates the `inbound_emails` table with all necessary fields.

---

## Integration Steps

### Step 1: Import Module

Add to top of `island_email_bot.py` and `email_bot_webhook.py`:

```python
from email_storage import save_inbound_email, update_email_processing_status
```

### Step 2: Save Email on Receipt

**In `island_email_bot.py` webhook handler:**

```python
@app.route('/webhook/inbound', methods=['POST'])
def handle_inbound_email():
    """Handle inbound email from SendGrid"""
    try:
        # Extract email data
        from_email = request.form.get('from', '')
        to_email = request.form.get('to', '')
        subject = request.form.get('subject', '')
        text_body = request.form.get('text', '')
        html_body = request.form.get('html', '')
        headers = request.form.get('headers', '')
        message_id = extract_message_id(headers)

        # 🎯 SAVE EMAIL IMMEDIATELY
        save_inbound_email(
            message_id=message_id or f"no-id-{datetime.now().timestamp()}",
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            headers=headers
        )

        # ... rest of processing ...
        parsed = parse_email_enhanced(subject, text_body, from_email, sender_name)
        booking_id = create_booking(parsed)

        # 🎯 UPDATE WITH BOOKING ID AND PARSED DATA
        update_email_processing_status(
            message_id=message_id,
            status='processed',
            booking_id=booking_id
        )

        # Also save parsed data for learning
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE inbound_emails
                SET parsed_data = %s::jsonb
                WHERE message_id = %s
            """, (
                json.dumps({
                    'dates': parsed.get('dates'),
                    'players': parsed.get('players'),
                    'intent': parsed.get('intent'),
                    'lodging': parsed.get('lodging_requested'),
                    'confidence': parsed.get('confidence'),
                }),
                message_id
            ))
            conn.commit()
            cursor.close()
            conn.close()

        return jsonify({'status': 'success'})

    except Exception as e:
        logger.exception("Error processing email")

        # 🎯 MARK AS ERROR
        if message_id:
            update_email_processing_status(
                message_id=message_id,
                status='error',
                error_message=str(e)
            )

        return jsonify({'status': 'error'}), 500
```

### Step 3: Handle Duplicates

```python
# Check for duplicate
if message_id and is_duplicate_message(message_id):
    logging.warning(f"⚠️  DUPLICATE - SKIPPING")

    # 🎯 MARK AS DUPLICATE
    update_email_processing_status(
        message_id=message_id,
        status='duplicate'
    )

    return jsonify({'status': 'duplicate'}), 200
```

---

## Usage Examples

### Retrieve Email for Debugging

```python
from email_storage import get_inbound_email

# Get full email content
email = get_inbound_email(message_id)
print(f"From: {email['from_email']}")
print(f"Subject: {email['subject']}")
print(f"Body: {email['text_body']}")
print(f"Parsed: {email['parsed_data']}")
```

### Get All Emails for a Booking

```python
from email_storage import get_emails_by_booking_id

# Get email thread
emails = get_emails_by_booking_id('ISL-20251213-ABC123')
for email in emails:
    print(f"{email['received_at']}: {email['subject']}")
```

### View Recent Emails

```python
from email_storage import get_recent_emails

# Get last 50 processed emails
emails = get_recent_emails(limit=50, status='processed')

# Get errors
errors = get_recent_emails(limit=20, status='error')
```

---

## Dashboard Integration (Optional)

Add to your Streamlit dashboard:

```python
import streamlit as st
from email_storage import get_emails_by_booking_id, get_recent_emails

# In booking detail view
st.subheader("Email History")
emails = get_emails_by_booking_id(booking_id)

for email in emails:
    with st.expander(f"{email['received_at']}: {email['subject']}"):
        st.text(email['text_body'])
        if email.get('parsed_data'):
            st.json(email['parsed_data'])

# In admin view
st.subheader("Recent Emails")
tab1, tab2, tab3 = st.tabs(["All", "Processed", "Errors"])

with tab1:
    emails = get_recent_emails(50)
    st.dataframe(emails)

with tab2:
    emails = get_recent_emails(50, status='processed')
    st.dataframe(emails)

with tab3:
    emails = get_recent_emails(50, status='error')
    st.dataframe(emails)
```

---

## Benefits

### For Learning System

```python
# Learning system can now access full email content
from email_storage import get_inbound_email
from parsing_intelligence import submit_correction

# When staff corrects a booking
email = get_inbound_email(original_message_id)

# Re-parse with full context
corrected_parse = parse_booking_email(
    email['text_body'],
    email['subject']
)

# Compare and learn
submit_correction(
    booking_id,
    actual_dates=corrected_dates,
    source='staff_with_context'
)
```

### For Debugging

```python
# When a customer complains about wrong booking
email = get_inbound_email(message_id)

print("What customer wrote:")
print(email['text_body'])

print("\nWhat we parsed:")
print(email['parsed_data'])

print("\nWhat we booked:")
print(booking_details)
```

### For Customer Service

```python
# View complete email thread
emails = get_emails_by_booking_id(booking_id)

print("Email conversation:")
for email in emails:
    print(f"\n{email['received_at']}")
    print(f"From: {email['from_email']}")
    print(f"Subject: {email['subject']}")
    print(f"Body: {email['text_body'][:200]}...")
```

---

## Database Schema

```sql
CREATE TABLE inbound_emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE,
    from_email VARCHAR(255) NOT NULL,
    to_email VARCHAR(255),
    subject TEXT,
    text_body TEXT,                    -- Full email content
    html_body TEXT,                    -- HTML version
    headers TEXT,                      -- Raw headers
    attachments JSONB,                 -- Attachment metadata
    booking_id VARCHAR(255),           -- Link to booking
    parsed_data JSONB,                 -- What we extracted
    processing_status VARCHAR(50),     -- received/processed/error/duplicate
    error_message TEXT,                -- If processing failed
    received_at TIMESTAMP,             -- When received
    processed_at TIMESTAMP,            -- When processed
    club VARCHAR(100)                  -- Multi-tenant support
);
```

---

## Storage Considerations

### Data Retention

Emails are stored indefinitely by default. To implement retention:

```sql
-- Delete emails older than 90 days (keep recent for learning)
DELETE FROM inbound_emails
WHERE received_at < NOW() - INTERVAL '90 days'
AND processing_status != 'error';  -- Keep errors for review
```

### Privacy

- Email content is stored encrypted at rest (PostgreSQL level)
- No customer PII exposed in logs
- Can be deleted on GDPR request:

```sql
DELETE FROM inbound_emails
WHERE from_email = 'customer@example.com';
```

### Size Estimates

- Average email: ~2-5 KB
- 1,000 emails/month: ~5 MB/month
- 12 months: ~60 MB
- Minimal storage impact

---

## Monitoring

### Check Processing Status

```sql
-- Email processing overview
SELECT
    processing_status,
    COUNT(*) as count,
    MAX(received_at) as latest
FROM inbound_emails
GROUP BY processing_status;
```

### Find Parsing Errors

```sql
-- Emails that failed processing
SELECT
    id, from_email, subject, error_message, received_at
FROM inbound_emails
WHERE processing_status = 'error'
ORDER BY received_at DESC
LIMIT 20;
```

### Audit Trail

```sql
-- All emails for a customer
SELECT
    received_at,
    subject,
    booking_id,
    processing_status
FROM inbound_emails
WHERE from_email = 'customer@example.com'
ORDER BY received_at DESC;
```

---

## API Endpoints (Optional)

Add these to your Flask app:

```python
@app.route('/api/emails/<message_id>')
def get_email_api(message_id):
    """Get full email content"""
    from email_storage import get_inbound_email

    email = get_inbound_email(message_id)
    if not email:
        return jsonify({'error': 'Not found'}), 404

    return jsonify(email)


@app.route('/api/bookings/<booking_id>/emails')
def get_booking_emails_api(booking_id):
    """Get all emails for a booking"""
    from email_storage import get_emails_by_booking_id

    emails = get_emails_by_booking_id(booking_id)
    return jsonify(emails)


@app.route('/api/emails/recent')
def get_recent_emails_api():
    """Get recent emails"""
    from email_storage import get_recent_emails

    limit = request.args.get('limit', 50, type=int)
    status = request.args.get('status')

    emails = get_recent_emails(limit, status)
    return jsonify(emails)
```

---

## Testing

```bash
# Send test email
curl -X POST http://localhost:10000/webhook/inbound \
  -F "from=test@example.com" \
  -F "subject=Test Booking" \
  -F "text=Can we book for April 15? Party of 4." \
  -F "headers=Message-ID: <test123@mail.example.com>"

# Check it was saved
psql $DATABASE_URL -c "
  SELECT message_id, from_email, subject, processing_status
  FROM inbound_emails
  ORDER BY received_at DESC
  LIMIT 5;
"
```

---

## Summary

✅ **Migration**: `migrations/add_inbound_emails_table.sql`
✅ **Module**: `email_storage.py` (ready to import)
✅ **Integration**: 3 lines per webhook
✅ **Storage**: ~5KB per email
✅ **Benefits**: Learning data + debugging + audit trail

**Next Steps:**
1. Run migration SQL
2. Add 3 lines to webhook handlers (save → process → update)
3. Start collecting full email content
4. Use for learning system improvements

All email content now preserved for continuous improvement! 📧✨
