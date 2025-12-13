#!/usr/bin/env python3
"""
Quick test for the Ryder Cup 2027 email parsing fix
"""

from enhanced_nlp import parse_booking_email

# The actual email that was problematic
email_body = """I hope this finds you well.

On behalf of the team at The Experience Golf and in anticipation of The Ryder Cup in 2027, I am reaching out to check availability and to ask you to please consider our following request for a visiting group of 48 golfers that we will be hosting around the event.

We are proud to have been recently appointed as an Authorized Partner to Ryder Cup Travel Services for the 2027 Ryder Cup at Adare Manor.

We're planning on offering 3–4 days of golf for them as an extension of that trip. We understand demand around the Ryder Cup will be high, so we're looking to confirm what may be possible well in advance.

Whilst we appreciate it will be challenging to get enough tee times to cater for all guests at one course each day, we can spread the group across multiple if we need to and alternate each day.

Would you have availability that week that accommodates us for 16 golfers on any given day i.e. 4x 4 balls.?

We appreciate you are just taking enquiries at the minute and don't plan to decide for another few months but would like to get our hat in the ring and see what we can offer our guests, all of whom want to have your course(s) on their itinerary.

Our planned window is September 10th 2027 – 22nd and we can be flexible to suit your schedule.

Could you please advise on:
The process and timeline for 2027 group bookings specifically early September
Group pricing, deposits, and any restrictions or requirements
"""

email_subject = ""
from_email = "teemailbaltray@gmail.com"

print("=" * 80)
print("TESTING RYDER CUP 2027 EMAIL PARSING")
print("=" * 80)
print()

entity = parse_booking_email(email_body, email_subject, from_email, "Baltray")

print("RESULTS:")
print("-" * 80)
print(f"📅 Dates extracted: {entity.booking_dates}")
print(f"   Expected: September 10-22, 2027 (13 dates)")
print()
print(f"👥 Players: {entity.player_count}")
print(f"   Expected: 16 (golfers on any given day)")
print()
print(f"🎯 Intent: {entity.intent.value}")
print(f"   Expected: question")
print()
print(f"⚡ Urgency: {entity.urgency.value}")
print(f"   Expected: low (2027 is well in advance)")
print()
print(f"🏨 Lodging requested: {entity.lodging_requested}")
print(f"   Expected: False")
print()
print(f"📊 Confidence: {entity.confidence:.2f}")
print()

# Validation
print("=" * 80)
print("VALIDATION:")
print("=" * 80)

errors = []
warnings = []

# Check dates
if len(entity.booking_dates) == 13:
    # Check if all dates are in September 2027
    all_sept_2027 = all('2027-09' in date for date in entity.booking_dates)
    if all_sept_2027:
        # Check range
        if entity.booking_dates[0] == '2027-09-10' and entity.booking_dates[-1] == '2027-09-22':
            print("✅ Dates: CORRECT (Sept 10-22, 2027)")
        else:
            errors.append(f"Date range wrong: {entity.booking_dates[0]} to {entity.booking_dates[-1]}")
    else:
        errors.append(f"Dates not all in Sept 2027: {entity.booking_dates}")
else:
    errors.append(f"Expected 13 dates, got {len(entity.booking_dates)}: {entity.booking_dates}")

# Check players
if entity.player_count == 16:
    print("✅ Players: CORRECT (16 golfers per day)")
elif entity.player_count == 48:
    warnings.append("Got total group size (48) instead of per-day size (16)")
else:
    errors.append(f"Expected 16 players, got {entity.player_count}")

# Check intent
if entity.intent.value == 'question':
    print("✅ Intent: CORRECT (question)")
else:
    errors.append(f"Expected intent 'question', got '{entity.intent.value}'")

# Check urgency
if entity.urgency.value == 'low':
    print("✅ Urgency: CORRECT (low)")
else:
    warnings.append(f"Expected urgency 'low', got '{entity.urgency.value}'")

# Check lodging
if not entity.lodging_requested:
    print("✅ Lodging: CORRECT (not requested)")
else:
    errors.append("Lodging incorrectly detected")

print()
if errors:
    print("❌ ERRORS:")
    for error in errors:
        print(f"   - {error}")
    print()

if warnings:
    print("⚠️  WARNINGS:")
    for warning in warnings:
        print(f"   - {warning}")
    print()

if not errors:
    if warnings:
        print("✅ TEST PASSED WITH WARNINGS")
    else:
        print("✅ ALL TESTS PASSED!")
else:
    print(f"❌ TEST FAILED ({len(errors)} errors)")

print("=" * 80)
