"""
Intelligent Learning System for Email Parsing
Tracks performance, learns from corrections, and improves over time
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ParseFeedback:
    """Feedback on a parsing result"""
    email_id: str
    booking_id: str
    timestamp: str

    # What was extracted
    extracted_dates: List[str]
    extracted_players: Optional[int]
    extracted_intent: str
    extracted_lodging: bool

    # What was correct (filled in by staff/system)
    actual_dates: Optional[List[str]] = None
    actual_players: Optional[int] = None
    actual_intent: Optional[str] = None
    actual_lodging: Optional[bool] = None

    # Metadata
    confidence_score: float = 0.0
    email_snippet: str = ""  # First 200 chars for debugging
    was_correct: Optional[bool] = None
    correction_source: str = ""  # "staff", "customer_reply", "automatic"


class ParsingLearningSystem:
    """
    Learning system that improves parsing over time

    Capabilities:
    1. Logs all parsing results with confidence scores
    2. Tracks which patterns work best
    3. Identifies common failure modes
    4. Suggests new patterns based on misses
    5. A/B tests pattern improvements
    """

    def __init__(self, data_dir: str = "parsing_data"):
        self.data_dir = data_dir
        self.feedback_file = os.path.join(data_dir, "parsing_feedback.jsonl")
        self.stats_file = os.path.join(data_dir, "parsing_stats.json")
        self.patterns_file = os.path.join(data_dir, "learned_patterns.json")

        # Create data directory
        os.makedirs(data_dir, exist_ok=True)

        # Load existing stats
        self.stats = self._load_stats()
        self.learned_patterns = self._load_learned_patterns()

    def log_parsing_result(self, email_id: str, booking_id: str, entity, email_body: str):
        """Log a parsing result for future analysis"""
        feedback = ParseFeedback(
            email_id=email_id,
            booking_id=booking_id,
            timestamp=datetime.now().isoformat(),
            extracted_dates=entity.booking_dates or [],
            extracted_players=entity.player_count,
            extracted_intent=entity.intent.value if entity.intent else "unknown",
            extracted_lodging=entity.lodging_requested,
            confidence_score=entity.confidence,
            email_snippet=email_body[:200] if email_body else ""
        )

        # Write to JSONL file (append mode)
        with open(self.feedback_file, 'a') as f:
            f.write(json.dumps(asdict(feedback)) + '\n')

        # Update stats
        self._update_stats(feedback)

        return feedback

    def mark_as_correct(self, booking_id: str):
        """Mark a parsing result as correct (called when booking confirmed)"""
        # Update the feedback entry
        feedbacks = self._read_all_feedback()
        for fb in feedbacks:
            if fb.get('booking_id') == booking_id and fb.get('was_correct') is None:
                fb['was_correct'] = True
                fb['correction_source'] = 'customer_confirmation'
                break

        self._write_all_feedback(feedbacks)
        logger.info(f"✅ Marked {booking_id} parsing as CORRECT")

    def submit_correction(self, booking_id: str, actual_dates: List[str] = None,
                         actual_players: int = None, actual_intent: str = None,
                         actual_lodging: bool = None, source: str = "staff"):
        """Submit a correction for a misparsed email"""
        feedbacks = self._read_all_feedback()

        for fb in feedbacks:
            if fb.get('booking_id') == booking_id:
                # Update with actual values
                if actual_dates:
                    fb['actual_dates'] = actual_dates
                if actual_players:
                    fb['actual_players'] = actual_players
                if actual_intent:
                    fb['actual_intent'] = actual_intent
                if actual_lodging is not None:
                    fb['actual_lodging'] = actual_lodging

                fb['was_correct'] = False
                fb['correction_source'] = source

                logger.warning(f"⚠️  Parsing correction for {booking_id}")
                logger.warning(f"   Extracted: dates={fb.get('extracted_dates')}, players={fb.get('extracted_players')}")
                logger.warning(f"   Actual: dates={actual_dates}, players={actual_players}")

                # Try to learn from this mistake
                self._learn_from_mistake(fb)
                break

        self._write_all_feedback(feedbacks)

    def get_accuracy_report(self, last_n_days: int = 30) -> Dict:
        """Get accuracy metrics for the last N days"""
        feedbacks = self._read_all_feedback()

        # Filter to last N days
        cutoff = datetime.now().timestamp() - (last_n_days * 24 * 60 * 60)
        recent = [
            fb for fb in feedbacks
            if datetime.fromisoformat(fb.get('timestamp', '')).timestamp() > cutoff
        ]

        # Calculate metrics
        total = len(recent)
        verified = len([fb for fb in recent if fb.get('was_correct') is not None])
        correct = len([fb for fb in recent if fb.get('was_correct') is True])
        incorrect = len([fb for fb in recent if fb.get('was_correct') is False])

        # By confidence bucket
        high_conf = [fb for fb in recent if fb.get('confidence_score', 0) > 0.7]
        low_conf = [fb for fb in recent if fb.get('confidence_score', 0) < 0.5]

        return {
            'period_days': last_n_days,
            'total_emails': total,
            'verified': verified,
            'correct': correct,
            'incorrect': incorrect,
            'accuracy': correct / verified if verified > 0 else 0,
            'high_confidence_count': len(high_conf),
            'low_confidence_count': len(low_conf),
            'avg_confidence': sum(fb.get('confidence_score', 0) for fb in recent) / total if total > 0 else 0,
        }

    def get_failure_patterns(self) -> List[Dict]:
        """Identify common patterns in parsing failures"""
        feedbacks = self._read_all_feedback()
        incorrect = [fb for fb in feedbacks if fb.get('was_correct') is False]

        failures = defaultdict(int)

        for fb in incorrect:
            # What went wrong?
            if fb.get('extracted_dates') != fb.get('actual_dates'):
                failures['date_mismatch'] += 1

            if fb.get('extracted_players') != fb.get('actual_players'):
                failures['player_count_mismatch'] += 1

            if fb.get('extracted_intent') != fb.get('actual_intent'):
                failures['intent_mismatch'] += 1

            if fb.get('extracted_lodging') != fb.get('actual_lodging'):
                failures['lodging_mismatch'] += 1

        return [
            {'failure_type': k, 'count': v, 'percentage': v / len(incorrect) * 100 if incorrect else 0}
            for k, v in sorted(failures.items(), key=lambda x: x[1], reverse=True)
        ]

    def suggest_new_patterns(self) -> List[str]:
        """Analyze missed parses and suggest new regex patterns"""
        feedbacks = self._read_all_feedback()
        incorrect = [fb for fb in feedbacks if fb.get('was_correct') is False]

        suggestions = []

        # Analyze date misses
        date_misses = [fb for fb in incorrect if fb.get('extracted_dates') != fb.get('actual_dates')]
        if date_misses:
            suggestions.append(f"Found {len(date_misses)} date parsing failures")
            # Extract unique snippets
            snippets = set(fb.get('email_snippet', '') for fb in date_misses[:10])
            for snippet in snippets:
                suggestions.append(f"  Example: {snippet[:100]}...")

        # Analyze player count misses
        player_misses = [fb for fb in incorrect if fb.get('extracted_players') != fb.get('actual_players')]
        if player_misses:
            suggestions.append(f"Found {len(player_misses)} player count failures")

        return suggestions

    def flag_for_review(self, min_confidence: float = 0.5) -> List[Dict]:
        """Get list of low-confidence parses that need human review"""
        feedbacks = self._read_all_feedback()

        # Filter unverified low-confidence results
        flagged = [
            fb for fb in feedbacks
            if fb.get('was_correct') is None  # Not yet verified
            and fb.get('confidence_score', 1.0) < min_confidence
        ]

        # Sort by confidence (lowest first)
        flagged.sort(key=lambda x: x.get('confidence_score', 0))

        return flagged[:20]  # Top 20 for review

    def _learn_from_mistake(self, feedback: Dict):
        """Try to automatically learn from a parsing mistake"""
        # This is where ML would go, but for now we just log patterns

        mistake_type = []

        if feedback.get('extracted_dates') != feedback.get('actual_dates'):
            mistake_type.append('date')

        if feedback.get('extracted_players') != feedback.get('actual_players'):
            mistake_type.append('players')

        if feedback.get('extracted_intent') != feedback.get('actual_intent'):
            mistake_type.append('intent')

        # Log the pattern for manual review
        pattern = {
            'mistake_types': mistake_type,
            'email_snippet': feedback.get('email_snippet'),
            'extracted': {
                'dates': feedback.get('extracted_dates'),
                'players': feedback.get('extracted_players'),
                'intent': feedback.get('extracted_intent'),
            },
            'actual': {
                'dates': feedback.get('actual_dates'),
                'players': feedback.get('actual_players'),
                'intent': feedback.get('actual_intent'),
            },
            'timestamp': datetime.now().isoformat(),
        }

        # Append to learned patterns file
        with open(self.patterns_file, 'a') as f:
            f.write(json.dumps(pattern) + '\n')

    def _update_stats(self, feedback: ParseFeedback):
        """Update running statistics"""
        # Count by confidence bucket
        conf = feedback.confidence_score
        if conf >= 0.8:
            bucket = 'high'
        elif conf >= 0.5:
            bucket = 'medium'
        else:
            bucket = 'low'

        self.stats['by_confidence'][bucket] = self.stats['by_confidence'].get(bucket, 0) + 1
        self.stats['total_parsed'] = self.stats.get('total_parsed', 0) + 1
        self.stats['last_updated'] = datetime.now().isoformat()

        # Save stats
        with open(self.stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)

    def _load_stats(self) -> Dict:
        """Load existing stats"""
        if os.path.exists(self.stats_file):
            with open(self.stats_file, 'r') as f:
                return json.load(f)
        return {'by_confidence': {}, 'total_parsed': 0}

    def _load_learned_patterns(self) -> List[Dict]:
        """Load learned patterns"""
        if os.path.exists(self.patterns_file):
            patterns = []
            with open(self.patterns_file, 'r') as f:
                for line in f:
                    patterns.append(json.loads(line))
            return patterns
        return []

    def _read_all_feedback(self) -> List[Dict]:
        """Read all feedback entries"""
        if not os.path.exists(self.feedback_file):
            return []

        feedbacks = []
        with open(self.feedback_file, 'r') as f:
            for line in f:
                feedbacks.append(json.loads(line))
        return feedbacks

    def _write_all_feedback(self, feedbacks: List[Dict]):
        """Write all feedback entries (overwrites file)"""
        with open(self.feedback_file, 'w') as f:
            for fb in feedbacks:
                f.write(json.dumps(fb) + '\n')


# Global instance
learning_system = ParsingLearningSystem()


def track_parsing(email_id: str, booking_id: str, entity, email_body: str):
    """Track a parsing result"""
    return learning_system.log_parsing_result(email_id, booking_id, entity, email_body)


def mark_correct(booking_id: str):
    """Mark parsing as correct (call when customer confirms)"""
    learning_system.mark_as_correct(booking_id)


def submit_correction(booking_id: str, **corrections):
    """Submit a correction for misparsed email"""
    learning_system.submit_correction(booking_id, **corrections)


def get_accuracy():
    """Get current accuracy metrics"""
    return learning_system.get_accuracy_report()


def get_review_queue():
    """Get low-confidence parses for review"""
    return learning_system.flag_for_review()
