# Island Golf Club Booking System - Complete Message Flow Analysis

## Overview
The Island Golf Club uses a sophisticated email-based booking system that processes incoming emails, parses booking requests, stores them in PostgreSQL, and manages confirmations through a reply-to-confirm workflow.

---

## Architecture Summary

### Core Components
1. **Main Application**: `island_email_bot.py` (1,473 lines) - Base booking system
2. **Enhanced Application**: `email_bot_webhook.py` (2,621 lines) - Extended version with alternative date checking
3. **Database**: PostgreSQL with connection pooling
4. **Email Service**: SendGrid for outbound emails
5. **Entry Point**: Flask web server (`app.py`)
6. **Deployment**: Render.com with Gunicorn

### Technology Stack
- Flask 3.0.0 - Web framework
- SendGrid 6.11.0 - Email delivery
- psycopg2 3.9 - PostgreSQL driver
- python-dateutil - Date parsing

---

## 1. WEBHOOK ENTRY POINTS (Inbound Email Handlers)

### Primary Webhook Routes

#### Route 1: POST `/webhook/inbound`
- **Purpose**: Handle incoming emails from Email Relay (bookings.teemail.io)
- **Handler**: `inbound_webhook()` in `island_email_bot.py`
- **Source**: Email Relay forwards all emails sent to `theisland@bookings.teemail.io`
- **Request Format**: Form data from SendGrid Inbound Parse webhook

**Request Data Received:**
```
POST /webhook/inbound
Content-Type: application/x-www-form-urlencoded

Fields:
- from: "Customer Name <customer@email.com>"
- to: "theisland@bookings.teemail.io"
- subject: "Request for tee times"
- text: "[email body in plain text]"
- html: "[email body in HTML]"
- headers: "[raw email headers]"
```

#### Route 2: POST `/webhook/events`
- **Purpose**: Track email events (opens, clicks, bounces)
- **Handler**: `event_webhook()` in `island_email_bot.py`
- **Data**: SendGrid event data for analytics

#### Route 3: Enhanced Webhook Handler
- **Location**: `email_bot_webhook.py`
- **Route**: POST `/webhook/inbound`
- **Handler**: `handle_inbound_email()`
- **Enhancements**: 
  - Automatic alternative date checking
  - Duplicate detection via Message-ID
  - Enhanced confirmation detection

---

## 2. EMAIL PROCESSING FLOW

### Step-by-Step: From Initial Email Receipt to Response

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: INCOMING EMAIL RECEIPT                                 │
└─────────────────────────────────────────────────────────────────┘

1. Customer sends email to:
   bookings@theislandgolfclub.ie (appears in mailto links)
   OR
   theisland@bookings.teemail.io (tracking email)

2. Email Relay receives and validates
   └─> Extracts headers, body, metadata

3. SendGrid Inbound Parse webhook triggers
   └─> POST /webhook/inbound with form data

4. Flask application receives request
   └─> Request ID generated for tracking

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: EMAIL VALIDATION & PARSING                             │
└─────────────────────────────────────────────────────────────────┘

5. Request validation:
   ✓ Check 'from' field exists
   ✓ Check 'subject' or 'text' not empty
   └─> Return 400 if validation fails

6. Extract clean email address:
   Input: "John Doe <john@example.com>"
   Output: sender_email = "john@example.com"
           sender_name = "John Doe"
   
   OR generate name from email:
   Input: "john.doe@example.com"
   Output: sender_name = "John Doe"

7. Duplicate check (email_bot_webhook.py):
   ✓ Extract Message-ID from email headers
   └─> Skip if already processed

8. Detection check:
   ✓ is_confirmation_email()? YES → Go to Phase 5
   ✓ is_confirmation_email()? NO  → Go to Step 9

9. Parse booking details from email:
   └─> parse_booking_from_email(text_body, subject)

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: BOOKING DATA EXTRACTION                                │
└─────────────────────────────────────────────────────────────────┘

