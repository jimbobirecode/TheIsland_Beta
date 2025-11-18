# Island Golf Club Booking System - Quick Reference Guide

## 1. WEBHOOK ENTRY POINTS

```
INCOMING EMAIL
     ↓
bookings@theislandgolfclub.ie
     ↓
Email Relay (Email Forwarding)
     ↓
SendGrid Inbound Parse Webhook
     ↓
POST /webhook/inbound
(Flask receives: from, to, subject, text, html, headers)
```

---

## 2. EMAIL PROCESSING DECISION TREE

```
                    EMAIL RECEIVED
                          ↓
                   ┌──────────────────┐
                   │ VALIDATE EMAIL   │
                   └────────┬─────────┘
                            ↓
                   ┌──────────────────┐
              ┌────┤ Extract Message  │
              │    │ ID for dedup     │
              │    └──────────────────┘
              │
         ┌────┴────────────────────────────────┐
         ↓                                      ↓
    Is Duplicate?                      Is Confirmation?
         │                                     │
         ├─ YES → Skip (200 OK)           YES ├─→ CONFIRMATION FLOW
         │                                     │
         └─ NO → Continue                  NO ├─→ NEW BOOKING FLOW
                     ↓
          ┌──────────────────────┐
          │ is_confirmation_     │
          │   email()?           │
          │ ✓ "CONFIRM BOOKING"  │
          │ ✓ "Re:" prefix       │
          │ ✓ ID + keywords      │
          └──────────────────────┘
```

---

## 3. NEW BOOKING REQUEST FLOW

```
Customer: "Hi, I'd like 4 players for 25 Nov at 10am"
                    ↓
        parse_booking_from_email()
                    ↓
    ┌─────────────────────────────┐
    │ EXTRACTED DATA:             │
    │ ├─ Players: 4               │
    │ ├─ Date: 2025-11-25         │
    │ ├─ Time: 10:00 AM           │
    │ ├─ Phone: +353 1 234 5678    │
    │ └─ Name: John Doe           │
    └──────────────┬──────────────┘
                   ↓
        Generate Booking ID
        ISL-20251118-A3F7
                   ↓
      ┌────────────────────────┐
      │ DATABASE SAVE POINT 1  │
      │ ├─ Insert new booking  │
      │ ├─ Status: provisional │
      │ ├─ total_fee = 4 × €325│
      │ └─ created_at = NOW()  │
      └────────────┬───────────┘
                   ↓
        Format Email Response
                   ↓
    ┌─────────────────────────────┐
    │ SEND AVAILABILITY EMAIL:    │
    │ ├─ Date: 2025-11-25         │
    │ ├─ Times: 08:00, 10:00,     │
    │ │          12:00, 14:00      │
    │ ├─ Buttons: "Reserve Now"   │
    │ │           (mailto links)   │
    │ └─ To: john@example.com     │
    └──────────────┬──────────────┘
                   ↓
        Customer receives email
                   ↓
        Customer clicks "Reserve Now"
```

---

## 4. "RESERVE NOW" BUTTON STRUCTURE

```
<a href="mailto:bookings@theislandgolfclub.ie
          ?cc=theisland@bookings.teemail.io
          &subject=CONFIRM BOOKING - 2025-11-25 at 10:00
          &body=CONFIRM BOOKING
                Booking Details:
                - Date: 2025-11-25
                - Time: 10:00
                - Players: 4
                - Green Fee: €325 per player
                - Total: €1,300
                Guest Email: john@example.com
                Booking ID: ISL-20251118-A3F7">
    Reserve Now
</a>

User clicks → Email client opens with pre-filled fields
              → User clicks Send (or optionally edits)
              → Email sent to club with tracking
```

---

## 5. CONFIRMATION EMAIL FLOW

