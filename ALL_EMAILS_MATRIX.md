# Complete Email Matrix - All System Emails

This document provides a comprehensive overview of **every email** sent by the booking system across all flows.

---

## Email Categories

1. **Inquiry Emails** - Initial customer contact
2. **Booking Request Emails** - Customer clicked "Book Now"
3. **Payment Emails** - Stripe checkout flow
4. **Waitlist Emails** - Waitlist system
5. **Confirmation Emails** - Manual staff confirmations

---

## Complete Email Matrix

### INQUIRY FLOW EMAILS

#### Email 1: Available Tee Times (Success)
| Property | Value |
|----------|-------|
| **Function** | `format_inquiry_email()` |
| **File** | island_email_bot.py:846 |
| **Trigger** | Customer sends initial inquiry email AND availability API returns results |
| **Recipient** | Customer (inquiry sender) |
| **Subject** | "Available Tee Times at Golf Club" |
| **When Sent** | After checking availability via Core API (success) |
| **Contains** | <ul><li>Available tee times table with dates and times</li><li>"Book Now" buttons for each time slot</li><li>Pricing information</li><li>Booking ID reference</li><li>Next steps instructions</li></ul> |
| **Button Actions** | Stripe checkout links (if configured) or mailto links |
| **Database Status** | Updated to "Inquiry" |

---

#### Email 2: No Availability
| Property | Value |
|----------|-------|
| **Function** | `format_no_availability_email()` |
| **File** | island_email_bot.py:1146 |
| **Trigger** | Customer sends inquiry AND API returns 0 available times |
| **Recipient** | Customer (inquiry sender) |
| **Subject** | "Tee Time Availability - Golf Club" |
| **When Sent** | After checking availability via Core API (empty results) |
| **Contains** | <ul><li>Sorry message - no availability for requested dates</li><li>Waitlist opt-in option</li><li>Alternative suggestions</li><li>Contact information</li></ul> |
| **Button Actions** | Optional waitlist opt-in mailto link |
| **Database Status** | Updated to "Inquiry" with note "No availability found" |

---

#### Email 3: Inquiry Received (Fallback)
| Property | Value |
|----------|-------|
| **Function** | `format_inquiry_received_email()` |
| **File** | island_email_bot.py:1232 |
| **Trigger** | One of: <ul><li>Customer inquiry has no dates</li><li>Availability API error/timeout</li><li>API returns non-200 status</li></ul> |
| **Recipient** | Customer (inquiry sender) |
| **Subject** | "Tee Time Inquiry - Golf Club" |
| **When Sent** | When system cannot check availability automatically |
| **Contains** | <ul><li>Thank you for inquiry message</li><li>"We'll respond within 24 hours" notice</li><li>Manual follow-up required message</li><li>Contact information</li></ul> |
| **Database Status** | Updated to "Inquiry" with note indicating manual follow-up needed |

---

### BOOKING REQUEST FLOW EMAILS

#### Email 4: Booking Request Acknowledgment
| Property | Value |
|----------|-------|
| **Function** | `format_acknowledgment_email()` |
| **File** | island_email_bot.py:944 |
| **Trigger** | Customer sends email with "BOOKING REQUEST" in subject (clicked "Book Now" button via mailto link) |
| **Recipient** | Customer (booking requester) |
| **Subject** | "Your Booking Request - Golf Club" |
| **When Sent** | Immediately after detecting booking request email |
| **Contains** | <ul><li>Acknowledgment of booking request</li><li>Booking ID</li><li>Requested date, time, players</li><li>"We'll confirm within 24 hours" message</li><li>What happens next instructions</li></ul> |
| **Database Status** | Status unchanged, note added "Acknowledgment email sent" |
| **Note** | Only sent if Stripe is NOT configured (fallback flow) |

---

