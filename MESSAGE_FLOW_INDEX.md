# Island Golf Club Booking System - Message Flow Documentation Index

## Document Overview

This directory contains comprehensive documentation of the Island Golf Club email-based booking system's complete message flow. Three documents provide different perspectives and detail levels.

---

## Files in This Documentation

### 1. MESSAGE_FLOW_QUICK_REFERENCE.md (545 lines, 18 KB)
**Best for**: Quick lookups, visual understanding, rapid reference

**Contents**:
- Webhook entry points overview
- Decision tree diagram for email processing
- Visual flow charts for new bookings and confirmations
- Database save points at a glance
- Key regex patterns and extraction rules
- Email template types and purposes
- Error handling summary
- Environment variables checklist
- API endpoints quick reference
- Logging key points
- Complete request/response cycle diagram
- Troubleshooting guide
- Quick test procedure

**When to use**: 
- Need a quick answer about how a part works
- Creating visual documentation
- Training new developers
- Understanding flow at 30,000 feet

---

### 2. MESSAGE_FLOW_ANALYSIS.md (1,137 lines, 36 KB)
**Best for**: Complete understanding, detailed implementation, debugging

**Contents**:
1. Architecture Summary (components and tech stack)
2. Webhook Entry Points (3 routes detailed)
3. Email Processing Flow (7 detailed phases)
4. Booking Creation Flow (with examples)
5. Email Response/Confirmation Flow (3 template types)
6. Reply-to-Confirm Mechanisms (3 methods)
7. Database Save Points (3 save points with SQL)
8. Email Templates Used (4 templates analyzed)
9. Configuration & Deployment (env vars, Render.yaml)
10. Complete Message Flow Summary (ASCII flowcharts)
11. Key Design Features (5 major features)
12. Testing & Monitoring (log points, health checks)

**When to use**:
- Learning the complete system
- Understanding edge cases
- Implementing features
- Debugging complex issues
- API design and data flow

---

### 3. MESSAGE_FLOW_INDEX.md (THIS FILE)
**Best for**: Navigation and understanding where to find information

---

## Quick Navigation Guide

### "I need to understand..."

**The email webhook entry point**
→ MESSAGE_FLOW_QUICK_REFERENCE.md § 1
→ MESSAGE_FLOW_ANALYSIS.md § 1 & § 2

**How emails are parsed**
→ MESSAGE_FLOW_QUICK_REFERENCE.md § 7 (patterns)
→ MESSAGE_FLOW_ANALYSIS.md § 3 (detailed flow)

**The complete new booking flow**
→ MESSAGE_FLOW_QUICK_REFERENCE.md § 3
→ MESSAGE_FLOW_ANALYSIS.md § 4

**Database operations and save points**
→ MESSAGE_FLOW_QUICK_REFERENCE.md § 6
→ MESSAGE_FLOW_ANALYSIS.md § 6

**How confirmations work**
→ MESSAGE_FLOW_QUICK_REFERENCE.md § 5
→ MESSAGE_FLOW_ANALYSIS.md § 5

**Email templates and formatting**
→ MESSAGE_FLOW_QUICK_REFERENCE.md § 8
→ MESSAGE_FLOW_ANALYSIS.md § 7

**Error handling and debugging**
→ MESSAGE_FLOW_QUICK_REFERENCE.md § 9 & 12
→ MESSAGE_FLOW_ANALYSIS.md § 2 (Phase 7)

**Configuration and deployment**
→ MESSAGE_FLOW_ANALYSIS.md § 8

**Complete visual flow**
→ MESSAGE_FLOW_QUICK_REFERENCE.md § 13
→ MESSAGE_FLOW_ANALYSIS.md § 2 & 9

---

## System Architecture at a Glance

```
CUSTOMER EMAIL
    ↓
bookings@theislandgolfclub.ie
    ↓
Email Relay
    ↓
SendGrid Inbound Parse
    ↓
POST /webhook/inbound
(Flask)
    ↓
┌─ NEW BOOKING BRANCH ─────┬─ CONFIRMATION BRANCH ────┐
│                          │                           │
│ Parse email              │ Detect confirmation       │
│ ↓                        │ ↓                         │
│ Extract: players, date,  │ Extract booking ID        │
│ time, phone              │ ↓                         │
│ ↓                        │ Query database            │
│ Generate booking ID      │ ↓                         │
│ ↓                        │ Verify confirmation intent│
│ INSERT booking           │ ↓                         │
│ Status: provisional      │ Extract tee time          │
│ ↓                        │ ↓                         │
│ Format email             │ UPDATE booking            │
│ (availability)           │ Status: Confirmed         │
│ ↓                        │ ↓                         │
│ Send via SendGrid        │ Format confirmation email │
│                          │ ↓                         │
│                          │ Send via SendGrid         │
└──────────────────────────┴───────────────────────────┘
    ↓
CUSTOMER RECEIVES EMAIL
    ↓
(If new booking)          (If confirmation)
Click "Reserve Now"       Booking now CONFIRMED
    ↓
CONFIRMATION EMAIL
    ↓
WEBHOOK TRIGGERED
    ↓
(Now confirmation branch above)
```

