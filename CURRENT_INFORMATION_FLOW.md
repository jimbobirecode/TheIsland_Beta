# Complete Information Flow - Golf Booking System
**Status: As of December 9, 2025**

---

## Overview

**System:** Email-based golf booking system for The Island Golf Club
**Database:** PostgreSQL (`theisland-db` on Render)
**Club ID:** `demo` (for database filtering)
**Course ID:** `theisland` (for API availability checks)

---

## FLOW 1: Customer Inquiry (New Request)

### Step 1: Email Arrives
```
Customer sends email to: clubname@bookings.teemail.io
Subject: "Tee Time Request for March"
Body: "Hi, I'd like to book a tee time for 4 players on January 08, 2026..."
```

### Step 2: SendGrid Inbound Parse Webhook
```
SendGrid receives email
↓
Forwards to Flask webhook
POST https://theisland-beta.onrender.com/webhook/inbound
Content-Type: application/x-www-form-urlencoded

Form Data:
- from: "teemailbaltray@gmail.com"
- subject: "Tee Time Request for March"
- text: "Hi, I'd like to book..."
- html: "<html>...</html>"
- headers: "..." (currently not parsing Message-ID correctly)
```

### Step 3: Flask Webhook Handler (`island_email_bot.py:1923`)
```python
@app.route('/webhook/inbound', methods=['POST'])
def handle_inbound_email():
    # Extract form data
    from_email = request.form.get('from', '')
    subject = request.form.get('subject', '')
    text_body = request.form.get('text', '')
    html_body = request.form.get('html', '')
    headers = request.form.get('headers', '')

    body = text_body if text_body else html_body
    message_id = extract_message_id(headers)  # Currently returns None
    sender_email = "teemailbaltray@gmail.com"
```

**Logs Output:**
```
📨 INBOUND WEBHOOK
From: teemailbaltray@gmail.com
Subject: Tee Time Request for March
Body (first 200 chars): Hi, I'd like to book a tee time for 4 players on January 08, 2026...
Message-ID: None
```

### Step 4: Email Parsing (`island_email_bot.py:1988`)
```python
parsed = parse_email_simple(subject, body)

# Regex patterns extract:
# - Players: "4 players" → players = 4
# - Date: "January 08, 2026" → dates = ['2026-01-08']

Returns:
{
    'players': 4,
    'dates': ['2026-01-08']
}
```

### Step 5: Generate Booking ID (`island_email_bot.py:2155`)
```python
timestamp = "2025-12-09 18:09:02"
booking_id = generate_booking_id(sender_email, timestamp)
# Format: ISL-YYYYMMDD-HASH
# Result: "ISL-20251209-8C9409B7"
```

### Step 6: Create Booking Data (`island_email_bot.py:2158-2172`)
```python
new_entry = {
    "booking_id": "ISL-20251209-8C9409B7",
    "timestamp": "2025-12-09 18:09:02",
    "guest_email": "teemailbaltray@gmail.com",
    "message_id": None,  # Currently not capturing
    "dates": ['2026-01-08'],
    "date": "2026-01-08",
    "tee_time": None,
    "players": 4,
    "total": 1300.00,  # 4 * 325.00
    "status": "Processing",
    "note": "Webhook received, checking availability...",
    "club": "demo",  # ← DATABASE_CLUB_ID from env
    "club_name": "Golf Club Bookings"  # ← FROM_NAME from env
}
```

### Step 7: Save to Database (`island_email_bot.py:200-228`)
```sql
INSERT INTO bookings (
    booking_id, message_id, timestamp, guest_email,
    dates, date, tee_time, players, total, status, note,
    club, club_name
) VALUES (
    'ISL-20251209-8C9409B7',
    NULL,
    '2025-12-09 18:09:02',
    'teemailbaltray@gmail.com',
    '["2026-01-08"]'::jsonb,
    '2026-01-08',
    NULL,
    4,
    1300.00,
    'Processing',
    'Webhook received, checking availability...',
    'demo',  -- ← This is the club field value
    'Golf Club Bookings'
)
ON CONFLICT (booking_id) DO UPDATE SET
    status = EXCLUDED.status,
    note = EXCLUDED.note,
    updated_at = CURRENT_TIMESTAMP;
```