10. parse_booking_from_email() extracts:

    a) NUMBER OF PLAYERS
       Patterns:
       - "4 players", "party of 4", "foursome"
       - "2 people", "twosome"
       - "3 guests", "threesome"
       Default: 4 players
       
    b) PHONE NUMBER
       Patterns:
       - "Phone: +353 1 234 5678"
       - Various formats with digits/hyphens
       Validation: Min 7 digits
       
    c) DATES
       Patterns (ordered by preference):
       - "on 25/11/2025", "for 25 Nov 2025"
       - "2025-11-25", "25-11-2025"
       - Relative: "tomorrow", "next Monday"
       Multiple dates: primary + alternate
       Validation: Future dates only
       
    d) TIME
       Patterns:
       - "10:00 AM", "14:30", "at 10am"
       - Keywords: "morning", "afternoon", "evening"
       Mapping:
       ├─ morning → 9:00 AM (or 8:00 early / 11:00 late)
       ├─ afternoon → 2:00 PM
       └─ evening → 5:00 PM
       
    Returns: {
        'num_players': int,
        'preferred_date': 'YYYY-MM-DD',
        'preferred_time': 'HH:MM AM/PM',
        'phone': str,
        'alternate_date': 'YYYY-MM-DD' or None
    }

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: BOOKING CREATION & DATABASE SAVE                       │
└─────────────────────────────────────────────────────────────────┘

11. Generate Booking ID:
    Format: ISL-YYYYMMDD-XXXX
    Example: ISL-20251118-A3F7
    
    Generation:
    - Current date: 20251118
    - Hash of: sender_email + timestamp
    - Take first 4 hex chars
    - Convert to uppercase

12. Create booking_data dictionary:
    {
        'id': 'ISL-20251118-A3F7',
        'name': 'John Doe',
        'email': 'john@example.com',
        'phone': '+353 1 234 5678',
        'num_players': 4,
        'preferred_date': '2025-11-25',
        'preferred_time': '10:00 AM',
        'alternate_date': '2025-11-26',
        'special_requests': '[email body or subject]',
        'status': 'provisional',
        'course_id': 'theisland'
    }

13. Store in PostgreSQL:
    └─> store_booking_in_db(booking_data)
    
    SQL Operation:
    INSERT INTO bookings (
        id, name, email, phone, num_players,
        preferred_date, preferred_time, alternate_date,
        special_requests, status, total_fee, created_at,
        course_id, raw_email_data
    ) VALUES (...)
    
    Database Save Points:
    ✓ Primary: id = 'ISL-20251118-A3F7'
    ✓ Indexed: guest_email, status, created_at, date
    ✓ Updated: ON CONFLICT (id) DO UPDATE
    ✓ Timestamp: created_at (NOW()), updated_at (trigger)
    ✓ Raw data: raw_email_data (JSONB column)

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 5: EMAIL RESPONSE GENERATION & SENDING                    │
└─────────────────────────────────────────────────────────────────┘

14. Prepare availability response:
    
    If dates provided:
    └─> format_availability_email(results, player_count, ...)
        └─> Generates table with tee times
        └─> Creates "Reserve Now" buttons
        
    If no valid dates:
    └─> format_provisional_email(booking_data)
        └─> Shows booking request received
        └─> Includes reply-to-confirm workflow

15. Build "Reserve Now" buttons:
    └─> build_booking_link(date, time, players, email, booking_id)
    
    Generates mailto link:
    mailto:bookings@theislandgolfclub.ie
    ?cc=theisland@bookings.teemail.io
    &subject=CONFIRM BOOKING - 2025-11-25 at 10:00
    &body=CONFIRM BOOKING
          Booking Details:
          - Date: 2025-11-25
          - Time: 10:00
          - Players: 4
          - Green Fee: €325 per player
          - Total: €1,300
          - Guest Email: john@example.com
          - Booking ID: ISL-20251118-A3F7

