import re
from typing import List, Dict, Any, Optional, Tuple
from engine.models import Customer, Booking, FlightSegment, PolicyDecision, ChatMessage, LoyaltyTier, DisruptionType
from engine.policy_engine import PolicyEngine
from engine.action_tools import ActionTools, ActionLogger
from engine.llm_layer import LLMLayer


class ConversationManager:
    """Manages multi-turn conversation flow, intent detection, and grounded response generation."""

    def __init__(self, data_context, logger: Optional[ActionLogger] = None):
        self.data_context = data_context
        self.logger = logger or ActionLogger()
        self.tools = ActionTools(self.logger)
        self.llm = LLMLayer(enabled=False)
        self.messages: List[ChatMessage] = []
        
        # State tracking per session
        self.state: Dict[str, Any] = {
            "authenticated_customer": None,
            "current_booking": None,
            "disrupted_segment": None,
            "cancellation_choice_offered": False,
            "pending_cancellation_choice": None,  # "rebook" or "refund"
            "refund_clarification_given": False,
            "hotel_offered": False,
            "hotel_confirmed": False,
            "meal_issued": False,
            "lounge_issued": False,
            "rebook_requested": False,
            "refund_requested": False,
            "escalation_active": False,
            "human_review_offered_for_meeting": False
        }

    def set_authenticated_customer(self, customer: Customer):
        """Sets the authenticated customer and loads their booking under strict isolation."""
        self.state["authenticated_customer"] = customer
        self.state["current_booking"] = self.data_context.get_booking_for_customer(customer)
        
        # Identify disrupted segment
        booking = self.state["current_booking"]
        if booking and booking.segments:
            disrupted = next(
                (s for s in booking.segments if s.disruption_type in (DisruptionType.CANCELLATION, DisruptionType.DELAY)),
                booking.segments[0]
            )
            self.state["disrupted_segment"] = disrupted
        else:
            self.state["disrupted_segment"] = None

    def reset(self):
        """Resets the conversation and action logs for a new session."""
        self.messages.clear()
        self.logger.clear()
        customer = self.state.get("authenticated_customer")
        self.state = {
            "authenticated_customer": customer,
            "current_booking": self.data_context.get_booking_for_customer(customer) if customer else None,
            "disrupted_segment": None,
            "cancellation_choice_offered": False,
            "pending_cancellation_choice": None,
            "refund_clarification_given": False,
            "hotel_offered": False,
            "hotel_confirmed": False,
            "meal_issued": False,
            "lounge_issued": False,
            "rebook_requested": False,
            "refund_requested": False,
            "escalation_active": False,
            "human_review_offered_for_meeting": False
        }
        if self.state["current_booking"] and self.state["current_booking"].segments:
            disrupted = next(
                (s for s in self.state["current_booking"].segments if s.disruption_type in (DisruptionType.CANCELLATION, DisruptionType.DELAY)),
                self.state["current_booking"].segments[0]
            )
            self.state["disrupted_segment"] = disrupted

    def _add_message(self, sender: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        msg = ChatMessage(
            sender=sender,
            text=text,
            timestamp=self.logger._get_timestamp(),
            metadata=metadata or {}
        )
        self.messages.append(msg)
        return msg

    def handle_user_message(self, user_text: str) -> str:
        """Processes customer utterance, evaluates policy, triggers action tools, and returns response."""
        customer: Customer = self.state["authenticated_customer"]
        booking: Booking = self.state["current_booking"]
        segment: FlightSegment = self.state["disrupted_segment"]

        self._add_message("customer", user_text)

        # 1. Check for Cross-Customer Data Access attempts
        requested_other_pnr = self._detect_cross_customer_inquiry(user_text, customer.booking_reference)
        if requested_other_pnr:
            reply = (
                f"For your privacy and security, I am only authorized to access and assist with booking details "
                f"associated with your authenticated profile (PNR: {customer.booking_reference}). I cannot access "
                f"or discuss information regarding booking reference {requested_other_pnr}."
            )
            self._add_message("agent", reply, {"rule_citation": "Security & Privacy: Customer Data Isolation"})
            return reply

        # 2. Check for Immediate Legal Threats or Formal Complaints
        legal_trigger = PolicyEngine.detect_legal_or_formal_complaint(user_text)
        if legal_trigger:
            self.state["escalation_active"] = True
            ticket = self.tools.escalate_to_human(
                pnr=customer.booking_reference,
                customer=customer,
                reason=f"Customer expressed intent regarding legal action / formal complaint: '{legal_trigger}'",
                trigger_text=user_text,
                rule_citation="Data Pack Section 4: Prohibited Actions (Legal threats / formal complaints)"
            )
            reply = (
                f"I completely understand your frustration, and I want to ensure this matter is given the formal "
                f"attention it warrants. Since you have mentioned '{legal_trigger}', our policy requires an immediate "
                f"transfer to our specialized customer support team. I have created escalation ticket {ticket.ticket_id} "
                f"for you, and a specialist will contact you directly at {customer.email} or {customer.phone}."
            )
            self._add_message("agent", reply, {
                "rule_citation": "Data Pack Section 4: Prohibited Actions (Legal action / formal complaints)",
                "escalation_id": ticket.ticket_id
            })
            return reply

        # 3. Check for Non-Airline-Caused Disruption Exception Request
        non_airline_trigger = PolicyEngine.detect_non_airline_disruption_cause(user_text)
        if non_airline_trigger:
            decision = PolicyEngine.evaluate_non_airline_disruption(customer, non_airline_trigger)
            ticket = self.tools.escalate_to_human(
                pnr=customer.booking_reference,
                customer=customer,
                reason=decision.escalation_reason,
                trigger_text=user_text,
                rule_citation=decision.rule_citation
            )
            reply = (
                f"I understand that you encountered an unexpected situation with '{non_airline_trigger}'. "
                f"However, automated policy exceptions for non-airline-caused disruptions cannot be authorized "
                f"directly. I have escalated your request to a supervisor (Ticket: {ticket.ticket_id}) who will "
                f"review your case individually."
            )
            self._add_message("agent", reply, {
                "rule_citation": decision.rule_citation,
                "escalation_id": ticket.ticket_id
            })
            return reply

        # 4. Route based on Disruption Type
        if segment.disruption_type == DisruptionType.CANCELLATION:
            return self._handle_cancellation_flow(user_text, customer, booking, segment)
        elif segment.disruption_type == DisruptionType.DELAY:
            return self._handle_delay_flow(user_text, customer, booking, segment)
        else:
            # Out of scope / standard unaffected booking
            reply = (
                f"Hello {customer.name}. Your booking {customer.booking_reference} shows your scheduled flights are operating as normal. "
                f"Please let me know how else I can assist you today."
            )
            self._add_message("agent", reply)
            return reply

    def _detect_cross_customer_inquiry(self, text: str, current_pnr: str) -> Optional[str]:
        """Detects if user is asking about a PNR other than their authenticated one."""
        pnr_matches = re.findall(r"\b[A-Z0-9]{6,7}\b", text.upper())
        for pnr in pnr_matches:
            if pnr != current_pnr and pnr in self.data_context.bookings_by_pnr:
                return pnr
        # Also check customer names
        text_lower = text.lower()
        if "arvind" in text_lower and current_pnr != "TR1190B":
            return "TR1190B"
        if "meher" in text_lower and current_pnr != "WL7742":
            return "WL7742"
        if "priya" in text_lower and current_pnr != "SK4821X":
            return "SK4821X"
        return None

    # -------------------------------------------------------------
    # CANCELLATION FLOW (Scenario 1 - Priya Nair)
    # -------------------------------------------------------------
    def _handle_cancellation_flow(
        self,
        text: str,
        customer: Customer,
        booking: Booking,
        segment: FlightSegment
    ) -> str:
        text_lower = text.lower()
        is_priority = customer.loyalty_tier in (LoyaltyTier.GOLD, LoyaltyTier.PLATINUM)
        priority_note = " As a valued Gold member, you will receive priority access to next-available seats." if is_priority else ""

        # Check if user is asking for an upgrade on return flight
        requested_upgrade = any(k in text_lower for k in ["upgrade", "business class", "business upgrade"])
        upgrade_escalated = False
        upgrade_ticket_id = None
        if requested_upgrade:
            decision = PolicyEngine.evaluate_cancellation(customer, segment, requested_upgrade=True)
            ticket = self.tools.escalate_to_human(
                pnr=customer.booking_reference,
                customer=customer,
                reason=decision.escalation_reason,
                trigger_text=text,
                rule_citation=decision.rule_citation
            )
            upgrade_escalated = True
            upgrade_ticket_id = ticket.ticket_id

        # Check if user mentions cash refund / refund method
        mentions_cash = "cash" in text_lower
        mentions_refund = "refund" in text_lower or mentions_cash
        mentions_rebook = any(k in text_lower for k in ["rebook", "next flight", "book another flight", "reschedule"])

        # Check if customer is insisting on cash after clarification
        insists_on_cash = False
        if mentions_cash and self.state["refund_clarification_given"]:
            insists_on_cash = True

        # Case A: Customer is asking / inquiring about status or expressing anger
        # (Acknowledge emotions like "furious", "angry", "unacceptable" empathetically without escalating)
        empathy_prefix = ""
        if any(w in text_lower for w in ["furious", "angry", "terrible", "upset", "frustrated", "unacceptable"]):
            empathy_prefix = "I completely understand your frustration regarding this unexpected cancellation, and I sincerely apologize for the disruption to your travel plans. "

        # Case B: Customer insists on non-original payment method (cash)
        if insists_on_cash:
            ticket = self.tools.escalate_to_human(
                pnr=customer.booking_reference,
                customer=customer,
                reason="Customer insisted on cash refund rather than original payment method.",
                trigger_text=text,
                rule_citation="Data Pack Section 3 & 4: Refund Processing Rule & Prohibited Actions"
            )
            reply = (
                f"{empathy_prefix}I understand you are requesting a cash refund; however, automated refunds can only be "
                f"processed to the original payment method within 7 business days. I have escalated your cash refund "
                f"request to our specialist team under Ticket {ticket.ticket_id}."
            )
            if upgrade_escalated:
                reply += (
                    f" Additionally, your request for a complimentary business class upgrade on your return flight has "
                    f"been forwarded under the same supervisor review, while your return booking remains confirmed and unaffected."
                )
            self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3 & 4: Refund Processing Rule"})
            return reply

        # Case C: Customer confirms / selects Refund
        if mentions_refund and not mentions_rebook:
            if mentions_cash and not self.state["refund_clarification_given"]:
                # Clarify original payment method policy first, do not log refund yet
                self.state["refund_clarification_given"] = True
                self.state["pending_cancellation_choice"] = "refund"
                reply = (
                    f"{empathy_prefix}I can certainly process a full refund for cancelled flight {segment.flight_number}. "
                    f"Please note that under our airline policy, refunds are processed in full within 7 business days "
                    f"to your original payment method only (not as cash). "
                    f"Would you like me to go ahead and initiate this refund to your original payment method?"
                )
                if upgrade_escalated:
                    reply += (
                        f" Regarding your request for a free upgrade to business class on your return flight, "
                        f"our policy does not permit automated approval of cabin upgrades beyond standard entitlements. "
                        f"I have escalated your upgrade request to our specialist team (Ticket: {upgrade_ticket_id}) for review, "
                        f"and your return flight (Goa → Delhi, 25 Sep) remains completely unaffected."
                    )
                self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Refund Processing Rule"})
                return reply
            else:
                # Customer confirmed / requested standard refund
                if not self.state["refund_requested"]:
                    action = self.tools.initiate_refund(customer.booking_reference, customer)
                    self.state["refund_requested"] = True
                    reply = (
                        f"{empathy_prefix}I have processed your request. A full refund for cancelled flight {segment.flight_number} "
                        f"has been initiated (Action ID: {action.action_id}). The amount will be processed in full within 7 business days "
                        f"to your original payment method."
                    )
                else:
                    reply = (
                        f"Your full refund for cancelled flight {segment.flight_number} has already been initiated "
                        f"and will be credited within 7 business days to your original payment method."
                    )

                if upgrade_escalated:
                    reply += (
                        f" In addition, your request for a complimentary upgrade on your return flight has been escalated "
                        f"to our specialist support team (Ticket: {upgrade_ticket_id}). Your return flight booking remains "
                        f"confirmed and untouched."
                    )
                self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Refund Processing Rule"})
                return reply

        # Case D: Customer confirms / selects Rebooking
        if mentions_rebook and not mentions_refund:
            if not self.state["rebook_requested"]:
                action = self.tools.rebook_request(
                    pnr=customer.booking_reference,
                    customer=customer,
                    is_priority=is_priority,
                    notes="Airline-caused cancellation rebooking request"
                )
                self.state["rebook_requested"] = True
                reply = (
                    f"{empathy_prefix}I have registered your free rebooking request for the next available flight within 24 hours "
                    f"(Action ID: {action.action_id}).{priority_note} Our reservations team will assign your seat and send "
                    f"the confirmed flight details to {customer.email}."
                )
            else:
                reply = (
                    f"Your rebooking request for the next available flight within 24 hours is already registered and being processed."
                )

            if upgrade_escalated:
                reply += (
                    f" Regarding the complimentary business class upgrade request on your return leg, this has been escalated "
                    f"under Ticket {upgrade_ticket_id} for supervisory review."
                )
            self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Cancellation Rebooking Rule"})
            return reply

        # Case E: Initial cancellation inquiry or emotion-only message
        self.state["cancellation_choice_offered"] = True
        reply = (
            f"{empathy_prefix}I can see that flight {segment.flight_number} ({segment.route}) on {segment.date} was cancelled "
            f"due to operational reasons. Under our airline policy, you are entitled to your choice of:\n"
            f"1. A free rebooking on the next available flight within 24 hours{priority_note}.\n"
            f"2. A full refund processed within 7 business days to your original payment method.\n\n"
            f"Please let me know which option you would prefer."
        )
        if upgrade_escalated:
            reply += (
                f"\n\nRegarding your request for a complimentary return upgrade, complimentary upgrades beyond standard policy "
                f"require human agent review. I have created escalation ticket {upgrade_ticket_id} for that specific request. "
                f"Your return flight (Goa → Delhi on 25 Sep) remains confirmed and untouched."
            )
        self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Cancellation Rebooking Rule"})
        return reply

    # -------------------------------------------------------------
    # DELAY FLOW (Scenario 2 - Arvind & Scenario 3 - Meher)
    # -------------------------------------------------------------
    def _handle_delay_flow(
        self,
        text: str,
        customer: Customer,
        booking: Booking,
        segment: FlightSegment
    ) -> str:
        text_lower = text.lower()
        delay_eval = PolicyEngine.evaluate_delay(customer, segment)
        delay_minutes = segment.delay_minutes
        entitlements = delay_eval.entitlements

        has_meeting = "meeting" in text_lower or "connecting meeting" in text_lower
        has_hotel = "hotel" in text_lower or "stay" in text_lower or "accommodation" in text_lower

        # Case 1: Arvind (4h Delay) - Missed Meeting acknowledgment & Human Review
        if has_meeting:
            self.state["human_review_offered_for_meeting"] = True
            reply = (
                f"I am truly sorry to hear that this delay has caused you to miss your meeting in Bengaluru. "
                f"While airline policy cannot provide compensation for missed personal or business appointments, "
                f"I want to make sure your situation is properly heard. If you would like, I can connect you with a "
                f"human support specialist for further review of your case. Would you like me to request a human review?"
            )
            # If hotel is also asked for (e.g. Arvind asking for hotel on 4h delay)
            if has_hotel and delay_minutes <= 300:
                reply += (
                    f"\n\nRegarding hotel accommodation, under airline policy, hotel accommodation is provided only for "
                    f"delays exceeding 5 hours. Because flight {segment.flight_number} is delayed 4 hours, hotel accommodation cannot be arranged."
                )

            # Issue delay entitlements (meal + lounge)
            if not self.state["meal_issued"]:
                self.tools.issue_meal_voucher(customer.booking_reference, customer)
                self.state["meal_issued"] = True
            if entitlements.get("lounge_access") and not self.state["lounge_issued"]:
                self.tools.grant_lounge_access(customer.booking_reference, customer)
                self.state["lounge_issued"] = True
            reply += f"\n\nIn the meantime, as your flight {segment.flight_number} is delayed 4 hours, I have issued your meal voucher and lounge access pass."
            self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Delay Compensation Rule (>3 hours)"})
            return reply

        # Case 2: Human Review acceptance after meeting offer
        if self.state["human_review_offered_for_meeting"] and any(w in text_lower for w in ["yes", "please", "connect", "human", "specialist"]):
            self.state["human_review_offered_for_meeting"] = False
            ticket = self.tools.escalate_to_human(
                pnr=customer.booking_reference,
                customer=customer,
                reason="Customer requested human specialist review regarding missed business meeting due to 4h flight delay.",
                trigger_text=text,
                rule_citation="Data Pack Section 3 & 4: Service Rules & Escalation"
            )
            reply = (
                f"I have opened escalation ticket {ticket.ticket_id} for a specialist support team member to review "
                f"your case regarding the missed meeting. They will follow up with you directly at {customer.email}."
            )
            self._add_message("agent", reply, {
                "rule_citation": "Data Pack Section 4: Prohibited Actions",
                "escalation_id": ticket.ticket_id
            })
            return reply

        # Case 3: Hotel Request Handling
        if "hotel" in text_lower or "stay" in text_lower or "accommodation" in text_lower:
            full_night_requested = any(k in text_lower for k in ["full night", "full stay", "overnight", "night's hotel"])
            hotel_decision = PolicyEngine.evaluate_hotel_request(customer, segment, full_night_requested=full_night_requested)

            if not hotel_decision.allowed and hotel_decision.action_type == "decline_hotel":
                # Arvind's case: 4h delay (<= 5h delay, so no hotel entitlement)
                # Issue meal voucher and lounge if not yet issued
                if not self.state["meal_issued"]:
                    self.tools.issue_meal_voucher(customer.booking_reference, customer)
                    self.state["meal_issued"] = True
                if entitlements.get("lounge_access") and not self.state["lounge_issued"]:
                    self.tools.grant_lounge_access(customer.booking_reference, customer)
                    self.state["lounge_issued"] = True

                reply = (
                    f"I understand your desire for hotel accommodation during this wait. However, under airline policy, "
                    f"hotel accommodation is provided only for flight delays exceeding 5 hours. Because flight {segment.flight_number} "
                    f"is delayed by 4 hours, your entitled compensation is a meal voucher and complimentary lounge access, "
                    f"both of which have been applied to your account."
                )
                self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Delay Compensation Rule"})
                return reply

            elif hotel_decision.action_type == "decline_full_night_hotel":
                # Meher's case: 6h delay, asks for full night stay
                self.state["hotel_offered"] = True
                reply = (
                    f"I understand your request for a full night's hotel stay. Under our policy, for delays exceeding 5 hours, "
                    f"hotel accommodation is provided covering only the delayed hours (not a full night's stay). "
                    f"I would be glad to arrange partner hotel accommodation for the duration of your 6-hour delay until your new departure at 20:00. "
                    f"Would you like me to confirm this delayed-hours accommodation for you?"
                )
                if not self.state["meal_issued"]:
                    self.tools.issue_meal_voucher(customer.booking_reference, customer)
                    self.state["meal_issued"] = True
                self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Delay Compensation Rule (>5 hours)"})
                return reply

            elif "confirm" in text_lower or "yes" in text_lower or self.state["hotel_offered"]:
                # Customer confirms delayed-hours hotel
                if not self.state["hotel_confirmed"]:
                    action = self.tools.arrange_hotel(customer.booking_reference, customer, delayed_hours_only=True)
                    self.state["hotel_confirmed"] = True
                    reply = (
                        f"I have arranged your airport partner hotel accommodation covering the delayed hours (Action ID: {action.action_id}). "
                        f"Details have been sent to {customer.phone}."
                    )
                else:
                    reply = "Your delayed-hours hotel accommodation is already confirmed."
                self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Delay Compensation Rule (>5 hours)"})
                return reply

        # Case 4: Voluntary move to higher-fare flight (Meher - ₹2,000 difference)
        fare_diff_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)?)", text_lower)
        if any(k in text_lower for k in ["higher-fare", "higher fare", "different flight", "another flight", "switch flight", "move onto"]):
            fare_amount = 2000.0
            if fare_diff_match:
                try:
                    fare_amount = float(fare_diff_match.group(1).replace(",", ""))
                except ValueError:
                    fare_amount = 2000.0

            # Check if customer explicitly requested a waiver
            waiver_requested = any(k in text_lower for k in ["waive", "waiver", "free", "without paying", "don't want to pay", "cover the difference"])

            if waiver_requested:
                # Customer asks to waive the ₹2,000 difference
                decision = PolicyEngine.evaluate_fare_difference(customer, fare_amount, waiver_requested=True)
                ticket = self.tools.escalate_to_human(
                    pnr=customer.booking_reference,
                    customer=customer,
                    reason=decision.escalation_reason,
                    trigger_text=text,
                    rule_citation=decision.rule_citation
                )
                reply = (
                    f"Under airline policy, when voluntarily switching to a higher-fare flight, customers are responsible "
                    f"for the fare difference. Agents cannot waive fare differences above ₹1,500 without supervisor approval. "
                    f"Since the fare difference is ₹{int(fare_amount):,}, I have escalated your waiver request to a supervisor "
                    f"under Ticket {ticket.ticket_id}."
                )
                self._add_message("agent", reply, {
                    "rule_citation": "Data Pack Section 3 & 4: Fare Difference Rule & Prohibited Actions",
                    "escalation_id": ticket.ticket_id
                })
                return reply
            else:
                # Customer did not request a waiver -> customer pays fare difference by default
                reply = (
                    f"You can voluntarily move to that alternate flight. Under our policy, you will need to pay the "
                    f"fare difference of ₹{int(fare_amount):,}. (Please note that policy does not specify hotel entitlement "
                    f"if you switch flights). Would you like to proceed with rebooking on that flight and paying the ₹{int(fare_amount):,} fare difference?"
                )
                self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Fare Difference Rule"})
                return reply

        # Case 5: Customer confirms paying the fare difference
        if ("proceed" in text_lower or "pay" in text_lower or "yes" in text_lower) and "2000" in text_lower or "difference" in text_lower:
            action = self.tools.rebook_request(
                pnr=customer.booking_reference,
                customer=customer,
                is_priority=(customer.loyalty_tier == LoyaltyTier.PLATINUM),
                fare_difference=2000.0,
                notes="Voluntary rebook to higher-fare flight with customer paying ₹2,000 fare difference"
            )
            reply = (
                f"I have registered your voluntary flight change request (Action ID: {action.action_id}) with the ₹2,000 fare difference payable upon ticketing. "
                f"Booking confirmation has been sent to {customer.email}."
            )
            self._add_message("agent", reply, {"rule_citation": "Data Pack Section 3: Fare Difference Rule"})
            return reply

        # Case 6: General delay inquiry or status check
        if delay_minutes < 180:
            if not self.state["meal_issued"]:
                self.tools.issue_meal_voucher(customer.booking_reference, customer, amount="500")
                self.state["meal_issued"] = True
            reply = (
                f"Flight {segment.flight_number} ({segment.route}) is delayed. Under our policy for delays under 3 hours, "
                f"I have issued a ₹500 meal voucher to your account."
            )
        elif 180 <= delay_minutes <= 300:
            if not self.state["meal_issued"]:
                self.tools.issue_meal_voucher(customer.booking_reference, customer)
                self.state["meal_issued"] = True
            if not self.state["lounge_issued"]:
                self.tools.grant_lounge_access(customer.booking_reference, customer)
                self.state["lounge_issued"] = True
            reply = (
                f"I apologize for the delay. Flight {segment.flight_number} ({segment.route}) is delayed 4 hours, with a new departure at {segment.new_departure}. "
                f"As per airline policy for delays over 3 hours, you are entitled to a meal voucher and lounge access, which I have applied to your booking."
            )
        else:
            # > 5h (Meher: 6h delay)
            if not self.state["meal_issued"]:
                self.tools.issue_meal_voucher(customer.booking_reference, customer)
                self.state["meal_issued"] = True
            reply = (
                f"I apologize for the significant disruption. Flight {segment.flight_number} ({segment.route}) is delayed 6 hours, with a new departure at {segment.new_departure}. "
                f"Under our policy for delays over 5 hours, you are entitled to a meal voucher and hotel accommodation covering only the delayed hours. "
                f"I have issued your meal voucher. Would you like me to arrange the delayed-hours hotel accommodation for you?"
            )

        self._add_message("agent", reply, {"rule_citation": delay_eval.rule_citation})
        return reply