**Database:**
- **Database Name:** `theisland_bookings`
- **Table:** `bookings`
- **Record Created:**
  - `id`: Auto-increment (e.g., 245)
  - `booking_id`: `ISL-20251209-8C9409B7` (UNIQUE)
  - `club`: `demo` ← **This is what gets saved**
  - `status`: `Processing`
  - All other fields as above

**Logs Output:**
```
✅ BOOKING SAVED - ID: ISL-20251209-8C9409B7
✅ Inquiry saved to DB (responded in 0.02s)
```

### Step 8: Return 200 OK to SendGrid
```python
return jsonify({
    'status': 'inquiry_accepted',
    'booking_id': 'ISL-20251209-8C9409B7',
    'processing': 'background'
}), 200
```

**Total time: ~0.02 seconds** (webhook must respond < 10 seconds)

---

## Step 9: Background Thread Starts (`island_email_bot.py:2181-2188`)
```python
# Webhook has already responded to SendGrid
# Now process in background (daemon thread)

thread = Thread(
    target=process_inquiry_async,
    args=(
        'teemailbaltray@gmail.com',  # sender_email
        {'players': 4, 'dates': ['2026-01-08']},  # parsed
        'ISL-20251209-8C9409B7',  # booking_id
        ['2026-01-08'],  # dates
        4  # players
    )
)
thread.daemon = True
thread.start()
```

**Logs Output:**
```
🔄 Background thread started for booking ISL-20251209-8C9409B7
⏱️  Response time: 0.02s
```

---

## Step 10: Background Processing - Core API Call (`island_email_bot.py:1368-1520`)

### 10a: Prepare API Request
```python
api_url = "https://core-new-aku3.onrender.com/check_availability"
payload = {
    'course_id': 'theisland',  # ← DEFAULT_COURSE_ID from env
    'dates': ['2026-01-08'],
    'players': 4
}
```

**Logs Output:**
```
🔄 Background processing started for booking ISL-20251209-8C9409B7
🔗 Calling Core API: https://core-new-aku3.onrender.com/check_availability
📦 Payload: {'course_id': 'theisland', 'dates': ['2026-01-08'], 'players': 4}
```

### 10b: Call Core API with Retries
```python
max_retries = 2
for attempt in range(max_retries + 1):  # 0, 1, 2
    try:
        response = requests.post(
            api_url,
            json=payload,
            timeout=120  # 2 minute timeout
        )

        if response.status_code != 502:
            break  # Success or non-502 error

        # If 502 and retries left, wait 10s and retry
        if attempt < max_retries:
            time.sleep(10)
    except requests.Timeout:
        # If timeout and retries left, wait 10s and retry
        if attempt == max_retries:
            raise  # Final attempt failed
        time.sleep(10)
```

**Logs Output (Attempt 1):**
```
🔄 Attempt 1/3
```

**⚠️ CURRENT ISSUE:** Logs stop here. No response logged, suggesting:
- API not responding
- Taking > 120 seconds
- Network issue
- Error not being caught

### 10c: If API Responds Successfully
```python
if response.status_code == 200:
    api_data = response.json()
    # Expected format:
    # {
    #     'success': true,
    #     'results': [
    #         {'date': '2026-01-08', 'time': '09:00', 'available_slots': 4},
    #         {'date': '2026-01-08', 'time': '10:30', 'available_slots': 4}
    #     ]
    # }

    results = api_data.get('results', [])
```

**Expected Logs (not seeing):**
```
✅ Core API responded with status: 200
📊 API returned 2 results
✅ Found 2 available times
```

---

## Step 11: Generate & Send Email with Tee Times

### 11a: Format HTML Email (`island_email_bot.py:1449`)
```python
html_email = format_inquiry_email(results, players, sender_email, booking_id)
subject_line = "Available Tee Times at Golf Club"
```

**Email Contains:**
- Header with club branding
- Table of available tee times
- "Book Now" button for each time slot (mailto link)
- Footer with contact info

