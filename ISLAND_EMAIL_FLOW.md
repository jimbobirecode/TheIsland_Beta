# The Island Golf Club - Email Flow Documentation

## Overview

The email bot implements a specific flow for handling customer inquiries and booking requests for The Island Golf Club.

## Email Flow Stages

### 1. Customer Inquiry → Database
**Status: `Inquiry` ✅**

**When it happens:**
- Customer sends initial email asking about tee times
- Email can include dates, number of players, etc.

**What the bot does:**
1. Creates new booking record with status `'Inquiry'`
2. Generates unique booking ID (format: `ISL-YYYYMMDD-XXXXXXXX`)
3. Checks availability via Core API
4. Sends email with available tee times and "Book Now" buttons
5. Note: `"Initial inquiry received"`

**Example:**
```
Customer Email:
"Hi, I'd like to book a tee time for 4 players on 2025-12-15"

Bot Response:
- Creates booking ISL-20251119-ABC12345 with status 'Inquiry'
- Sends email showing available times with "Book Now" buttons
```

---

### 2. Customer Clicks "Book Now" → Database
**Status: `Inquiry` → `Requested` ✅**

**When it happens:**
- Customer clicks a "Book Now" button in the inquiry email
- Email client opens with subject: "BOOKING REQUEST - [date] at [time]"
- Customer sends that email

**What the bot does:**
1. Detects "BOOKING REQUEST" in subject line
2. Extracts booking ID from email body
3. Updates booking status from `'Inquiry'` to `'Requested'`
4. Captures date and time from the booking request
5. Note: `"Customer sent booking request on [timestamp]"`
6. Sends acknowledgment email to customer
7. Updates note: `"Customer sent booking request on [timestamp]\nAcknowledgment email sent on [timestamp]"`

**Example:**
```
Customer Email:
Subject: "BOOKING REQUEST - 2025-12-15 at 10:00"
Body: Contains booking ID ISL-20251119-ABC12345

Bot Actions:
- Updates ISL-20251119-ABC12345: status 'Inquiry' → 'Requested'
- Sets date = 2025-12-15, tee_time = 10:00
- Sends acknowledgment email
- Updates notes with timestamps
```

---

### 3. Bot Sends Acknowledgment → Database
**Status: `Requested` (maintained)**

**When it happens:**
- Automatically triggered after customer sends booking request
- Part of step 2 above

**What the bot does:**
1. Sends "Booking Request Received" email to customer
2. Email shows booking details (ID, date, time, players, total fee)
3. Informs customer that team will review and confirm
4. Status remains `'Requested'`
5. Note updated: `"Acknowledgment email sent on [timestamp]"`

**Example Acknowledgment Email:**
```
Subject: "Your Booking Request - The Island Golf Club"

📬 Booking Request Received

Thank you for your booking request at The Island Golf Club.

Your Booking Request:
- Booking ID: ISL-20251119-ABC12345
- Date: 2025-12-15
- Time: 10:00
- Players: 4
- Total Fee: €1,300.00

Our team is reviewing your request and will confirm shortly.
```

---

### 4. Customer Replies Again → Database
**Status: `Requested` (maintained)**

**When it happens:**
- Customer replies to any email (acknowledgment or inquiry)
- Subject starts with "Re:"

**What the bot does:**
1. Detects "Re:" in subject line
2. Extracts booking ID from subject or body
3. Appends to existing note: `"Customer replied again on [timestamp]"`
4. Status remains `'Requested'`
5. **No email sent** - just updates database

**Example:**
```
Customer Email:
Subject: "Re: Your Booking Request - The Island Golf Club"
Body: "Thanks! Just confirming we need 4 players."

Bot Actions:
- Finds booking ISL-20251119-ABC12345
- Status stays 'Requested'
- Appends note: "Customer replied again on 2025-11-19 14:35:00"
```

---

## Database Status Flow