#### Email 5: Manual Staff Confirmation
| Property | Value |
|----------|-------|
| **Function** | `format_confirmation_email()` |
| **File** | island_email_bot.py:1034 |
| **Trigger** | Staff member manually sends email with confirmation keywords + booking ID |
| **Recipient** | Customer (original booking requester) |
| **Subject** | "Booking Confirmed - Golf Club" |
| **When Sent** | When staff manually confirms a booking via email |
| **Contains** | <ul><li>Green confirmation badge</li><li>Booking details (ID, date, time, players)</li><li>Confirmed status</li><li>What's next instructions</li><li>Cancellation policy</li></ul> |
| **Database Status** | Updated to "Confirmed" |
| **Note** | Manual confirmation flow (no Stripe payment) |

---

### PAYMENT FLOW EMAILS

#### Email 6: Payment Confirmed (Instant)
| Property | Value |
|----------|-------|
| **Function** | `send_payment_confirmation_email()` |
| **File** | island_email_bot.py:2996 |
| **Trigger** | Stripe webhook `checkout.session.completed` for:<ul><li>All card payments (test & live)</li><li>SEPA Direct Debit (test mode only)</li><li>BACS Direct Debit (test mode only)</li></ul> |
| **Recipient** | Customer (email from checkout session) |
| **Subject** | "✅ Payment Confirmed - Booking [ID]" |
| **When Sent** | Instant (0 seconds after payment) |
| **Contains** | <ul><li>Green "Payment Confirmed" badge</li><li>Booking details (ID, date, time, players)</li><li>Amount paid (€)</li><li>Payment method</li><li>What's next instructions</li><li>Cancellation policy</li></ul> |
| **Database Status** | Updated to "Confirmed" |
| **Timeline** | Instant |

---

#### Email 7: Direct Debit Payment Pending
| Property | Value |
|----------|-------|
| **Function** | `send_direct_debit_pending_email()` |
| **File** | island_email_bot.py:3069 |
| **Trigger** | Stripe webhook `checkout.session.completed` for:<ul><li>SEPA Direct Debit (live mode only)</li><li>BACS Direct Debit (live mode only)</li></ul> |
| **Recipient** | Customer (email from checkout session) |
| **Subject** | "⏳ Booking Request Received - [ID]" |
| **When Sent** | Instant (Day 0 - checkout completion) |
| **Contains** | <ul><li>Orange "Payment Pending" badge</li><li>3-5 business day clearing timeline notice</li><li>Booking details with "Pending" status</li><li>Payment method info (SEPA or BACS)</li><li>"What Happens Next" explanation</li><li>Booking reserved message</li></ul> |
| **Database Status** | Updated to "Pending SEPA" or "Pending BACS" |
| **Timeline** | Day 0 (instant) |
| **Follow-up** | Email 8 sent after 3-5 days |

---

#### Email 8: Direct Debit Payment Cleared
| Property | Value |
|----------|-------|
| **Function** | `send_direct_debit_confirmed_email()` |
| **File** | island_email_bot.py:3156 |
| **Trigger** | Stripe webhook `charge.succeeded` for Direct Debit payments (3-5 days after checkout) |
| **Recipient** | Customer (email from payment intent) |
| **Subject** | "✅ Payment Confirmed (SEPA/BACS Cleared) - [ID]" |
| **When Sent** | 3-5 business days after checkout |
| **Contains** | <ul><li>Green "Payment Cleared" badge</li><li>Confirmation that Direct Debit payment cleared</li><li>Booking details with "Confirmed" status</li><li>Amount paid (€)</li><li>What's next instructions</li><li>Cancellation policy</li></ul> |
| **Database Status** | Updated from "Pending SEPA/BACS" to "Confirmed" |
| **Timeline** | Day 3-5 after checkout |
| **Note** | Only for live mode Direct Debit payments |

---

### WAITLIST FLOW EMAILS