**"Book Now" Mailto Link Format:**
```
mailto:clubname@bookings.teemail.io?subject=BOOKING%20REQUEST%20-%202026-01-08%20at%2009:00&body=I%20would%20like%20to%20book...Booking%20ID:%20ISL-20251209-8C9409B7
```

### 11b: Send via SendGrid (`island_email_bot.py:1451`)
```python
send_email_sendgrid(sender_email, subject_line, html_email)

# SendGrid API call
POST https://api.sendgrid.com/v3/mail/send
Authorization: Bearer {SENDGRID_API_KEY}
Content-Type: application/json

{
    "personalizations": [{
        "to": [{"email": "teemailbaltray@gmail.com"}]
    }],
    "from": {
        "email": "clubname@bookings.teemail.io",
        "name": "Golf Club Bookings"
    },
    "subject": "Available Tee Times at Golf Club",
    "content": [{
        "type": "text/html",
        "value": "<html>...</html>"
    }]
}
```

**Expected Logs (not seeing):**
```
📧 Sending email to: teemailbaltray@gmail.com
   Subject: Available Tee Times at Golf Club
✅ Email sent successfully
   Status code: 202
```

### 11c: Update Booking Status
```python
update_booking_in_db(booking_id, {
    'status': 'Inquiry',
    'note': 'Initial inquiry received. Available times sent.'
})
```

**SQL Update:**
```sql
UPDATE bookings
SET status = 'Inquiry',
    note = 'Initial inquiry received. Available times sent.',
    updated_at = CURRENT_TIMESTAMP
WHERE booking_id = 'ISL-20251209-8C9409B7';
```

**Expected Logs (not seeing):**
```
💾 DATABASE UPDATE INITIATED
📋 Booking ID: ISL-20251209-8C9409B7
📝 Updates to apply:
   • status: Inquiry
   • note: Initial inquiry received. Available times sent.
✅ Database updated successfully - 1 row(s) affected
✅ Background processing completed for booking ISL-20251209-8C9409B7
```

---

## FLOW 2: Customer Clicks "Book Now"

### Step 1: Customer Action
Customer receives email with available times, clicks "Book Now" button for 09:00 slot.

### Step 2: Mailto Opens Email Client
```
To: clubname@bookings.teemail.io
Subject: BOOKING REQUEST - 2026-01-08 at 09:00
Body: I would like to book this tee time.

Date: 2026-01-08
Time: 09:00
Players: 4

Booking ID: ISL-20251209-8C9409B7

Please confirm this booking.
```

### Step 3: Customer Sends Email
Email goes to SendGrid → webhook triggers again

### Step 4: Webhook Detects Booking Request (`island_email_bot.py:2048`)
```python
if is_booking_request(subject, body):
    # Detects "BOOKING REQUEST" in subject
    booking_id = extract_booking_id(subject) or extract_booking_id(body)
    # Extracts: ISL-20251209-8C9409B7
```

### Step 5: Update to "Requested" Status
```python
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
updates = {
    'status': 'Requested',
    'note': f"Customer sent booking request on {timestamp}",
    'confirmation_message_id': message_id
}

# Extract date and time from subject/body
date_match = re.search(r'(\d{4}-\d{2}-\d{2})', subject + body)
time_match = re.search(r'(\d{1,2}:\d{2})', subject + body)

if date_match:
    updates['date'] = '2026-01-08'
if time_match:
    updates['tee_time'] = '09:00'

update_booking_in_db(booking_id, updates)
```

**SQL Update:**
```sql
UPDATE bookings
SET status = 'Requested',
    date = '2026-01-08',
    tee_time = '09:00',
    note = 'Customer sent booking request on 2025-12-09 18:10:15',
    confirmation_message_id = NULL,
    updated_at = CURRENT_TIMESTAMP
WHERE booking_id = 'ISL-20251209-8C9409B7';
```

### Step 6: Send Acknowledgment Email
Background thread sends:
```
To: teemailbaltray@gmail.com
Subject: Your Booking Request - Golf Club
Body: We've received your booking request for:
      - Date: 2026-01-08
      - Time: 09:00
      - Players: 4

      Our team will review and confirm shortly.
      Booking ID: ISL-20251209-8C9409B7
```