16. Send email via SendGrid:
    └─> send_email(to_email, subject, html_content)
    
    Email Template: The Island branded HTML with:
    ✓ VLUB logo in header
    ✓ Navy blue (#24388f) + royal blue (#1923c2) branding
    ✓ Gold accent (#D4AF37) highlights
    ✓ Championship links course description
    ✓ Pre-filled confirmation instructions
    
    Response includes:
    - Booking confirmation email OR
    - Availability with time slots OR
    - No availability notice

17. Log response:
    └─> WEBHOOK_COMPLETE with status
    
    Return to Email Relay:
    {
        'status': 'success',
        'booking_id': 'ISL-20251118-A3F7',
        'database_stored': true,
        'email_sent': true,
        'from': 'john@example.com',
        'subject': 'Available Tee Times at The Island Golf Club',
        'request_id': 'xxxxxxxx'
    }

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 5 ALTERNATIVE: CONFIRMATION EMAIL DETECTION               │
└─────────────────────────────────────────────────────────────────┘

5A. is_confirmation_email() checks:
    ✓ Subject contains "CONFIRM BOOKING"
    ✓ Subject contains "CONFIRM GROUP BOOKING"
    ✓ Subject starts with "Re:" (reply detection)
    ✓ Body contains booking ref (ISL-XXXXXX-XXXX) + confirmation keywords
    
    Confirmation keywords:
    ['confirm', 'yes', 'book', 'proceed', 'accept', 'ok', 'okay', 'sure', 'sounds good']

5B. If confirmation detected:
    └─> process_confirmation(from_email, subject, body, message_id)

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 6: BOOKING CONFIRMATION FLOW                              │
└─────────────────────────────────────────────────────────────────┘

18. Confirmation email received:
    Example: Customer clicks "Reserve Now" button or replies manually
    
    Email received:
    From: john@example.com
    Subject: Re: CONFIRM BOOKING - 2025-11-25 at 10:00
    Body: CONFIRM ISL-20251118-A3F7
    OR
    Body: Yes, please confirm this booking

19. Extract booking ID from email:
    └─> extract_booking_id(subject, body)
    
    Pattern: BOOK-XXXXXXXX-XXXXXXXX or ISL-XXXXXX-XXXX
    Returns: 'ISL-20251118-A3F7' or None

20. Retrieve booking from database:
    └─> get_booking_by_id(booking_id)
    
    SQL:
    SELECT * FROM bookings
    WHERE booking_id = 'ISL-20251118-A3F7'
    
    Returns booking record with:
    - id, name, email, phone, num_players
    - preferred_date, preferred_time, alternate_date
    - status, created_at, updated_at
    - raw_email_data

21. Check booking status:
    ✓ If status = 'confirmed' → Return already_confirmed
    ✓ If status = 'provisional' → Proceed to confirmation
    ✓ If not found → Return booking_not_found

22. Verify confirmation intent:
    └─> Search body for confirmation keywords
    └─> Return 'reply_received' if no keywords

23. Extract tee time from email:
    └─> extract_tee_time_from_email(subject, body)
    
    Patterns searched (in order):
    a) Subject: "CONFIRM BOOKING - 2025-11-25 at 10:00"
    b) Subject: "2025-11-25 @ 10:00"
    c) Subject: "2025/11/25 at 10:00"
    d) Subject: "25-11-2025 at 10:00"
    e) Body: Similar date/time patterns
    f) Body: Email quoted text parsing

24. Update booking status in database:
    └─> update_booking_in_db(booking_id, updates)
    
    SQL:
    UPDATE bookings
    SET status = 'Confirmed',
        date = '2025-11-25',
        tee_time = '10:00',
        customer_confirmed_at = NOW(),
        confirmation_message_id = '[message-id]',
        note = 'Confirmed via email',
        updated_at = NOW()
    WHERE booking_id = 'ISL-20251118-A3F7'
    
    Database Save Point:
    ✓ Status updated: 'provisional' → 'confirmed'
    ✓ Timestamp: customer_confirmed_at = NOW()
    ✓ Tracking: confirmation_message_id stored
    ✓ Updated_at trigger fires automatically

25. Send confirmation email to customer:
    └─> format_confirmation_email(booking_data)
    
    Email contents:
    - Green success banner: "✅ Booking Confirmed!"
    - Booking ID, date, time, players
    - Total fee calculation
    - Arrival instructions (30 mins before)
    - Payment info (cash/credit cards)
    - Contact club office link

26. Return confirmation response:
    {
        'status': 'confirmed',
        'booking_id': 'ISL-20251118-A3F7',
        'tee_date': '2025-11-25',
        'tee_time': '10:00'
    }

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 7: ERROR HANDLING & LOGGING                               │
└─────────────────────────────────────────────────────────────────┘

27. Error scenarios handled:
    ✓ Missing 'from' email → Return 400
    ✓ Empty body/subject → Return 400
    ✓ Duplicate message → Skip silently (return 200)
    ✓ Invalid email format → Return 400
    ✓ DB connection failure → Log error, return error response
    ✓ SendGrid API error → Log error, return error response
    ✓ Booking not found → Return 404
    ✓ No booking ID in confirmation → Log, return 200
    ✓ Already confirmed → Return 200 (idempotent)