#### Email 9: Waitlist Confirmation
| Property | Value |
|----------|-------|
| **Function** | `send_waitlist_confirmation_email()` |
| **File** | island_email_bot.py:1869 |
| **Trigger** | Customer sends waitlist opt-in email (clicks waitlist link from "No Availability" email) |
| **Recipient** | Customer (waitlist requester) |
| **Subject** | "Waitlist Confirmation - Golf Club" |
| **When Sent** | Immediately after processing waitlist opt-in |
| **Contains** | <ul><li>Green "Added to Waitlist" header</li><li>Waitlist ID</li><li>Requested dates, time, players</li><li>Status: "Active - Waiting"</li><li>"What happens next" explanation</li><li>Auto-check every few hours notice</li></ul> |
| **Database Table** | Added to `waitlist` table with status "Waiting" |
| **Follow-up** | Email 10 when availability opens |

---

#### Email 10: Waitlist Availability Notification
| Property | Value |
|----------|-------|
| **Function** | `format_waitlist_notification_email()` |
| **File** | email_bot_webhook.py:3633 |
| **Trigger** | Automated waitlist checker finds availability for customer's requested date |
| **Recipient** | Customer (from waitlist entry) |
| **Subject** | "Great News! Tee Times Available - Golf Club" |
| **When Sent** | When scheduled job detects availability (runs every 4 hours) |
| **Contains** | <ul><li>"Great News!" header</li><li>Waitlist request details</li><li>Table of available tee times</li><li>Instructions to reply or contact club</li><li>Waitlist ID reference</li></ul> |
| **Database Status** | Waitlist entry updated to "Notified" |
| **Scheduled Job** | `/api/waitlist/check-availability` endpoint |

---

## Email Trigger Summary Table

| Email # | Email Name | Trigger Source | Trigger Type |
|---------|------------|----------------|--------------|
| 1 | Available Tee Times | Customer inquiry email | Inbound email |
| 2 | No Availability | Customer inquiry email | Inbound email |
| 3 | Inquiry Received | Customer inquiry email | Inbound email |
| 4 | Booking Request Acknowledgment | Customer "Book Now" email | Inbound email |
| 5 | Manual Staff Confirmation | Staff confirmation email | Inbound email |
| 6 | Payment Confirmed (Instant) | Stripe checkout completed | Webhook |
| 7 | Direct Debit Pending | Stripe checkout completed | Webhook |
| 8 | Direct Debit Cleared | Stripe charge succeeded | Webhook |
| 9 | Waitlist Confirmation | Customer waitlist opt-in | Inbound email |
| 10 | Waitlist Notification | Scheduled availability check | Cron job |

---

## Email Frequency by Customer Journey

### Journey 1: Simple Inquiry → Stripe Payment (Card)
1. Customer sends inquiry email
2. ✉️ **Email 1**: Available Tee Times (instant)
3. Customer clicks "Book Now"
4. Customer pays with card on Stripe
5. ✉️ **Email 6**: Payment Confirmed (instant)

**Total emails: 2**

---

### Journey 2: Inquiry → Stripe Payment (SEPA/BACS Test Mode)
1. Customer sends inquiry email
2. ✉️ **Email 1**: Available Tee Times (instant)
3. Customer clicks "Book Now"
4. Customer pays with Direct Debit on Stripe (test mode)
5. ✉️ **Email 6**: Payment Confirmed (instant)

**Total emails: 2**
**Note:** Test mode auto-confirms Direct Debit instantly

---

### Journey 3: Inquiry → Stripe Payment (SEPA/BACS Live Mode)
1. Customer sends inquiry email
2. ✉️ **Email 1**: Available Tee Times (instant)
3. Customer clicks "Book Now"
4. Customer pays with Direct Debit on Stripe (live mode)
5. ✉️ **Email 7**: Direct Debit Pending (instant - Day 0)
6. Wait 3-5 business days
7. ✉️ **Email 8**: Direct Debit Cleared (Day 3-5)

**Total emails: 3**

---

### Journey 4: Inquiry → No Availability → Waitlist → Notification
1. Customer sends inquiry email
2. ✉️ **Email 2**: No Availability (instant)
3. Customer opts into waitlist
4. ✉️ **Email 9**: Waitlist Confirmation (instant)
5. System checks availability every 4 hours
6. When available: ✉️ **Email 10**: Waitlist Notification
7. Customer books via normal flow (Emails 1 → 6/7/8)

