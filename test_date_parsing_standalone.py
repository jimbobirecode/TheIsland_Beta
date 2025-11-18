#!/usr/bin/env python3
"""Standalone test script to verify date/time parsing improvements"""

import re
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from typing import Dict

def parse_booking_from_email(text: str, subject: str = "") -> Dict:
    """
    Parse booking details from email content using intelligent pattern matching.
    Returns a dictionary with extracted booking information.
    """
    full_text = f"{subject}\n{text}".lower()
    result = {
        'num_players': None,
        'preferred_date': None,
        'preferred_time': None,
        'phone': None,
        'alternate_date': None
    }

    # --- EXTRACT NUMBER OF PLAYERS ---
    player_patterns = [
        r'(\d+)\s*(?:players?|people|persons?|golfers?|guests?)',
        r'(?:party|group)\s*(?:of|size)?\s*(\d+)',
        r'(?:foursome|4some)',  # Special case for 4
        r'(?:twosome|2some)',   # Special case for 2
        r'(?:threesome|3some)', # Special case for 3
        r'for\s*(\d+)',
        r'(\d+)\s*(?:ball|person)'
    ]

    for pattern in player_patterns:
        match = re.search(pattern, full_text)
        if match:
            if 'foursome' in pattern or '4some' in pattern:
                result['num_players'] = 4
            elif 'twosome' in pattern or '2some' in pattern:
                result['num_players'] = 2
            elif 'threesome' in pattern or '3some' in pattern:
                result['num_players'] = 3
            else:
                try:
                    num = int(match.group(1))
                    if 1 <= num <= 4:  # Valid golf group size
                        result['num_players'] = num
                except (ValueError, IndexError):
                    pass
            if result['num_players']:
                break

    # Default to 4 if not found
    if not result['num_players']:
        result['num_players'] = 4

    # --- EXTRACT PHONE NUMBER ---
    phone_patterns = [
        # Pattern with explicit phone keywords (highest priority)
        r'(?:phone|tel|mobile|cell|contact)\s*:?\s*([+]?[\d\s\-\(\)]{9,})',
        # International format with country code
        r'([+]\d{1,4}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4})',
        # Standard format with separators (hyphens, spaces, or parentheses)
        r'(\d{3}[\s\-]\d{3,4}[\s\-]\d{4})',
        r'(\(\d{3}\)[\s\-]?\d{3}[\s\-]?\d{4})',
    ]

    for pattern in phone_patterns:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            phone = match.group(1).strip()
            # Clean up phone number - keep only digits, +, (), -, and spaces
            phone = re.sub(r'[^\d+\(\)\-\s]', '', phone).strip()
            # Count digits only
            digit_count = len(re.sub(r'[^\d]', '', phone))
            # Require at least 10 digits for valid phone (avoid matching booking IDs like 20251118)
            # Or 7+ digits if it has proper formatting (spaces, hyphens, parentheses)
            has_formatting = bool(re.search(r'[\s\-\(\)]', phone))
            if (digit_count >= 10) or (digit_count >= 7 and has_formatting):
                result['phone'] = phone
                break

    # --- EXTRACT DATES ---
    # Common date patterns - ordered from most specific to least specific
    date_patterns = [
        # ISO date format (YYYY-MM-DD or YYYY/MM/DD) - most specific, check first
        r'(?:on|for|date[:\s]*)\s*(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})',
        r'(?<!\d)(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})(?!\d)',
        # Dates with keywords
        r'(?:on|for|date[:\s]*)\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        r'(?:on|for|date[:\s]*)\s*(\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{2,4})',
        r'(?:on|for|date[:\s]*)\s*((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{2,4})?)',
        r'(?:on|for|date[:\s]*)\s*(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))',
        r'(?:on|for|date[:\s]*)\s*(tomorrow)',
        # Month name + day (with or without year) - no keyword required
        r'\b((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{2,4})?)\b',
        r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)\b',
        # Numeric dates without keywords
        r'\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b',
        # Relative dates
        r'\b(tomorrow)\b',
        r'\b(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
    ]

    dates_found = []
    for pattern in date_patterns:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            date_str = match.group(1).strip()
            try:
                # Try to parse the date
                parsed_date = None

                if 'tomorrow' in date_str:
                    parsed_date = datetime.now() + timedelta(days=1)
                elif 'next' in date_str:
                    # Handle "next Friday" etc
                    days = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                           'friday': 4, 'saturday': 5, 'sunday': 6}
                    for day, offset in days.items():
                        if day in date_str:
                            today = datetime.now()
                            current_day = today.weekday()
                            days_ahead = (offset - current_day + 7) % 7
                            if days_ahead == 0:
                                days_ahead = 7
                            parsed_date = today + timedelta(days=days_ahead)
                            break
                else:
                    # Check if this is ISO format (YYYY-MM-DD or YYYY/MM/DD)
                    is_iso_format = re.match(r'^\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}$', date_str)

                    if is_iso_format:
                        # Parse ISO format with yearfirst=True
                        parsed_date = date_parser.parse(date_str, yearfirst=True, default=datetime.now().replace(day=1))
                    else:
                        # Use dateutil parser for flexible date parsing with dayfirst for European format
                        parsed_date = date_parser.parse(date_str, fuzzy=True, dayfirst=True, default=datetime.now().replace(day=1))

                    # If no year was specified and date is in the past, assume next year
                    if parsed_date and not re.search(r'\d{4}', date_str):
                        if parsed_date.date() < datetime.now().date():
                            parsed_date = parsed_date.replace(year=parsed_date.year + 1)

                if parsed_date:
                    # Only accept future dates (or today)
                    if parsed_date.date() >= datetime.now().date():
                        dates_found.append(parsed_date.strftime('%Y-%m-%d'))
            except (ValueError, TypeError):
                continue

    # Assign first two unique dates found
    unique_dates = list(dict.fromkeys(dates_found))  # Remove duplicates while preserving order
    if unique_dates:
        result['preferred_date'] = unique_dates[0]
        if len(unique_dates) > 1:
            result['alternate_date'] = unique_dates[1]

    # --- EXTRACT TIME ---
    # First check for specific times with context
    time_patterns = [
        # Specific times with keywords
        r'(?:time|tee\s*time)[:\s]+(\d{1,2}:\d{2}\s*(?:am|pm)?)',
        r'(?:time|tee\s*time)[:\s]+(\d{1,2}\s*(?:am|pm))',
        r'(?:at|around|about)\s+(\d{1,2}:\d{2}\s*(?:am|pm)?)',
        r'(?:at|around|about)\s+(\d{1,2}\s*(?:am|pm))',
        # Standalone times
        r'\b(\d{1,2}:\d{2}\s*(?:am|pm))\b',
        r'\b(\d{1,2}\s*(?:am|pm))\b',
        # General time periods
        r'\b(morning)\b',
        r'\b(afternoon)\b',
        r'\b(evening)\b',
        r'\b(early|late)\s+(morning|afternoon)\b',
    ]

    for pattern in time_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            time_str = match.group(1).strip().lower()

            # Convert general times to specific ranges
            if 'morning' in time_str:
                if 'early' in time_str:
                    result['preferred_time'] = '8:00 AM'
                elif 'late' in time_str:
                    result['preferred_time'] = '11:00 AM'
                else:
                    result['preferred_time'] = '9:00 AM'
            elif 'afternoon' in time_str:
                if 'early' in time_str:
                    result['preferred_time'] = '1:00 PM'
                elif 'late' in time_str:
                    result['preferred_time'] = '4:00 PM'
                else:
                    result['preferred_time'] = '2:00 PM'
            elif 'evening' in time_str:
                result['preferred_time'] = '5:00 PM'
            else:
                # Normalize time format
                try:
                    # Add AM/PM if missing and hour is ambiguous
                    if not re.search(r'am|pm', time_str, re.IGNORECASE):
                        hour_match = re.match(r'(\d{1,2})', time_str)
                        if hour_match:
                            hour = int(hour_match.group(1))
                            if hour >= 7 and hour <= 11:
                                time_str += ' AM'
                            elif hour >= 12:
                                time_str += ' PM'
                            elif hour >= 1 and hour <= 6:
                                time_str += ' PM'

                    result['preferred_time'] = time_str.upper()
                except:
                    result['preferred_time'] = time_str.upper()
            break

    # If no specific time found but "tee times" (plural) mentioned, default to morning preference
    if not result['preferred_time']:
        if re.search(r'\b(?:looking for|need|want|requesting|seeking)\s+(?:tee\s*)?times?\b', full_text, re.IGNORECASE):
            result['preferred_time'] = 'Morning (flexible)'
        elif re.search(r'\btee\s*times?\b', full_text, re.IGNORECASE):
            result['preferred_time'] = 'Flexible'

    return result


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
    ("April 9 2026", "Month name format"),
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