```
Customer sends confirmation
(via pre-filled button or manual reply)
        ↓
Email received by webhook
        ↓
is_confirmation_email() checks:
├─ Subject: "CONFIRM BOOKING"?
├─ Subject: Starts with "Re:"?
└─ Body: Booking ID + confirmation keywords?
        ↓
    extract_booking_id()
    Returns: ISL-20251118-A3F7
        ↓
┌─────────────────────────────┐
│ DATABASE QUERY:             │
│ SELECT * FROM bookings      │
│ WHERE id = 'ISL-...'        │
│                             │
│ Returns: Current booking    │
│ Status check: provisional? │
└──────────────┬──────────────┘
               ↓
    Verify confirmation intent
    ├─ Has keywords: yes/confirm/ok?
    └─ If NO → Return 'reply_received'
               (don't confirm yet)
        ↓
    extract_tee_time_from_email()
    ├─ Subject: "at 10:00"?
    ├─ Body: "2025-11-25"?
    └─ Returns: (date, time)
        ↓
  ┌──────────────────────────────┐
  │ DATABASE SAVE POINT 2        │
  │ UPDATE bookings              │
  │ SET status = 'Confirmed'     │
  │ SET date = '2025-11-25'      │
  │ SET tee_time = '10:00'       │
  │ SET customer_confirmed_at    │
  │     = NOW()                  │
  │ WHERE id = 'ISL-...'         │
  └──────────────┬───────────────┘
                 ↓
    format_confirmation_email()
    └─ "✅ Booking Confirmed!"
       Date, time, players, fee
       Arrival instructions
       Contact info
                 ↓
    send_email() via SendGrid
                 ↓
    Return: {
        'status': 'confirmed',
        'booking_id': 'ISL-...',
        'tee_date': '2025-11-25',
        'tee_time': '10:00'
    }
```

---

## 6. DATABASE SAVE POINTS SUMMARY

### Save Point 1: New Booking Created
```sql
INSERT INTO bookings (
    id, name, email, phone, num_players,
    preferred_date, preferred_time, alternate_date,
    special_requests, status, total_fee,
    created_at, course_id, raw_email_data
)
Status: 'provisional'
Timestamp: created_at = NOW()
Trigger: Auto-update trigger for updated_at
```

### Save Point 2: Booking Confirmed
```sql
UPDATE bookings
SET status = 'Confirmed',
    customer_confirmed_at = NOW(),
    confirmation_message_id = '...',
    updated_at = NOW()
WHERE id = 'ISL-...'
Status: 'provisional' → 'Confirmed'
```

### Save Point 3: Tee Time Updated
```sql
UPDATE bookings
SET date = '2025-11-25',
    tee_time = '10:00',
    updated_at = NOW()
WHERE booking_id = 'ISL-...'
Extracted from confirmation email
```

---

## 7. KEY PATTERNS & REGEX

### Booking ID Patterns
```python
# Extract booking ID from email
Pattern: r'ISL-\d{8}-[A-F0-9]{4}'
         r'BOOK-\d{8}-[A-F0-9]{8}'

Example: ISL-20251118-A3F7
         BOOK-20251118-A3F7BCDE
```

### Confirmation Keywords
```python
['confirm', 'yes', 'book', 'proceed', 
 'accept', 'ok', 'okay', 'sure', 'sounds good']
```

### Date Patterns
```
"on 25/11/2025"           → 2025-11-25
"25 Nov 2025"             → 2025-11-25
"2025-11-25"              → 2025-11-25
"tomorrow"                → TODAY + 1 day
"next Friday"             → Next Friday date
```

### Time Patterns
```
"10:00 AM"                → 10:00
"14:30"                   → 14:30
"morning"                 → 09:00 (9 AM)
"afternoon"               → 14:00 (2 PM)
"evening"                 → 17:00 (5 PM)
```

### Player Count Patterns
```
"4 players"               → 4
"party of 3"              → 3
"foursome"                → 4
"twosome"                 → 2
"threesome"               → 3
[No match]                → 4 (default)
```

---

## 8. EMAIL TEMPLATES AT A GLANCE

### Template 1: Availability Email
**When**: Dates provided and valid
**Shows**: Available tee times with "Reserve Now" buttons
**Key sections**:
- VLUB logo header
- Booking details box
- Date/time table
- How to confirm (3 steps)

### Template 2: Provisional Email
**When**: No valid dates extracted
**Shows**: Booking received, reply-to-confirm workflow
**Key sections**:
- Booking ID prominently displayed
- "Confirm Now" button (pre-filled)
- Reply instructions: "CONFIRM ISL-..."

