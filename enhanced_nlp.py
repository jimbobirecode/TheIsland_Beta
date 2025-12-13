"""
Enhanced NLP Module for Golf Club Email Parsing
Comprehensive parsing for tee times and lodging requests using spaCy + dateparser

This module provides maximum coverage to ensure NO inbound opportunities are missed.
"""

import re
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# Try to import spaCy, fallback to None if not available
try:
    import spacy
    SPACY_AVAILABLE = True
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        # Model not downloaded yet, will use without spaCy
        SPACY_AVAILABLE = False
        nlp = None
except ImportError:
    SPACY_AVAILABLE = False
    nlp = None

# Try to import dateparser, fallback to python-dateutil
try:
    import dateparser
    DATEPARSER_AVAILABLE = True
except ImportError:
    DATEPARSER_AVAILABLE = False

from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Email intent classification"""
    NEW_INQUIRY = "new_inquiry"
    BOOKING_REQUEST = "booking_request"
    CONFIRMATION = "confirmation"
    MODIFICATION = "modification"
    CANCELLATION = "cancellation"
    QUESTION = "question"
    LODGING_REQUEST = "lodging_request"
    COMBINED_REQUEST = "combined_request"  # Tee time + lodging
    UNKNOWN = "unknown"


class UrgencyLevel(Enum):
    """Urgency classification"""
    URGENT = "urgent"          # ASAP, urgent, today, tomorrow
    HIGH = "high"              # Within 3 days
    NORMAL = "normal"          # 4-14 days
    LOW = "low"                # 15+ days
    UNKNOWN = "unknown"


@dataclass
class BookingEntity:
    """Structured booking information extracted from email"""
    # Tee time information
    booking_dates: List[str] = field(default_factory=list)  # Multiple possible dates
    tee_times: List[str] = field(default_factory=list)      # Multiple possible times
    preferred_date: Optional[str] = None                     # Primary date
    preferred_time: Optional[str] = None                     # Primary time
    flexible_dates: bool = False                             # "flexible", "any day"
    flexible_times: bool = False                             # "any time", "morning"

    # Lodging information
    lodging_requested: bool = False
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    num_nights: Optional[int] = None
    num_rooms: Optional[int] = None
    room_type: Optional[str] = None  # "single", "double", "suite"

    # Contact and group information
    player_count: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    # Additional details
    special_requests: List[str] = field(default_factory=list)
    dietary_requirements: List[str] = field(default_factory=list)
    golf_experience: Optional[str] = None  # "beginner", "intermediate", "advanced"

    # Intent and urgency
    intent: IntentType = IntentType.UNKNOWN
    urgency: UrgencyLevel = UrgencyLevel.UNKNOWN

    # Confidence scores
    date_confidence: float = 0.0
    time_confidence: float = 0.0
    lodging_confidence: float = 0.0

    # Raw extracted data for debugging
    raw_dates: List[str] = field(default_factory=list)
    raw_times: List[str] = field(default_factory=list)
    extracted_entities: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def confidence(self) -> float:
        """
        Overall confidence score (for email_bot_webhook.py compatibility)
        Average of date and time confidence, or just date if no time
        """
        if self.time_confidence > 0:
            return (self.date_confidence + self.time_confidence) / 2
        elif self.date_confidence > 0:
            return self.date_confidence
        else:
            # If we have any data, give at least 0.3 confidence
            if self.booking_dates or self.player_count or self.lodging_requested:
                return 0.3
            return 0.0

    @property
    def dates(self):
        """
        Dates object for email_bot_webhook.py compatibility
        Returns an object with start_date and end_date attributes
        """
        class DateRange:
            def __init__(self, start_date=None, end_date=None):
                self.start_date = start_date
                self.end_date = end_date

        start = None
        end = None

        if self.booking_dates:
            # Parse first date as start_date
            try:
                start = datetime.strptime(self.booking_dates[0], '%Y-%m-%d')
            except:
                pass

            # If multiple dates, last one is end_date
            if len(self.booking_dates) > 1:
                try:
                    end = datetime.strptime(self.booking_dates[-1], '%Y-%m-%d')
                except:
                    pass

        return DateRange(start, end)


class EnhancedEmailParser:
    """Comprehensive email parser for golf bookings and lodging"""

    # Extensive date pattern regexes
    DATE_PATTERNS = [
        # ISO formats (most specific)
        r'(?:on|for|date[:\s]*)\s*(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})',
        r'(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})',

        # Month name formats
        r'(?:on|for|date[:\s]*)\s*(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})',
        r'(?:on|for|date[:\s]*)\s*((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*\d{2,4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})',
        r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*\d{2,4})',

        # Relative dates
        r'(?:on|for|date[:\s]*)\s*(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))',
        r'(?:on|for|date[:\s]*)\s*(this\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))',
        r'\b(this\s+(?:morning|afternoon|evening))\b',  # "this afternoon"
        r'\b(today)\b',
        r'\b(tomorrow)\b',
        r'(?:on|for|date[:\s]*)\s*(tomorrow)',
        r'(?:on|for|date[:\s]*)\s*(day\s+after\s+tomorrow)',
        r'(?:on|for|date[:\s]*)\s*(next\s+week)',
        r'(?:on|for|date[:\s]*)\s*(next\s+month)',
        r'(in\s+\d+\s+days?)',
        r'(in\s+\d+\s+weeks?)',
        r'(in\s+\d+\s+months?)',

        # Numeric formats
        r'(?:on|for|date[:\s]*)\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',

        # Natural language
        r'(first\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+in\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)',
        r'(last\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+in\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)',
        r'(mid\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)',
        r'(early\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)',
        r'(late\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)',
        r'(end\s+of\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)',
        r'(beginning\s+of\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)',
    ]

    # Extensive time pattern regexes
    TIME_PATTERNS = [
        # Specific times with context
        r'(?:time|tee\s*time|t-time|start)[:\s]+(\d{1,2}:\d{2}\s*(?:am|pm)?)',
        r'(?:at|around|about|approximately)\s+(\d{1,2}:\d{2}\s*(?:am|pm)?)',
        r'(?:at|around|about|approximately)\s+(\d{1,2}\s*(?:am|pm))',

        # Group format
        r'(?:group|tee)\s*\d+[:\s]+(\d{1,2}:\d{2}\s*(?:am|pm)?)',

        # General patterns
        r'(\d{1,2}:\d{2}\s*(?:am|pm))',
        r'(\d{1,2}\s*(?:am|pm))',
        r'(\d{1,2}:\d{2})',  # 24-hour format

        # Natural language times
        r'(early\s+morning)',
        r'(mid\s*morning)',
        r'(late\s+morning)',
        r'(noon|midday)',
        r'(early\s+afternoon)',
        r'(mid\s*afternoon)',
        r'(late\s+afternoon)',
        r'(evening)',
        r'(morning)',
        r'(afternoon)',
        r'(sunrise)',
        r'(sunset)',
    ]

    # Lodging keywords (comprehensive list)
    LODGING_KEYWORDS = [
        # Direct accommodation terms
        r'\b(?:room|rooms|accommodation|accommodations|lodging|lodge|stay|staying)\b',
        r'\b(?:hotel|motel|resort|inn|bed and breakfast|b&b|bnb)\b',
        r'\b(?:overnight|sleep|night|nights)\b',
        r'\b(?:check[\s-]?in|check[\s-]?out)\b',

        # Booking related
        r'\b(?:book a room|reserve a room|need a room|room for)\b',
        r'\b(?:place to stay|somewhere to stay)\b',

        # Package deals
        r'\b(?:stay and play|golf package|accommodation package)\b',
        r'\b(?:inclusive|all-inclusive|package deal)\b',
    ]

    # Urgency keywords
    URGENCY_KEYWORDS = {
        'urgent': [r'\burgent\b', r'\basap\b', r'\bas soon as possible\b', r'\bimmediate\b', r'\bright away\b'],
        'high': [r'\btoday\b', r'\btomorrow\b', r'\bthis week\b', r'\bshort notice\b', r'\blast minute\b'],
        'normal': [r'\bnext week\b', r'\bupcoming\b', r'\bsoon\b'],
    }

    # Flexibility indicators
    FLEXIBILITY_KEYWORDS = {
        'dates': [r'\bflexible\b', r'\bany day\b', r'\bany date\b', r'\bopen\b', r'\bdoesn\'t matter\b'],
        'times': [r'\bany time\b', r'\bflexible\b', r'\bwhenever\b', r'\banytime\b'],
    }

    def __init__(self):
        """Initialize the parser"""
        self.logger = logging.getLogger(__name__)
        if SPACY_AVAILABLE and nlp:
            self.logger.info("spaCy model loaded successfully")
        else:
            self.logger.warning("spaCy not available, using fallback parsing")

        if DATEPARSER_AVAILABLE:
            self.logger.info("dateparser available")
        else:
            self.logger.warning("dateparser not available, using python-dateutil")

    def parse_booking_email(self, email_body: str, email_subject: str = "",
                           from_email: str = "", from_name: str = "") -> BookingEntity:
        """
        Comprehensive email parsing - main entry point

        Args:
            email_body: Email body text
            email_subject: Email subject line
            from_email: Sender email address
            from_name: Sender name

        Returns:
            BookingEntity with all extracted information
        """
        entity = BookingEntity()

        # Combine subject and body for analysis
        full_text = f"{email_subject}\n\n{email_body}"
        full_text_lower = full_text.lower()

        # Store contact info
        entity.contact_email = from_email or self._extract_email(email_body)
        entity.contact_name = from_name or self._extract_name(email_body, full_text)

        # Extract all date/time information
        self._extract_dates_comprehensive(full_text, entity)
        self._extract_times_comprehensive(full_text, entity)

        # Extract lodging information
        self._extract_lodging_info(full_text, full_text_lower, entity)

        # Extract contact and group details
        entity.contact_phone = self._extract_phone(email_body)
        entity.player_count = self._extract_player_count(email_body)

        # Extract special requests and preferences
        entity.special_requests = self._extract_special_requests(email_body)
        entity.dietary_requirements = self._extract_dietary_requirements(email_body)
        entity.golf_experience = self._extract_golf_experience(email_body)

        # Classify intent and urgency
        entity.intent = self._classify_intent(full_text, full_text_lower, entity)
        entity.urgency = self._classify_urgency(full_text, full_text_lower, entity)

        # Check for flexibility
        entity.flexible_dates = self._check_flexibility('dates', full_text_lower)
        entity.flexible_times = self._check_flexibility('times', full_text_lower)

        # Use spaCy if available for enhanced entity extraction
        if SPACY_AVAILABLE and nlp:
            self._enhance_with_spacy(full_text, entity)

        # Calculate confidence scores
        self._calculate_confidence_scores(entity)

        return entity

    def _extract_dates_comprehensive(self, text: str, entity: BookingEntity):
        """Extract all possible dates using multiple methods"""
        dates_found = set()
        text_lower = text.lower()

        # Method 1: Regex patterns
        for pattern in self.DATE_PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                date_str = match.group(1) if match.groups() else match.group(0)
                entity.raw_dates.append(date_str)

                # Try to parse the date
                parsed_date = self._parse_date_flexible(date_str)
                if parsed_date:
                    dates_found.add(parsed_date)

        # Method 2: dateparser library (if available)
        if DATEPARSER_AVAILABLE:
            # Split text into sentences and try to parse each
            sentences = re.split(r'[.!?\n]', text)
            for sentence in sentences:
                if len(sentence) > 10:  # Skip very short sentences
                    parsed = dateparser.parse(
                        sentence,
                        settings={
                            'PREFER_DATES_FROM': 'future',
                            'RELATIVE_BASE': datetime.now(),
                            'RETURN_AS_TIMEZONE_AWARE': False
                        }
                    )
                    if parsed and parsed > datetime.now() - timedelta(days=1):
                        date_str = parsed.strftime('%Y-%m-%d')
                        dates_found.add(date_str)

        # Method 3: Look for date ranges
        date_ranges = self._extract_date_ranges(text_lower)
        dates_found.update(date_ranges)

        # Store all found dates
        entity.booking_dates = sorted(list(dates_found))

        # Set preferred date (first one found, or most specific)
        if entity.booking_dates:
            entity.preferred_date = entity.booking_dates[0]

    def _extract_times_comprehensive(self, text: str, entity: BookingEntity):
        """Extract all possible tee times"""
        times_found = set()
        text_lower = text.lower()

        # Extract using regex patterns
        for pattern in self.TIME_PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                time_str = match.group(1) if match.groups() else match.group(0)
                entity.raw_times.append(time_str)

                # Normalize the time
                normalized_time = self._normalize_time(time_str)
                if normalized_time:
                    times_found.add(normalized_time)

        # Store all found times
        entity.tee_times = sorted(list(times_found))

        # Set preferred time
        if entity.tee_times:
            entity.preferred_time = entity.tee_times[0]

    def _extract_lodging_info(self, text: str, text_lower: str, entity: BookingEntity):
        """Extract lodging/accommodation information"""
        lodging_score = 0

        # Check for lodging keywords
        for pattern in self.LODGING_KEYWORDS:
            matches = re.findall(pattern, text_lower)
            lodging_score += len(matches)

        if lodging_score > 0:
            entity.lodging_requested = True
            entity.lodging_confidence = min(lodging_score / 10.0, 1.0)

            # Extract number of nights
            nights_match = re.search(r'(\d+)\s*nights?', text_lower)
            if nights_match:
                entity.num_nights = int(nights_match.group(1))

            # Extract number of rooms
            # Try specific patterns first
            rooms_patterns = [
                r'(\d+)\s*(?:double|single|twin|queen|king|suite)?\s*rooms?',
                r'(\d+)\s*rooms?',
            ]

            rooms_found = False
            for pattern in rooms_patterns:
                rooms_match = re.search(pattern, text_lower)
                if rooms_match:
                    entity.num_rooms = int(rooms_match.group(1))
                    rooms_found = True
                    break

            if not rooms_found:
                # Default to 1 room if not specified
                entity.num_rooms = 1

            # Extract room type
            if re.search(r'\b(?:single|twin)\b', text_lower):
                entity.room_type = 'single'
            elif re.search(r'\b(?:double|queen|king)\b', text_lower):
                entity.room_type = 'double'
            elif re.search(r'\bsuite\b', text_lower):
                entity.room_type = 'suite'

            # Extract check-in/check-out dates
            checkin_match = re.search(r'check[\s-]?in[:\s]+([^\n,]+)', text_lower)
            if checkin_match:
                entity.check_in_date = self._parse_date_flexible(checkin_match.group(1))

            checkout_match = re.search(r'check[\s-]?out[:\s]+([^\n,]+)', text_lower)
            if checkout_match:
                entity.check_out_date = self._parse_date_flexible(checkout_match.group(1))

            # If we have booking dates but no check-in, assume check-in is the booking date
            if entity.booking_dates and not entity.check_in_date:
                entity.check_in_date = entity.booking_dates[0]

            # Calculate nights if we have check-in/out dates
            if entity.check_in_date and entity.check_out_date and not entity.num_nights:
                try:
                    checkin = datetime.strptime(entity.check_in_date, '%Y-%m-%d')
                    checkout = datetime.strptime(entity.check_out_date, '%Y-%m-%d')
                    entity.num_nights = (checkout - checkin).days
                except:
                    pass

    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number"""
        # International format
        phone_patterns = [
            r'\+\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{1,4}',
            r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
            r'\d{3}[\s.-]?\d{3}[\s.-]?\d{4}',
            r'(?:phone|mobile|cell|tel)[:\s]+([+\d\s\(\)\-\.]+)',
        ]

        for pattern in phone_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                phone = match.group(1) if match.groups() else match.group(0)
                # Clean up the phone number
                phone = re.sub(r'[^\d+]', '', phone)
                if len(phone) >= 10:
                    return phone
        return None

    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email address from text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        return match.group(0) if match else None

    def _extract_name(self, text: str, full_text: str) -> Optional[str]:
        """Extract contact name"""
        # Look for common name patterns
        name_patterns = [
            r'(?:from|name|contact)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # Name at start
            r'(?:regards|sincerely|thanks),?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ]

        for pattern in name_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                return match.group(1).strip()

        # Use spaCy for person entity recognition
        if SPACY_AVAILABLE and nlp:
            doc = nlp(full_text[:500])  # First 500 chars
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    return ent.text

        return None

    def _extract_player_count(self, text: str) -> Optional[int]:
        """Extract number of players"""
        text_lower = text.lower()

        # Look for "X golfers on any given day" or "X golfers per day" (for corporate groups) - HIGHEST PRIORITY
        per_day_patterns = [
            r'(\d+)\s*golfers?\s*(?:on any given day|per day|each day|a day)',
            r'(\d+)\s*players?\s*(?:on any given day|per day|each day|a day)',
        ]

        for pattern in per_day_patterns:
            match = re.search(pattern, text_lower)
            if match:
                count = int(match.group(1))
                if 1 <= count <= 100:  # Allow larger corporate groups
                    return count

        # Look for general number patterns - SECOND PRIORITY
        player_patterns = [
            r'(?:group|party)\s*of\s*(\d+)\s*(?:players?|people|persons?|golfers?)',  # "group of 8 golfers"
            r'(\d+)\s*(?:players?|people|persons?|golfers?|guests?)',
            r'(?:party|group)\s*of\s*(\d+)',
        ]

        for pattern in player_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                # Avoid matching dates like "15 April" as "15 players"
                before = text_lower[max(0, match.start()-20):match.start()]
                after = text_lower[match.end():match.end()+20]

                # Check if month names are nearby (avoid date false positives)
                month_names = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
                is_date = any(month in before or month in after for month in month_names)

                # Also check for "split into X foursomes" which indicates grouping, not total
                is_grouping = 'split into' in before or 'into' in before

                if not is_date and not is_grouping:
                    count = int(match.group(1))
                    if 1 <= count <= 100:
                        return count

        # Special golf terms - LAST PRIORITY (only if no explicit number found)
        golf_groups = {
            'foursome': 4, 'four-some': 4, 'four ball': 4,
            'threesome': 3, 'three-some': 3, 'three ball': 3,
            'twosome': 2, 'two-some': 2, 'two ball': 2,
            'single': 1, 'solo': 1,
        }

        for term, count in golf_groups.items():
            if term in text_lower:
                return count

        return None

    def _extract_special_requests(self, text: str) -> List[str]:
        """Extract special requests"""
        requests = []
        text_lower = text.lower()

        # Look for request indicators
        request_keywords = [
            r'(?:special request|request|need|require|would like)[:\s]+([^.!?\n]+)',
            r'(?:also|additionally|furthermore)[:\s,]+([^.!?\n]+)',
        ]

        for pattern in request_keywords:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                request = match.group(1).strip()
                if len(request) > 10 and len(request) < 200:
                    requests.append(request)

        # Look for specific amenities
        amenities = ['buggy', 'cart', 'caddy', 'caddie', 'club rental', 'club hire',
                    'lesson', 'coaching', 'practice', 'driving range']
        for amenity in amenities:
            if amenity in text_lower:
                requests.append(f"Mentioned: {amenity}")

        return requests

    def _extract_dietary_requirements(self, text: str) -> List[str]:
        """Extract dietary requirements"""
        requirements = []
        text_lower = text.lower()

        dietary_keywords = [
            'vegetarian', 'vegan', 'gluten-free', 'dairy-free',
            'nut allergy', 'shellfish allergy', 'halal', 'kosher',
            'pescatarian', 'lactose intolerant', 'celiac'
        ]

        for keyword in dietary_keywords:
            if keyword in text_lower:
                requirements.append(keyword)

        return requirements

    def _extract_golf_experience(self, text: str) -> Optional[str]:
        """Extract golf experience level"""
        text_lower = text.lower()

        if any(word in text_lower for word in ['beginner', 'new to golf', 'first time', 'never played']):
            return 'beginner'
        elif any(word in text_lower for word in ['intermediate', 'average', 'casual']):
            return 'intermediate'
        elif any(word in text_lower for word in ['advanced', 'experienced', 'low handicap', 'scratch']):
            return 'advanced'
        elif any(word in text_lower for word in ['professional', 'pro', 'tour']):
            return 'professional'

        return None

    def _classify_intent(self, text: str, text_lower: str, entity: BookingEntity) -> IntentType:
        """Classify email intent"""
        # Question keywords (check FIRST before other classifications)
        question_indicators = [
            'could you please advise', 'could you advise', 'please advise',
            'would you have availability', 'do you have availability',
            'do you have', 'can you accommodate', 'what tee times',
            'what is the', 'what are the', 'how much', 'what\'s the pricing',
            'what dates', 'any availability', 'any tee times',
            'reaching out to check', 'checking availability',
            'question', 'query', 'wondering', 'curious',
            'can you tell', 'what is', 'how do', 'when can',
            'please confirm', 'could you confirm',  # Asking for confirmation, not giving it
            'let me know', 'could you let me know',
        ]

        for indicator in question_indicators:
            if indicator in text_lower:
                return IntentType.QUESTION

        # Confirmation keywords (customer confirming a booking)
        # Use word boundaries to avoid false positives
        confirmation_patterns = [
            r'\b(?:i |we )?confirm(?:ing)?\b',
            r'\byes,? (?:i|we) (?:confirm|accept|agree)\b',
            r'\bproceed with (?:the )?booking\b',
        ]

        for pattern in confirmation_patterns:
            if re.search(pattern, text_lower):
                # But not if they're asking questions
                if 'could you' not in text_lower and 'please advise' not in text_lower:
                    return IntentType.CONFIRMATION

        # Cancellation keywords
        if any(word in text_lower for word in ['cancel', 'cancellation', 'no longer', 'withdraw']):
            return IntentType.CANCELLATION

        # Modification keywords
        if any(word in text_lower for word in ['change', 'modify', 'reschedule', 'move', 'update']):
            return IntentType.MODIFICATION

        # Lodging + Tee time = Combined
        if entity.lodging_requested and entity.booking_dates:
            return IntentType.COMBINED_REQUEST

        # Lodging only
        if entity.lodging_requested and not entity.booking_dates:
            return IntentType.LODGING_REQUEST

        # Booking request (has dates/times)
        if entity.booking_dates or entity.tee_times:
            return IntentType.BOOKING_REQUEST

        # Default to new inquiry
        if any(word in text_lower for word in ['book', 'reserve', 'enquiry', 'inquiry', 'interested']):
            return IntentType.NEW_INQUIRY

        return IntentType.UNKNOWN

    def _classify_urgency(self, text: str, text_lower: str, entity: BookingEntity) -> UrgencyLevel:
        """Classify urgency level"""
        # Check urgency keywords
        for level, patterns in self.URGENCY_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    if level == 'urgent':
                        return UrgencyLevel.URGENT
                    elif level == 'high':
                        return UrgencyLevel.HIGH
                    elif level == 'normal':
                        return UrgencyLevel.NORMAL

        # Check based on booking date
        if entity.preferred_date:
            try:
                booking_date = datetime.strptime(entity.preferred_date, '%Y-%m-%d')
                days_until = (booking_date - datetime.now()).days

                if days_until <= 1:
                    return UrgencyLevel.URGENT
                elif days_until <= 3:
                    return UrgencyLevel.HIGH
                elif days_until <= 14:
                    return UrgencyLevel.NORMAL
                else:
                    return UrgencyLevel.LOW
            except:
                pass

        return UrgencyLevel.UNKNOWN

    def _check_flexibility(self, flex_type: str, text_lower: str) -> bool:
        """Check if dates or times are flexible"""
        patterns = self.FLEXIBILITY_KEYWORDS.get(flex_type, [])
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def _enhance_with_spacy(self, text: str, entity: BookingEntity):
        """Use spaCy for enhanced entity extraction"""
        if not nlp:
            return

        try:
            doc = nlp(text[:1000])  # Process first 1000 chars

            # Extract entities
            for ent in doc.ents:
                if ent.label_ not in entity.extracted_entities:
                    entity.extracted_entities[ent.label_] = []
                entity.extracted_entities[ent.label_].append(ent.text)

                # Use DATE entities to supplement date extraction
                if ent.label_ == 'DATE':
                    parsed = self._parse_date_flexible(ent.text)
                    if parsed and parsed not in entity.booking_dates:
                        entity.booking_dates.append(parsed)

                # Use TIME entities
                if ent.label_ == 'TIME':
                    normalized = self._normalize_time(ent.text)
                    if normalized and normalized not in entity.tee_times:
                        entity.tee_times.append(normalized)

                # Use PERSON entities if name not found
                if ent.label_ == 'PERSON' and not entity.contact_name:
                    entity.contact_name = ent.text
        except Exception as e:
            self.logger.warning(f"spaCy processing error: {e}")

    def _calculate_confidence_scores(self, entity: BookingEntity):
        """Calculate confidence scores for extracted data"""
        # Date confidence
        if entity.preferred_date:
            confidence = 0.5  # Base confidence
            if len(entity.booking_dates) == 1:
                confidence += 0.3  # Higher if only one date found
            if entity.raw_dates:
                confidence += 0.2  # Higher if we have raw matches
            entity.date_confidence = min(confidence, 1.0)

        # Time confidence
        if entity.preferred_time:
            confidence = 0.5
            if len(entity.tee_times) == 1:
                confidence += 0.3
            if entity.raw_times:
                confidence += 0.2
            entity.time_confidence = min(confidence, 1.0)

        # Lodging confidence already set in _extract_lodging_info

    def _parse_date_flexible(self, date_str: str) -> Optional[str]:
        """Parse date string using multiple methods"""
        if not date_str or len(date_str) < 3:
            return None

        date_str = date_str.strip()

        # Try dateparser first (if available)
        if DATEPARSER_AVAILABLE:
            try:
                parsed = dateparser.parse(
                    date_str,
                    settings={
                        'PREFER_DATES_FROM': 'future',
                        'RELATIVE_BASE': datetime.now(),
                        'RETURN_AS_TIMEZONE_AWARE': False
                    }
                )
                if parsed:
                    return parsed.strftime('%Y-%m-%d')
            except:
                pass

        # Try python-dateutil
        try:
            parsed = dateutil_parser.parse(date_str, fuzzy=True, default=datetime.now())
            # Only accept future dates (or today)
            if parsed.date() >= datetime.now().date():
                return parsed.strftime('%Y-%m-%d')
        except:
            pass

        # Handle relative dates manually
        today = datetime.now()
        date_str_lower = date_str.lower()

        if 'today' in date_str_lower or 'this morning' in date_str_lower or 'this afternoon' in date_str_lower or 'this evening' in date_str_lower:
            return today.strftime('%Y-%m-%d')
        elif 'tomorrow' in date_str_lower:
            return (today + timedelta(days=1)).strftime('%Y-%m-%d')
        elif 'day after tomorrow' in date_str_lower:
            return (today + timedelta(days=2)).strftime('%Y-%m-%d')
        elif 'next week' in date_str_lower:
            return (today + timedelta(weeks=1)).strftime('%Y-%m-%d')
        elif 'next month' in date_str_lower:
            return (today + relativedelta(months=1)).strftime('%Y-%m-%d')

        # Handle "in X days/weeks/months"
        in_match = re.search(r'in\s+(\d+)\s+(day|week|month)s?', date_str_lower)
        if in_match:
            count = int(in_match.group(1))
            unit = in_match.group(2)
            if unit == 'day':
                return (today + timedelta(days=count)).strftime('%Y-%m-%d')
            elif unit == 'week':
                return (today + timedelta(weeks=count)).strftime('%Y-%m-%d')
            elif unit == 'month':
                return (today + relativedelta(months=count)).strftime('%Y-%m-%d')

        return None

    def _normalize_time(self, time_str: str) -> Optional[str]:
        """Normalize time to HH:MM format"""
        if not time_str:
            return None

        time_str = time_str.strip().lower()

        # Handle natural language times
        time_mappings = {
            'early morning': '07:00', 'mid morning': '09:00', 'late morning': '11:00',
            'morning': '09:00', 'noon': '12:00', 'midday': '12:00',
            'early afternoon': '13:00', 'mid afternoon': '15:00', 'late afternoon': '17:00',
            'afternoon': '14:00', 'evening': '18:00',
            'sunrise': '06:30', 'sunset': '19:00',
        }

        for key, value in time_mappings.items():
            if key in time_str:
                return value

        # Try to parse as time
        try:
            # Remove extra spaces
            time_str = ' '.join(time_str.split())

            # Try different time formats
            for fmt in ['%I:%M %p', '%I %p', '%H:%M', '%I:%M%p', '%I%p']:
                try:
                    dt = datetime.strptime(time_str, fmt)
                    return dt.strftime('%H:%M')
                except:
                    continue
        except:
            pass

        return None

    def _extract_date_ranges(self, text: str) -> List[str]:
        """Extract date ranges (e.g., 'April 9-11', 'September 10th 2027 - 22nd')"""
        dates = []

        # Pattern 1: "Month DD YYYY - DD" (e.g., "September 10th 2027 – 22nd")
        range_with_year_patterns = [
            r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})\s*[-–—]\s*(\d{1,2})(?:st|nd|rd|th)?',
        ]

        for pattern in range_with_year_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    month = match.group(1)
                    start_day = int(match.group(2))
                    year = int(match.group(3))
                    end_day = int(match.group(4))

                    for day in range(start_day, end_day + 1):
                        date_str = f"{month} {day} {year}"
                        parsed = self._parse_date_flexible(date_str)
                        if parsed:
                            dates.append(parsed)
                except:
                    continue

        # Pattern 2: "Month DD-DD" or "DD-DD Month" (without year)
        range_patterns = [
            r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)\s+(\d{1,2})(?:st|nd|rd|th)?\s*[-–—]\s*(\d{1,2})(?:st|nd|rd|th)?',
            r'(\d{1,2})(?:st|nd|rd|th)?\s*[-–—]\s*(\d{1,2})(?:st|nd|rd|th)?\s+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)',
        ]

        for pattern in range_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    if match.group(1).isdigit():
                        # Format: DD-DD Month
                        start_day = int(match.group(1))
                        end_day = int(match.group(2))
                        month = match.group(3)
                    else:
                        # Format: Month DD-DD
                        month = match.group(1)
                        start_day = int(match.group(2))
                        end_day = int(match.group(3))

                    # Use current year as default, but prefer future dates
                    year = datetime.now().year
                    for day in range(start_day, end_day + 1):
                        date_str = f"{month} {day} {year}"
                        parsed = self._parse_date_flexible(date_str)
                        if parsed:
                            dates.append(parsed)
                except:
                    continue

        return dates


# Create singleton instance for easy importing
parser = EnhancedEmailParser()


def parse_booking_email(email_body: str, email_subject: str = "",
                       from_email: str = "", from_name: str = "") -> BookingEntity:
    """
    Convenience function - parse a booking email

    Args:
        email_body: Email body text
        email_subject: Email subject line
        from_email: Sender email
        from_name: Sender name

    Returns:
        BookingEntity with extracted information
    """
    return parser.parse_booking_email(email_body, email_subject, from_email, from_name)
