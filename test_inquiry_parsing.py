#!/usr/bin/env python3
"""
Regression tests for parsing inbound tee time enquiries.

These cover the cases that previously produced no dates (so the bot replied
"please send us your dates" instead of fetching available tee times) and the
cases that produced a spurious extra date.

Run with: python3 test_inquiry_parsing.py
"""

import sys
from datetime import date, timedelta

from enhanced_nlp import parse_booking_email

# A month far enough ahead that a year-less date ("10th <Month>") can only mean
# this year - keeps the expectations stable whenever the tests are run.
TODAY = date.today()
# Anchored to the 15th so a "+2 days" range in the cases below never crosses
# into the next month
_ROUGHLY_TWO_MONTHS = TODAY + timedelta(days=60)
FUTURE = _ROUGHLY_TWO_MONTHS.replace(day=15)
MONTH_NAME = FUTURE.strftime('%B')
MONTH_ABBR = FUTURE.strftime('%b')
DAY = FUTURE.day
YEAR = FUTURE.year


def expected(day_offset: int = 0) -> str:
    return (FUTURE + timedelta(days=day_offset)).strftime('%Y-%m-%d')


def next_weekday(name: str) -> str:
    """The next occurrence of a weekday, never today"""
    index = ['monday', 'tuesday', 'wednesday', 'thursday',
             'friday', 'saturday', 'sunday'].index(name)
    days_ahead = (index - TODAY.weekday()) % 7 or 7
    return (TODAY + timedelta(days=days_ahead)).strftime('%Y-%m-%d')


CASES = [
    # (description, subject, body, expected dates, expected players)
    (
        'Day and month, no year',
        'Tee time enquiry',
        f'Hi, I would like to book a tee time for 4 players on {DAY}th {MONTH_NAME}. Thanks',
        [expected()],
        4,
    ),
    (
        'Weekday qualifying an explicit date is not a second date',
        'Tee time enquiry',
        f'Could we play on {FUTURE.strftime("%A")} {DAY}th {MONTH_NAME}? 4 players.',
        [expected()],
        4,
    ),
    (
        'Month first, abbreviated, no year',
        'Golf booking',
        f'We would like to play on {MONTH_ABBR} {DAY}, morning if possible. Booking for 3.',
        [expected()],
        3,
    ),
    (
        '"the Nth of Month" phrasing',
        'Enquiry',
        f'Can we book for the {DAY}th of {MONTH_NAME} for 4 players',
        [expected()],
        4,
    ),
    (
        'Explicit year does not also produce a year-less duplicate',
        'Enquiry',
        f'Hi, 8 players, {DAY}th {MONTH_NAME} {YEAR} please',
        [expected()],
        8,
    ),
    (
        'Relative weekday',
        'Re: tee times',
        'Any availability next Tuesday for three of us?',
        [next_weekday('tuesday')],
        3,
    ),
    (
        'Player count alongside a date',
        'Enquiry',
        f'Looking for 4 tee times on {DAY}th {MONTH_NAME}',
        [expected()],
        4,
    ),
    (
        'Date range covers every day in between',
        'Enquiry',
        f'Hi, we are 4 and would like to play {MONTH_NAME} {DAY}-{DAY + 2} {YEAR}',
        [expected(), expected(1), expected(2)],
        4,
    ),
    (
        'A number that is part of a date is not a player count',
        'Enquiry',
        f'We would like to play on {DAY}th {MONTH_NAME}',
        [expected()],
        None,
    ),
]


def main() -> int:
    failures = []

    for description, subject, body, want_dates, want_players in CASES:
        entity = parse_booking_email(body, subject, 'guest@example.com', 'Guest')

        errors = []
        if entity.booking_dates != want_dates:
            errors.append(f'dates: expected {want_dates}, got {entity.booking_dates}')
        if entity.player_count != want_players:
            errors.append(f'players: expected {want_players}, got {entity.player_count}')

        if errors:
            failures.append((description, errors))
            print(f'❌ {description}')
            for error in errors:
                print(f'     {error}')
        else:
            print(f'✅ {description}')

    print()
    if failures:
        print(f'{len(failures)} of {len(CASES)} cases failed')
        return 1

    print(f'All {len(CASES)} cases passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