---

## FLOW 3: Staff Confirmation

### Step 1: Staff Sends Confirmation Email
```
To: clubname@bookings.teemail.io
Subject: CONFIRM BOOKING ISL-20251209-8C9409B7
Body: Approved
```

### Step 2: Webhook Detects Staff Confirmation (`island_email_bot.py:1994`)
```python
if is_staff_confirmation(subject, body, sender_email):
    booking_id = extract_booking_id(subject) or extract_booking_id(body)
    # Extracts: ISL-20251209-8C9409B7

    booking = get_booking_by_id(booking_id)

    if booking and booking.get('status') == 'Requested':
        # Update to Confirmed
```

### Step 3: Update to "Confirmed" Status
```sql
UPDATE bookings
SET status = 'Confirmed',
    note = '...Booking confirmed by team on 2025-12-09 18:15:00',
    updated_at = CURRENT_TIMESTAMP
WHERE booking_id = 'ISL-20251209-8C9409B7';
```

### Step 4: Send Confirmation Email to Customer
```
To: teemailbaltray@gmail.com
Subject: Booking Confirmed - Golf Club
Body: ✅ Your booking is confirmed!

      Date: 2026-01-08
      Time: 09:00
      Players: 4
      Total: €1,300.00

      Payment Instructions: ...
      Booking ID: ISL-20251209-8C9409B7
```

---

## Data Storage Summary

### Database Location
```
Render PostgreSQL: theisland-db
Database Name: theisland_bookings
Table: bookings
```

### Key Fields Saved
| Field | Example Value | Source |
|-------|---------------|--------|
| `booking_id` | `ISL-20251209-8C9409B7` | Generated (MD5 hash) |
| `club` | `demo` | `DATABASE_CLUB_ID` env var |
| `club_name` | `Golf Club Bookings` | `FROM_NAME` env var |
| `guest_email` | `teemailbaltray@gmail.com` | Parsed from webhook |
| `players` | `4` | Parsed from email body |
| `date` | `2026-01-08` | Parsed from email body |
| `dates` | `["2026-01-08"]` | JSONB array |
| `tee_time` | `09:00` | Set when customer requests |
| `total` | `1300.00` | `players * PER_PLAYER_FEE` |
| `status` | `Processing` → `Inquiry` → `Requested` → `Confirmed` | Workflow progression |

### Environment Variables Used
```bash
# Database
DATABASE_URL=postgresql://...
DATABASE_CLUB_ID=demo          # ← Saved to bookings.club

# Email
SENDGRID_API_KEY=SG.xxx...
FROM_EMAIL=clubname@bookings.teemail.io
FROM_NAME=Golf Club Bookings

# API
CORE_API_URL=https://core-new-aku3.onrender.com
DEFAULT_COURSE_ID=theisland    # ← Sent to Core API

# Pricing
PER_PLAYER_FEE=325.00
```

---

## Current Issues

### ❌ Issue #1: Core API Not Responding
**Symptom:** Logs show "Attempt 1/3" then nothing
**Impact:** Customers never receive tee times email
**Location:** `island_email_bot.py:1390-1430`

### ❌ Issue #2: Message-ID is None
**Symptom:** `Message-ID: None` in all logs
**Impact:** Duplicate detection not working
**Location:** `island_email_bot.py:1972` - `extract_message_id(headers)`

### ✅ Working Correctly
- Email parsing (players, dates)
- Database saves (with `club='demo'`)
- Booking ID generation
- Webhook response time (< 0.02s)
- Status progression logic

---

## Query to Check Current Data

```sql
-- Check what's actually in database
SELECT
    booking_id,
    club,
    status,
    guest_email,
    players,
    date,
    tee_time,
    created_at,
    note
FROM bookings
WHERE club = 'demo'
  AND created_at >= CURRENT_DATE
ORDER BY created_at DESC
LIMIT 10;
```

**Expected:** All rows should have `club='demo'`

---

**Last Updated:** December 9, 2025
**Next Steps:** Debug Core API timeout issue
