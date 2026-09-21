from engine.action_tools import ActionLogger, ActionTools
from engine.models import Customer, LoyaltyTier, TravelHistory


def test_action_logger_timestamps_and_execution():
    logger = ActionLogger()
    tools = ActionTools(logger)
    
    customer = Customer(
        id="CUST-001",
        name="Priya Nair",
        loyalty_tier=LoyaltyTier.GOLD,
        booking_reference="SK4821X",
        email="priya.nair@example.com",
        phone="+91-98xxxxxxx1",
        travel_history=TravelHistory(flights_last_12_months=6)
    )

    # 1. Log rebook request
    rebook_entry = tools.rebook_request(
        pnr="SK4821X",
        customer=customer,
        is_priority=True,
        notes="Airline cancellation rebook"
    )
    assert rebook_entry.action_id == "ACT-001"
    assert rebook_entry.timestamp.startswith("2026-09-23T")
    assert rebook_entry.parameters["is_priority"] is True
    assert "next available flight within 24 hours" in rebook_entry.parameters["window"]
    # Verify no fake flight number is invented
    assert "SK-9" not in rebook_entry.details

    # 2. Log refund
    refund_entry = tools.initiate_refund(
        pnr="SK4821X",
        customer=customer,
        payment_method="original_payment_method"
    )
    assert refund_entry.action_id == "ACT-002"
    assert refund_entry.timestamp.startswith("2026-09-23T")
    assert refund_entry.parameters["timeframe"] == "within 7 business days"
    assert refund_entry.parameters["payment_method"] == "original_payment_method"

    # 3. Log hotel arrangement
    hotel_entry = tools.arrange_hotel(
        pnr="SK4821X",
        customer=customer,
        delayed_hours_only=True
    )
    assert hotel_entry.action_id == "ACT-003"
    assert hotel_entry.parameters["delayed_hours_only"] is True
    # Verify no invented hotel name or address
    assert "Hilton" not in hotel_entry.details
    assert "Hyatt" not in hotel_entry.details

    # 4. Log escalation ticket
    ticket = tools.escalate_to_human(
        pnr="SK4821X",
        customer=customer,
        reason="Supervisor approval required for upgrade",
        trigger_text="I want business class upgrade"
    )
    assert ticket.ticket_id == "ESC-001"
    assert ticket.timestamp.startswith("2026-09-23T")
    assert ticket.status == "OPEN"
    assert len(logger.logs) == 3
    assert len(logger.escalations) == 1
