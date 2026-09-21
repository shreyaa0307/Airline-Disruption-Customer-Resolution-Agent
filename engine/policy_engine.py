import re
from typing import Dict, Any, List, Optional, Tuple
from engine.models import Customer, Booking, FlightSegment, PolicyDecision, LoyaltyTier, DisruptionType


LEGAL_THREAT_KEYWORDS = [
    "lawyer",
    "legal",
    "legal action",
    "court",
    "sue",
    "lawsuit",
    "formal complaint",
    "file a complaint",
    "file a formal complaint",
    "lodge a complaint",
    "lodge a formal complaint",
    "register a complaint",
    "consumer forum",
    "consumer court",
    "litigation",
    "attorney"
]

NON_AIRLINE_CAUSE_KEYWORDS = [
    "missed my flight",
    "missed the flight",
    "stuck in traffic",
    "overslept",
    "personal emergency",
    "late to the airport",
    "missed check-in"
]


class PolicyEngine:
    """Pure Python Deterministic Policy Engine for Airline Disruption Resolution."""

    @staticmethod
    def detect_legal_or_formal_complaint(text: str) -> Optional[str]:
        """Detects if customer utterance contains a legal threat or formal complaint request.
        Returns the matched trigger phrase or None.
        """
        text_lower = text.lower()
        for kw in LEGAL_THREAT_KEYWORDS:
            # Use regex word boundaries where appropriate to avoid false positives
            pattern = rf"\b{re.escape(kw)}\b"
            if re.search(pattern, text_lower):
                return kw
        return None

    @staticmethod
    def detect_non_airline_disruption_cause(text: str) -> Optional[str]:
        """Detects if customer mentions a non-airline-caused disruption reason."""
        text_lower = text.lower()
        for kw in NON_AIRLINE_CAUSE_KEYWORDS:
            if kw in text_lower:
                return kw
        return None

    @staticmethod
    def evaluate_cancellation(
        customer: Customer,
        segment: FlightSegment,
        choice: Optional[str] = None,  # "rebook", "refund", None
        requested_upgrade: bool = False,
        alternate_payment_method_insisted: bool = False
    ) -> PolicyDecision:
        """Evaluates entitlements for an airline-caused cancelled flight."""
        if segment.disruption_type != DisruptionType.CANCELLATION:
            return PolicyDecision(
                allowed=False,
                action_type="none",
                rule_id="RULE-CANC-01",
                rule_name="Cancellation Rebooking Rule",
                rule_citation="Data Pack Section 3: Cancellation Rebooking Rule",
                explanation="Flight is not cancelled."
            )

        is_priority = customer.loyalty_tier in (LoyaltyTier.GOLD, LoyaltyTier.PLATINUM)

        # Base entitlements
        entitlements = {
            "rebook_available": True,
            "rebook_window": "next available flight within 24 hours",
            "rebook_cost": 0,
            "is_priority_rebooking": is_priority,
            "refund_available": True,
            "refund_timeframe": "within 7 business days",
            "refund_method": "original payment method only"
        }

        # Check if customer requested an upgrade or compensation beyond policy
        if requested_upgrade:
            return PolicyDecision(
                allowed=False,
                action_type="escalate_to_human",
                rule_id="RULE-PROHIBITED-01",
                rule_name="Prohibited Actions - Beyond Policy Compensation",
                rule_citation="Data Pack Section 4: Prohibited Actions",
                explanation="Complimentary cabin upgrades or additional compensation beyond standard policy are not permitted for agent approval.",
                entitlements=entitlements,
                escalation_required=True,
                escalation_reason="Customer requested complimentary business class upgrade on return leg beyond standard cancellation policy."
            )

        # Check if customer insisted on a non-original refund payment method
        if alternate_payment_method_insisted:
            return PolicyDecision(
                allowed=False,
                action_type="escalate_to_human",
                rule_id="RULE-REFUND-01",
                rule_name="Refund Processing Rule",
                rule_citation="Data Pack Section 3 & 4: Refund Processing Rule & Prohibited Actions",
                explanation="Refunds can only be issued to the original payment method by automated agent. Processing refunds to alternative payment methods requires escalation.",
                entitlements=entitlements,
                escalation_required=True,
                escalation_reason="Customer insisted on refund via alternative payment method (e.g., cash) rather than original payment method."
            )

        if choice == "rebook":
            return PolicyDecision(
                allowed=True,
                action_type="rebook_request",
                rule_id="RULE-CANC-01",
                rule_name="Cancellation Rebooking Rule",
                rule_citation="Data Pack Section 3: Cancellation Rebooking Rule & Loyalty Tier Rule",
                explanation=f"Entitled to free rebooking on the next available flight within 24 hours{' with priority queue access' if is_priority else ''}.",
                entitlements=entitlements,
                requires_confirmation=False
            )
        elif choice == "refund":
            return PolicyDecision(
                allowed=True,
                action_type="initiate_refund",
                rule_id="RULE-REFUND-01",
                rule_name="Refund Processing Rule",
                rule_citation="Data Pack Section 3: Refund Processing Rule",
                explanation="Entitled to a full refund processed in full within 7 business days to the original payment method only.",
                entitlements=entitlements,
                requires_confirmation=False
            )
        else:
            # Customer has not made a confirmed choice yet
            return PolicyDecision(
                allowed=True,
                action_type="offer_options",
                rule_id="RULE-CANC-01",
                rule_name="Cancellation Rebooking Rule",
                rule_citation="Data Pack Section 3: Cancellation Rebooking Rule",
                explanation="Customer is entitled to choose between free rebooking on the next available flight within 24 hours or a full refund within 7 business days to the original payment method.",
                entitlements=entitlements,
                requires_confirmation=True
            )

    @staticmethod
    def evaluate_delay(customer: Customer, segment: FlightSegment) -> PolicyDecision:
        """Evaluates delay compensation tier based on delay_minutes."""
        if segment.disruption_type != DisruptionType.DELAY:
            return PolicyDecision(
                allowed=False,
                action_type="none",
                rule_id="RULE-DELAY-01",
                rule_name="Delay Compensation Rule",
                rule_citation="Data Pack Section 3: Delay Compensation Rule",
                explanation="Flight is not delayed."
            )

        delay_minutes = segment.delay_minutes

        # Boundary Definitions:
        # < 180 minutes: Tier 1 (₹500 meal voucher)
        # 180 to 300 minutes: Tier 2 (meal voucher + lounge access)
        # > 300 minutes: Tier 3 (meal voucher + hotel accommodation for delayed hours only)
        if delay_minutes < 180:
            tier = "under_3h"
            entitlements = {
                "meal_voucher": True,
                "meal_voucher_amount": "₹500",
                "lounge_access": False,
                "hotel_accommodation": False,
                "hotel_delayed_hours_only": False
            }
            explanation = "Delay under 3 hours entitles customer to a ₹500 meal voucher."
            citation = "Data Pack Section 3: Delay Compensation Rule (Delay under 3 hours: ₹500 meal voucher)"
        elif 180 <= delay_minutes <= 300:
            tier = "3h_to_5h"
            entitlements = {
                "meal_voucher": True,
                "meal_voucher_amount": "standard",  # No rupee figure stated in pack for this tier
                "lounge_access": True,
                "hotel_accommodation": False,
                "hotel_delayed_hours_only": False
            }
            explanation = "Delay of more than 3 hours entitles customer to a meal voucher and lounge access."
            citation = "Data Pack Section 3: Delay Compensation Rule (Delay more than 3 hours: meal voucher + lounge access)"
        else:
            tier = "over_5h"
            # Literal interpretation of pack: meal voucher + hotel for delayed hours only. Lounge access is not listed.
            entitlements = {
                "meal_voucher": True,
                "meal_voucher_amount": "standard",  # No rupee figure stated in pack for this tier
                "lounge_access": False,
                "hotel_accommodation": True,
                "hotel_delayed_hours_only": True
            }
            explanation = "Delay of more than 5 hours entitles customer to a meal voucher and hotel accommodation covering only the delayed hours (not a full night's stay)."
            citation = "Data Pack Section 3: Delay Compensation Rule (Delay more than 5 hours: meal voucher + hotel accommodation, covering only the delayed hours)"

        return PolicyDecision(
            allowed=True,
            action_type="delay_compensation",
            rule_id="RULE-DELAY-01",
            rule_name="Delay Compensation Rule",
            rule_citation=citation,
            explanation=explanation,
            entitlements=entitlements
        )

    @staticmethod
    def evaluate_hotel_request(customer: Customer, segment: FlightSegment, full_night_requested: bool = False) -> PolicyDecision:
        """Evaluates a hotel accommodation request."""
        delay_eval = PolicyEngine.evaluate_delay(customer, segment)
        delay_minutes = segment.delay_minutes

        if delay_minutes <= 300:
            # Under or equal to 5 hours -> No hotel entitlement
            return PolicyDecision(
                allowed=False,
                action_type="decline_hotel",
                rule_id="RULE-DELAY-01",
                rule_name="Delay Compensation Rule",
                rule_citation="Data Pack Section 3: Delay Compensation Rule",
                explanation="Hotel accommodation is only provided for delays exceeding 5 hours. For delays between 3 and 5 hours, entitlements are a meal voucher and lounge access.",
                entitlements=delay_eval.entitlements,
                escalation_required=False
            )

        if full_night_requested:
            # More than 5 hours, but customer asks for full night stay
            return PolicyDecision(
                allowed=False,
                action_type="decline_full_night_hotel",
                rule_id="RULE-DELAY-01",
                rule_name="Delay Compensation Rule",
                rule_citation="Data Pack Section 3: Delay Compensation Rule",
                explanation="Under our policy, hotel accommodation covers only the delayed hours portion, not a full night's stay.",
                entitlements=delay_eval.entitlements,
                escalation_required=False  # Agent can offer the delayed-hours stay per policy; escalate only if customer insists on full night exception
            )

        # Qualifies for delayed hours hotel
        return PolicyDecision(
            allowed=True,
            action_type="arrange_hotel",
            rule_id="RULE-DELAY-01",
            rule_name="Delay Compensation Rule",
            rule_citation="Data Pack Section 3: Delay Compensation Rule",
            explanation="Customer is entitled to hotel accommodation covering only the delayed hours portion.",
            entitlements=delay_eval.entitlements,
            requires_confirmation=True  # Confirm with customer before logging hotel
        )

    @staticmethod
    def evaluate_fare_difference(
        customer: Customer,
        fare_difference_amount: float,
        waiver_requested: bool = False
    ) -> PolicyDecision:
        """Evaluates voluntary rebooking on a higher-fare flight."""
        if not waiver_requested:
            # Customer pays difference by default, no proactive waiver
            return PolicyDecision(
                allowed=True,
                action_type="voluntary_rebook_with_fare_diff",
                rule_id="RULE-FARE-01",
                rule_name="Fare Difference Rule",
                rule_citation="Data Pack Section 3: Fare Difference Rule",
                explanation=f"Customer voluntarily choosing a higher-fare flight pays the fare difference (₹{int(fare_difference_amount):,}).",
                entitlements={"fare_difference": fare_difference_amount, "waiver_offered": False},
                escalation_required=False
            )

        # Customer specifically asked for a waiver
        if fare_difference_amount > 1500:
            return PolicyDecision(
                allowed=False,
                action_type="escalate_to_human",
                rule_id="RULE-FARE-01",
                rule_name="Fare Difference Rule & Prohibited Actions",
                rule_citation="Data Pack Section 3 & 4: Fare Difference Rule & Prohibited Actions",
                explanation="Agents cannot waive fare differences above ₹1,500 without supervisor approval. This request must be escalated to a supervisor.",
                entitlements={"fare_difference": fare_difference_amount, "waiver_requested": True},
                escalation_required=True,
                escalation_reason=f"Customer requested waiver of ₹{int(fare_difference_amount):,} fare difference, which exceeds the ₹1,500 supervisor approval limit."
            )
        else:
            # Assumption: Pack does not state agents may waive up to ₹1,500 on their own, so customer pays or request is escalated.
            return PolicyDecision(
                allowed=False,
                action_type="escalate_to_human",
                rule_id="RULE-FARE-01",
                rule_name="Fare Difference Rule",
                rule_citation="Data Pack Section 3 & 4: Fare Difference Rule",
                explanation="Fare difference waiver requested. Policy requires supervisor review.",
                entitlements={"fare_difference": fare_difference_amount, "waiver_requested": True},
                escalation_required=True,
                escalation_reason=f"Customer requested waiver of ₹{int(fare_difference_amount):,} fare difference."
            )

    @staticmethod
    def evaluate_non_airline_disruption(customer: Customer, trigger_text: str) -> PolicyDecision:
        """Evaluates exceptions for non-airline-caused disruptions."""
        return PolicyDecision(
            allowed=False,
            action_type="escalate_to_human",
            rule_id="RULE-PROHIBITED-01",
            rule_name="Prohibited Actions - Non-Airline-Caused Disruptions",
            rule_citation="Data Pack Section 4: Prohibited Actions",
            explanation="Making exceptions for non-airline-caused disruptions (e.g. missed flight, personal delays) is prohibited for automated agents and must be escalated.",
            escalation_required=True,
            escalation_reason=f"Customer requested exception for non-airline-caused disruption: '{trigger_text}'"
        )
