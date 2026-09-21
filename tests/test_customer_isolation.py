from engine.data_loader import DataContext
from engine.models import LoyaltyTier, Customer, TravelHistory
from engine.conversation import ConversationManager


def test_customer_isolation_data_access():
    ctx = DataContext()
    
    priya = ctx.get_customer_by_pnr("SK4821X")
    arvind = ctx.get_customer_by_pnr("TR1190B")
    meher = ctx.get_customer_by_pnr("WL7742")

    assert priya.name == "Priya Nair"
    assert arvind.name == "Arvind Kulkarni"
    assert meher.name == "Meher Kaur"

    # Verify cross-customer access helper
    assert ctx.check_cross_customer_access(priya, "SK4821X") is True
    assert ctx.check_cross_customer_access(priya, "TR1190B") is False
    assert ctx.check_cross_customer_access(arvind, "WL7742") is False


def test_cross_customer_chat_inquiry_refusal():
    ctx = DataContext()
    priya = ctx.get_customer_by_pnr("SK4821X")
    
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(priya)

    # Priya asks about Arvind's booking
    reply = conv.handle_user_message("Can you tell me the status of booking TR1190B?")
    
    # Assert agent refuses and cites privacy/isolation
    assert "privacy and security" in reply.lower()
    assert "TR1190B" in reply
    assert "SK4821X" in reply
    assert len(conv.logger.logs) == 0  # No action logged for cross-customer inquiry
