# Stripe Payment Integration Guide

This document explains how the Stripe payment integration works for the golf booking system.

## Overview

The booking system now supports automatic payment processing via Stripe. When customers receive available tee times via email, they can click "Book Now" to pay immediately and receive instant confirmation.

## Flow Diagram

```
1. Customer emails inquiry
   ↓
2. System checks availability
   ↓
3. Customer receives email with available times
   ↓
4. Customer clicks "Book Now" button
   ↓
5. Redirected to /book endpoint
   ↓
6. System creates Stripe checkout session
   ↓
7. Customer redirected to Stripe payment page
   ↓
8. Customer completes payment
   ↓
9. Stripe webhook notifies system (/webhook/stripe)
   ↓
10. System updates booking status to "Confirmed"
   ↓
11. System sends confirmation email
   ↓
12. Booking appears as "Confirmed" in dashboard
```

## Key Components

### 1. Environment Variables

Required Stripe configuration in `.env`:

```bash
# Stripe API Keys (from https://dashboard.stripe.com/apikeys)
STRIPE_SECRET_KEY=sk_test_... or sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Success/Cancel URLs
STRIPE_SUCCESS_URL=https://theisland.ie/booking-success
STRIPE_CANCEL_URL=https://theisland.ie/booking-cancelled

# Booking App URL (your Flask app URL)
BOOKING_APP_URL=https://theisland-email-bot.onrender.com
```

### 2. API Endpoints

#### `/book` (GET)
Simple redirect endpoint for email buttons.

**Parameters:**
- `booking_id` - Unique booking identifier
- `date` - Booking date (YYYY-MM-DD)
- `time` - Tee time (HH:MM)
- `players` - Number of players
- `email` - Customer email

**Behavior:**
1. Creates Stripe checkout session with booking details
2. Redirects customer to Stripe payment page
3. Pre-fills customer email
4. Includes booking metadata

**Example:**
```
https://theisland-email-bot.onrender.com/book?booking_id=ISL-20251209-8C9409B7&date=2025-12-15&time=10:30&players=4&email=customer@example.com
```

#### `/api/create-checkout-session` (POST)
Programmatic checkout session creation.

**Request Body:**
```json
{
  "booking_id": "ISL-20251209-8C9409B7",
  "date": "2025-12-15",
  "tee_time": "10:30",
  "players": 4,
  "total": 1300.00,
  "guest_email": "customer@example.com"
}
```

**Response:**
```json
{
  "sessionId": "cs_test_...",
  "url": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```

#### `/webhook/stripe` (POST)
Stripe webhook handler for payment events.

**Handles Events:**
- `checkout.session.completed` - Payment successful

**Actions on Success:**
1. Extracts booking data from session metadata
2. Updates booking status to "Confirmed"
3. Adds payment note with Stripe session ID
4. Sends confirmation email to customer

### 3. Booking Link Generation

The `build_booking_link()` function automatically detects if Stripe is configured:

**With Stripe:**
```python
https://theisland-email-bot.onrender.com/book?booking_id=ISL-...&date=2025-12-15&time=10:30&players=4&email=customer@example.com
```

**Without Stripe (fallback):**
```
mailto:clubname@bookings.teemail.io?subject=BOOKING REQUEST...
```

### 4. Email Templates

The inquiry email automatically shows different instructions based on Stripe configuration:

**With Stripe:**
- Step 1: Click "Book Now" for your preferred time
- Step 2: Complete your payment securely via Stripe
- Step 3: Receive instant confirmation via email

**Without Stripe:**
- Step 1: Click "Book Now" for your preferred time
- Step 2: Your email client will open with booking details
- Step 3: Send the email to request your tee time

### 5. Confirmation Email

When payment succeeds, customers receive an automatic confirmation email with:

- Payment confirmation badge
- Booking details (ID, date, time, players)
- Amount paid
- What's next instructions
- Cancellation policy

## Setup Instructions

### 1. Create Stripe Account

1. Sign up at https://stripe.com
2. Complete account verification
3. Get API keys from https://dashboard.stripe.com/apikeys

### 2. Configure Environment Variables

Add to your `.env` file or deployment platform (Render.com):

```bash
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_secret_here
STRIPE_SUCCESS_URL=https://theisland.ie/booking-success
STRIPE_CANCEL_URL=https://theisland.ie/booking-cancelled
BOOKING_APP_URL=https://theisland-email-bot.onrender.com
```

### 3. Set Up Stripe Webhook

1. Go to https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. Enter URL: `https://your-app-url.onrender.com/webhook/stripe`
4. Select events: `checkout.session.completed`
5. Copy webhook signing secret to `STRIPE_WEBHOOK_SECRET`

### 4. Create Success/Cancel Pages

Create simple HTML pages at:
- `https://theisland.ie/booking-success` - Thank you page
- `https://theisland.ie/booking-cancelled` - Booking cancelled page

### 5. Test the Integration

#### Test Mode (Recommended First)

1. Use test API keys (start with `sk_test_`)
2. Use test card: `4242 4242 4242 4242`
3. Any future expiry date
4. Any 3-digit CVC

#### Live Mode

1. Switch to live API keys (start with `sk_live_`)
2. Update webhook URL to live endpoint
3. Real cards will be charged

## Database Changes

The webhook handler updates bookings with:

```python
{
  'status': 'Confirmed',
  'note': 'Payment confirmed via Stripe on 2025-12-10 14:30:00
           Amount paid: €1300.00
           Stripe Session ID: cs_test_...'
}
```

## Dashboard Integration

Bookings appear in the dashboard with:
- Status: "Confirmed" (green badge)
- Note includes payment details and Stripe session ID
- No manual confirmation needed

## Troubleshooting

### Webhook Not Working

1. Check webhook URL is correct
2. Verify `STRIPE_WEBHOOK_SECRET` is set
3. Check Stripe dashboard for webhook delivery attempts
4. Review app logs for errors

### Payment Not Updating Booking

1. Check booking_id exists in database
2. Verify `update_booking_in_db()` is working
3. Check metadata is passed correctly to Stripe
4. Review webhook event payload in Stripe dashboard

### Email Not Sending

1. Verify SendGrid API key is valid
2. Check email address is verified in SendGrid
3. Review app logs for SendGrid errors
4. Check spam folder

## Security Considerations

1. **Webhook Signature Verification**: Always set `STRIPE_WEBHOOK_SECRET` for production
2. **SSL Required**: Stripe requires HTTPS for webhooks
3. **API Key Protection**: Never commit API keys to git
4. **Test Mode First**: Always test with test keys before going live

## Cost Breakdown

### Stripe Fees (Ireland)
- **Card payments**: 1.4% + €0.25 per transaction
- **Example**: €1,300 booking = €18.45 + €0.25 = €18.70 fee

### What You Keep
- €1,300.00 booking
- -€18.70 Stripe fee
- **= €1,281.30 net**

## Support

### Stripe Dashboard
- View payments: https://dashboard.stripe.com/payments
- View webhooks: https://dashboard.stripe.com/webhooks
- View customers: https://dashboard.stripe.com/customers
- View logs: https://dashboard.stripe.com/logs

### Testing Resources
- Test cards: https://stripe.com/docs/testing
- Webhook testing: https://stripe.com/docs/webhooks/test

## Fallback Behavior

If Stripe is not configured (no `STRIPE_SECRET_KEY`):
- System falls back to mailto links
- Old booking request flow still works
- No payment processing
- Manual confirmation required

This ensures the system works with or without Stripe.
