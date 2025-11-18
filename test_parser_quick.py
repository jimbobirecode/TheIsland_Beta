#!/usr/bin/env python3
"""Quick test of email parser improvements"""

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

    # --- EXTRACT DATES ---
    date_patterns = [
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
                parsed_date = None

                if 'tomorrow' in date_str:
                    parsed_date = datetime.now() + timedelta(days=1)
                elif 'next' in date_str:
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
                    parsed_date = date_parser.parse(date_str, fuzzy=True, dayfirst=True, default=datetime.now().replace(day=1))

                    if parsed_date and not re.search(r'\d{4}', date_str):
                        if parsed_date.date() < datetime.now().date():
                            parsed_date = parsed_date.replace(year=parsed_date.year + 1)

                if parsed_date:
                    if parsed_date.date() >= datetime.now().date():
                        dates_found.append(parsed_date.strftime('%Y-%m-%d'))
            except (ValueError, TypeError):
                continue

    unique_dates = list(dict.fromkeys(dates_found))
    if unique_dates:
        result['preferred_date'] = unique_dates[0]
        if len(unique_dates) > 1:
            result['alternate_date'] = unique_dates[1]

    # --- EXTRACT TIME ---
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


if __name__ == '__main__':
    # Test cases
    test_cases = [
        'Looking for tee times March 18 4 players',
        'Need tee time for 2 players on March 25 at 10:30 AM',
        'March 18 morning 4 players',
        'Want to book for 3 golfers, March 20, afternoon',
        'Tee times available for March 22? 4 people',
    ]

    for test_email in test_cases:
        print('=' * 70)
        print(f'Test Email: "{test_email}"')
        result = parse_booking_from_email(test_email, '')
        print(f'\nParsed Results:')
        print(f'  Players: {result["num_players"]}')
        print(f'  Date: {result["preferred_date"]}')
        print(f'  Time: {result["preferred_time"]}')
        print(f'  Phone: {result["phone"] or "Not found"}')
        if result['alternate_date']:
            print(f'  Alternate Date: {result["alternate_date"]}')
        print()
