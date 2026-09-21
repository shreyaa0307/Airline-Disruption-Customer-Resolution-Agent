from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class DisruptionType(str, Enum):
    CANCELLATION = "cancellation"
    DELAY = "delay"
    NONE = "none"


class LoyaltyTier(str, Enum):
    PLATINUM = "Platinum"
    GOLD = "Gold"
    SILVER = "Silver"


@dataclass
class ComplaintRecord:
    type: str
    resolution: str


@dataclass
class TravelHistory:
    flights_last_12_months: int
    prior_complaints: List[ComplaintRecord] = field(default_factory=list)


@dataclass
class Customer:
    id: str
    name: str
    loyalty_tier: LoyaltyTier
    booking_reference: str
    email: str
    phone: str
    travel_history: TravelHistory


@dataclass
class FlightSegment:
    segment_id: str
    flight_number: str
    route: str
    origin: str
    destination: str
    date: str
    date_iso: str
    scheduled_departure: str
    status: str
    disruption_type: DisruptionType
    disruption_cause: str
    delay_minutes: int = 0
    new_departure: Optional[str] = None


@dataclass
class Booking:
    pnr: str
    customer_id: str
    customer_name: str
    segments: List[FlightSegment] = field(default_factory=list)


@dataclass
class PolicyDecision:
    allowed: bool
    action_type: str
    rule_id: str
    rule_name: str
    rule_citation: str
    explanation: str
    entitlements: Dict[str, Any] = field(default_factory=dict)
    escalation_required: bool = False
    escalation_reason: Optional[str] = None
    requires_confirmation: bool = False


@dataclass
class ActionLogEntry:
    action_id: str
    timestamp: str  # Simulated 2026-09-23T...
    pnr: str
    customer_name: str
    action_type: str
    parameters: Dict[str, Any]
    status: str
    rule_citation: str
    details: str


@dataclass
class EscalationTicket:
    ticket_id: str
    timestamp: str
    pnr: str
    customer_name: str
    loyalty_tier: str
    reason: str
    trigger_text: str
    status: str = "OPEN"
    notes: str = ""
    rule_citation: str = ""


@dataclass
class ChatMessage:
    sender: str  # "customer", "agent", "system"
    text: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
