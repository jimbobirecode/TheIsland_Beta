#!/usr/bin/env python3
"""
Comprehensive Email Parsing Test Suite
Tests real-world scenarios to ensure accurate parsing
"""

import sys
from datetime import datetime, timedelta
from enhanced_nlp import parse_booking_email, IntentType, UrgencyLevel


class TestCase:
    """Test case with expected results"""
    def __init__(self, name, email_body, email_subject="", expected=None):
        self.name = name
        self.email_body = email_body
        self.email_subject = email_subject
        self.expected = expected or {}


# ============================================================================
# REAL-WORLD TEST CASES (Based on actual emails)
# ============================================================================

REAL_WORLD_TESTS = [
    # Ryder Cup Corporate Group (actual production email)
    TestCase(
        name="Ryder Cup 2027 Corporate Group",
        email_subject="",
        email_body="""I hope this finds you well.

On behalf of the team at The Experience Golf and in anticipation of The Ryder Cup in 2027, I am reaching out to check availability and to ask you to please consider our following request for a visiting group of 48 golfers that we will be hosting around the event.

We are proud to have been recently appointed as an Authorized Partner to Ryder Cup Travel Services for the 2027 Ryder Cup at Adare Manor.

We're planning on offering 3–4 days of golf for them as an extension of that trip. We understand demand around the Ryder Cup will be high, so we're looking to confirm what may be possible well in advance.

Whilst we appreciate it will be challenging to get enough tee times to cater for all guests at one course each day, we can spread the group across multiple if we need to and alternate each day.

Would you have availability that week that accommodates us for 16 golfers on any given day i.e. 4x 4 balls.?

We appreciate you are just taking enquiries at the minute and don't plan to decide for another few months but would like to get our hat in the ring and see what we can offer our guests, all of whom want to have your course(s) on their itinerary.

Our planned window is September 10th 2027 – 22nd and we can be flexible to suit your schedule.

Could you please advise on:
The process and timeline for 2027 group bookings specifically early September
Group pricing, deposits, and any restrictions or requirements""",
        expected={
            'min_dates': 13,  # Sept 10-22
            'dates_start': '2027-09-10',
            'dates_end': '2027-09-22',
            'players': 16,  # "16 golfers on any given day"
            'intent': 'question',
            'urgency': 'low',
            'lodging': False,
            'flexible_dates': True,
        }
    ),

    # Simple Weekend Booking
    TestCase(
        name="Simple Weekend Tee Time",
        email_subject="Golf this Saturday",
        email_body="Hi, can we book a tee time for this Saturday at 10am? Party of 4. Thanks!",
        expected={
            'has_date': True,
            'has_time': True,
            'players': 4,
            'intent': 'booking_request',
            'lodging': False,
        }
    ),

    # Golf + Hotel Package
    TestCase(
        name="Golf Weekend with Hotel",
        email_subject="Weekend golf package",
        email_body="""Hello,

We'd like to book a golf weekend for April 15-17, 2026.

Golf:
- 4 players
- Tee time April 16 at 10:00 AM

Accommodation:
- 2 double rooms
- Check-in April 15, check-out April 17

One player is vegetarian.

Contact: John Smith
Phone: +353 86 123 4567
Email: john@example.com""",
        expected={
            'has_date': True,
            'has_time': True,
            'players': 4,
            'lodging': True,
            'num_rooms': 2,
            'room_type': 'double',
            'dietary_requirements': True,
            'contact_phone': True,
            'intent': 'combined_request',
        }
    ),

    # Last Minute Urgent
    TestCase(
        name="Last Minute Urgent Booking",
        email_subject="URGENT: Today's tee time",
        email_body="Hi, any chance we can get a tee time this afternoon? 3 players, ASAP please!",
        expected={
            'has_date': True,  # "this afternoon" = today
            'players': 3,
            'urgency': 'urgent',
            'intent': 'booking_request',
        }
    ),

    # Flexible Multi-Day
    TestCase(
        name="Flexible Multi-Day Request",
        email_subject="Golf trip - flexible dates",
        email_body="""Looking to book a 3-day golf trip in late May or early June.

Preferred dates:
- May 28-30 (first choice)
- June 4-6 (second choice)
- Any dates in between work too

Group of 8 golfers. We can split into two foursomes.
Morning tee times preferred but we're flexible.""",
        expected={
            'has_date': True,
            'players': 8,
            'flexible_dates': True,
            'flexible_times': True,
            'intent': 'booking_request',
        }
    ),

    # European Date Format
    TestCase(
        name="European Date Format",
        email_subject="Booking for 15/04/2026",
        email_body="Hi, I'd like to book a tee time for 15/04/2026 at 14:30. 2 players please.",
        expected={
            'has_date': True,
            'dates_contains': '2026-04-15',
            'has_time': True,
            'players': 2,
            'intent': 'booking_request',
        }
    ),

    # Natural Language Dates
    TestCase(
        name="Natural Language - Next Friday",
        email_subject="Golf next Friday",
        email_body="Can we book for next Friday morning? Twosome. Around 9am would be perfect.",
        expected={
            'has_date': True,
            'has_time': True,
            'players': 2,
            'intent': 'booking_request',
        }
    ),

    # Confirmation Reply
    TestCase(
        name="Customer Confirmation Reply",
        email_subject="Re: CONFIRM BOOKING - April 15",
        email_body="Yes, I confirm the booking for April 15 at 10:00 AM. See you then!",
        expected={
            'has_date': True,
            'has_time': True,
            'intent': 'confirmation',
        }
    ),

    # Modification Request
    TestCase(
        name="Modification Request",
        email_subject="Change my booking",
        email_body="I need to reschedule my booking from April 15 to April 22. Same time (10am), same group of 4.",
        expected={
            'has_date': True,
            'players': 4,
            'intent': 'modification',
        }
    ),

    # Cancellation
    TestCase(
        name="Cancellation Request",
        email_subject="Cancel booking",
        email_body="Unfortunately I need to cancel my booking for April 15. Booking ref: ISL-20260410-ABC123",
        expected={
            'intent': 'cancellation',
        }
    ),

    # Large Corporate Event
    TestCase(
        name="Large Corporate Golf Day",
        email_subject="Corporate golf day - 40 players",
        email_body="""Hi,

Planning a corporate golf day for June 10, 2026.

Details:
- 40 players total
- Need 10 tee times (4-balls)
- Morning shotgun start preferred
- Lunch and dinner included
- 5 players are vegetarian, 2 gluten-free

Can you accommodate this? What's the pricing?

Thanks,
Sarah Johnson
Corporate Events
+44 20 1234 5678""",
        expected={
            'has_date': True,
            'players': 40,
            'contact_phone': True,
            'dietary_requirements': True,
            'intent': 'question',
        }
    ),

    # Lodging Only
    TestCase(
        name="Accommodation Only Request",
        email_subject="Room booking",
        email_body="Hi, do you have 3 double rooms available for May 15-18? No golf needed, just accommodation.",
        expected={
            'has_date': True,
            'lodging': True,
            'num_rooms': 3,
            'room_type': 'double',
            'intent': 'lodging_request',
        }
    ),

    # Beginner Group with Requests
    TestCase(
        name="Beginner Group with Special Requests",
        email_subject="First time golfers",
        email_body="""We're a group of 4 beginners looking to play on April 20.

We'll need:
- Club rental
- Buggy/cart
- Maybe a lesson beforehand?

Afternoon time preferred as we're not early risers!

Thanks,
Mike""",
        expected={
            'has_date': True,
            'players': 4,
            'golf_experience': 'beginner',
            'special_requests': True,
            'flexible_times': True,
        }
    ),

    # Question About Availability
    TestCase(
        name="General Availability Question",
        email_subject="Availability in June?",
        email_body="Hi, what tee times do you have available in early June? We're a group of 4 looking to play.",
        expected={
            'has_date': True,  # "early June"
            'players': 4,
            'intent': 'question',
        }
    ),

    # Multiple Alternative Dates
    TestCase(
        name="Multiple Alternative Date Options",
        email_subject="Booking - several date options",
        email_body="""Hi, looking to book for 2 players.

Our preferred dates in order:
1. April 15 at 10:00
2. April 16 at 9:00
3. April 22 anytime morning

Let me know what's available!""",
        expected={
            'has_date': True,
            'has_time': True,
            'players': 2,
        }
    ),

    # International Format
    TestCase(
        name="International Phone and Date",
        email_subject="Booking from France",
        email_body="""Bonjour,

I would like to book for 15 April 2026 at 10h00.

Contact: Pierre Dubois
Telephone: +33 1 42 86 82 00
Email: pierre.dubois@example.fr

Merci!""",
        expected={
            'has_date': True,
            'dates_contains': '2026-04-15',
            'has_time': True,
            'contact_phone': True,
            'contact_email': 'pierre.dubois@example.fr',
        }
    ),
]


