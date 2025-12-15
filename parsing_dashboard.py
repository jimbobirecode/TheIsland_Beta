#!/usr/bin/env python3
"""
Parsing Intelligence Dashboard
View accuracy metrics, review low-confidence parses, submit corrections
"""

import sys
from parsing_intelligence import learning_system
from datetime import datetime


def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def show_accuracy_report():
    """Display accuracy metrics"""
    print_header("📊 PARSING ACCURACY REPORT")

    # Get reports for different time periods
    periods = [7, 30, 90]

    for days in periods:
        report = learning_system.get_accuracy_report(days)

        print(f"\n📅 Last {days} days:")
        print(f"   Total emails parsed:  {report['total_emails']}")
        print(f"   Verified (confirmed): {report['verified']}")

        if report['verified'] > 0:
            accuracy = report['accuracy'] * 100
            print(f"   ✅ Correct:            {report['correct']} ({accuracy:.1f}%)")
            print(f"   ❌ Incorrect:          {report['incorrect']}")
        else:
            print(f"   ⚠️  No verified results yet")

        print(f"   📊 Avg confidence:     {report['avg_confidence']:.2f}")
        print(f"   🔼 High confidence (>0.7): {report['high_confidence_count']}")
        print(f"   🔽 Low confidence (<0.5):  {report['low_confidence_count']}")


def show_failure_patterns():
    """Display common failure modes"""
    print_header("🔍 COMMON FAILURE PATTERNS")

    failures = learning_system.get_failure_patterns()

    if not failures:
        print("\n✅ No failures recorded yet (or all parses are unverified)")
        return

    print(f"\nFound {len(failures)} failure types:")
    for fail in failures:
        print(f"   • {fail['failure_type']:25s}: {fail['count']:3d} ({fail['percentage']:.1f}%)")


def show_review_queue():
    """Display parses that need human review"""
    print_header("⚠️  LOW-CONFIDENCE PARSES (Need Review)")

    flagged = learning_system.flag_for_review(min_confidence=0.6)

    if not flagged:
        print("\n✅ No low-confidence parses to review!")
        return

    print(f"\nFound {len(flagged)} parses needing review:\n")

    for i, fb in enumerate(flagged[:10], 1):  # Show top 10
        print(f"{i}. Booking ID: {fb.get('booking_id')}")
        print(f"   Confidence: {fb.get('confidence_score', 0):.2f}")
        print(f"   Extracted:  dates={fb.get('extracted_dates')}, players={fb.get('extracted_players')}")
        print(f"   Email:      {fb.get('email_snippet', '')[:80]}...")
        print()


def show_suggestions():
    """Display pattern suggestions"""
    print_header("💡 PATTERN IMPROVEMENT SUGGESTIONS")

    suggestions = learning_system.suggest_new_patterns()

    if not suggestions:
        print("\n✅ No suggestions yet (need more failure data)")
        return

    for suggestion in suggestions:
        print(f"   {suggestion}")


def interactive_correction():
    """Interactive mode to submit corrections"""
    print_header("✏️  SUBMIT PARSING CORRECTION")

    booking_id = input("\nEnter Booking ID: ").strip()
    if not booking_id:
        print("Cancelled.")
        return

    print("\nWhat needs correction? (leave blank to skip)")

    # Dates
    dates_input = input("Actual dates (comma-separated, YYYY-MM-DD): ").strip()
    actual_dates = [d.strip() for d in dates_input.split(',')] if dates_input else None

    # Players
    players_input = input("Actual player count: ").strip()
    actual_players = int(players_input) if players_input else None

    # Intent
    intent_input = input("Actual intent (question/booking_request/confirmation/etc): ").strip()
    actual_intent = intent_input if intent_input else None

    # Lodging
    lodging_input = input("Actual lodging requested (yes/no): ").strip().lower()
    actual_lodging = None
    if lodging_input == 'yes':
        actual_lodging = True
    elif lodging_input == 'no':
        actual_lodging = False

    # Submit correction
    learning_system.submit_correction(
        booking_id,
        actual_dates=actual_dates,
        actual_players=actual_players,
        actual_intent=actual_intent,
        actual_lodging=actual_lodging,
        source='staff_manual'
    )

    print(f"\n✅ Correction submitted for {booking_id}")


def main_menu():
    """Main dashboard menu"""
    while True:
        print("\n" + "=" * 80)
        print("  📊 PARSING INTELLIGENCE DASHBOARD")
        print("=" * 80)
        print("\n1. View Accuracy Report")
        print("2. View Failure Patterns")
        print("3. Review Low-Confidence Parses")
        print("4. View Pattern Suggestions")
        print("5. Submit Correction")
        print("6. Export Stats (JSON)")
        print("7. Exit")

        choice = input("\nSelect option (1-7): ").strip()

        if choice == '1':
            show_accuracy_report()
        elif choice == '2':
            show_failure_patterns()
        elif choice == '3':
            show_review_queue()
        elif choice == '4':
            show_suggestions()
        elif choice == '5':
            interactive_correction()
        elif choice == '6':
            export_stats()
        elif choice == '7':
            print("\nGoodbye! 👋")
            break
        else:
            print("Invalid choice. Try again.")

        input("\nPress Enter to continue...")


def export_stats():
    """Export stats to JSON file"""
    import json

    stats = {
        'accuracy_7d': learning_system.get_accuracy_report(7),
        'accuracy_30d': learning_system.get_accuracy_report(30),
        'failures': learning_system.get_failure_patterns(),
        'review_queue_count': len(learning_system.flag_for_review()),
        'exported_at': datetime.now().isoformat(),
    }

    filename = f"parsing_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filename, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"\n✅ Stats exported to: {filename}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'report':
        # Quick report mode
        show_accuracy_report()
        show_failure_patterns()
    else:
        # Interactive mode
        main_menu()
