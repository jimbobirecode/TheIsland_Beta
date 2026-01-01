"""
Anthropic API Integration for Email Parsing

Uses Claude to parse booking emails with superior natural language understanding.
Provides better inference for ambiguous cases compared to regex-based parsing.
"""

import os
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import anthropic

logger = logging.getLogger(__name__)


class ClaudeEmailParser:
    """Parse booking emails using Anthropic's Claude API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude email parser

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("⚠️  ANTHROPIC_API_KEY not set - Claude parsing disabled")
            self.enabled = False
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.enabled = True
            logger.info("✅ Claude email parser initialized")

        # Model selection - Haiku for speed and cost efficiency
        self.model = "claude-3-5-haiku-20241022"  # Fast and cheap for parsing
        self.max_tokens = 1000

    def parse_booking_email(self, body: str, subject: str = "") -> Dict[str, Any]:
        """
        Parse booking email using Claude API

        Args:
            body: Email body text
            subject: Email subject line

        Returns:
            Dictionary with parsed booking information
        """
        if not self.enabled:
            logger.error("❌ Claude parser not enabled - missing API key")
            return self._get_fallback_response("API key not configured")

        try:
            logger.info("🤖 Parsing email with Claude API...")

            # Prepare the email text
            email_text = f"Subject: {subject}\n\n{body}" if subject else body

            # Current date for context
            today = datetime.now().strftime("%Y-%m-%d")

            # Create the parsing prompt
            prompt = self._create_parsing_prompt(email_text, today)

            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract and parse the response
            response_text = message.content[0].text
            logger.info(f"📝 Claude response: {response_text[:200]}...")

            # Parse JSON response
            parsed_data = self._parse_claude_response(response_text)

            logger.info(f"✅ Claude parsing successful - Confidence: {parsed_data.get('confidence', 0):.0%}")

            return parsed_data

        except anthropic.APIError as e:
            logger.error(f"❌ Anthropic API error: {e}")
            return self._get_fallback_response(f"API error: {str(e)}")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Claude response as JSON: {e}")
            logger.error(f"   Response was: {response_text}")
            return self._get_fallback_response("Invalid JSON response")

        except Exception as e:
            logger.error(f"❌ Unexpected error in Claude parsing: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._get_fallback_response(f"Unexpected error: {str(e)}")

    def _create_parsing_prompt(self, email_text: str, today: str) -> str:
        """Create the prompt for Claude to parse the email"""

        return f"""You are an expert at parsing golf course booking emails. Extract structured information from the email below.

Today's date: {today}

Email to parse:
---
{email_text}
---

Extract the following information and return as JSON:

{{
  "intent": "<booking_request|availability_check|booking_confirmation|booking_modification|booking_cancellation|general_inquiry|pricing_inquiry|complaint>",
  "urgency": "<urgent|soon|flexible|unknown>",
  "confidence": <0.0-1.0>,
  "player_count": <number or null>,
  "dates": {{
    "start_date": "<YYYY-MM-DD or null>",
    "end_date": "<YYYY-MM-DD or null>",
    "is_range": <true|false>,
    "is_weekend": <true|false>,
    "raw_text": "<original date text>"
  }},
  "time_preference": {{
    "preferred_time": "<morning|afternoon|evening|HH:MM or null>",
    "flexibility": "<strict|flexible|any>",
    "raw_text": "<original time text>"
  }},
  "special_requests": {{
    "cart": <true|false>,
    "caddie": <true|false>,
    "meal": <true|false>,
    "lodging": <true|false>
  }},
  "is_corporate": <true|false>,
  "company_name": "<name or null>",
  "is_tournament": <true|false>,
  "ambiguities": ["<list of unclear points>"],
  "reasoning": "<brief explanation of your interpretation>"
}}

IMPORTANT RULES:
1. For dates: Convert relative dates like "tomorrow", "next Tuesday", "in 2 weeks" to actual YYYY-MM-DD format based on today's date ({today})
2. For player_count: Extract from phrases like "foursome" (4), "our group of 12", "2 players", etc.
3. For intent: Classify the primary purpose of the email
4. For urgency: "urgent" = today/tomorrow, "soon" = within 1 week, "flexible" = more than 1 week
5. For confidence: High (0.8-1.0) if all key info is clear, Medium (0.5-0.7) if some ambiguity, Low (<0.5) if very unclear
6. List any ambiguities or unclear points
7. Return ONLY valid JSON, no other text

Analyze the email carefully and return the JSON."""

    def _parse_claude_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response and validate it"""

        # Try to extract JSON if Claude added extra text
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]
        else:
            json_text = response_text

        # Parse JSON
        data = json.loads(json_text)

        # Validate and set defaults
        parsed = {
            'intent': data.get('intent', 'general_inquiry'),
            'urgency': data.get('urgency', 'unknown'),
            'confidence': float(data.get('confidence', 0.5)),
            'player_count': data.get('player_count'),
            'dates': data.get('dates', {}),
            'time_preference': data.get('time_preference', {}),
            'special_requests': data.get('special_requests', {}),
            'is_corporate': data.get('is_corporate', False),
            'company_name': data.get('company_name'),
            'is_tournament': data.get('is_tournament', False),
            'ambiguities': data.get('ambiguities', []),
            'reasoning': data.get('reasoning', ''),
            'parsed_by': 'claude_api'
        }

        return parsed

    def _get_fallback_response(self, error_reason: str) -> Dict[str, Any]:
        """Return a safe fallback response when Claude parsing fails"""
        return {
            'intent': 'general_inquiry',
            'urgency': 'unknown',
            'confidence': 0.0,
            'player_count': None,
            'dates': {},
            'time_preference': {},
            'special_requests': {'cart': False, 'caddie': False, 'meal': False},
            'is_corporate': False,
            'company_name': None,
            'is_tournament': False,
            'ambiguities': [f"Claude parsing failed: {error_reason}"],
            'reasoning': 'Fallback response due to parsing error',
            'parsed_by': 'fallback',
            'error': error_reason
        }


# Global instance
_claude_parser = None


def get_claude_parser() -> ClaudeEmailParser:
    """Get or create global Claude parser instance"""
    global _claude_parser
    if _claude_parser is None:
        _claude_parser = ClaudeEmailParser()
    return _claude_parser


def parse_with_claude(body: str, subject: str = "") -> Dict[str, Any]:
    """
    Convenience function to parse email with Claude

    Args:
        body: Email body text
        subject: Email subject line

    Returns:
        Parsed booking information
    """
    parser = get_claude_parser()
    return parser.parse_booking_email(body, subject)