---

## Key File References

**Implementation Files**:
- `island_email_bot.py` (1,473 lines) - Main application
- `email_bot_webhook.py` (2,621 lines) - Enhanced version
- `schema.sql` - Database schema

**Main Functions**:
- `inbound_webhook()` - Main webhook handler
- `parse_booking_from_email()` - Email parsing
- `store_booking_in_db()` - Database save point 1
- `format_availability_email()` - Email template generation
- `is_confirmation_email()` - Confirmation detection
- `process_confirmation()` - Confirmation workflow
- `extract_booking_id()` - Booking ID extraction
- `extract_tee_time_from_email()` - Tee time parsing
- `update_booking_in_db()` - Database save point 2
- `send_email()` / `send_email_sendgrid()` - Email sending

---

## Data Flow Summary

```
INPUT (Inbound Email)
├─ from: "John Doe <john@example.com>"
├─ to: "bookings@theislandgolfclub.ie"
├─ subject: "4 players for 25 Nov at 10am"
├─ text: [full email body]
└─ headers: [with Message-ID]

PROCESSING
├─ Validation & parsing
├─ Data extraction (players, date, time, phone)
├─ Booking ID generation
└─ Confirmation detection

STORAGE (Database)
├─ Save Point 1: INSERT (status: provisional)
├─ Save Point 2: UPDATE (status: confirmed)
└─ Save Point 3: UPDATE (tee_time details)

OUTPUT (Response Email)
├─ Availability email OR
├─ Provisional email OR
├─ Confirmation email OR
└─ No availability email
```

---

## Three Email Processing Paths

### Path 1: New Booking → Availability Email
```
New email detected
    ↓
parse_booking_from_email()
    ↓
Save to DB (provisional)
    ↓
format_availability_email()
    ↓
Send email with "Reserve Now" buttons
    ↓
Customer receives options
```

### Path 2: New Booking → Provisional Email
```
New email detected
    ↓
parse_booking_from_email()
    ↓
No valid dates extracted
    ↓
Save to DB (provisional)
    ↓
format_provisional_email()
    ↓
Send email with reply-to-confirm workflow
    ↓
Customer replies with booking ID
```

### Path 3: Confirmation Email
```
Confirmation email detected
    ↓
extract_booking_id()
    ↓
Query booking from DB
    ↓
extract_tee_time_from_email()
    ↓
Update DB (confirmed)
    ↓
format_confirmation_email()
    ↓
Send confirmation to customer
```

---

## Database Operations Summary

### Three Save Points:

**Save Point 1: Initial Booking**
- Operation: `INSERT INTO bookings`
- Status: 'provisional'
- Fields: All booking details
- Indexed: booking_id, email, status, created_at, date

**Save Point 2: Confirmation Status**
- Operation: `UPDATE bookings`
- Status: 'provisional' → 'Confirmed'
- New fields: customer_confirmed_at, confirmation_message_id
- Trigger: updated_at auto-updates via trigger

**Save Point 3: Tee Time Details**
- Operation: `UPDATE bookings`
- New fields: date, tee_time
- Source: Extracted from confirmation email

---

## Email Templates Used

1. **Availability Email**
   - When: Valid dates extracted
   - Contains: Time slots, Reserve buttons
   - Users: First responders (initial booking)

2. **Provisional Email**
   - When: No valid dates extracted
   - Contains: Booking ID, confirm button
   - Users: Second attempt (fallback)

3. **Confirmation Email**
   - When: Booking confirmed
   - Contains: ✅ Green banner, all details
   - Users: Final confirmation recipients

4. **No Availability Email**
   - When: No tee times available
   - Contains: Contact info, apology
   - Users: Booking unavailable scenario

---

## Key Detection Mechanisms

### Confirmation Email Detection
```python
is_confirmation_email() checks:
├─ "confirm booking" in subject
├─ "re:" at start of subject
└─ booking_id + confirmation_keyword in body
```

### Booking ID Extraction
```python
extract_booking_id() matches:
├─ ISL-YYYYMMDD-XXXX (e.g., ISL-20251118-A3F7)
└─ BOOK-XXXXXXXX-XXXXXXXX
```

### Tee Time Extraction
```python
extract_tee_time_from_email() searches:
├─ Subject: "2025-11-25 at 10:00"
├─ Body: Date/time patterns
└─ Quoted text from email chains
```

---

## Webhook Endpoints

| Route | Method | Purpose | Returns |
|-------|--------|---------|---------|
| `/webhook/inbound` | POST | Email processing | {status, booking_id, db_stored, email_sent} |
| `/webhook/events` | POST | Event tracking | {status} |
| `/api/bookings` | GET | List bookings | {success, bookings[], count} |
| `/api/confirm/<id>` | POST | Manual confirm | {status, booking_id} |
| `/health` | GET | Health check | {status, service, database} |

---

## Configuration

### Required Environment Variables
```
SENDGRID_API_KEY=<your-key>
DATABASE_URL=postgresql://...
FROM_EMAIL=bookings@theislandgolfclub.ie
CLUB_BOOKING_EMAIL=bookings@theislandgolfclub.ie
```

