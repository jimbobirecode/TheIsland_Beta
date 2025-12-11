# Payment Flows & Email Matrix

## Complete Event and Email Matrix

### 1. CARD PAYMENT (Instant - Test & Live Mode)

| Event | Webhook | Status Change | Email Sent | Email Subject | Email Content |
|-------|---------|---------------|------------|---------------|---------------|
| Customer completes checkout | `checkout.session.completed` | → **Confirmed** | ✅ Instant confirmation | "✅ Payment Confirmed - Booking [ID]" | Full confirmation with booking details, amount paid, what's next |

**Timeline:** Instant (0 seconds)

---

### 2. SEPA DIRECT DEBIT - TEST MODE

| Event | Webhook | Status Change | Email Sent | Email Subject | Email Content |
|-------|---------|---------------|------------|---------------|---------------|
| Customer completes checkout | `checkout.session.completed` | → **Confirmed** | ✅ Instant confirmation | "✅ Payment Confirmed - Booking [ID]" | Full confirmation (same as card payment) |

**Timeline:** Instant (0 seconds)
**Note:** Test mode auto-confirms immediately for easier testing

---

### 3. SEPA DIRECT DEBIT - LIVE/PRODUCTION MODE

| Event | Webhook | Status Change | Email Sent | Email Subject | Email Content |
|-------|---------|---------------|------------|---------------|---------------|
| **Day 0:** Customer completes checkout | `checkout.session.completed` | → **Pending SEPA** | ✅ Pending notification | "⏳ Booking Request Received - [ID]" | Payment pending notice, 3-5 day timeline, booking reserved |
| **Day 3-5:** Payment clears | `charge.succeeded` | Pending SEPA → **Confirmed** | ✅ Final confirmation | "✅ Payment Confirmed (SEPA Cleared) - [ID]" | Payment cleared, booking confirmed, what's next |

**Timeline:** 3-5 business days
**Total Emails:** 2 (pending + confirmation)

---

### 4. BACS DIRECT DEBIT - TEST MODE

| Event | Webhook | Status Change | Email Sent | Email Subject | Email Content |
|-------|---------|---------------|------------|---------------|---------------|
| Customer completes checkout | `checkout.session.completed` | → **Confirmed** | ✅ Instant confirmation | "✅ Payment Confirmed - Booking [ID]" | Full confirmation (same as card payment) |

**Timeline:** Instant (0 seconds)
**Note:** Test mode auto-confirms immediately for easier testing

---

### 5. BACS DIRECT DEBIT - LIVE/PRODUCTION MODE

| Event | Webhook | Status Change | Email Sent | Email Subject | Email Content |
|-------|---------|---------------|------------|---------------|---------------|
| **Day 0:** Customer completes checkout | `checkout.session.completed` | → **Pending BACS** | ✅ Pending notification | "⏳ Booking Request Received - [ID]" | Payment pending notice, 3-5 day timeline, booking reserved |
| **Day 3-5:** Payment clears | `charge.succeeded` | Pending BACS → **Confirmed** | ✅ Final confirmation | "✅ Payment Confirmed (BACS Cleared) - [ID]" | Payment cleared, booking confirmed, what's next |

**Timeline:** 3-5 business days
**Total Emails:** 2 (pending + confirmation)

---

### 6. PAYMENT FAILURES (All Methods)

| Event | Webhook | Status Change | Email Sent | Action Taken |
|-------|---------|---------------|------------|--------------|
| Checkout cancelled | User cancels | No change | ❌ None | User redirected to cancel page |
| Direct Debit payment fails | `charge.failed` | No change | ❌ None | Logged in system, customer would need to retry |

---

## Status Summary

| Payment Method | Mode | Initial Status | Final Status | Status Duration |
|----------------|------|----------------|--------------|-----------------|
| **Card** | Test/Live | Confirmed | Confirmed | Instant |
| **SEPA** | Test | Confirmed | Confirmed | Instant |
| **SEPA** | Live | Pending SEPA | Confirmed | 3-5 days |
| **BACS** | Test | Confirmed | Confirmed | Instant |
| **BACS** | Live | Pending BACS | Confirmed | 3-5 days |

---

## Email Templates Reference

### Email 1: Instant Confirmation (Card & Direct Debit Test Mode)
**Function:** `send_payment_confirmation_email()`
**Trigger:** `checkout.session.completed` webhook
**Applies to:**
- ✅ All card payments (test & live)
- ✅ SEPA Direct Debit (test mode only)
- ✅ BACS Direct Debit (test mode only)

**Content:**
- Green confirmation badge
- Booking details (ID, date, time, players, amount)
- "What's Next" section
- Cancellation policy

---

### Email 2: Pending Notification (Direct Debit Live Mode Only)
**Function:** `send_direct_debit_pending_email()`
**Trigger:** `checkout.session.completed` webhook
**Applies to:**
- ✅ SEPA Direct Debit (live mode only)
- ✅ BACS Direct Debit (live mode only)

**Content:**
- Orange "Payment Pending" badge
- Notice about 3-5 day clearing time
- Booking details with "Pending" status
- "What Happens Next" section
- Payment method information (SEPA or BACS)

---

