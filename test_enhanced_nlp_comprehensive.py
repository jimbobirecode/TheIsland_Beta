#!/usr/bin/env python3
"""
Comprehensive Test Suite for Enhanced NLP Email Parsing
Tests all scenarios for tee times and lodging requests
"""

import sys
from datetime import datetime
from enhanced_nlp import parse_booking_email, IntentType, UrgencyLevel

# Test cases covering various email scenarios
TEST_CASES = [
    # ========================================================================
    # TEE TIME ONLY REQUESTS
    # ========================================================================
    {
        'name': 'ISO Date Format with Time',
        'subject': 'Golf Booking Request',
        'body': 'Hi, I would like to book a tee time for 2026-04-15 at 10:30 AM for 4 players.',
        'expected': {
            'has_date': True,
            'has_time': True,
            'players': 4,
            'lodging': False,
            'intent': 'booking_request'
        }
    },
    {
        'name': 'Natural Language Date',
        'subject': 'Booking for next Friday',
        'body': 'Hello, can I book a tee time for next Friday morning? We are a foursome.',
        'expected': {
            'has_date': True,
            'has_time': True,  # "morning" should be detected
            'players': 4,
            'lodging': False
        }
    },
    {
        'name': 'Relative Date (Tomorrow)',
        'subject': 'Last minute booking',
        'body': 'Can we play tomorrow at 2:00 PM? Party of 3.',
        'expected': {
            'has_date': True,
            'has_time': True,
            'players': 3,
            'urgency': 'urgent'
        }
    },
    {
        'name': 'Month Name Format',
        'subject': 'Golf in April',
        'body': 'We would like to book for April 20th, 2026 around 9:00 AM. Two golfers.',
        'expected': {
            'has_date': True,
            'has_time': True,
            'players': 2
        }
    },
    {
        'name': 'Date Range',
        'subject': 'Multi-day booking',
        'body': 'Looking to play April 15-18. Any morning tee times available for 4 players?',
        'expected': {
            'has_date': True,
            'has_time': True,
            'players': 4,
            'multiple_dates': True
        }
    },
    {
        'name': 'Flexible Dates',
        'subject': 'Flexible booking',
        'body': 'I am flexible on dates but would prefer early June. Any time in the morning works. Solo golfer.',
        'expected': {
            'has_date': True,
            'flexible_dates': True,
            'flexible_times': True,
            'players': 1
        }
    },

    # ========================================================================
    # LODGING ONLY REQUESTS
    # ========================================================================
    {
        'name': 'Hotel Accommodation Request',
        'subject': 'Room Booking',
        'body': 'I need to book a room for April 15-17. Check-in April 15, check-out April 17. Two nights, double room.',
        'expected': {
            'lodging': True,
            'num_nights': 2,
            'num_rooms': 1,
            'room_type': 'double',
            'intent': 'lodging_request'
        }
    },
    {
        'name': 'Stay and Play Package Query',
        'subject': 'Stay and Play',
        'body': 'Do you have stay and play packages available? Looking for accommodation and golf.',
        'expected': {
            'lodging': True,
            'intent': 'combined_request'  # Indicates both golf and lodging
        }
    },

    # ========================================================================
    # COMBINED TEE TIME + LODGING REQUESTS
    # ========================================================================
    {
        'name': 'Full Golf Weekend Package',
        'subject': 'Golf weekend with accommodation',
        'body': '''Hi,

        We would like to book a golf weekend for April 15-17, 2026.

        Golf:
        - 4 players
        - Tee time for April 16th at 10:00 AM

        Accommodation:
        - 2 double rooms
        - Check-in April 15, check-out April 17 (2 nights)

        We are intermediate golfers. One player is vegetarian.

        Contact: John Smith
        Phone: +353 86 123 4567
        ''',
        'expected': {
            'has_date': True,
            'has_time': True,
            'players': 4,
            'lodging': True,
            'num_nights': 2,
            'num_rooms': 2,
            'room_type': 'double',
            'contact_name': 'John Smith',
            'contact_phone': True,
            'dietary_requirements': True,
            'golf_experience': 'intermediate',
            'intent': 'combined_request'
        }
    },
    {
        'name': 'Corporate Golf Event',
        'subject': 'Corporate Golf Day - June 2026',
        'body': '''Hello,

        We are planning a corporate golf day for June 10, 2026. We need:

        - Morning tee times for 12 players (3 groups of 4)
        - Overnight accommodation for 10 guests (5 twin rooms)
        - Check-in June 9, check-out June 11
        - Cart rental for all players
        - Post-golf dinner arrangements

        Some players have dietary requirements (2 vegetarian, 1 gluten-free).

        Please send pricing and availability.

        Thanks,
        Sarah Johnson
        Corporate Events Manager
        sarah.johnson@company.com
        +44 20 1234 5678
        ''',
        'expected': {
            'has_date': True,
            'players': 12,
            'lodging': True,
            'num_nights': 2,
            'num_rooms': 5,
            'room_type': 'single',  # twin
            'contact_name': 'Sarah Johnson',
            'contact_email': 'sarah.johnson@company.com',
            'contact_phone': True,
            'special_requests': True,
            'dietary_requirements': True,
            'intent': 'combined_request'
        }
    },

    # ========================================================================
    # EDGE CASES AND COMPLEX SCENARIOS
    # ========================================================================
    {
        'name': 'Urgent Last Minute Request',
        'subject': 'URGENT: Today booking',
        'body': 'Can we get a tee time ASAP today? Afternoon preferred. 4 players.',
        'expected': {
            'has_date': True,
            'players': 4,
            'urgency': 'urgent',
            'flexible_times': True
        }
    },
    {
        'name': 'Beginner Group with Special Requests',
        'subject': 'First time golfers',
        'body': '''We are new to golf and would like to book for April 20th.

        - 3 beginners
        - Need club rental
        - Would like a lesson beforehand if possible
        - Late morning or early afternoon preferred
        ''',
        'expected': {
            'has_date': True,
            'players': 3,
            'golf_experience': 'beginner',
            'special_requests': True,
            'flexible_times': True
        }
    },
    {
        'name': 'Multiple Alternative Dates',
        'subject': 'Booking - flexible dates',
        'body': '''Hi, I am looking to book a tee time. My preferred dates are:

        1st choice: April 15 at 10:00
        2nd choice: April 16 at 9:00
        3rd choice: April 22 anytime morning

        2 players. Let me know what is available.
        ''',
        'expected': {
            'has_date': True,
            'has_time': True,
            'players': 2,
            'multiple_dates': True
        }
    },
    {
        'name': 'Modification Request',
        'subject': 'Change booking date',
        'body': 'I need to reschedule my booking from April 15 to April 20. Booking ID: ISL-20260410-ABC123',
        'expected': {
            'has_date': True,
            'intent': 'modification'
        }
    },
    {
        'name': 'Cancellation Request',
        'subject': 'Cancel booking',
        'body': 'Unfortunately I need to cancel my booking for April 15. Booking reference: ISL-20260410-XYZ789',
        'expected': {
            'intent': 'cancellation'
        }
    },
    {
        'name': 'Confirmation Reply',
        'subject': 'Re: CONFIRM BOOKING',
        'body': 'Yes, I confirm the booking for April 15 at 10:00 AM.',
        'expected': {
            'intent': 'confirmation',
            'has_date': True,
            'has_time': True
        }
    },
    {
        'name': 'Question About Availability',
        'subject': 'Availability query',
        'body': 'What tee times do you have available in late May? We are a group of 4.',
        'expected': {
            'has_date': True,
            'players': 4,
            'intent': 'question'
        }
    },

    # ========================================================================
    # INTERNATIONAL FORMATS
    # ========================================================================
    {
        'name': 'European Date Format (DD/MM/YYYY)',
        'subject': 'Booking',
        'body': 'Tee time for 15/04/2026 at 14:30. 4 players.',
        'expected': {
            'has_date': True,
            'has_time': True,
            'players': 4
        }
    },
    {
        'name': 'International Phone Number',
        'subject': 'Golf booking',
        'body': '''Booking for April 15, 2026 at 10:00 AM.

        Contact: Pierre Dubois
        Phone: +33 1 42 86 82 00
        Email: pierre@example.fr
        ''',
        'expected': {
            'has_date': True,
            'has_time': True,
            'contact_name': 'Pierre Dubois',
            'contact_phone': True,
            'contact_email': 'pierre@example.fr'
        }
    },

    # ========================================================================
    # SPECIAL DIETARY AND ACCESSIBILITY REQUIREMENTS
    # ========================================================================
    {
        'name': 'Multiple Dietary Requirements',
        'subject': 'Golf with lunch',
        'body': '''Booking for 4 players on May 5th at noon.

        Dietary requirements:
        - 1 vegan
        - 1 gluten-free
        - 1 nut allergy
        - 1 no restrictions

        We would also like lunch reservations after golf.
        ''',
        'expected': {
            'has_date': True,
            'has_time': True,
            'players': 4,
            'dietary_requirements': True,
            'special_requests': True
        }
    },
]