### Template 3: Confirmation Email
**When**: Booking confirmed
**Shows**: Final confirmation details
**Key sections**:
- ✅ Green success banner
- Booking details table
- Arrival instructions (30 min early)
- Payment info

### Template 4: No Availability Email
**When**: No tee times available
**Shows**: Regret message + contact info
**Key sections**:
- ⚠️ No availability notice
- "Please contact us"
- Phone + email

---

## 9. ERROR HANDLING QUICK GUIDE

```
WEBHOOK REQUEST
    ↓
Missing 'from' email? → Return 400 Bad Request
Empty body/subject? → Return 400 Bad Request
Invalid email format? → Return 400 Bad Request
    ↓
Duplicate Message-ID? → Skip (return 200 OK)
    ↓
Database unavailable? → Log error, return 500
SendGrid API error? → Log error, return 500
    ↓
Booking not found? → Return 404 Not Found
No booking ID in confirmation? → Log, return 200
Already confirmed? → Return 200 OK (idempotent)
    ↓
SUCCESS → Return 200 OK with status details
```

---

## 10. ENVIRONMENT VARIABLES CHECKLIST

```
REQUIRED:
✓ SENDGRID_API_KEY         - SendGrid API key
✓ DATABASE_URL             - PostgreSQL connection
✓ FROM_EMAIL               - Sender email address
✓ CLUB_BOOKING_EMAIL       - Club booking email

OPTIONAL (with defaults):
○ FROM_NAME                - Default: "The Island Golf Club"
○ PER_PLAYER_FEE           - Default: 325.00
○ DEFAULT_COURSE_ID        - Default: "theisland"
○ TRACKING_EMAIL_PREFIX    - Default: "theisland"
○ PORT                     - Default: 10000
```

---

## 11. API ENDPOINTS SUMMARY

```
POST /webhook/inbound
├─ Inbound email processing
├─ Request: form data (from, subject, text, html, headers)
└─ Response: {status, booking_id, database_stored, email_sent}

POST /webhook/events
├─ SendGrid event tracking
└─ Request: JSON array of events

GET /api/bookings
├─ List all bookings
└─ Response: {success, bookings[], count}

POST /api/confirm/<booking_id>
├─ Manual confirmation endpoint
└─ Response: {status, booking_id}

GET /health
├─ Health check
└─ Response: {status, service, database, features}
```

---

## 12. LOGGING KEY POINTS

Monitor logs for these messages:

```
✅ "WEBHOOK TRIGGERED [request_id]"
   ↓ Email received and processing starts

✅ "Parsed Results: Players: 4, Date: 2025-11-25"
   ↓ Email parsed successfully

✅ "BOOKING STORED - ID: ISL-20251118-A3F7"
   ↓ Database save point 1 complete

✅ "Email sent to john@example.com: 200"
   ↓ Response email sent successfully

✅ "CONFIRMATION EMAIL DETECTED"
   ↓ Customer confirmation received

✅ "BOOKING CONFIRMED SUCCESSFULLY"
   ↓ Database save point 2 complete

❌ "Failed to store booking in database"
   ↓ Database connection or insert error

❌ "Failed to send email"
   ↓ SendGrid API error
```

---

## 13. COMPLETE REQUEST→RESPONSE CYCLE