28. Comprehensive logging:
    ├─ Request ID generation (tracking)
    ├─ Email details logged (from, to, subject, length)
    ├─ Parsing results logged (players, dates, time, phone)
    ├─ Database operations logged (success/failure, row count)
    ├─ Email send status logged (SendGrid status code)
    ├─ Confirmation process logged (step-by-step)
    └─ Errors logged with traceback
    
    Log format:
    [timestamp] [LEVEL] [message]
    Example:
    2025-11-18 15:30:45 [INFO] ✅ WEBHOOK COMPLETE [request_id]
    2025-11-18 15:30:45 [INFO] Booking ID: ISL-20251118-A3F7
    2025-11-18 15:30:45 [INFO] Database: ✅
    2025-11-18 15:30:45 [INFO] Email: ✅
```

---

## 3. BOOKING CREATION FLOW - DETAILED

### New Booking Request Processing

**Trigger**: Customer emails `bookings@theislandgolfclub.ie`

**Input Data Extracted**:
```
FROM HEADER:    "John Smith <john.smith@gmail.com>"
TO HEADER:      "bookings@theislandgolfclub.ie"
SUBJECT:        "Tee time request for 25th Nov, 4 players, 10am"
TEXT BODY:      "Hi, I'd like to book 4 players for 25 Nov 2025 at 10am.
                 My phone is +353 1 234 5678. 
                 Please let me know available tee times.
                 Regards, John"
```

**Parsing Results**:
```python
parsed_data = {
    'num_players': 4,
    'preferred_date': '2025-11-25',
    'preferred_time': '10:00 AM',
    'phone': '+353 1 234 5678',
    'alternate_date': None
}
```

**Booking Record Created**:
```python
booking_data = {
    'id': 'ISL-20251118-7F2A',  # Generated
    'name': 'John Smith',        # Extracted from email
    'email': 'john.smith@gmail.com',
    'phone': '+353 1 234 5678',
    'num_players': 4,
    'preferred_date': '2025-11-25',
    'preferred_time': '10:00 AM',
    'alternate_date': None,
    'special_requests': 'Hi, I\'d like to book...',
    'status': 'provisional',
    'course_id': 'theisland'
}
```

**Database Insert**:
```sql
INSERT INTO bookings (
    id, name, email, phone, num_players,
    preferred_date, preferred_time, alternate_date,
    special_requests, status, total_fee, created_at,
    course_id, raw_email_data
) VALUES (
    'ISL-20251118-7F2A',
    'John Smith',
    'john.smith@gmail.com',
    '+353 1 234 5678',
    4,
    '2025-11-25',
    '10:00 AM',
    NULL,
    'Hi, I\'d like to book...',
    'provisional',
    1300.00,
    NOW(),
    'theisland',
    '{"id": "ISL-20251118-7F2A", "name": "John Smith", ...}'
)
```

**Response Email Sent**:
```
To: john.smith@gmail.com
Subject: Available Tee Times at The Island Golf Club

Email contains:
- Thank you message
- Booking details box (Players: 4, Fee: €325pp, Status: ✓ Available Times Found)
- Date: 2025-11-25
  - Time slots: 08:00, 10:00, 12:00, 14:00, 16:00
  - Each with "Reserve Now" button
