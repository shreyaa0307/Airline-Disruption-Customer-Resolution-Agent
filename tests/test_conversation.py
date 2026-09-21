from engine.data_loader import DataContext
from engine.conversation import ConversationManager


def test_emotion_does_not_escalate_and_shows_empathy():
    ctx = DataContext()
    priya = ctx.get_customer_by_pnr("SK4821X")
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(priya)

    reply = conv.handle_user_message("I am furious about this cancellation! This is completely unacceptable!")
    
    # Assert empathetic reply provided
    assert "frustration" in reply.lower() or "apologize" in reply.lower()
    # Assert NO escalation was created for emotion alone
    assert len(conv.logger.escalations) == 0
    # Options presented
    assert "rebooking" in reply.lower() or "refund" in reply.lower()


def test_legal_threat_escalates_immediately_in_same_turn():
    ctx = DataContext()
    arvind = ctx.get_customer_by_pnr("TR1190B")
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(arvind)

    # User mentions lawyer mid-conversation
    reply = conv.handle_user_message("If this is not sorted right now, I am having my lawyer sue the airline!")
    
    # Assert immediate escalation ticket logged
    assert len(conv.logger.escalations) == 1
    ticket = conv.logger.escalations[0]
    assert ticket.ticket_id == "ESC-001"
    assert "lawyer" in ticket.reason.lower() or "sue" in ticket.reason.lower()
    assert "ESC-001" in reply
    assert "specialist support team" in reply.lower() or "escalation" in reply.lower()


def test_formal_complaint_escalates_immediately():
    ctx = DataContext()
    meher = ctx.get_customer_by_pnr("WL7742")
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(meher)

    reply = conv.handle_user_message("I want to file a formal complaint regarding this 6-hour delay.")
    
    assert len(conv.logger.escalations) == 1
    ticket = conv.logger.escalations[0]
    assert "formal complaint" in ticket.reason.lower()
    assert ticket.ticket_id in reply


def test_non_airline_disruption_escalation():
    ctx = DataContext()
    arvind = ctx.get_customer_by_pnr("TR1190B")
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(arvind)

    reply = conv.handle_user_message("I got stuck in traffic and missed check-in. Can you give me a free flight?")
    
    assert len(conv.logger.escalations) == 1
    ticket = conv.logger.escalations[0]
    assert "non-airline-caused" in ticket.reason.lower()
    assert "stuck in traffic" in ticket.trigger_text.lower()