def run_test(test_case: TestCase) -> dict:
    """Run a single test case and return results"""
    entity = parse_booking_email(
        test_case.email_body,
        test_case.email_subject,
        test_case.expected.get('contact_email', ''),
        ''
    )

    results = {
        'passed': True,
        'errors': [],
        'warnings': [],
        'entity': entity,
    }

    expected = test_case.expected

    # Check dates
    if expected.get('has_date'):
        if not entity.booking_dates:
            results['errors'].append("Expected dates but none found")
            results['passed'] = False

    if expected.get('min_dates'):
        if len(entity.booking_dates) < expected['min_dates']:
            results['errors'].append(f"Expected at least {expected['min_dates']} dates, got {len(entity.booking_dates)}")
            results['passed'] = False

    if expected.get('dates_start'):
        if not entity.booking_dates or entity.booking_dates[0] != expected['dates_start']:
            results['errors'].append(f"Expected start date {expected['dates_start']}, got {entity.booking_dates[0] if entity.booking_dates else 'None'}")
            results['passed'] = False

    if expected.get('dates_end'):
        if not entity.booking_dates or entity.booking_dates[-1] != expected['dates_end']:
            results['errors'].append(f"Expected end date {expected['dates_end']}, got {entity.booking_dates[-1] if entity.booking_dates else 'None'}")
            results['passed'] = False

    if expected.get('dates_contains'):
        if expected['dates_contains'] not in entity.booking_dates:
            results['errors'].append(f"Expected dates to contain {expected['dates_contains']}")
            results['passed'] = False

    # Check times
    if expected.get('has_time'):
        if not entity.tee_times and not entity.preferred_time:
            results['warnings'].append("Expected time but none found")

    # Check players
    if expected.get('players'):
        if entity.player_count != expected['players']:
            results['errors'].append(f"Expected {expected['players']} players, got {entity.player_count}")
            results['passed'] = False

    # Check lodging
    if expected.get('lodging') is not None:
        if entity.lodging_requested != expected['lodging']:
            results['errors'].append(f"Expected lodging={expected['lodging']}, got {entity.lodging_requested}")
            results['passed'] = False

    if expected.get('num_rooms'):
        if entity.num_rooms != expected['num_rooms']:
            results['warnings'].append(f"Expected {expected['num_rooms']} rooms, got {entity.num_rooms}")

    if expected.get('room_type'):
        if entity.room_type != expected['room_type']:
            results['warnings'].append(f"Expected room_type={expected['room_type']}, got {entity.room_type}")

    # Check intent
    if expected.get('intent'):
        if entity.intent.value != expected['intent']:
            results['errors'].append(f"Expected intent '{expected['intent']}', got '{entity.intent.value}'")
            results['passed'] = False

    # Check urgency
    if expected.get('urgency'):
        if entity.urgency.value != expected['urgency']:
            results['warnings'].append(f"Expected urgency '{expected['urgency']}', got '{entity.urgency.value}'")

    # Check flexibility
    if expected.get('flexible_dates'):
        if not entity.flexible_dates:
            results['warnings'].append("Expected flexible_dates=True")

    if expected.get('flexible_times'):
        if not entity.flexible_times:
            results['warnings'].append("Expected flexible_times=True")

    # Check contact info
    if expected.get('contact_phone'):
        if not entity.contact_phone:
            results['warnings'].append("Expected phone number extraction")

    if expected.get('contact_email'):
        if entity.contact_email != expected['contact_email']:
            results['warnings'].append(f"Expected email {expected['contact_email']}, got {entity.contact_email}")

    # Check special requests
    if expected.get('special_requests'):
        if not entity.special_requests:
            results['warnings'].append("Expected special requests")

    if expected.get('dietary_requirements'):
        if not entity.dietary_requirements:
            results['warnings'].append("Expected dietary requirements")

    if expected.get('golf_experience'):
        if entity.golf_experience != expected['golf_experience']:
            results['warnings'].append(f"Expected golf_experience={expected['golf_experience']}, got {entity.golf_experience}")

    return results


