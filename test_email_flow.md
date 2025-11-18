# Email Flow Test Documentation

## Current Email Flow (After Fix)

### 1. Initial Booking Request
**Trigger:** Customer sends email to `theisland@bookings.teemail.io`

**Example Email:**
```
From: customer@example.com
Subject: Tee Time Request

Hi, I'd like to book a tee time for 2026-04-09 at 12:00 PM for 4 players.
```

**System Action:**
- Parses email for booking details
- Creates provisional booking in database
- **Sends ONE email:** Provisional acknowledgment

**Email Sent:**
- Subject: "Your Island Golf Club Booking Request"
- Content: Booking ID, requested date/time, estimated fee, instructions to confirm

---

### 2. Manual Confirmation
**Trigger:** Staff manually confirms via API endpoint or dashboard

**API Call:**
```
POST /api/confirm/ISL-20251118-D001
```

**System Action:**
- Updates booking status to 'confirmed' in database
- **Sends ONE email:** Confirmation email

**Email Sent:**
- Subject: "✅ Your Island Golf Club Booking is Confirmed!"
- Content: Confirmed booking details, arrival instructions, contact info

---

## Email Types

### Provisional Email (Acknowledgment)
- Used for: Initial booking requests
- Shows: Requested date/time, booking ID, estimated fee
- Action: Customer can reply to confirm or modify

### Confirmation Email
- Used for: Confirmed bookings (manual or API)
- Shows: Confirmed date/time, arrival instructions, payment details
- Action: Customer has confirmed booking

### Availability Email (NOT USED in current flow)
- Previously sent time slots when date was parsed
- Now removed from inbound webhook
- Could be used for future availability query feature

---

## Problem Fixed

**Before:**
1. Customer request → Availability email with time slots (WRONG)
2. Customer request → Provisional email (correct)
3. Result: 2 emails sent (duplicate/confusing)

**After:**
1. Customer request → Provisional acknowledgment only ✅
2. Manual confirmation → Confirmation email ✅
3. Result: 1 email per stage (clear flow)