**Total emails: 3 + booking flow emails (2-3 more)**

---

### Journey 5: Inquiry → Manual Booking (No Stripe)
1. Customer sends inquiry email
2. ✉️ **Email 1**: Available Tee Times (with mailto links)
3. Customer clicks "Book Now" (sends email)
4. ✉️ **Email 4**: Booking Request Acknowledgment (instant)
5. Staff manually confirms
6. ✉️ **Email 5**: Manual Staff Confirmation

**Total emails: 3**

---

### Journey 6: Inquiry with Issues → Fallback
1. Customer sends inquiry email (no dates or API error)
2. ✉️ **Email 3**: Inquiry Received (instant)
3. Staff manually responds via email

**Total emails: 1 (+ manual follow-up)**

---

## Email Content Comparison

| Email | Header Color | Badge | Call-to-Action | Urgency |
|-------|-------------|-------|----------------|---------|
| **Email 1** - Available Times | Navy/Purple | ⛳ Available | "Book Now" buttons | High - Limited availability |
| **Email 2** - No Availability | Orange/Yellow | ⚠️ Notice | "Join Waitlist" | Medium - Alternative option |
| **Email 3** - Inquiry Received | Blue | 📧 Received | None | Low - Manual follow-up |
| **Email 4** - Acknowledgment | Blue | 📋 Received | None | Low - Awaiting confirmation |
| **Email 5** - Staff Confirmation | Green | ✅ Confirmed | None | Low - Booking complete |
| **Email 6** - Payment Confirmed | Green | ✅ Confirmed | None | Low - Booking complete |
| **Email 7** - DD Pending | Orange | ⏳ Pending | None | Medium - 3-5 day wait |
| **Email 8** - DD Cleared | Green | ✅ Cleared | None | Low - Booking complete |
| **Email 9** - Waitlist Confirmed | Green | ✅ Waitlist | None | Low - Passive waiting |
| **Email 10** - Waitlist Notify | Navy/Green | 🎉 Available | "Reply to book" | High - Act quickly |

---

## Database Status Changes from Emails

| Email | Status Before | Status After | Table |
|-------|---------------|--------------|-------|
| Email 1 | - | Inquiry | bookings |
| Email 2 | - | Inquiry | bookings |
| Email 3 | - | Inquiry | bookings |
| Email 4 | Requested | Requested | bookings |
| Email 5 | Any | Confirmed | bookings |
| Email 6 | Processing | Confirmed | bookings |
| Email 7 | Processing | Pending SEPA/BACS | bookings |
| Email 8 | Pending SEPA/BACS | Confirmed | bookings |
| Email 9 | - | Waiting | waitlist |
| Email 10 | Waiting | Notified | waitlist |

---

## SendGrid Integration

All emails are sent via the `send_email_sendgrid()` function:

**File:** island_email_bot.py:1335, email_bot_webhook.py:2899

**Required Environment Variables:**
- `SENDGRID_API_KEY` - SendGrid API key
- `FROM_EMAIL` - Sender email address
- `FROM_NAME` - Sender display name

**Email Headers:**
- From: `FROM_NAME <FROM_EMAIL>`
- Content-Type: `text/html`
- All emails use responsive HTML templates

---

## Email Template Features

All emails include:
- ✅ Responsive HTML design
- ✅ Mobile-friendly layout
- ✅ Brand colors and styling
- ✅ Clear call-to-action buttons
- ✅ Contact information footer
- ✅ Professional formatting

**Shared Components:**
- `get_email_header()` - Standard header with branding
- `get_email_footer()` - Standard footer with contact info
- `BRAND_COLORS` - Consistent color scheme across all emails

---

## Testing Email Flows

### Test Card Payments
1. Use test Stripe key: `sk_test_...`
2. Test card: `4242 4242 4242 4242`
3. Any future expiry, any CVC
4. Triggers: **Email 1** → **Email 6**