- Alternative dates info (if applicable)
- How to confirm instructions
- Championship links description
- Contact information
- Footer with club details
```

---

## 4. EMAIL RESPONSE/CONFIRMATION FLOW

### Initial Response Template

**Three response types are generated**:

#### Type 1: Availability Email (Recommended)
**Condition**: Dates provided and valid
**Template**: `format_availability_email()`
**Contents**:
- Header with VLUB logo + "Visitor Tee Time Booking"
- Thank you message
- Booking details box (players, fee, status)
- Alternative dates notice (if applicable)
- Grouped by date tables:
  - Date header with badge
  - Tee times table with availability & fee
  - "Reserve Now" buttons
- Championship links description
- How to confirm section:
  * Step 1: Click "Reserve Now"
  * Step 2: Email client opens with pre-filled booking
  * Step 3: Send the email - confirmed within 30 minutes
- Contact phone number
- Footer with club address, phone, email

#### Type 2: Provisional Booking Email (Fallback)
**Condition**: No valid dates extracted
**Template**: `format_provisional_email()`
**Contents**:
- Header: "⏳ Booking Request Received"
- Dear [Name] message
- Booking request details box
  - Booking ID
  - Requested date
  - Alternate date (if found)
  - Requested time
  - Number of players
  - Estimated fee
- How to confirm section:
  * Reply with: "CONFIRM [BOOKING-ID]"
  * OR click "Confirm Booking Now" button
- Confirmation button (pre-filled)
- "Need to make changes?" tip
- Footer

#### Type 3: No Availability Email
**Condition**: No tee times available
**Template**: `format_no_availability_email()`
**Contents**:
- Header: "⚠️ No Availability Found"
- Requested dates show as unavailable
- Alternative dates checked message
- "Please Contact Us" box
- Email and phone numbers
- Footer

### "Reserve Now" Button Creation

**Function**: `build_booking_link()`

**Output**: mailto hyperlink

```
href="mailto:bookings@theislandgolfclub.ie
      ?cc=theisland@bookings.teemail.io
      &subject=CONFIRM BOOKING - 2025-11-25 at 10:00
      &body=CONFIRM BOOKING
            
            Booking Details:
            - Date: 2025-11-25
            - Time: 10:00
            - Players: 4
            - Green Fee: €325 per player
            - Total: €1,300
            
            Guest Email: john.smith@gmail.com
            Booking ID: ISL-20251118-7F2A"
```

**User Experience**:
1. Customer clicks "Reserve Now"
2. Email client opens with pre-filled:
   - TO: bookings@theislandgolfclub.ie
   - CC: theisland@bookings.teemail.io (tracking)
   - SUBJECT: CONFIRM BOOKING - 2025-11-25 at 10:00
   - BODY: Pre-filled with booking details
3. Customer can edit (optional) or just send
4. Email arrives with booking ID and confirmation trigger

---

## 5. REPLY-TO-CONFIRM MECHANISMS

### Method 1: Pre-filled "Reserve Now" Button
- **Trigger**: Customer clicks button in availability email
- **Email generated**: By customer's email client
- **Format**: 
  - Subject: "CONFIRM BOOKING - [DATE] at [TIME]"
  - Body: Pre-filled with booking ID
- **Detection**: 
  - `is_confirmation_email()` checks subject for "CONFIRM BOOKING"
  - Booking ID extracted from body
- **Flow**: → process_confirmation() → Database update → Confirmation email

### Method 2: Manual Reply with Confirmation Keywords
- **Trigger**: Customer replies to confirmation email
- **Format**: 
  - Subject: "Re: [original subject]"
  - Body: "Yes, confirm booking" OR "CONFIRM ISL-20251118-7F2A" etc
- **Detection**:
  - `is_confirmation_email()` checks for "Re:" prefix
  - Searches for booking ID in body
  - Verifies confirmation keywords present
- **Flow**: → process_confirmation() → Extract booking ID → Database update → Confirmation email

### Method 3: Dedicated Confirmation Workflow
- **Trigger**: Customer replies to provisional email
- **Format**:
  - Reply with body: "CONFIRM [BOOKING-ID]"
  - Simple confirmation format
- **Detection**: Pattern matching for booking ID + confirmation context
- **Flow**: → process_confirmation() → Database update → Confirmation email

### Confirmation Email Detection Logic

```python
def is_confirmation_email(subject: str, body: str) -> bool:
    """
    Detect if this is a confirmation email
    """
    # Check 1: Explicit confirmation keywords in subject
    if "confirm booking" in subject.lower():
        return True
    
    # Check 2: Is this a reply?
    if subject.lower().startswith('re:'):
        return True
    
    # Check 3: Booking reference + confirmation keywords in body
    has_booking_ref = extract_booking_id(body)
    confirmation_keywords = [
        'confirm', 'yes', 'book', 'proceed', 
        'accept', 'ok', 'okay', 'sure', 'sounds good'
    ]
    has_keyword = any(kw in body.lower() for kw in confirmation_keywords)
    
    if has_booking_ref and has_keyword:
        return True
    
    return False
```

---

## 6. DATABASE SAVE POINTS

### Connection Architecture

```
Application Layer
    ↓
