# Customer-Facing Airline Disruption Resolution Agent (Assignment 3)

A local, production-grade prototype for an airline disruption customer resolution agent built strictly using the **Assignment 3 Data Pack** (Reference Date: **Wednesday, 23 September 2026**).

---

## 🚀 Quick Start (Single Command)

```bash
pip install -r requirements.txt && streamlit run app.py
```

### Running Automated Test Suite

```bash
pytest -v
```

---

## 🏛️ System Architecture

1. **Pure Python Policy Engine (`engine/policy_engine.py`)**:
   - Zero-hallucination, deterministic rule evaluator.
   - Evaluates delay tiers based on minutes (<180m, 180m-300m, >300m).
   - Enforces cancellation entitlements (Free rebooking within 24h OR full refund in 7 business days to original payment method).
   - Validates loyalty tier priorities (Gold/Platinum priority seat access).
   - Evaluates voluntary fare differences (customer pays by default; supervisor approval required for waivers above ₹1,500).
   - Detects and isolates escalation triggers (legal threats, formal complaints, non-airline disruptions, unauthorized compensation).
   - Returns structured policy decisions with exact citations from the Data Pack.

2. **Auditable Action Tools & Logger (`engine/action_tools.py`)**:
   - Executes permitted actions: `rebook_request`, `issue_meal_voucher`, `grant_lounge_access`, `arrange_hotel`, `initiate_refund`, `escalate_to_human`.
   - Every action is logged with sequential IDs (`ACT-001`), parameters, status, Data Pack citation, and simulation timestamps (`2026-09-23T...`).
   - The agent strictly states an action is completed only if recorded in the Action Log.
   - No flight schedules, seat numbers, or hotel names/addresses are ever invented.

3. **Multi-Turn Conversation Layer (`engine/conversation.py`)**:
   - Stateful dialogue manager maintaining per-session state (pending choices, confirmations, escalation tickets).
   - Rebooking or refund is initiated only after explicit customer confirmation.
   - Empathizes with frustrated customers ("furious", "unacceptable") without unnecessary escalation, while immediately escalating on legal threats ("lawyer", "court", "sue") and formal complaints ("file a complaint").

4. **Optional LLM Layer (`engine/llm_layer.py`)**:
   - Disabled by default (runs with zero API keys).
   - If enabled, validates that no facts, rupee amounts (₹500, ₹1,500, ₹2,000), PNRs, or citations are modified, otherwise falls back to deterministic replies.

5. **Customer Isolation & Security (`engine/data_loader.py`)**:
   - Strict customer data isolation ensuring an authenticated passenger can only access their own booking records.

6. **Interactive Streamlit UI (`app.py`)**:
   - Authenticated Passenger Login switcher (Priya Nair, Arvind Kulkarni, Meher Kaur).
   - 1-Click Quick-Start Scenario buttons.
   - Live Side-by-Side Policy Inspector: Profile, Action Log, Escalation Tickets, Live Decision Trace, and Data Pack Rule Book.

---

## 📋 Assumptions & Open Ambiguities

1. **Meal Voucher Amounts**: The pack explicitly specifies ₹500 *only* for delays under 3 hours. For delays >3h and >5h, the pack states "meal voucher" without a specific monetary value. The agent mentions ₹500 only for the <3h tier and refers to standard meal vouchers for other tiers.
2. **Delay Tier Boundaries (in minutes)**:
   - `< 180 min` (< 3h): ₹500 meal voucher.
   - `180 to 300 min` (3h to 5h inclusive): meal voucher + lounge access.
   - `> 300 min` (> 5h): meal voucher + hotel accommodation covering delayed hours only (no lounge).
3. **Literal Tier Reading for >5h Delay**: Per the literal text in Section 3 ("meal voucher + hotel accommodation, covering only the delayed hours"), lounge access is not listed and therefore not granted.
4. **No Alternative Flight Schedules**: The Data Pack contains no alternative flight schedules or seat inventory. Rebooking requests are recorded for the "next available flight within 24 hours" and confirmed via back-office reservations.
5. **Fare Difference & Waivers**:
   - When voluntarily switching to a higher-fare flight, the customer pays the fare difference by default.
   - The agent never offers a waiver proactively.
   - Waivers above ₹1,500 require supervisor approval and are escalated.
   - The ₹2,000 difference in Scenario 3 is taken directly from customer input.
6. **Refund Method**: Refunds are issued within 7 business days to the original payment method only. If a customer requests cash, the agent clarifies the policy first and escalates only if insisted upon.
7. **Return Leg Unaffected**: Priya's return leg (Goa → Delhi, 25 Sep) remains confirmed and untouched during the outbound cancellation resolution unless the customer explicitly requests changes.
8. **Delay Entitlements Confirmation**: Meal vouchers and lounge access are issued upon status verification, while hotel accommodation is offered and confirmed before booking.

---

## 🧪 Scenarios Tested & Verified

### Scenario 1 — Priya Nair (Gold, `SK4821X`)
- **Situation**: Flight `SK-204` (Delhi → Goa) cancelled for operational reasons. Priya expresses anger ("furious") and asks for a cash refund plus a free return business class upgrade.
- **Agent Handling**:
  - Acknowledges frustration empathetically without escalating on emotion alone.
  - Explains that refunds are processed within 7 business days to original payment method (not cash).
  - Clarifies that free cabin upgrades beyond policy require supervisory review and creates an escalation ticket (`ESC-001`).
  - Confirms return leg (`Goa → Delhi`, 25 Sep) is unaffected and untouched.
  - Initiates full refund (`ACT-001`) only after Priya confirms.

### Scenario 2 — Arvind Kulkarni (Silver, `TR1190B`)
- **Situation**: Flight `SK-118` (Mumbai → Bengaluru) delayed 4 hours. Arvind is worried about a missed meeting and requests hotel accommodation.
- **Agent Handling**:
  - Issues meal voucher and lounge access (`ACT-001`, `ACT-002`) for the 4-hour delay.
  - Declines hotel accommodation politely, explaining that hotel coverage requires delays exceeding 5 hours.
  - Acknowledges missed meeting with empathy, makes no unauthorized compensation promises, and offers human review.
  - Escalates to a specialist only after Arvind accepts the offer.

### Scenario 3 — Meher Kaur (Platinum, `WL7742`)
- **Situation**: Flight `SK-305` (Delhi → Hyderabad) delayed 6 hours. Meher asks for a full night's hotel stay, and separately asks to move to a higher-fare flight with a ₹2,000 fare difference.
- **Agent Handling**:
  - Issues meal voucher; declines full night hotel stay and offers hotel accommodation covering only the delayed hours (no lounge access per literal rule text).
  - Arranges delayed-hours accommodation upon confirmation (`ACT-002`).
  - **Path A (Pays Difference)**: Informs Meher she must pay the ₹2,000 fare difference. When confirmed, registers voluntary rebooking request without escalation.
  - **Path B (Asks for Waiver)**: Explains that agents cannot waive fare differences above ₹1,500 without supervisor approval and escalates the waiver request to a supervisor.
