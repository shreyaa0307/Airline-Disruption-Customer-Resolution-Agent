from typing import List, Dict, Any, Optional
from datetime import datetime
from engine.models import ActionLogEntry, EscalationTicket, Customer, LoyaltyTier


# Simulated Reference Timestamp Base for 23 September 2026
SIMULATED_BASE_TIME = "2026-09-23T18:45:00+05:30"


class ActionLogger:
    """Maintains an auditable log of all actions and escalation tickets taken in the session."""

    def __init__(self):
        self.logs: List[ActionLogEntry] = []
        self.escalations: List[EscalationTicket] = []
        self._action_counter = 1
        self._escalation_counter = 1
        self._minute_offset = 0

    def _get_timestamp(self) -> str:
        """Generates a sequential timestamp on the simulated date Wednesday 23 September 2026."""
        hour = 18 + (self._minute_offset // 60)
        minute = 45 + (self._minute_offset % 60)
        if minute >= 60:
            hour += minute // 60
            minute = minute % 60
        self._minute_offset += 1
        return f"2026-09-23T{hour:02d}:{minute:02d}:00+05:30"

    def clear(self):
        self.logs.clear()
        self.escalations.clear()
        self._action_counter = 1
        self._escalation_counter = 1
        self._minute_offset = 0

    def log_action(
        self,
        pnr: str,
        customer_name: str,
        action_type: str,
        parameters: Dict[str, Any],
        status: str,
        rule_citation: str,
        details: str
    ) -> ActionLogEntry:
        action_id = f"ACT-{self._action_counter:03d}"
        self._action_counter += 1
        entry = ActionLogEntry(
            action_id=action_id,
            timestamp=self._get_timestamp(),
            pnr=pnr,
            customer_name=customer_name,
            action_type=action_type,
            parameters=parameters,
            status=status,
            rule_citation=rule_citation,
            details=details
        )
        self.logs.append(entry)
        return entry

    def log_escalation(
        self,
        pnr: str,
        customer_name: str,
        loyalty_tier: str,
        reason: str,
        trigger_text: str,
        notes: str = "",
        rule_citation: str = ""
    ) -> EscalationTicket:
        ticket_id = f"ESC-{self._escalation_counter:03d}"
        self._escalation_counter += 1
        ticket = EscalationTicket(
            ticket_id=ticket_id,
            timestamp=self._get_timestamp(),
            pnr=pnr,
            customer_name=customer_name,
            loyalty_tier=loyalty_tier,
            reason=reason,
            trigger_text=trigger_text,
            status="OPEN",
            notes=notes,
            rule_citation=rule_citation
        )
        self.escalations.append(ticket)
        return ticket


class ActionTools:
    """Executes actions permitted under airline policy and registers them in the action log."""

    def __init__(self, logger: ActionLogger):
        self.logger = logger

    def rebook_request(
        self,
        pnr: str,
        customer: Customer,
        is_priority: bool = False,
        fare_difference: float = 0.0,
        notes: str = ""
    ) -> ActionLogEntry:
        """Records a rebooking request for the next available flight within 24 hours."""
        priority_label = "Priority Rebooking (Gold/Platinum)" if is_priority else "Standard Rebooking"
        fare_text = f" [Fare difference payable: ₹{int(fare_difference):,}]" if fare_difference > 0 else " [Free Rebooking]"
        details = (
            f"Logged {priority_label} request for next available flight within 24 hours.{fare_text} "
            f"Confirmation will be sent to {customer.email}."
        )
        return self.logger.log_action(
            pnr=pnr,
            customer_name=customer.name,
            action_type="rebook_request",
            parameters={
                "pnr": pnr,
                "is_priority": is_priority,
                "window": "next available flight within 24 hours",
                "fare_difference": fare_difference,
                "notes": notes
            },
            status="CONFIRMED",
            rule_citation="Data Pack Section 3: Cancellation Rebooking Rule & Loyalty Tier Rule",
            details=details
        )

    def issue_meal_voucher(
        self,
        pnr: str,
        customer: Customer,
        amount: Optional[str] = None
    ) -> ActionLogEntry:
        """Issues a meal voucher to the customer."""
        voucher_text = f"₹{amount}" if amount and amount != "standard" else "standard meal voucher"
        details = f"Issued {voucher_text} to customer account / registered phone ({customer.phone})."
        return self.logger.log_action(
            pnr=pnr,
            customer_name=customer.name,
            action_type="issue_meal_voucher",
            parameters={
                "pnr": pnr,
                "amount": voucher_text,
                "recipient": customer.phone
            },
            status="ISSUED",
            rule_citation="Data Pack Section 3: Delay Compensation Rule",
            details=details
        )

    def grant_lounge_access(
        self,
        pnr: str,
        customer: Customer
    ) -> ActionLogEntry:
        """Grants airport lounge access pass to the customer."""
        details = f"Granted airport lounge access pass for flight delay to {customer.name} (PNR: {pnr})."
        return self.logger.log_action(
            pnr=pnr,
            customer_name=customer.name,
            action_type="grant_lounge_access",
            parameters={"pnr": pnr, "recipient": customer.name},
            status="GRANTED",
            rule_citation="Data Pack Section 3: Delay Compensation Rule (>3 hours delay)",
            details=details
        )

    def arrange_hotel(
        self,
        pnr: str,
        customer: Customer,
        delayed_hours_only: bool = True
    ) -> ActionLogEntry:
        """Arranges airport transit accommodation covering only the delayed hours portion."""
        scope_text = "delayed-hours portion only (not full night)" if delayed_hours_only else "full stay"
        details = f"Arranged airport partner hotel accommodation covering {scope_text} for {customer.name}."
        return self.logger.log_action(
            pnr=pnr,
            customer_name=customer.name,
            action_type="arrange_hotel",
            parameters={
                "pnr": pnr,
                "delayed_hours_only": delayed_hours_only,
                "recipient": customer.name
            },
            status="BOOKED",
            rule_citation="Data Pack Section 3: Delay Compensation Rule (>5 hours delay)",
            details=details
        )

    def initiate_refund(
        self,
        pnr: str,
        customer: Customer,
        payment_method: str = "original_payment_method"
    ) -> ActionLogEntry:
        """Initiates full refund processed in full within 7 business days to original payment method."""
        details = f"Full refund initiated for PNR {pnr}. Processed in full within 7 business days to original payment method."
        return self.logger.log_action(
            pnr=pnr,
            customer_name=customer.name,
            action_type="initiate_refund",
            parameters={
                "pnr": pnr,
                "timeframe": "within 7 business days",
                "payment_method": payment_method
            },
            status="PROCESSED",
            rule_citation="Data Pack Section 3: Refund Processing Rule",
            details=details
        )

    def escalate_to_human(
        self,
        pnr: str,
        customer: Customer,
        reason: str,
        trigger_text: str,
        notes: str = "",
        rule_citation: str = ""
    ) -> EscalationTicket:
        """Escalates case to a specialist human agent."""
        return self.logger.log_escalation(
            pnr=pnr,
            customer_name=customer.name,
            loyalty_tier=customer.loyalty_tier.value,
            reason=reason,
            trigger_text=trigger_text,
            notes=notes,
            rule_citation=rule_citation or "Data Pack Section 4: Prohibited Actions"
        )
