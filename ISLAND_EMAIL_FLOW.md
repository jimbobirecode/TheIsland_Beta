# The Island Golf Club - Email Flow Documentation

## Overview

The email bot implements a clear three-stage customer journey for handling bookings at The Island Golf Club.

## CUSTOMER JOURNEY - CLEAR TERMINOLOGY

The booking process follows three distinct stages with clear status transitions:

1. **Inquiry** - Customer asks about availability
2. **Request** - Customer requests a specific booking
3. **Confirmation** - Booking team manually confirms the booking

## Email Flow Stages

### Stage 1: Inquiry
**Status: `Inquiry` ✅**
**Email Display: "Status: Inquiry - Awaiting Your Request"**

**When it happens:**
- Customer sends initial email asking about tee times
- Email can include dates, number of players, etc.

**What the bot does:**
1. Creates new booking record with status `'Inquiry'`
2. Generates unique booking ID (format: `ISL-YYYYMMDD-XXXXXXXX`)
3. Checks availability via Core API
4. Sends email with available tee times and "Book Now" buttons
5. Email shows: **"Status: Inquiry - Awaiting Your Request"**
6. Note: `"Initial inquiry received"`

**Example:**
```
Customer Email:
"Hi, I'd like to book a tee time for 4 players on 2025-12-15"

Bot Response:
- Creates booking ISL-20251119-ABC12345 with status 'Inquiry'
- Sends email showing available times with "Book Now" buttons
- Status displayed: "Inquiry - Awaiting Your Request"
```

---

### Stage 2: Request
**Status: `Inquiry` → `Requested` ✅**
**Acknowledgment: "📬 Booking Request Received"**

**When it happens:**
- Customer clicks a "Book Now" button in the inquiry email
- Email client opens with subject: "BOOKING REQUEST - [date] at [time]"
- Customer REQUESTS a booking via mailto link

**What the bot does:**
1. Detects "BOOKING REQUEST" in subject line
2. Extracts booking ID from email body
3. Updates booking status from `'Inquiry'` to `'Requested'`
4. Captures date and time from the booking request
5. Note: `"Customer sent booking request on [timestamp]"`
6. **Sends acknowledgment email** with heading "📬 Booking Request Received"
7. Updates note: `"Customer sent booking request on [timestamp]\nAcknowledgment email sent on [timestamp]"`

**Example:**
```
Customer Email:
Subject: "BOOKING REQUEST - 2025-12-15 at 10:00"
Body: Contains booking ID ISL-20251119-ABC12345

Bot Actions:
- Updates ISL-20251119-ABC12345: status 'Inquiry' → 'Requested'
- Sets date = 2025-12-15, tee_time = 10:00
- Sends acknowledgment email: "Booking Request Received"
- Updates notes with timestamps
```

**Acknowledgment Email:**
```
Subject: "Your Booking Request - The Island Golf Club"

📬 Booking Request Received

Thank you for your booking request at The Island Golf Club.
We have received your request and will review it shortly.

Your Booking Request:
- Booking ID: ISL-20251119-ABC12345
- Date: 2025-12-15
- Time: 10:00
- Players: 4
- Total Fee: €1,300.00

✅ Request Received
We have received your booking request and our team will be in touch
shortly to confirm your tee time. We'll contact you via email or phone
within 24 hours.
```

---

### Stage 3: Confirmation (Manual by Team)
**Status: `Requested` → `Confirmed` ✅**
**Email Display: "✅ Booking Confirmed"**

**When it happens:**
- Booking team reviews the request
- Team manually sends confirmation email (with keywords like "CONFIRM BOOKING")
- Email must include the booking ID

**What the bot does:**
1. Detects "CONFIRM BOOKING" or similar keywords in subject/body
2. Extracts booking ID from email
3. Verifies booking is in 'Requested' status
4. Updates booking status from `'Requested'` to `'Confirmed'`
5. Note: `"Booking confirmed by team on [timestamp]"`
6. **Sends confirmation email with payment details**
7. Updates note: `"Booking confirmed by team on [timestamp]\nConfirmation email sent on [timestamp]"`

**Example:**
```
Staff Email:
Subject: "Confirm Booking ISL-20251119-ABC12345"
Body: "CONFIRM BOOKING for ISL-20251119-ABC12345"

Bot Actions:
- Updates ISL-20251119-ABC12345: status 'Requested' → 'Confirmed'
- Sends confirmation email with payment details to customer
- Updates notes with timestamps
```

