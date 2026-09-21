import pytest
from engine.models import Customer, FlightSegment, TravelHistory, LoyaltyTier, DisruptionType
from engine.policy_engine import PolicyEngine


@pytest.fixture
def gold_customer():
    return Customer(
        id="CUST-001",
        name="Priya Nair",
        loyalty_tier=LoyaltyTier.GOLD,
        booking_reference="SK4821X",
        email="priya.nair@example.com",
        phone="+91-98xxxxxxx1",
        travel_history=TravelHistory(flights_last_12_months=6)
    )


@pytest.fixture
def silver_customer():
    return Customer(
        id="CUST-002",
        name="Arvind Kulkarni",
        loyalty_tier=LoyaltyTier.SILVER,
        booking_reference="TR1190B",
        email="arvind.kulkarni@example.com",
        phone="+91-98xxxxxxx2",
        travel_history=TravelHistory(flights_last_12_months=3)
    )


@pytest.fixture
def platinum_customer():
    return Customer(
        id="CUST-003",
        name="Meher Kaur",
        loyalty_tier=LoyaltyTier.PLATINUM,
        booking_reference="WL7742",
        email="meher.kaur@example.com",
        phone="+91-98xxxxxxx3",
        travel_history=TravelHistory(flights_last_12_months=10)
    )


def test_delay_tier_boundaries(silver_customer):
    """Test strict boundary minutes for delay compensation tiers."""
    
    # 179 minutes (< 3 hours) -> ₹500 meal voucher only
    seg_179 = FlightSegment(
        segment_id="S1", flight_number="SK-101", route="DEL-BOM", origin="DEL", destination="BOM",
        date="Wed 23 Sep 2026", date_iso="2026-09-23", scheduled_departure="10:00",
        status="Delayed", disruption_type=DisruptionType.DELAY, disruption_cause="airline_delay",
        delay_minutes=179
    )
    decision = PolicyEngine.evaluate_delay(silver_customer, seg_179)
    assert decision.allowed is True
    assert decision.entitlements["meal_voucher"] is True
    assert decision.entitlements["meal_voucher_amount"] == "₹500"
    assert decision.entitlements["lounge_access"] is False
    assert decision.entitlements["hotel_accommodation"] is False

    # 180 minutes (exact 3 hours boundary) -> meal voucher + lounge access
    seg_180 = FlightSegment(
        segment_id="S2", flight_number="SK-102", route="DEL-BOM", origin="DEL", destination="BOM",
        date="Wed 23 Sep 2026", date_iso="2026-09-23", scheduled_departure="10:00",
        status="Delayed", disruption_type=DisruptionType.DELAY, disruption_cause="airline_delay",
        delay_minutes=180
    )
    decision_180 = PolicyEngine.evaluate_delay(silver_customer, seg_180)
    assert decision_180.entitlements["meal_voucher"] is True
    assert decision_180.entitlements["meal_voucher_amount"] == "standard"
    assert decision_180.entitlements["lounge_access"] is True
    assert decision_180.entitlements["hotel_accommodation"] is False

    # 300 minutes (exact 5 hours boundary) -> meal voucher + lounge access
    seg_300 = FlightSegment(
        segment_id="S3", flight_number="SK-103", route="DEL-BOM", origin="DEL", destination="BOM",
        date="Wed 23 Sep 2026", date_iso="2026-09-23", scheduled_departure="10:00",
        status="Delayed", disruption_type=DisruptionType.DELAY, disruption_cause="airline_delay",
        delay_minutes=300
    )
    decision_300 = PolicyEngine.evaluate_delay(silver_customer, seg_300)
    assert decision_300.entitlements["meal_voucher"] is True
    assert decision_300.entitlements["lounge_access"] is True
    assert decision_300.entitlements["hotel_accommodation"] is False

    # 301 minutes (> 5 hours) -> meal voucher + hotel for delayed hours only (NO lounge per literal rule)
    seg_301 = FlightSegment(
        segment_id="S4", flight_number="SK-104", route="DEL-BOM", origin="DEL", destination="BOM",
        date="Wed 23 Sep 2026", date_iso="2026-09-23", scheduled_departure="10:00",
        status="Delayed", disruption_type=DisruptionType.DELAY, disruption_cause="airline_delay",
        delay_minutes=301
    )
    decision_301 = PolicyEngine.evaluate_delay(silver_customer, seg_301)
    assert decision_301.entitlements["meal_voucher"] is True
    assert decision_301.entitlements["hotel_accommodation"] is True
    assert decision_301.entitlements["hotel_delayed_hours_only"] is True
    assert decision_301.entitlements["lounge_access"] is False