```
┌─────────────────────────────────────────────────────────┐
│ CYCLE 1: INITIAL REQUEST                                │
├─────────────────────────────────────────────────────────┤
│ REQUEST RECEIVED                                        │
│ From: john@example.com                                  │
│ Subject: 4 players for 25 Nov 10am                       │
│ Body: [Full email content]                              │
│                                                          │
│ PROCESSING                                              │
│ 1. Parse email → {players:4, date:2025-11-25, ...}    │
│ 2. Generate ID → ISL-20251118-A3F7                     │
│ 3. Create booking_data dict                            │
│ 4. INSERT into bookings (status: provisional)          │
│ 5. Generate HTML email with Reserve Now buttons        │
│ 6. SendGrid sends response email                       │
│                                                          │
│ RESPONSE SENT                                           │
│ To: john@example.com                                    │
│ Subject: Available Tee Times at The Island Golf Club   │
│ Body: HTML with 5 time slots + Reserve Now buttons    │
│                                                          │
│ STORAGE                                                 │
│ Database: booking_id=ISL-20251118-A3F7, status=prov... │
│ Email: response logged with tracking_id                │
└─────────────────────────────────────────────────────────┘
              [Customer receives email]
                       ↓
          [Customer clicks "Reserve Now"]
                       ↓
┌─────────────────────────────────────────────────────────┐
│ CYCLE 2: CONFIRMATION                                   │
├─────────────────────────────────────────────────────────┤
│ REQUEST RECEIVED                                        │
│ From: john@example.com                                  │
│ Subject: CONFIRM BOOKING - 2025-11-25 at 10:00        │
│ Body: [Pre-filled with booking details]                │
│       Booking ID: ISL-20251118-A3F7                    │
│                                                          │
│ PROCESSING                                              │
│ 1. is_confirmation_email() → YES                       │
│ 2. extract_booking_id() → ISL-20251118-A3F7            │
│ 3. Check for duplicates (Message-ID)                   │
│ 4. SELECT booking from DB → found, status=provisional  │
│ 5. extract_tee_time_from_email() → (2025-11-25, 10:00)│
│ 6. UPDATE booking: status=Confirmed, date, tee_time   │
│ 7. Generate confirmation email                        │
│ 8. SendGrid sends confirmation                        │
│                                                          │
│ RESPONSE SENT                                           │
│ To: john@example.com                                    │
│ Subject: ✅ Your Island Golf Club Booking is Confirmed │
│ Body: HTML with confirmed details + instructions      │
│                                                          │
│ STORAGE                                                 │
│ Database: booking_id=ISL-20251118-A3F7, status=Conf... │
│          customer_confirmed_at=NOW()                   │
│          date=2025-11-25, tee_time=10:00              │
└─────────────────────────────────────────────────────────┘
            [Booking is now CONFIRMED]
                     ↓
         [Customer arrives 30 min before]
                     ↓
              [READY TO TEE OFF]
```

---

## 14. TROUBLESHOOTING QUICK GUIDE

| Issue | Cause | Solution |
|-------|-------|----------|
| Webhook returns 400 | Missing email from field | Check Email Relay configuration |
| No email sent | SendGrid API key missing | Set SENDGRID_API_KEY env var |
| Database error | CONNECTION_TIMEOUT | Check DATABASE_URL, PostgreSQL status |
| Booking not found | ID doesn't exist | Verify booking_id format (ISL-...) |
| Confirmation ignored | Not detected as confirmation | Check confirmation keywords in body |
| Duplicate booking | Message-ID not tracked | Enable Message-ID extraction |

---

## 15. KEY FILE LOCATIONS

```
/home/user/TheIsland_Beta/
├── island_email_bot.py (1,473 lines)
│   └─ Main booking system
├── email_bot_webhook.py (2,621 lines)
│   └─ Enhanced with alternative dates
├── schema.sql
│   └─ Database schema
├── app.py
│   └─ Flask entry point
├── requirements.txt
├── render.yaml
│   └─ Deployment config
├── MESSAGE_FLOW_ANALYSIS.md (this file)
└── MESSAGE_FLOW_QUICK_REFERENCE.md
```

---

## QUICK TEST FLOW

To manually test the system:

1. Send email to: bookings@theislandgolfclub.ie
   Subject: "4 players for 25 Nov 2025 at 10am"
   Body: "Please book for John Doe, phone +353 1 234 5678"
   
2. Check logs for:
   ✓ "WEBHOOK TRIGGERED"
   ✓ "Booking stored: ISL-..."
   ✓ "Email sent"
   
3. Receive email with available times
   
4. Click "Reserve Now" for 10:00
   
5. Check logs for:
   ✓ "CONFIRMATION DETECTED"
   ✓ "BOOKING CONFIRMED"
   
6. Verify in PostgreSQL:
   ```sql
   SELECT id, status, date, tee_time, customer_confirmed_at
   FROM bookings
   WHERE id = 'ISL-...';
   ```
   Should show: status='Confirmed'

