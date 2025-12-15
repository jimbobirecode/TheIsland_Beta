"""
Integration Example: Add Learning to Existing Email Bot

This shows exactly where to add tracking code in island_email_bot.py
"""

# ==============================================================================
# EXAMPLE 1: Track parsing results
# ==============================================================================

# In island_email_bot.py, after parsing the email:

def handle_inbound_email_BEFORE():
    """BEFORE - No tracking"""
    # ... existing code ...
    parsed = parse_email_enhanced(subject, body, sender_email, sender_name)

    # Create booking
    booking_id = save_to_database(parsed, sender_email)

    # Send response
    send_availability_email(sender_email, parsed, booking_id)
    # ... rest of code ...


def handle_inbound_email_AFTER():
    """AFTER - With tracking"""
    from parsing_intelligence import track_parsing

    # ... existing code ...
    parsed = parse_email_enhanced(subject, body, sender_email, sender_name)

    # Create booking
    booking_id = save_to_database(parsed, sender_email)

    # 🎯 ADD THIS: Track the parsing result
    track_parsing(
        email_id=message_id or f"email_{datetime.now().timestamp()}",
        booking_id=booking_id,
        entity=parsed,  # The parsed BookingEntity
        email_body=body
    )

    # Send response
    send_availability_email(sender_email, parsed, booking_id)
    # ... rest of code ...


# ==============================================================================
# EXAMPLE 2: Mark correct parses
# ==============================================================================

# When customer confirms booking:

def handle_confirmation_BEFORE():
    """BEFORE - No feedback"""
    if is_confirmation_email(subject, body):
        booking_id = extract_booking_id(subject, body)
        update_booking_status(booking_id, 'Confirmed')
        send_confirmation_receipt(customer_email, booking_id)


def handle_confirmation_AFTER():
    """AFTER - With feedback"""
    from parsing_intelligence import mark_correct

    if is_confirmation_email(subject, body):
        booking_id = extract_booking_id(subject, body)
        update_booking_status(booking_id, 'Confirmed')

        # 🎯 ADD THIS: Mark the original parse as correct
        mark_correct(booking_id)

        send_confirmation_receipt(customer_email, booking_id)


# ==============================================================================
# EXAMPLE 3: Submit corrections from dashboard
# ==============================================================================

# In dashboard.py, when staff edits a booking:

def update_booking_BEFORE(booking_id, updates):
    """BEFORE - No correction tracking"""
    # Update database
    db.execute("UPDATE bookings SET ... WHERE booking_id = ?", updates)


def update_booking_AFTER(booking_id, updates):
    """AFTER - With correction tracking"""
    from parsing_intelligence import submit_correction

    # Get original booking
    original = db.query("SELECT * FROM bookings WHERE booking_id = ?", booking_id)

    # Update database
    db.execute("UPDATE bookings SET ... WHERE booking_id = ?", updates)

    # 🎯 ADD THIS: If critical fields changed, log as correction
    corrections = {}

    if 'date' in updates and updates['date'] != original['date']:
        corrections['actual_dates'] = [updates['date']]

    if 'players' in updates and updates['players'] != original['players']:
        corrections['actual_players'] = updates['players']

    if corrections:
        submit_correction(
            booking_id,
            source='staff_dashboard',
            **corrections
        )


# ==============================================================================
# EXAMPLE 4: API endpoint for corrections (optional)
# ==============================================================================

# Add to Flask app for easy staff corrections:

@app.route('/api/parsing/correct/<booking_id>', methods=['POST'])
def submit_parsing_correction(booking_id):
    """API endpoint for submitting parsing corrections"""
    from parsing_intelligence import submit_correction

    data = request.json

    submit_correction(
        booking_id,
        actual_dates=data.get('dates'),
        actual_players=data.get('players'),
        actual_intent=data.get('intent'),
        actual_lodging=data.get('lodging'),
        source='api'
    )

    return jsonify({'status': 'correction_submitted', 'booking_id': booking_id})


@app.route('/api/parsing/accuracy')
def get_parsing_accuracy():
    """API endpoint to get current accuracy metrics"""
    from parsing_intelligence import get_accuracy

    return jsonify(get_accuracy())


@app.route('/api/parsing/review-queue')
def get_parsing_review_queue():
    """API endpoint to get low-confidence parses for review"""
    from parsing_intelligence import get_review_queue

    return jsonify(get_review_queue())


# ==============================================================================
# EXAMPLE 5: Automatic low-confidence flagging
# ==============================================================================

# Flag low-confidence parses for manual review:

def handle_inbound_email_WITH_FLAGGING():
    """Automatically flag low-confidence parses"""
    from parsing_intelligence import track_parsing

    parsed = parse_email_enhanced(subject, body, sender_email, sender_name)
    booking_id = save_to_database(parsed, sender_email)

    # Track the result
    feedback = track_parsing(
        email_id=message_id,
        booking_id=booking_id,
        entity=parsed,
        email_body=body
    )

    # 🎯 If confidence is low, notify staff for review
    if feedback.confidence_score < 0.5:
        send_staff_notification(
            f"⚠️ Low confidence parse ({feedback.confidence_score:.2f})",
            f"Booking {booking_id} needs review",
            details={
                'dates': parsed.booking_dates,
                'players': parsed.player_count,
                'email_snippet': body[:200]
            }
        )

    send_availability_email(sender_email, parsed, booking_id)


# ==============================================================================
# USAGE SUMMARY
# ==============================================================================

"""
1. Import at top of file:
   from parsing_intelligence import track_parsing, mark_correct, submit_correction

2. Track every parse:
   track_parsing(email_id, booking_id, parsed, email_body)

3. Mark confirmations:
   mark_correct(booking_id)

4. Submit corrections:
   submit_correction(booking_id, actual_dates=[...], actual_players=8)

5. View dashboard:
   python parsing_dashboard.py
"""