### Test SEPA Direct Debit (Test Mode)
1. Use test Stripe key: `sk_test_...`
2. Test IBAN: `DE89370400440532013000`
3. Auto-confirms instantly
4. Triggers: **Email 1** → **Email 6** (NOT Email 7+8)

### Test SEPA Direct Debit (Live Mode)
1. Use live Stripe key: `sk_live_...`
2. Real bank account required
3. 3-5 day clearing time
4. Triggers: **Email 1** → **Email 7** → (wait) → **Email 8**

### Test Waitlist Flow
1. Send inquiry for unavailable date
2. Triggers: **Email 2**
3. Click waitlist opt-in link
4. Triggers: **Email 9**
5. Run `/api/waitlist/check-availability` when dates open
6. Triggers: **Email 10**

---

## Email Logs

All email sends are logged with:
```
📧 Sending email to: customer@example.com
   Subject: Available Tee Times at Golf Club
✅ Email sent successfully
   Status code: 202
```

Check application logs to debug email delivery issues.

---

## Troubleshooting

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| No emails sent | SendGrid API key missing | Set `SENDGRID_API_KEY` environment variable |
| Email not received | Spam folder | Check spam/junk folder |
| Email 6 not sent | Webhook not configured | Add Stripe webhook for `checkout.session.completed` |
| Email 8 not sent | Missing webhook event | Add Stripe webhook for `charge.succeeded` |
| Email 10 not sent | Cron job not running | Set up scheduled job for `/api/waitlist/check-availability` |
| Email formatting broken | HTML rendering issue | Check email client compatibility |

---

## Email Rate Limits

**SendGrid Free Tier:**
- 100 emails/day
- Upgrade to paid plan for higher volumes

**Recommendation:**
- Monitor daily email volume
- Upgrade to SendGrid Essentials ($19.95/month) for 40,000 emails/month

---

## Future Email Enhancements

**Potential additions:**
1. Reminder emails (24 hours before tee time)
2. Review/feedback emails (after tee time)
3. Cancellation confirmation emails
4. Modification confirmation emails
5. Weather alerts for upcoming bookings
6. Promotional emails for quiet periods

---

## Quick Reference: All Email Functions

| Function Name | File | Line | Purpose |
|---------------|------|------|---------|
| `format_inquiry_email()` | island_email_bot.py | 846 | Email 1 - Available times |
| `format_no_availability_email()` | island_email_bot.py | 1146 | Email 2 - No availability |
| `format_inquiry_received_email()` | island_email_bot.py | 1232 | Email 3 - Fallback |
| `format_acknowledgment_email()` | island_email_bot.py | 944 | Email 4 - Acknowledgment |
| `format_confirmation_email()` | island_email_bot.py | 1034 | Email 5 - Staff confirmation |
| `send_payment_confirmation_email()` | island_email_bot.py | 2996 | Email 6 - Payment confirmed |
| `send_direct_debit_pending_email()` | island_email_bot.py | 3069 | Email 7 - DD pending |
| `send_direct_debit_confirmed_email()` | island_email_bot.py | 3156 | Email 8 - DD cleared |
| `send_waitlist_confirmation_email()` | island_email_bot.py | 1869 | Email 9 - Waitlist confirmed |
| `format_waitlist_notification_email()` | email_bot_webhook.py | 3633 | Email 10 - Availability opened |
| `send_email_sendgrid()` | island_email_bot.py | 1335 | Base sending function |

---

## Summary Statistics

**Total Unique Emails:** 10
**Automated Emails:** 10 (100%)
**Manual Emails:** 0
**Webhook-Triggered:** 2 (Emails 6, 7, 8)
**Inbound Email-Triggered:** 6 (Emails 1-5, 9)
**Cron-Triggered:** 1 (Email 10)

**Average Emails per Booking Journey:** 2-3 emails
**Maximum Emails per Journey:** 7 emails (inquiry → no availability → waitlist → notify → inquiry → payment DD live)
**Minimum Emails per Journey:** 2 emails (inquiry → payment card)

---

**Last Updated:** 2025-12-11
**Document Version:** 1.0