SimpleConnectionPool (1-10 connections)
    ↓
PostgreSQL Server (Render.com)
    ↓
theisland_bookings database
```

### Save Points in Booking Lifecycle

#### Save Point 1: Initial Booking Creation
**Function**: `store_booking_in_db(booking_data)`
**Trigger**: New booking request email received
**Operation**:
```sql
INSERT INTO bookings (
    id, name, email, phone, num_players,
    preferred_date, preferred_time, alternate_date,
    special_requests, status, total_fee, created_at,
    course_id, raw_email_data
) VALUES (...)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW()
```
**Status**: 'provisional'
**Columns Updated**:
- id (PRIMARY KEY) ← Booking ID
- name ← Parsed name
- email ← Sender email
- phone ← Parsed phone
- num_players ← Parsed count
- preferred_date ← Parsed date
- preferred_time ← Parsed time
- alternate_date ← Second date if found
- special_requests ← Email body/subject
- status ← 'provisional'
- total_fee ← players × €325
- created_at ← NOW()
- course_id ← 'theisland'
- raw_email_data ← Full booking JSON

**Indexes Available**:
- booking_id (UNIQUE)
- guest_email
- status
- created_at (DESC)
- date
- message_id

#### Save Point 2: Confirmation Update
**Function**: `update_booking_status(booking_id, status, notes)`
**Trigger**: Confirmation email received and validated
**Operation**:
```sql
UPDATE bookings
SET status = 'Confirmed',
    customer_confirmed_at = NOW(),
    confirmation_message_id = %(message_id)s,
    note = 'Confirmed via email',
    updated_at = NOW()
WHERE id = %(booking_id)s
```
**Status**: 'provisional' → 'confirmed'
**Columns Updated**:
- status ← 'Confirmed'
- customer_confirmed_at ← NOW()
- confirmation_message_id ← Email Message-ID
- note ← Confirmation notes
- updated_at ← NOW() (via trigger)

#### Save Point 3: Tee Time Details Update
**Function**: `update_booking_in_db(booking_id, updates)`
**Trigger**: Tee time extracted from confirmation email
**Operation**:
```sql
UPDATE bookings
SET date = %(date)s,
    tee_time = %(tee_time)s,
    updated_at = NOW()
WHERE booking_id = %(booking_id)s
```
**Columns Updated**:
- date ← Extracted tee date
- tee_time ← Extracted tee time
- updated_at ← NOW() (via trigger)

### Database Schema

```sql
CREATE TABLE bookings (
    -- Primary Key
    id VARCHAR(255) PRIMARY KEY,
    
    -- Customer Information
    name VARCHAR(255),
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(255),
    
    -- Booking Details
    num_players INTEGER NOT NULL DEFAULT 4,
    preferred_date VARCHAR(255),
    preferred_time VARCHAR(255),
    alternate_date VARCHAR(255),
    
    -- Status Tracking
    status VARCHAR(50) NOT NULL DEFAULT 'provisional',
    status CHECK (status IN ('provisional', 'confirmed', 'cancelled', 'completed')),
    
    -- Pricing
    total_fee DECIMAL(10, 2),
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    customer_confirmed_at TIMESTAMP,
    
    -- Email Tracking
    message_id VARCHAR(255),
    confirmation_message_id VARCHAR(255),
    raw_email_data JSONB,
    
    -- Course Reference
    course_id VARCHAR(255),
    
    -- Notes
    special_requests TEXT,
    internal_notes TEXT,
    
    -- Indexes
    UNIQUE(id),
    INDEX(email),
    INDEX(status),
    INDEX(created_at DESC),
    INDEX(date),
    INDEX(message_id)
}

-- Auto-update trigger
CREATE TRIGGER update_bookings_updated_at
BEFORE UPDATE ON bookings
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column()
```

### Transaction Management

**Isolation Level**: psycopg2 default (READ COMMITTED)

**Transaction Flow**:
```
1. get_db_connection() ← Get from pool
2. conn.cursor() ← Create cursor
3. cur.execute(INSERT/UPDATE) ← Execute query
4. conn.commit() ← Commit transaction
5. release_db_connection(conn) ← Return to pool
```

**Error Handling**:
```
Exception occurs:
    ↓
