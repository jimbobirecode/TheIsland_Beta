#!/usr/bin/env python3
"""
Test Ryder Cup 2027 email parsing accuracy
"""

from enhanced_nlp import parse_booking_email

# Exact email from user
email_body = """I hope this finds you well.

On behalf of the team at The Experience Golf and in anticipation of The
Ryder Cup in 2027, I am reaching out to check availability and to ask you
to please consider our following request for a visiting group of 48 golfers
that we will be hosting around the event.

We are proud to have been recently appointed as an Authorized Partner to
Ryder Cup Travel Services for the 2027 Ryder Cup at Adare Manor.

We're planning on offering 3–4 days of golf for them as an extension of
that trip. We understand demand around the Ryder Cup will be high, so we're
looking to confirm what may be possible well in advance.

Whilst we appreciate it will be challenging to get enough tee times to
cater for all guests at one course each day, we can spread the group across
multiple if we need to and alternate each day.

Would you have availability that week that accommodates us for 16 golfers
on any given day i.e. 4x 4 balls.?

We appreciate you are just taking enquiries at the minute and don't plan to
decide for another few months but would like to get our hat in the ring and
see what we can offer our guests, all of whom want to have your course(s)
on their itinerary.

Our planned window is September 10th 2027 – 22nd and we can be flexible to
suit your schedule.

Could you please advise on:

   - The process and timeline for 2027 group bookings specifically early
   September
   - Group pricing, deposits, and any restrictions or requirements"""

email_subject = "Ryder Cup 2027 Group Inquiry"
from_email = "teemailbaltray@gmail.com"
from_name = "Baltray"

print("=" * 80)
print("Testing Ryder Cup 2027 Email Parsing")
print("=" * 80)

entity = parse_booking_email(email_body, email_subject, from_email, from_name)

print(f"\n📅 DATES EXTRACTED:")
print(f"   Found {len(entity.booking_dates)} dates:")
for date in entity.booking_dates:
    print(f"   - {date}")

print(f"\n👥 PLAYER COUNT: {entity.player_count}")

print(f"\n🎯 INTENT: {entity.intent.value}")

# Expected results
expected_dates = [f"2027-09-{day:02d}" for day in range(10, 23)]  # Sept 10-22, 2027
expected_players = 16

print("\n" + "=" * 80)
print("VALIDATION:")
print("=" * 80)

# Check dates
if set(entity.booking_dates) == set(expected_dates):
    print("✅ DATES: Correct! All Sept 10-22, 2027")
else:
    print(f"❌ DATES: Expected {len(expected_dates)} dates in Sept 2027")
    print(f"   Got: {entity.booking_dates}")
    missing = set(expected_dates) - set(entity.booking_dates)
    extra = set(entity.booking_dates) - set(expected_dates)
    if missing:
        print(f"   Missing: {sorted(missing)}")
    if extra:
        print(f"   Extra (should not be there): {sorted(extra)}")

# Check players
if entity.player_count == expected_players:
    print(f"✅ PLAYERS: Correct! {expected_players} golfers")
else:
    print(f"❌ PLAYERS: Expected {expected_players}, got {entity.player_count}")

# Overall result
dates_correct = set(entity.booking_dates) == set(expected_dates)
players_correct = entity.player_count == expected_players

if dates_correct and players_correct:
    print("\n🎉 ALL TESTS PASSED! Email parsing is accurate.")
else:
    print("\n⚠️  TESTS FAILED - Parsing needs improvement")