def print_test_result(test_case: TestCase, results: dict, test_num: int, total: int):
    """Print results for a single test"""
    status = "✅ PASS" if results['passed'] else "❌ FAIL"
    if results['warnings'] and results['passed']:
        status = "⚠️  PASS*"

    print(f"\n[{test_num}/{total}] {test_case.name}")
    print("-" * 80)

    entity = results['entity']

    # Show extracted data
    if entity.booking_dates:
        print(f"📅 Dates: {entity.booking_dates[:3]}{'...' if len(entity.booking_dates) > 3 else ''} ({len(entity.booking_dates)} total)")
    if entity.tee_times or entity.preferred_time:
        print(f"⏰ Times: {entity.tee_times or entity.preferred_time}")
    if entity.player_count:
        print(f"👥 Players: {entity.player_count}")
    if entity.lodging_requested:
        print(f"🏨 Lodging: {entity.num_rooms} room(s), {entity.num_nights} night(s)")
    print(f"🎯 Intent: {entity.intent.value}")
    print(f"⚡ Urgency: {entity.urgency.value}")
    print(f"📊 Confidence: {entity.confidence:.2f}")

    # Show errors and warnings
    if results['errors']:
        print(f"\n❌ ERRORS:")
        for error in results['errors']:
            print(f"   - {error}")

    if results['warnings']:
        print(f"\n⚠️  WARNINGS:")
        for warning in results['warnings']:
            print(f"   - {warning}")

    print(f"\n{status}")