conn.rollback() ← Rollback transaction
    ↓
Logging: "Failed to [operation]"
    ↓
return False
    ↓
User receives error response
```

---

## 7. EMAIL TEMPLATES USED

### Template 1: Availability Email
**File**: Generated inline in `format_availability_email()`
**Used for**: Displaying available tee times
**Components**:
- HTML5 email template
- Outlook compatibility
- The Island branding colors
- Responsive design
- VLUB logo header
- Date/time tables
- Reserve buttons
- Championship description

### Template 2: Provisional Email
**File**: Generated inline in `format_provisional_email()`
**Used for**: Reply-to-confirm workflow
**Components**:
- Booking request confirmation
- Pre-filled confirmation button
- Reply-to-confirm instructions
- Edit request handling

### Template 3: Confirmation Email
**File**: Generated inline in `format_confirmation_email()`
**Used for**: Final booking confirmation
**Components**:
- Green success banner
- Booking details table
- Arrival instructions
- Payment information
- Contact club office link

### Template 4: No Availability Email
**File**: Generated inline in `format_no_availability_email()`
**Used for**: No tee times available
**Components**:
- No availability warning
- Contact club message
- Email/phone numbers

### Template Features (All)
- **Styling**: Inline CSS for email client compatibility
- **Branding**:
  - Navy blue (#24388f) primary
  - Royal blue (#1923c2) accent
  - Gold (#D4AF37) highlights
  - Powder blue (#b8c1da) secondary
- **Layout**: 800px max-width, centered
- **Responsive**: Mobile-optimized media queries
- **Images**: VLUB logo from GitHub CDN
- **Security**: No external scripts, HTML only

---

## 8. CONFIGURATION & DEPLOYMENT

### Environment Variables Required

```
# SendGrid
SENDGRID_API_KEY=<secret>

# Email Configuration
FROM_EMAIL=bookings@theislandgolfclub.ie
FROM_NAME=The Island Golf Club
CLUB_BOOKING_EMAIL=bookings@theislandgolfclub.ie

# Database
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Booking Settings
PER_PLAYER_FEE=325.00
DEFAULT_COURSE_ID=theisland

# Email Relay
TRACKING_EMAIL_PREFIX=theisland

# Deployment
PORT=10000
```

### Render.com Deployment

```yaml
services:
  - name: theisland-email-bot
    type: web
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --bind 0.0.0.0:$PORT app:app
    region: oregon
    plan: starter
    healthCheckPath: /health

databases:
  - name: theisland-db
    type: PostgreSQL
    databaseName: theisland_bookings
    user: theisland_admin
```

### API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/webhook/inbound` | Inbound email processing |
| POST | `/webhook/events` | SendGrid event tracking |
| GET | `/api/bookings` | List all bookings |
| POST | `/api/confirm/<booking_id>` | Manual confirmation |
| GET | `/health` | Health check |

---

## 9. COMPLETE MESSAGE FLOW SUMMARY