### Email 3: Direct Debit Cleared Confirmation (Live Mode Only)
**Function:** `send_direct_debit_confirmed_email()`
**Trigger:** `charge.succeeded` webhook (3-5 days later)
**Applies to:**
- ✅ SEPA Direct Debit (live mode only)
- ✅ BACS Direct Debit (live mode only)

**Content:**
- Green "Payment Cleared" badge
- Confirmation that Direct Debit payment has cleared
- Booking details with "Confirmed" status
- "What's Next" section
- Cancellation policy

---

## Database Status Values

### Valid Statuses
All these statuses are allowed in the database:

**General:**
- `Processing`
- `Inquiry`
- `Requested`
- `Confirmed` ← Final status for all successful payments
- `Booked`
- `Pending`
- `Rejected`
- `Provisional`
- `Cancelled`
- `Completed`

**Direct Debit Specific:**
- `Pending SEPA` ← SEPA payment initiated, waiting to clear
- `Pending BACS` ← BACS payment initiated, waiting to clear

**Note:** Lowercase variants are also allowed for backwards compatibility.

---

## Webhook Events We Listen To

| Event | When It Fires | What We Do |
|-------|---------------|------------|
| `checkout.session.completed` | Customer completes checkout (instant) | Detect payment method, set status, send appropriate email |
| `charge.succeeded` | Payment actually settles (3-5 days for Direct Debit) | Update "Pending X" to "Confirmed", send final email |
| `charge.failed` | Payment fails | Log the failure (no customer email) |
| `checkout.session.async_payment_succeeded` | SEPA completes async | Currently just logged (covered by charge.succeeded) |

---

## Mode Detection Logic

```python
# How the system detects test vs live mode
is_test_mode = session['id'].startswith('cs_test_') or STRIPE_SECRET_KEY.startswith('sk_test_')

if is_test_mode:
    # Direct Debit → Instant confirmation
    status = "Confirmed"
    email = send_payment_confirmation_email()
else:
    # Direct Debit → Pending, wait for clearing
    status = "Pending SEPA" or "Pending BACS"
    email = send_direct_debit_pending_email()
```

---

## Customer Experience Summary

### Test Mode - All Payment Methods
1. Customer pays
2. ✅ Instant "Payment Confirmed" email
3. ✅ Booking shows as "Confirmed" in dashboard
4. **Total wait time:** 0 seconds
5. **Total emails:** 1

---

### Live Mode - Card Payment
1. Customer pays with card
2. ✅ Instant "Payment Confirmed" email
3. ✅ Booking shows as "Confirmed" in dashboard
4. **Total wait time:** 0 seconds
5. **Total emails:** 1

---

### Live Mode - SEPA/BACS Direct Debit
1. Customer pays with Direct Debit
2. ⏳ Instant "Booking Request Received" email (pending)
3. ⏳ Booking shows as "Pending SEPA/BACS" in dashboard
4. **Wait 3-5 business days**
5. ✅ "Payment Confirmed (SEPA/BACS Cleared)" email
6. ✅ Booking shows as "Confirmed" in dashboard
7. **Total wait time:** 3-5 business days
8. **Total emails:** 2

---

## Payment Method Availability

### What Customers See at Checkout

**EUR Currency (Your Setup):**
- ✅ Card (all customers)
- ✅ SEPA Direct Debit (European customers)
- ❌ BACS Direct Debit (hidden - only works with GBP)

**GBP Currency (If you ever need it):**
- ✅ Card (all customers)
- ✅ BACS Direct Debit (UK customers)
- ❌ SEPA Direct Debit (hidden - only works with EUR)

---

## Troubleshooting Matrix

| Issue | Symptom | Cause | Solution |
|-------|---------|-------|----------|
| "payment method type invalid" error | Checkout fails | SEPA/BACS not enabled in Stripe | System auto-falls back to card-only |
| "valid_status constraint violation" | Database error | New statuses not in constraint | Auto-migration on startup fixes this |
| Only seeing Card + SEPA | BACS not appearing | Using EUR currency | Normal - BACS only works with GBP |
| Email not sent | No confirmation email | SendGrid issue | Check SendGrid logs |
| Pending status never clears | Stuck on "Pending SEPA" | `charge.succeeded` webhook not configured | Add webhook event in Stripe dashboard |

---

## Quick Reference: Email Count by Scenario

| Scenario | Emails Sent | Timeline |
|----------|-------------|----------|
| Card payment (any mode) | 1 | Instant |
| SEPA/BACS in test mode | 1 | Instant |
| SEPA/BACS in live mode | 2 | Instant + 3-5 days |
| Cancelled checkout | 0 | N/A |
| Failed payment | 0 | N/A |

---

## Fees Comparison

| Payment Method | Fee Structure | Example (€1,300) | What Customer Pays | What You Keep |
|----------------|---------------|------------------|-------------------|---------------|
| Card | 1.4% + €0.25 | €18.70 | €1,300 | €1,281.30 |
| SEPA | 0.8% (cap €2) | €2.00 | €1,300 | €1,298.00 |
| BACS | 0.8% (cap €2) | €2.00 | €1,300 | €1,298.00 |

**Savings with Direct Debit:** €16.70 per €1,300 booking!