def run_all_tests():
    """Run all test cases and report results"""
    print("=" * 80)
    print("🧪 COMPREHENSIVE EMAIL PARSING TEST SUITE")
    print("=" * 80)
    print(f"Running {len(REAL_WORLD_TESTS)} real-world test cases...")
    print()

    total_tests = len(REAL_WORLD_TESTS)
    passed = 0
    failed = 0
    warnings = 0

    for i, test_case in enumerate(REAL_WORLD_TESTS, 1):
        results = run_test(test_case)
        print_test_result(test_case, results, i, total_tests)

        if results['passed']:
            if results['warnings']:
                warnings += 1
            else:
                passed += 1
        else:
            failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests:       {total_tests}")
    print(f"✅ Passed:          {passed} ({passed/total_tests*100:.1f}%)")
    print(f"⚠️  Passed (warns):  {warnings} ({warnings/total_tests*100:.1f}%)")
    print(f"❌ Failed:          {failed} ({failed/total_tests*100:.1f}%)")
    print()

    success_rate = (passed + warnings) / total_tests * 100

    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
        if warnings > 0:
            print(f"   Note: {warnings} test(s) had warnings (non-critical)")
        print()
        print(f"✨ Success Rate: {success_rate:.1f}%")
    else:
        print(f"⚠️  {failed} test(s) failed")
        print(f"   Success Rate: {success_rate:.1f}%")
        print()
        print("Review failed tests above and fix parsing logic.")

    print("=" * 80)

    # Detailed stats
    print("\n📈 DETAILED STATISTICS")
    print("-" * 80)

    # Count different categories
    date_parsing_tests = sum(1 for tc in REAL_WORLD_TESTS if tc.expected.get('has_date'))
    player_count_tests = sum(1 for tc in REAL_WORLD_TESTS if tc.expected.get('players'))
    intent_tests = sum(1 for tc in REAL_WORLD_TESTS if tc.expected.get('intent'))
    lodging_tests = sum(1 for tc in REAL_WORLD_TESTS if tc.expected.get('lodging'))

    print(f"Date parsing tests:    {date_parsing_tests}")
    print(f"Player count tests:    {player_count_tests}")
    print(f"Intent classification: {intent_tests}")
    print(f"Lodging detection:     {lodging_tests}")
    print("=" * 80)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