```
┌─────────────────────┐
│  Customer Inquiry   │
│   (initial email)   │
└──────────┬──────────┘
           │
           ▼
    ┌─────────────┐
    │   Inquiry   │ ← Initial status
    └──────┬──────┘
           │
           │ Customer clicks "Book Now"
           │
           ▼
    ┌─────────────┐
    │  Requested  │ ← Status changes here
    └──────┬──────┘
           │
           │ Bot sends acknowledgment
           │ (status maintained)
           ▼
    ┌─────────────┐
    │  Requested  │ ← Status unchanged
    └──────┬──────┘
           │
           │ Customer replies
           │ (status maintained)
           ▼
    ┌─────────────┐
    │  Requested  │ ← Status unchanged
    └─────────────┘
```

---

## Database Notes Evolution

### After Step 1 (Inquiry):
```
note: "Initial inquiry received"
```

### After Step 2 (Book Now):
```
note: "Customer sent booking request on 2025-11-19 14:30:00"
```

### After Step 3 (Acknowledgment):
```
note: "Customer sent booking request on 2025-11-19 14:30:00
Acknowledgment email sent on 2025-11-19 14:30:15"
```

### After Step 4 (Customer Reply):
```
note: "Customer sent booking request on 2025-11-19 14:30:00
Acknowledgment email sent on 2025-11-19 14:30:15
Customer replied again on 2025-11-19 14:35:00"
```

---

## Key Features

### 1. Email Detection
The bot intelligently detects email type:
- **Booking Request**: Contains "BOOKING REQUEST" in subject
- **Customer Reply**: Subject starts with "Re:"
- **New Inquiry**: Everything else (default)

### 2. Booking ID Format
- Format: `ISL-YYYYMMDD-XXXXXXXX`
- Example: `ISL-20251119-ABC12345`
- Always included in emails for tracking

### 3. Email Templates
- **Inquiry Email**: Shows available times with "Book Now" buttons
- **Acknowledgment Email**: Confirms booking request received
- **No Availability Email**: Politely informs customer when no times available

### 4. Integration with Core API
- Checks real-time availability
- Returns available tee times
- Supports filtering by date and player count

---

## Configuration

### Environment Variables
```bash
# Email
FROM_EMAIL=bookings@theislandgolfclub.ie
FROM_NAME=The Island Golf Club
SENDGRID_API_KEY=your_sendgrid_key

# Database
DATABASE_URL=postgresql://...

# API
CORE_API_URL=http://localhost:5001

# Pricing
PER_PLAYER_FEE=325.00

# Course
DEFAULT_COURSE_ID=theisland
TRACKING_EMAIL_PREFIX=theisland
CLUB_BOOKING_EMAIL=bookings@theislandgolfclub.ie
```

---

## Differences from County Louth Flow

| Feature | County Louth | The Island |
|---------|--------------|------------|
| Initial Status | 'Pending' | **'Inquiry'** |
| After Book Now | 'Confirmed' | **'Requested'** |
| Acknowledgment | No auto-ack | **Auto-acknowledgment sent** |
| Reply Handling | Updates status | **Maintains 'Requested' status** |
| Note Tracking | Basic | **Detailed timestamps** |

---

## API Endpoints

### Webhook Endpoint
```
POST /webhook/inbound
```
Receives incoming emails from SendGrid Inbound Parse

### Bookings API
```
GET  /api/bookings          - List all bookings
PUT  /api/bookings/{id}     - Update booking
```

### Health Check
```
GET  /health
```
Returns service status and configuration

---

## Testing the Flow

### Test Sequence:
1. **Send inquiry email** to theisland@bookings.teemail.io
   - Should create booking with status 'Inquiry'
   - Should receive email with available times

2. **Click "Book Now"** in the email
   - Email client opens with "BOOKING REQUEST" subject
   - Send the email

3. **Bot should:**
   - Update status to 'Requested'
   - Send acknowledgment email

4. **Reply to acknowledgment**
   - Status should stay 'Requested'
   - Note should be updated with timestamp

---

## Troubleshooting

### Booking not created?
- Check database connection (DATABASE_URL)
- Check logs for errors
- Verify email has valid from address

### Status not updating?
- Check booking ID is present in email
- Verify subject contains "BOOKING REQUEST"
- Check database logs

### No acknowledgment sent?
- Check SENDGRID_API_KEY is set
- Verify FROM_EMAIL is configured
- Check SendGrid dashboard for errors

---

## Contact

For questions about The Island Golf Club email bot:
- Email: bookings@theislandgolfclub.ie
- Phone: +353 1 843 6205
