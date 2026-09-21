from engine.data_loader import DataContext
from engine.conversation import ConversationManager


def test_scenario_1_priya_nair_cancellation_and_upgrade_request():
    """Scenario 1: Priya Nair (Gold, SK4821X).
    
    Flight SK-204 cancelled. Furious, asks for full cash refund + free upgrade to
    business class on return flight for the trouble.
    """
    ctx = DataContext()
    priya = ctx.get_customer_by_pnr("SK4821X")
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(priya)

    # Turn 1: Priya expresses anger, asks for cash refund and business class upgrade
    reply_1 = conv.handle_user_message(
        "I am furious that flight SK-204 was cancelled! I want a full cash refund and a free upgrade to business class on my return flight for the trouble."
    )

    # 1. Empathetic response acknowledging frustration without escalating on anger alone
    assert "frustration" in reply_1.lower() or "apologize" in reply_1.lower()

    # 2. Upgrade request is escalated to human support
    assert len(conv.logger.escalations) == 1
    upgrade_ticket = conv.logger.escalations[0]
    assert "upgrade" in upgrade_ticket.reason.lower()
    assert upgrade_ticket.ticket_id in reply_1

    # 3. Cash refund is clarified to original payment method (within 7 business days)
    assert "original payment method" in reply_1.lower()
    assert "7 business days" in reply_1.lower()

    # 4. Return booking remains untouched and confirmed
    booking = conv.state["current_booking"]
    return_leg = next(s for s in booking.segments if s.flight_number == "Return")
    assert return_leg.status == "Unaffected"

    # 5. Refund has NOT been logged yet (awaiting confirmation)
    assert len(conv.logger.logs) == 0

    # Turn 2: Priya confirms refund to original payment method
    reply_2 = conv.handle_user_message("Yes, please initiate the refund to my original payment method.")

    # 6. Refund is now logged in action log
    assert len(conv.logger.logs) == 1
    refund_action = conv.logger.logs[0]
    assert refund_action.action_type == "initiate_refund"
    assert refund_action.status == "PROCESSED"
    assert refund_action.parameters["timeframe"] == "within 7 business days"
    assert refund_action.action_id in reply_2


def test_scenario_2_arvind_kulkarni_4h_delay_meeting_and_hotel():
    """Scenario 2: Arvind Kulkarni (Silver, TR1190B).
    
    Flight SK-118 delayed 4h. Frustrated about missing a meeting, asks for hotel.
    """
    ctx = DataContext()
    arvind = ctx.get_customer_by_pnr("TR1190B")
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(arvind)

    # Turn 1: Arvind asks about hotel and mentions missing connecting meeting
    reply_1 = conv.handle_user_message(
        "My flight SK-118 is delayed 4 hours. I'm going to miss my connecting meeting in Bengaluru. Can you arrange hotel accommodation since it's been such a long delay?"
    )

    # 1. Hotel request is declined because 4h delay <= 5h
    assert "exceeding 5 hours" in reply_1 or "more than 5 hours" in reply_1 or "5 hours" in reply_1

    # 2. Entitlements for 4h delay (meal voucher + lounge access) are issued & logged
    assert len(conv.logger.logs) == 2
    action_types = [a.action_type for a in conv.logger.logs]
    assert "issue_meal_voucher" in action_types
    assert "grant_lounge_access" in action_types

    # 3. Missed meeting acknowledged empathetically, no promises made, human review offered
    assert "meeting" in reply_1.lower()
    assert "human" in reply_1.lower() or "specialist" in reply_1.lower()
    # Escalation is NOT logged yet
    assert len(conv.logger.escalations) == 0

    # Turn 2: Arvind takes up the offer for human review
    reply_2 = conv.handle_user_message("Yes please, connect me with a specialist for human review.")

    # 4. Escalation is logged only after Arvind accepts
    assert len(conv.logger.escalations) == 1
    meeting_ticket = conv.logger.escalations[0]
    assert "meeting" in meeting_ticket.reason.lower()
    assert meeting_ticket.ticket_id in reply_2


def test_scenario_3_meher_kaur_path_a_pays_fare_difference():
    """Scenario 3 (Path A): Meher Kaur (Platinum, WL7742).
    
    Flight SK-305 delayed 6h. Asks for full night hotel, and asks to move to higher-fare
    flight (fare diff ₹2,000). She agrees to pay the difference (no waiver requested).
    """
    ctx = DataContext()
    meher = ctx.get_customer_by_pnr("WL7742")
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(meher)

    # Turn 1: Meher asks for a full night hotel stay
    reply_1 = conv.handle_user_message("Flight SK-305 is delayed 6 hours. I want a full night's hotel stay.")

    # 1. Literal 6h delay entitlement: Meal voucher + delayed hours hotel (NO lounge access)
    assert "delayed hours" in reply_1.lower()
    assert "full night" in reply_1.lower()
    assert "lounge" not in reply_1.lower()
    assert len(conv.logger.logs) == 1  # Meal voucher issued
    assert conv.logger.logs[0].action_type == "issue_meal_voucher"

    # Turn 2: Meher confirms delayed-hours hotel
    reply_2 = conv.handle_user_message("Yes, please confirm the delayed-hours hotel accommodation.")
    assert len(conv.logger.logs) == 2
    assert conv.logger.logs[1].action_type == "arrange_hotel"
    assert conv.logger.logs[1].parameters["delayed_hours_only"] is True

    # Turn 3: Meher asks to move to higher-fare flight with ₹2,000 difference (no waiver requested)
    reply_3 = conv.handle_user_message("Can I be moved onto a different, higher-fare flight instead of waiting? The fare difference is ₹2,000.")
    assert "2,000" in reply_3
    assert "pay" in reply_3.lower()
    # No waiver was offered proactively, and no escalation logged
    assert len(conv.logger.escalations) == 0

    # Turn 4: Meher confirms paying the ₹2,000 difference
    reply_4 = conv.handle_user_message("I agree to pay the ₹2,000 fare difference, please proceed.")
    assert len(conv.logger.logs) == 3
    rebook_action = conv.logger.logs[2]
    assert rebook_action.action_type == "rebook_request"
    assert rebook_action.parameters["fare_difference"] == 2000.0
    assert len(conv.logger.escalations) == 0  # No escalation in Path A


def test_scenario_3_meher_kaur_path_b_waiver_request_escalation():
    """Scenario 3 (Path B): Meher Kaur asks for a waiver of the ₹2,000 fare difference.
    
    Since ₹2,000 > ₹1,500, this requires supervisor approval and escalates.
    """
    ctx = DataContext()
    meher = ctx.get_customer_by_pnr("WL7742")
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(meher)

    reply = conv.handle_user_message(
        "I want to switch to a higher-fare flight with a ₹2,000 fare difference, but I want you to waive the difference for free."
    )

    # 1. Explains that waivers above ₹1,500 require supervisor approval
    assert "1,500" in reply
    assert "supervisor" in reply.lower()
    # 2. Never says "cannot be waived"; mentions supervisor approval required
    assert "cannot be waived" not in reply.lower()

    # 3. Escalated to supervisor
    assert len(conv.logger.escalations) == 1
    waiver_ticket = conv.logger.escalations[0]
    assert "waiver" in waiver_ticket.reason.lower()
    assert waiver_ticket.ticket_id in reply