### Optional Variables (with defaults)
```
FROM_NAME="The Island Golf Club"
PER_PLAYER_FEE=325.00
DEFAULT_COURSE_ID=theisland
TRACKING_EMAIL_PREFIX=theisland
PORT=10000
```

---

## Logging & Monitoring

### Key Log Messages to Monitor

```
✅ SUCCESS INDICATORS:
   - "WEBHOOK TRIGGERED [request_id]"
   - "Parsed Results: Players: X, Date: YYYY-MM-DD"
   - "BOOKING STORED - ID: ISL-..."
   - "Email sent: 200"
   - "BOOKING CONFIRMED SUCCESSFULLY"

❌ ERROR INDICATORS:
   - "Missing required field: from"
   - "Failed to store booking in database"
   - "Failed to send email"
   - "NO BOOKING ID FOUND"
```

---

## Testing the System

### Manual Test Procedure

1. Send booking email:
   - To: bookings@theislandgolfclub.ie
   - Subject: "4 players for 25 Nov 2025 at 10am"
   - Body: "Please book for John Doe, phone +353 1 234 5678"

2. Verify new booking:
   - Check logs: "WEBHOOK TRIGGERED"
   - Check logs: "BOOKING STORED - ID: ISL-..."
   - Check logs: "Email sent"
   - Check email inbox: Receive availability email

3. Send confirmation:
   - Click "Reserve Now" button in email
   - OR manually reply with "CONFIRM ISL-20251118-A3F7"

4. Verify confirmation:
   - Check logs: "CONFIRMATION EMAIL DETECTED"
   - Check logs: "BOOKING CONFIRMED SUCCESSFULLY"
   - Check database: status = 'Confirmed'
   - Check email inbox: Receive confirmation email

---

## Document Statistics

| Document | Lines | Size | Purpose |
|----------|-------|------|---------|
| MESSAGE_FLOW_QUICK_REFERENCE.md | 545 | 18 KB | Quick lookup, visual |
| MESSAGE_FLOW_ANALYSIS.md | 1,137 | 36 KB | Complete details |
| MESSAGE_FLOW_INDEX.md | - | - | Navigation guide |
| **TOTAL** | **1,682** | **54 KB** | **Complete documentation** |

---

## Related Files

### Source Code
- `/home/user/TheIsland_Beta/island_email_bot.py` - Main application
- `/home/user/TheIsland_Beta/email_bot_webhook.py` - Enhanced version
- `/home/user/TheIsland_Beta/app.py` - Flask entry point
- `/home/user/TheIsland_Beta/schema.sql` - Database schema

### Configuration
- `/home/user/TheIsland_Beta/render.yaml` - Deployment config
- `/home/user/TheIsland_Beta/Procfile` - Process file
- `/home/user/TheIsland_Beta/requirements.txt` - Dependencies

### Database
- `/home/user/TheIsland_Beta/DATABASE_SETUP.md` - DB troubleshooting

---

## Reading Recommendations

### For First-Time Understanding
1. Start with MESSAGE_FLOW_QUICK_REFERENCE.md § 2 (Decision Tree)
2. Read MESSAGE_FLOW_QUICK_REFERENCE.md § 3 (New Booking Flow)
3. Read MESSAGE_FLOW_QUICK_REFERENCE.md § 5 (Confirmation Flow)
4. Refer to MESSAGE_FLOW_ANALYSIS.md for details

### For Implementation
1. Read MESSAGE_FLOW_ANALYSIS.md § 2 (Full Processing Flow)
2. Check MESSAGE_FLOW_ANALYSIS.md § 3-6 (Detailed Flows)
3. Use MESSAGE_FLOW_QUICK_REFERENCE.md § 7 for patterns

### For Debugging
1. Check MESSAGE_FLOW_QUICK_REFERENCE.md § 12 (Troubleshooting)
2. Check MESSAGE_FLOW_QUICK_REFERENCE.md § 12 (Logging Points)
3. Reference MESSAGE_FLOW_ANALYSIS.md § 2 Phase 7 (Error Handling)

---

## Version Information

- **System**: Island Golf Club Email Booking System
- **Main App**: island_email_bot.py (1,473 lines)
- **Enhanced App**: email_bot_webhook.py (2,621 lines)
- **Database**: PostgreSQL with connection pooling
- **Email Service**: SendGrid
- **Web Framework**: Flask 3.0.0
- **Deployment**: Render.com
- **Documentation Version**: 1.0
- **Last Updated**: 2025-11-18

---

## Quick Links within This Repo

- Main application: `/home/user/TheIsland_Beta/island_email_bot.py`
- Database schema: `/home/user/TheIsland_Beta/schema.sql`
- Webhook definition (line 1144): `inbound_webhook()`
- Confirmation detection (line 1124): `is_confirmation_email()`
- Confirmation processing (line 1371): `process_confirmation()`
- Email parsing (line 838): `parse_booking_from_email()`
- Database save (line 1064): `store_booking_in_db()`