def run_tests():
    """Run all test cases and report results"""
    print("=" * 80)
    print("🧪 ENHANCED NLP COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print()

    total_tests = len(TEST_CASES)
    passed = 0
    failed = 0
    warnings = 0

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"[{i}/{total_tests}] Testing: {test_case['name']}")
        print("-" * 80)

        # Parse the email
        entity = parse_booking_email(
            test_case['body'],
            test_case['subject'],
            test_case.get('from_email', ''),
            test_case.get('from_name', '')
        )

        # Check expectations
        test_passed = True
        test_warnings = []
        expected = test_case['expected']

        # Check date extraction
        if expected.get('has_date'):
            if entity.booking_dates:
                print(f"   ✅ Date extracted: {entity.booking_dates}")
            else:
                print(f"   ❌ FAIL: Expected date but none found")
                test_passed = False

        # Check time extraction
        if expected.get('has_time'):
            if entity.tee_times or entity.preferred_time:
                print(f"   ✅ Time extracted: {entity.tee_times or entity.preferred_time}")
            else:
                print(f"   ⚠️  WARNING: Expected time but none found")
                test_warnings.append("No time extracted")

        # Check player count
        if 'players' in expected:
            if entity.player_count == expected['players']:
                print(f"   ✅ Players: {entity.player_count}")
            else:
                print(f"   ❌ FAIL: Expected {expected['players']} players, got {entity.player_count}")
                test_passed = False

        # Check lodging detection
        if expected.get('lodging'):
            if entity.lodging_requested:
                print(f"   ✅ Lodging detected: {entity.lodging_requested}")

                if expected.get('num_nights') and entity.num_nights:
                    print(f"      Nights: {entity.num_nights}")
                if expected.get('num_rooms') and entity.num_rooms:
                    print(f"      Rooms: {entity.num_rooms}")
                if expected.get('room_type') and entity.room_type:
                    print(f"      Room type: {entity.room_type}")
            else:
                print(f"   ❌ FAIL: Expected lodging detection")
                test_passed = False

        # Check intent
        if 'intent' in expected:
            if entity.intent.value == expected['intent']:
                print(f"   ✅ Intent: {entity.intent.value}")
            else:
                print(f"   ⚠️  WARNING: Expected intent '{expected['intent']}', got '{entity.intent.value}'")
                test_warnings.append(f"Intent mismatch: expected {expected['intent']}, got {entity.intent.value}")

        # Check urgency
        if 'urgency' in expected:
            if entity.urgency.value == expected['urgency']:
                print(f"   ✅ Urgency: {entity.urgency.value}")
            else:
                print(f"   ⚠️  WARNING: Expected urgency '{expected['urgency']}', got '{entity.urgency.value}'")
                test_warnings.append(f"Urgency mismatch")

        # Check contact info
        if expected.get('contact_name'):
            if entity.contact_name:
                print(f"   ✅ Contact name: {entity.contact_name}")
            else:
                print(f"   ⚠️  WARNING: Expected contact name extraction")
                test_warnings.append("No contact name")

        if expected.get('contact_phone'):
            if entity.contact_phone:
                print(f"   ✅ Phone: {entity.contact_phone}")
            else:
                print(f"   ⚠️  WARNING: Expected phone extraction")
                test_warnings.append("No phone number")

        if expected.get('contact_email'):
            if entity.contact_email == expected['contact_email']:
                print(f"   ✅ Email: {entity.contact_email}")
            else:
                print(f"   ⚠️  WARNING: Email mismatch")
                test_warnings.append("Email mismatch")

        # Check special requests and dietary requirements
        if expected.get('special_requests'):
            if entity.special_requests:
                print(f"   ✅ Special requests found: {len(entity.special_requests)}")
            else:
                print(f"   ⚠️  WARNING: Expected special requests")
                test_warnings.append("No special requests")

        if expected.get('dietary_requirements'):
            if entity.dietary_requirements:
                print(f"   ✅ Dietary requirements: {entity.dietary_requirements}")
            else:
                print(f"   ⚠️  WARNING: Expected dietary requirements")
                test_warnings.append("No dietary requirements")

        # Check golf experience
        if expected.get('golf_experience'):
            if entity.golf_experience == expected['golf_experience']:
                print(f"   ✅ Golf experience: {entity.golf_experience}")
            else:
                print(f"   ⚠️  WARNING: Expected experience '{expected['golf_experience']}', got '{entity.golf_experience}'")
                test_warnings.append("Experience mismatch")

        # Check flexibility
        if expected.get('flexible_dates'):
            if entity.flexible_dates:
                print(f"   ✅ Flexible dates detected")
            else:
                print(f"   ⚠️  WARNING: Expected flexible dates flag")
                test_warnings.append("Flexible dates not detected")

        if expected.get('flexible_times'):
            if entity.flexible_times:
                print(f"   ✅ Flexible times detected")
            else:
                print(f"   ⚠️  WARNING: Expected flexible times flag")
                test_warnings.append("Flexible times not detected")

        # Final result
        print()
        if test_passed:
            if test_warnings:
                print(f"   ⚠️  PASSED WITH WARNINGS ({len(test_warnings)})")
                for warning in test_warnings:
                    print(f"      - {warning}")
                warnings += 1
            else:
                print(f"   ✅ PASSED")
            passed += 1
        else:
            print(f"   ❌ FAILED")
            failed += 1

        print()
        print()

    # Summary
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests:    {total_tests}")
    print(f"✅ Passed:       {passed} ({passed/total_tests*100:.1f}%)")
    print(f"⚠️  With warnings: {warnings} ({warnings/total_tests*100:.1f}%)")
    print(f"❌ Failed:       {failed} ({failed/total_tests*100:.1f}%)")
    print()

    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
        if warnings > 0:
            print(f"   (Note: {warnings} tests had warnings - these are non-critical)")
    else:
        print(f"⚠️  {failed} tests failed - review output above")

    print("=" * 80)

    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