**Confirmation Email (Sent to Customer):**
```
Subject: "Booking Confirmed - The Island Golf Club"

✅ Booking Confirmed

Congratulations! Your booking at The Island Golf Club has been confirmed.

📋 Confirmed Booking Details:
- Booking ID: ISL-20251119-ABC12345
- Date: 2025-12-15
- Tee Time: 10:00
- Number of Players: 4
- Total Amount Due: €1,300.00

💳 Payment Details:
- Payment Method: Bank Transfer or Card Payment
- When: Payment is required to secure your booking
- Bank Details: Please contact us for bank transfer details
💡 For card payment or bank transfer details, please reply to this
email or call us at +353 1 843 6205

📍 Important Information:
- Please arrive 30 minutes before your tee time
- Please bring proof of handicap (if applicable)
- Cancellations must be made at least 48 hours in advance
- Weather permitting - we'll contact you if conditions are unsuitable

Contact Us:
📧 Email: bookings@theislandgolfclub.ie
📞 Phone: +353 1 843 6205
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

## Three-Stage Customer Journey Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 1: INQUIRY                         │
│  Customer sends initial email asking about availability     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Inquiry   │ ← Status: "Inquiry - Awaiting Your Request"
                    └──────┬──────┘
                           │
                           │ Bot sends available times
                           │ with "Book Now" buttons
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    STAGE 2: REQUEST                         │
│  Customer clicks "Book Now" and REQUESTS a booking          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Requested  │ ← Status changes: 'Inquiry' → 'Requested'
                    └──────┬──────┘
                           │
                           │ Bot sends acknowledgment:
                           │ "📬 Booking Request Received"
                           │ (status maintained)
                           │
                           ▼
                    ┌─────────────┐
                    │  Requested  │ ← Status maintained
                    └──────┬──────┘
                           │
                           │ Team reviews booking
                           │
┌──────────────────────────┴──────────────────────────────────┐
│              STAGE 3: CONFIRMATION                          │
│  Booking team manually CONFIRMS the booking                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Confirmed  │ ← Status changes: 'Requested' → 'Confirmed'
                    └──────┬──────┘
                           │
                           │ Bot sends confirmation email
                           │ "✅ Booking Confirmed"
                           │ with payment details
                           │
                           ▼
                    ┌─────────────┐
                    │  Confirmed  │ ← Final status
                    └─────────────┘

Additional Flow:
- Customer can reply at any time during Stage 2 (status maintained as 'Requested')
```

---

## Database Notes Evolution

### After Stage 1 (Inquiry):
```
status: "Inquiry"
note: "Initial inquiry received"
```

### After Stage 2 (Request - Book Now):
```
status: "Requested"
note: "Customer sent booking request on 2025-11-19 14:30:00"
```

### After Stage 2 (Acknowledgment Sent):
```
status: "Requested"
note: "Customer sent booking request on 2025-11-19 14:30:00
Acknowledgment email sent on 2025-11-19 14:30:15"
```

### After Stage 3 (Confirmation):
```
status: "Confirmed"
note: "Customer sent booking request on 2025-11-19 14:30:00
Acknowledgment email sent on 2025-11-19 14:30:15
Booking confirmed by team on 2025-11-19 15:00:00
Confirmation email sent on 2025-11-19 15:00:10"
```

### Optional: After Customer Reply (during Stage 2):
```
status: "Requested"
note: "Customer sent booking request on 2025-11-19 14:30:00
Acknowledgment email sent on 2025-11-19 14:30:15
Customer replied again on 2025-11-19 14:35:00"
```

---

## Key Features

### 1. Email Detection
The bot intelligently detects email type:
- **Staff Confirmation**: Contains "CONFIRM BOOKING" or similar keywords + booking ID (Stage 3)
- **Booking Request**: Contains "BOOKING REQUEST" in subject (Stage 2)
- **Customer Reply**: Subject starts with "Re:" (maintains Stage 2 status)
- **New Inquiry**: Everything else (Stage 1 - default)

### 2. Booking ID Format
- Format: `ISL-YYYYMMDD-XXXXXXXX`
- Example: `ISL-20251119-ABC12345`
- Always included in emails for tracking

### 3. Email Templates
- **Inquiry Email** (Stage 1): Shows available times with "Book Now" buttons - "Status: Inquiry - Awaiting Your Request"
- **Acknowledgment Email** (Stage 2): Confirms booking request received - "📬 Booking Request Received"
- **Confirmation Email** (Stage 3): Confirms booking with payment details - "✅ Booking Confirmed"
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

## Testing the Complete Three-Stage Flow

### Test Sequence:

**Stage 1: Inquiry**
1. **Send inquiry email** to theisland@bookings.teemail.io
   - Should create booking with status 'Inquiry'
   - Should receive email with available times
   - Email should display: "Status: Inquiry - Awaiting Your Request"

**Stage 2: Request**
2. **Click "Book Now"** in the email
   - Email client opens with "BOOKING REQUEST" subject
   - Send the email

3. **Bot should:**
   - Update status from 'Inquiry' to 'Requested'
   - Send acknowledgment email with "📬 Booking Request Received"
   - Update notes with timestamps

4. **(Optional) Reply to acknowledgment**
   - Status should stay 'Requested'
   - Note should be updated with timestamp

**Stage 3: Confirmation**
5. **Staff sends confirmation email** (manual step)
   - Include booking ID in subject or body
   - Include keywords: "CONFIRM BOOKING" or "BOOKING CONFIRMED"
   - Example: "Confirm Booking ISL-20251119-ABC12345"

6. **Bot should:**
   - Update status from 'Requested' to 'Confirmed'
   - Send confirmation email to customer with payment details
   - Email shows: "✅ Booking Confirmed"
   - Update notes with confirmation timestamps

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
