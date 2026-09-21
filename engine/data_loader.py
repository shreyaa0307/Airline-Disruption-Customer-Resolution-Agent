import json
import os
from typing import Dict, List, Optional
from engine.models import Customer, Booking, FlightSegment, TravelHistory, ComplaintRecord, LoyaltyTier, DisruptionType


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_customers(data_dir: str = DATA_DIR) -> Dict[str, Customer]:
    path = os.path.join(data_dir, "customers.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    customers = {}
    for item in data:
        complaints = [
            ComplaintRecord(type=c["type"], resolution=c["resolution"])
            for c in item["travel_history"].get("prior_complaints", [])
        ]
        history = TravelHistory(
            flights_last_12_months=item["travel_history"]["flights_last_12_months"],
            prior_complaints=complaints
        )
        cust = Customer(
            id=item["id"],
            name=item["name"],
            loyalty_tier=LoyaltyTier(item["loyalty_tier"]),
            booking_reference=item["booking_reference"],
            email=item["email"],
            phone=item["phone"],
            travel_history=history
        )
        customers[cust.id] = cust
    return customers


def load_bookings(data_dir: str = DATA_DIR) -> Dict[str, Booking]:
    path = os.path.join(data_dir, "bookings.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    bookings = {}
    for item in data:
        segments = []
        for s in item["segments"]:
            seg = FlightSegment(
                segment_id=s["segment_id"],
                flight_number=s["flight_number"],
                route=s["route"],
                origin=s["origin"],
                destination=s["destination"],
                date=s["date"],
                date_iso=s["date_iso"],
                scheduled_departure=s["scheduled_departure"],
                status=s["status"],
                disruption_type=DisruptionType(s["disruption_type"]),
                disruption_cause=s["disruption_cause"],
                delay_minutes=s.get("delay_minutes", 0),
                new_departure=s.get("new_departure")
            )
            segments.append(seg)
        booking = Booking(
            pnr=item["pnr"],
            customer_id=item["customer_id"],
            customer_name=item["customer_name"],
            segments=segments
        )
        bookings[booking.pnr] = booking
    return bookings


def load_policies(data_dir: str = DATA_DIR) -> Dict:
    path = os.path.join(data_dir, "policies.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class DataContext:
    def __init__(self, data_dir: str = DATA_DIR):
        self.customers_by_id = load_customers(data_dir)
        self.customers_by_pnr = {c.booking_reference: c for c in self.customers_by_id.values()}
        self.bookings_by_pnr = load_bookings(data_dir)
        self.policies = load_policies(data_dir)

    def get_customer_by_id(self, customer_id: str) -> Optional[Customer]:
        return self.customers_by_id.get(customer_id)

    def get_customer_by_pnr(self, pnr: str) -> Optional[Customer]:
        return self.customers_by_pnr.get(pnr)

    def get_booking_for_customer(self, customer: Customer) -> Optional[Booking]:
        """Strict isolation: customer can only access their own booking."""
        return self.bookings_by_pnr.get(customer.booking_reference)

    def check_cross_customer_access(self, authenticated_customer: Customer, requested_pnr: str) -> bool:
        """Returns True if the authenticated customer is authorized to access the requested PNR."""
        return authenticated_customer.booking_reference == requested_pnr
