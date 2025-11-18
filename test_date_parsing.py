#!/usr/bin/env python3
"""Test script to verify date/time parsing improvements"""

import sys
sys.path.insert(0, '/home/user/TheIsland_Beta')

from island_email_bot import parse_booking_from_email

# Test case 1: ISO format date from the actual email
test_subject_1 = "CONFIRM BOOKING - 2026-04-09 at 12:00"
test_body_1 = """CONFIRM BOOKING

Booking Details:
- Booking ID: ISL-20251118-DC68
- Date: 2026-04-09
- Time: 12:00
- Players: 4
- Green Fee: €325 per player
- Total: €1300

Guest Email: teemailbaltray@gmail.com
"""

print("=" * 80)
print("TEST 1: ISO Format Date (YYYY-MM-DD)")
print("=" * 80)
print(f"Subject: {test_subject_1}")
print(f"Body Preview:\n{test_body_1[:150]}...")
print("\nParsing results:")
result_1 = parse_booking_from_email(test_body_1, test_subject_1)
print(f"  Players: {result_1.get('num_players')}")
print(f"  Date: {result_1.get('preferred_date')}")
print(f"  Time: {result_1.get('preferred_time')}")
print(f"  Phone: {result_1.get('phone')}")
print(f"\n✅ PASS" if result_1.get('preferred_date') == '2026-04-09' else f"❌ FAIL - Expected '2026-04-09', got '{result_1.get('preferred_date')}'")

# Test case 2: Different date formats
test_cases = [
    ("2026-04-09", "ISO format with hyphens"),
    ("2026/04/09", "ISO format with slashes"),
    ("09-04-2026", "European format DD-MM-YYYY"),
    ("April 9, 2026", "Month name format"),
    ("9th April 2026", "Day with ordinal"),
]

print("\n" + "=" * 80)
print("TEST 2: Multiple Date Formats")
print("=" * 80)

for date_str, description in test_cases:
    test_text = f"I would like to book a tee time on {date_str} at 2:00 PM for 4 players"
    result = parse_booking_from_email(test_text, "")
    status = "✅" if result.get('preferred_date') else "❌"
    print(f"{status} {description:30} -> Date: {result.get('preferred_date')}, Time: {result.get('preferred_time')}")

# Test case 3: Phone number parsing (should NOT match booking IDs)
print("\n" + "=" * 80)
print("TEST 3: Phone Number Parsing (Avoiding False Positives)")
print("=" * 80)

phone_tests = [
    ("Booking ID: ISL-20251118-DC68", None, "Should NOT match booking ID"),
    ("Phone: +353 1 843 6205", "+353 1 843 6205", "Should match international format"),
    ("Contact: 555-123-4567", "555-123-4567", "Should match US format"),
    ("Tel: (555) 123-4567", "(555) 123-4567", "Should match US format with parens"),
]

for text, expected, description in phone_tests:
    result = parse_booking_from_email(text, "")
    phone = result.get('phone')
    # Clean up expected for comparison
    if expected:
        expected_clean = expected.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        phone_clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '') if phone else ''
        status = "✅" if expected_clean in phone_clean else "❌"
    else:
        status = "✅" if phone is None else "❌"
    print(f"{status} {description:40} -> Phone: {phone}")

print("\n" + "=" * 80)
print("All tests complete!")
print("=" * 80)