```
Customer sends email to bookings@theislandgolfclub.ie
    ↓
Email Relay receives and validates
    ↓
SendGrid Inbound Parse webhook → POST /webhook/inbound
    ↓
Flask app receives form data (from, subject, text, html)
    ↓
┌─ VALIDATION ───────────────────┐
│ Check email, subject/body       │
│ Extract clean email address     │
│ Check if duplicate (Message-ID) │
└─────────────────────────────────┘
    ↓
┌─ DETECTION ────────────────────┐
│ is_confirmation_email()?        │
│   NO → New booking request      │
│   YES → Confirmation email      │
└─────────────────────────────────┘
    ↓
╔═ NEW BOOKING BRANCH ════════════╗
║ 1. parse_booking_from_email()   ║
║    - Extract players, dates,    ║
║      time, phone                ║
║                                 ║
║ 2. Generate booking ID          ║
║    - ISL-YYYYMMDD-XXXX format  ║
║                                 ║
║ 3. CREATE booking_data dict     ║
║                                 ║
║ 4. store_booking_in_db()        ║
║    - INSERT into PostgreSQL     ║
║    - Status: 'provisional'      ║
║                                 ║
║ 5. format_availability_email()  ║
║ or format_provisional_email()   ║
║    - Generate HTML email        ║
║    - Add Reserve Now buttons    ║
║                                 ║
║ 6. send_email()                 ║
║    - SendGrid sends to customer ║
║                                 ║
║ 7. Return webhook response      ║
║    {status: 'success'}          ║
╚═════════════════════════════════╝
              OR
╔═ CONFIRMATION BRANCH ══════════╗
║ 1. extract_booking_id()         ║
║    - Find ISL-XXXXX-XXXX or    ║
║      BOOK-XXXXX-XXXXX          ║
║                                 ║
║ 2. Check for duplicates         ║
║    - Message-ID already seen?   ║
║                                 ║
║ 3. get_booking_by_id()          ║
║    - Query PostgreSQL           ║
║                                 ║
║ 4. Verify status = 'provisional'║
║                                 ║
║ 5. Check confirmation keywords  ║
║    - yes, confirm, proceed, etc║
║                                 ║
║ 6. extract_tee_time_from_email()║
║    - Parse date/time from email ║
║                                 ║
║ 7. update_booking_in_db()       ║
║    - UPDATE status='Confirmed'  ║
║    - Set date, time             ║
║    - customer_confirmed_at      ║
║                                 ║
║ 8. format_confirmation_email()  ║
║    - Generate HTML email        ║
║    - Show confirmed details     ║
║                                 ║
║ 9. send_email()                 ║
║    - SendGrid sends confirmation║
║                                 ║
║ 10. Return webhook response     ║
║     {status: 'confirmed'}       ║
╚═════════════════════════════════╝
    ↓
Customer receives confirmation email
    ↓
Booking stored in database with status='confirmed'
    ↓
Club staff can view in dashboard
    ↓
Customer arrives 30 minutes before tee time
    ↓
COMPLETE!
```

---

## 10. KEY DESIGN FEATURES

### 1. Self-Contained Booking Flow
- **No external API calls** for core functionality
- Email parsing built-in using regex patterns
- Database-backed storage
- Deterministic booking ID generation

### 2. Reply-to-Confirm Workflow
- Pre-filled email buttons in responses
- Tracking email (theisland@bookings.teemail.io) for automation
- Booking ID embedded in subject for quick extraction
- Confirmation keywords detection

### 3. Email Parsing Intelligence
- Multiple date/time patterns supported
- Relative dates (tomorrow, next Friday)
- Flexible phone number formats
- Default values (4 players)

### 4. Duplicate Detection
- Message-ID tracking prevents double-processing
- Idempotent operations (ON CONFLICT in SQL)
- Status checks (already confirmed → skip)

### 5. Branding & Template System
- The Island Golf Club color scheme
- Responsive email design
- VLUB logo integration
- Mobile-friendly layouts

### 6. Error Recovery
- Connection pooling for reliability
- Transaction rollback on errors
- Comprehensive logging for debugging
- Graceful error responses

### 7. Scalability
- SimpleConnectionPool for concurrent requests
- Index strategy on frequently queried columns
- Stateless Flask app (scales horizontally)
- Render.com auto-deployment

---

## 11. TESTING & MONITORING

### Log Monitoring Points

```
✅ "Database: SUCCESS" - Booking stored
❌ "Database: FAILED" - Connection/insert error
✅ "Email: SUCCESS" - Sent via SendGrid
❌ "Email: FAILED" - API/configuration error
✅ "CONFIRMATION DETECTED" - Reply recognized
❌ "NO BOOKING ID FOUND" - Extraction failed
✅ "BOOKING CONFIRMED SUCCESSFULLY" - Confirmed
```

### Health Check Endpoint

```
GET /health
Returns: {
    'status': 'healthy',
    'service': 'The Island Email Bot',
    'database': 'connected|disconnected',
    'timestamp': ISO8601
}
```

---

## Summary

The Island Golf Club booking system implements a complete email-driven workflow:

1. **Webhook Receives** → Email from customer
2. **Parser Extracts** → Date, time, players, phone
3. **Database Saves** → Booking with 'provisional' status
4. **Email Responds** → Available times with pre-filled buttons
5. **Customer Confirms** → Clicks button or replies
6. **Detection Recognizes** → Confirmation intent + booking ID
7. **Status Updates** → 'provisional' → 'confirmed'
8. **Email Confirms** → Final confirmation to customer
9. **Complete** → Ready for tee time

All with comprehensive logging, error handling, and database persistence using PostgreSQL.