def test_cancellation_options_and_priority(gold_customer, silver_customer):
    seg_canc = FlightSegment(
        segment_id="S5", flight_number="SK-204", route="Delhi → Goa", origin="Delhi", destination="Goa",
        date="Wed 23 Sep 2026", date_iso="2026-09-23", scheduled_departure="18:40",
        status="Cancelled", disruption_type=DisruptionType.CANCELLATION, disruption_cause="airline_operational"
    )

    # Gold Customer Rebooking -> Priority true
    decision_gold = PolicyEngine.evaluate_cancellation(gold_customer, seg_canc, choice="rebook")
    assert decision_gold.allowed is True
    assert decision_gold.entitlements["is_priority_rebooking"] is True
    assert decision_gold.entitlements["rebook_cost"] == 0

    # Silver Customer Rebooking -> Priority false
    decision_silver = PolicyEngine.evaluate_cancellation(silver_customer, seg_canc, choice="rebook")
    assert decision_silver.allowed is True
    assert decision_silver.entitlements["is_priority_rebooking"] is False

    # Refund check
    decision_refund = PolicyEngine.evaluate_cancellation(gold_customer, seg_canc, choice="refund")
    assert decision_refund.allowed is True
    assert decision_refund.action_type == "initiate_refund"
    assert "7 business days" in decision_refund.entitlements["refund_timeframe"]
    assert "original payment method only" in decision_refund.entitlements["refund_method"]


def test_cancellation_upgrade_request_escalation(gold_customer):
    seg_canc = FlightSegment(
        segment_id="S5", flight_number="SK-204", route="Delhi → Goa", origin="Delhi", destination="Goa",
        date="Wed 23 Sep 2026", date_iso="2026-09-23", scheduled_departure="18:40",
        status="Cancelled", disruption_type=DisruptionType.CANCELLATION, disruption_cause="airline_operational"
    )
    decision = PolicyEngine.evaluate_cancellation(gold_customer, seg_canc, requested_upgrade=True)
    assert decision.allowed is False
    assert decision.escalation_required is True
    assert "upgrade" in decision.escalation_reason.lower()


def test_fare_difference_rules(platinum_customer):
    # Default path: customer pays difference, no escalation
    dec_default = PolicyEngine.evaluate_fare_difference(platinum_customer, 2000.0, waiver_requested=False)
    assert dec_default.allowed is True
    assert dec_default.escalation_required is False
    assert dec_default.entitlements["fare_difference"] == 2000.0

    # Waiver requested > ₹1,500 -> supervisor escalation
    dec_waiver = PolicyEngine.evaluate_fare_difference(platinum_customer, 2000.0, waiver_requested=True)
    assert dec_waiver.allowed is False
    assert dec_waiver.escalation_required is True
    assert "1,500" in dec_waiver.explanation


def test_non_airline_disruption_escalation(silver_customer):
    dec = PolicyEngine.evaluate_non_airline_disruption(silver_customer, "missed my flight")
    assert dec.allowed is False
    assert dec.escalation_required is True
    assert "Prohibited Actions" in dec.rule_name


def test_legal_threat_detection():
    assert PolicyEngine.detect_legal_or_formal_complaint("I will talk to my lawyer") == "lawyer"
    assert PolicyEngine.detect_legal_or_formal_complaint("I want to file a formal complaint") in ("formal complaint", "file a formal complaint", "file a complaint")
    assert PolicyEngine.detect_legal_or_formal_complaint("I am going to sue your airline") == "sue"
    assert PolicyEngine.detect_legal_or_formal_complaint("I will lodge a complaint with consumer forum") in ("lodge a complaint", "consumer forum")
    
    # Emotional words should NOT trigger legal escalation
    assert PolicyEngine.detect_legal_or_formal_complaint("I am furious about this delay") is None
    assert PolicyEngine.detect_legal_or_formal_complaint("This service is completely unacceptable and terrible") is None
