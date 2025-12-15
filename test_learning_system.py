#!/usr/bin/env python3
"""
Demo: Learning System in Action
Shows how the system learns from real emails
"""

from parsing_intelligence import learning_system, track_parsing, mark_correct, submit_correction
from enhanced_nlp import parse_booking_email
from datetime import datetime


def demo_learning_cycle():
    """Demonstrate complete learning cycle"""
    print("=" * 80)
    print("🧠 LEARNING SYSTEM DEMO")
    print("=" * 80)

    # Email 1: Perfect parse (will be marked correct)
    print("\n1️⃣ Email 1: Simple Booking")
    print("-" * 80)

    email1 = {
        'subject': 'Golf Booking',
        'body': 'Hi, can we book for April 15, 2026 at 10:00 AM? Party of 4.',
        'email_id': 'msg_001',
        'booking_id': 'ISL-20260410-001',
    }

    entity1 = parse_booking_email(email1['body'], email1['subject'])

    print(f"📧 Email: {email1['body'][:80]}...")
    print(f"✅ Parsed: dates={entity1.booking_dates}, players={entity1.player_count}")
    print(f"📊 Confidence: {entity1.confidence:.2f}")

    # Track it
    track_parsing(email1['email_id'], email1['booking_id'], entity1, email1['body'])

    # Customer confirms - mark correct
    mark_correct(email1['booking_id'])
    print(f"✅ Customer confirmed → Marked as CORRECT")

    # Email 2: Misparsed (will need correction)
    print("\n2️⃣ Email 2: Group of 8 (Misparsed)")
    print("-" * 80)

    email2 = {
        'subject': 'Large group booking',
        'body': 'We have a group of 8 golfers. Can we split into two foursomes? May 20, 2026.',
        'email_id': 'msg_002',
        'booking_id': 'ISL-20260515-002',
    }

    entity2 = parse_booking_email(email2['body'], email2['subject'])

    print(f"📧 Email: {email2['body'][:80]}...")
    print(f"❌ Parsed: players={entity2.player_count} (WRONG - should be 8)")
    print(f"📊 Confidence: {entity2.confidence:.2f}")

    # Track it
    track_parsing(email2['email_id'], email2['booking_id'], entity2, email2['body'])

    # Staff corrects it
    submit_correction(
        email2['booking_id'],
        actual_players=8,
        source='staff_correction'
    )
    print(f"✏️  Staff corrected: 8 players → Marked as INCORRECT")
    print(f"💡 System learns: 'group of 8 golfers' should extract 8, not 4")

    # Email 3: Low confidence (needs review)
    print("\n3️⃣ Email 3: Ambiguous Date (Low Confidence)")
    print("-" * 80)

    email3 = {
        'subject': 'Weekend golf',
        'body': 'Looking to play sometime next weekend. Flexible on dates. 3 players.',
        'email_id': 'msg_003',
        'booking_id': 'ISL-20251220-003',
    }

    entity3 = parse_booking_email(email3['body'], email3['subject'])

    print(f"📧 Email: {email3['body'][:80]}...")
    print(f"⚠️  Parsed: dates={entity3.booking_dates}, players={entity3.player_count}")
    print(f"📊 Confidence: {entity3.confidence:.2f} (LOW)")

    # Track it
    track_parsing(email3['email_id'], email3['booking_id'], entity3, email3['body'])
    print(f"🚩 Flagged for manual review (confidence < 0.5)")

    # Show results
    print("\n" + "=" * 80)
    print("📊 LEARNING SYSTEM RESULTS")
    print("=" * 80)

    # Accuracy report
    accuracy = learning_system.get_accuracy_report(30)
    print(f"\n✅ Accuracy: {accuracy['correct']}/{accuracy['verified']} verified "
          f"({accuracy['accuracy']*100:.1f}%)")

    # Failures
    failures = learning_system.get_failure_patterns()
    if failures:
        print(f"\n❌ Failure patterns:")
        for fail in failures:
            print(f"   • {fail['failure_type']}: {fail['count']} times")

    # Review queue
    review = learning_system.flag_for_review(min_confidence=0.6)
    print(f"\n⚠️  Parses needing review: {len(review)}")
    for r in review[:3]:
        print(f"   • {r.get('booking_id')}: confidence={r.get('confidence_score'):.2f}")

    print("\n" + "=" * 80)
    print("✨ Learning cycle complete!")
    print("=" * 80)
    print("\nData saved to: parsing_data/")
    print("View dashboard: python parsing_dashboard.py")
    print()


if __name__ == '__main__':
    demo_learning_cycle()
