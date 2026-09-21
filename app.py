import streamlit as st
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.data_loader import DataContext
from engine.conversation import ConversationManager
from engine.models import LoyaltyTier, DisruptionType


# Page configuration
st.set_page_config(
    page_title="Airline Disruption Resolution Agent",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark/light mode compatibility with high contrast
st.markdown("""
<style>
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e40af 100%);
        padding: 16px 22px;
        border-radius: 12px;
        color: #ffffff;
        margin-bottom: 16px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .main-header h1 {
        color: #ffffff !important;
        margin: 0;
        font-size: 24px;
        font-weight: 700;
    }
    .date-badge {
        background: rgba(255, 255, 255, 0.15);
        color: #ffffff !important;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
        display: inline-block;
        margin-top: 6px;
    }

    /* Passenger Card */
    .passenger-card {
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 10px;
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: #f1f5f9;
    }
    .passenger-card.active {
        background: rgba(30, 58, 138, 0.6);
        border: 2px solid #38bdf8;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.25);
    }

    /* Flight Segment Card */
    .flight-segment-card {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
        color: #f8fafc;
    }

    /* Action Log Card */
    .action-card {
        background: rgba(15, 23, 42, 0.85);
        border-left: 4px solid #38bdf8;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 12px;
        color: #f1f5f9;
        font-size: 13.5px;
    }
    .action-card strong {
        color: #38bdf8 !important;
    }
    .action-card small {
        color: #94a3b8 !important;
    }
    .action-details {
        color: #e2e8f0 !important;
        margin: 6px 0;
        font-size: 13px;
        line-height: 1.4;
    }

    /* Escalation Card */
    .escalation-card {
        background: rgba(30, 10, 20, 0.85);
        border-left: 4px solid #f43f5e;
        border-top: 1px solid rgba(244, 63, 94, 0.2);
        border-right: 1px solid rgba(244, 63, 94, 0.2);
        border-bottom: 1px solid rgba(244, 63, 94, 0.2);
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 12px;
        color: #ffe4e6;
        font-size: 13.5px;
    }
    .escalation-card strong {
        color: #fb7185 !important;
    }

    /* Status Badges */
    .status-cancelled {
        background-color: #ef4444;
        color: #ffffff !important;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 12px;
        display: inline-block;
    }
    .status-delayed {
        background-color: #f59e0b;
        color: #1e1b4b !important;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 12px;
        display: inline-block;
    }
    .status-unaffected {
        background-color: #10b981;
        color: #ffffff !important;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 12px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Session State
if "data_context" not in st.session_state:
    st.session_state.data_context = DataContext()

ctx: DataContext = st.session_state.data_context

if "active_pnr" not in st.session_state:
    st.session_state.active_pnr = "SK4821X"

if "conversation_manager" not in st.session_state:
    cust = ctx.get_customer_by_pnr(st.session_state.active_pnr)
    conv = ConversationManager(ctx)
    conv.set_authenticated_customer(cust)
    st.session_state.conversation_manager = conv

conv: ConversationManager = st.session_state.conversation_manager


# Helper function to switch customer and trigger initial message
def switch_to_customer(pnr: str, initial_text: str = None):
    st.session_state.active_pnr = pnr
    cust = ctx.get_customer_by_pnr(pnr)
    conv.reset()
    conv.set_authenticated_customer(cust)
    if initial_text:
        conv.handle_user_message(initial_text)


# Header
st.markdown("""
<div class="main-header">
    <h1>✈️ Airline Disruption Customer Resolution Agent</h1>
    <div class="date-badge">📅 Reference Date: Wednesday, 23 September 2026 | Pure Python Policy Engine</div>
</div>
""", unsafe_allow_html=True)


# Passenger Profiles Definition
passengers_info = [
    {
        "pnr": "SK4821X",
        "name": "Priya Nair",
        "tier": "Gold",
        "route": "Delhi → Goa",
        "status": "Cancelled (operational)",
        "scenario_title": "Scenario 1 (Priya Nair)",
        "scenario_prompt": "I am furious that flight SK-204 was cancelled! I want a full cash refund and a free upgrade to business class on my return flight for the trouble."
    },
    {
        "pnr": "TR1190B",
        "name": "Arvind Kulkarni",
        "tier": "Silver",
        "route": "Mumbai → Bengaluru",
        "status": "Delayed 4h (new dep 11:10)",
        "scenario_title": "Scenario 2 (Arvind Kulkarni)",
        "scenario_prompt": "My flight SK-118 is delayed 4 hours. I'm going to miss my connecting meeting in Bengaluru. Can you arrange hotel accommodation since it's been such a long delay?"
    },
    {
        "pnr": "WL7742",
        "name": "Meher Kaur",
        "tier": "Platinum",
        "route": "Delhi → Hyderabad",
        "status": "Delayed 6h (new dep 20:00)",
        "scenario_title": "Scenario 3 (Meher Kaur)",
        "scenario_prompt": "Flight SK-305 is delayed 6 hours. I want a full night's hotel stay rather than just the delayed hours, and I want to be moved onto a higher-fare flight with a ₹2,000 fare difference."
    }
]

# Passenger Switcher Cards / Quick Launcher
st.markdown("### 👤 Authenticated Passenger Profiles & Quick Scenarios")
p_cols = st.columns(3)

for idx, p in enumerate(passengers_info):
    with p_cols[idx]:
        is_active = (st.session_state.active_pnr == p["pnr"])
        card_class = "passenger-card active" if is_active else "passenger-card"
        status_badge_class = "status-cancelled" if "Cancelled" in p["status"] else "status-delayed"
        
        st.markdown(f"""
        <div class="{card_class}">
            <div style="font-size: 15px; font-weight: 700; color: #f8fafc;">
                {'✅ ' if is_active else ''}{p['name']} ({p['tier']})
            </div>
            <div style="font-size: 13px; color: #cbd5e1; margin: 6px 0;">
                PNR: <code>{p['pnr']}</code> | {p['route']}
            </div>
            <div>
                <span class="{status_badge_class}">{p['status']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            if st.button(f"👤 Login as {p['name'].split()[0]}", key=f"login_{p['pnr']}", use_container_width=True):
                switch_to_customer(p["pnr"])
                st.rerun()
        with b_col2:
            if st.button(f"⚡ Run Scenario {idx+1}", key=f"run_scen_{p['pnr']}", use_container_width=True):
                switch_to_customer(p["pnr"], initial_text=p["scenario_prompt"])
                st.rerun()

st.markdown("---")

# Active Customer Context
active_cust = ctx.get_customer_by_pnr(st.session_state.active_pnr)
if conv.state.get("authenticated_customer") != active_cust:
    conv.set_authenticated_customer(active_cust)

current_cust = conv.state["authenticated_customer"]
current_book = conv.state["current_booking"]
current_seg = conv.state["disrupted_segment"]

# Main Layout: 2 Columns
chat_col, inspector_col = st.columns([1.1, 0.9])

with chat_col:
    header_col1, header_col2 = st.columns([2, 1])
    with header_col1:
        st.subheader(f"💬 Chat — {current_cust.name} ({current_cust.loyalty_tier.value})")
    with header_col2:
        if st.button("🔄 Clear Chat", key="clear_chat_btn", use_container_width=True):
            conv.reset()
            st.rerun()

    # Quick Suggestion Chips based on scenario
    st.caption("Quick suggested replies:")
    sug_cols = st.columns(3)
    
    if current_seg and current_seg.disruption_type == DisruptionType.CANCELLATION:
        if sug_cols[0].button("What are my options?", key="sug_opt"):
            conv.handle_user_message("My flight is cancelled. What options do I have?")
            st.rerun()
        if sug_cols[1].button("Confirm refund (original method)", key="sug_rfd_btn"):
            conv.handle_user_message("Yes, please initiate the refund to my original payment method.")
            st.rerun()
        if sug_cols[2].button("Rebook next available flight", key="sug_rbk_btn"):
            conv.handle_user_message("Please rebook me on the next available flight within 24 hours.")
            st.rerun()
    else:
        if current_seg and current_seg.delay_minutes > 300:
            if sug_cols[0].button("Confirm delayed-hours hotel", key="sug_htl_confirm"):
                conv.handle_user_message("Yes, please confirm the delayed-hours hotel accommodation.")
                st.rerun()
            if sug_cols[1].button("Switch flight (pay ₹2,000 diff)", key="sug_pay_diff"):
                conv.handle_user_message("I agree to pay the ₹2,000 fare difference, please proceed.")
                st.rerun()
            if sug_cols[2].button("Ask to waive ₹2,000 fare diff", key="sug_waive_diff"):
                conv.handle_user_message("Can you waive the ₹2,000 fare difference for free?")
                st.rerun()
        else:
            if sug_cols[0].button("What delay compensation do I get?", key="sug_del_comp"):
                conv.handle_user_message("What compensation do I get for this 4-hour delay?")
                st.rerun()
            if sug_cols[1].button("Can I get a hotel room?", key="sug_htl_req"):
                conv.handle_user_message("Can you arrange hotel accommodation since it's a long delay?")
                st.rerun()
            if sug_cols[2].button("Connect with human specialist", key="sug_human_spec"):
                conv.handle_user_message("Yes please, connect me with a specialist for human review.")
                st.rerun()

    # Chat Messages Scroll Area
    chat_container = st.container(height=450)
    with chat_container:
        if not conv.messages:
            st.info(f"👋 Logged in as **{current_cust.name}** ({current_cust.loyalty_tier.value} Member, PNR: `{current_cust.booking_reference}`). Send a message below or click a scenario button above to start.")
        
        for msg in conv.messages:
            if msg.sender == "customer":
                with st.chat_message("user", avatar="👤"):
                    st.write(msg.text)
                    st.caption(f"🕒 {msg.timestamp}")
            elif msg.sender == "agent":
                with st.chat_message("assistant", avatar="✈️"):
                    st.write(msg.text)
                    if msg.metadata.get("rule_citation"):
                        clean_citation = msg.metadata["rule_citation"].replace("Data Pack Section 3: ", "").replace("Data Pack Section 4: ", "").replace("Data Pack Section 3 & 4: ", "")
                        st.caption(f"📜 *Policy Applied: {clean_citation}*")
                    if msg.metadata.get("escalation_id"):
                        st.error(f"🚨 Escalation Ticket Created: **{msg.metadata['escalation_id']}**")

    # Chat Input Box
    user_input = st.chat_input("Type your message to the support agent...")
    if user_input:
        conv.handle_user_message(user_input)
        st.rerun()


# Right Column: Inspector & Audit Panel
with inspector_col:
    st.subheader("🔍 Policy Engine Inspector & Audit")

    tabs = st.tabs(["👤 Profile", "📝 Action Log", "🚨 Escalations", "📐 Decision Trace", "📖 Policy Rules"])

    with tabs[0]:
        st.markdown(f"### {current_cust.name} ({current_cust.loyalty_tier.value})")
        st.markdown(f"- **PNR**: `{current_cust.booking_reference}`")
        st.markdown(f"- **Contact**: `{current_cust.email}` | `{current_cust.phone}`")
        st.markdown(f"- **12-Month Travel History**: {current_cust.travel_history.flights_last_12_months} flights, {len(current_cust.travel_history.prior_complaints)} prior complaints")
        if current_cust.travel_history.prior_complaints:
            for pc in current_cust.travel_history.prior_complaints:
                st.caption(f"  *Prior Complaint: {pc.type} ({pc.resolution})*")
        
        st.markdown("#### Authenticated Flight Segments:")
        if current_book:
            for s in current_book.segments:
                badge_class = "status-cancelled" if "Cancelled" in s.status else ("status-delayed" if "Delayed" in s.status else "status-unaffected")
                new_dep_html = f"| New: <strong style='color: #f8fafc;'>{s.new_departure}</strong>" if s.new_departure else ""
                st.markdown(f"""
                <div class="flight-segment-card">
                    <strong style="font-size: 14.5px; color: #38bdf8;">{s.flight_number}</strong> ({s.route}) — {s.date}<br/>
                    <div style="margin: 4px 0; color: #cbd5e1;">
                        Scheduled: <strong style="color: #f8fafc;">{s.scheduled_departure}</strong> {new_dep_html}
                    </div>
                    <div>
                        Status: <span class="{badge_class}">{s.status}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    with tabs[1]:
        st.markdown("#### Auditable Action Log (23 Sep 2026)")
        if not conv.logger.logs:
            st.info("No actions executed yet in this session.")
        else:
            for log in conv.logger.logs:
                clean_log_rule = log.rule_citation.replace("Data Pack Section 3: ", "").replace("Data Pack Section 4: ", "").replace("Data Pack Section 3 & 4: ", "")
                st.markdown(f"""
                <div class="action-card">
                    <div>
                        <strong>⚡ {log.action_id} — {log.action_type.upper()}</strong> 
                        <span style="color:#38bdf8; font-weight:700;">[{log.status}]</span>
                    </div>
                    <div style="margin: 2px 0;">
                        <small style="color:#94a3b8;">🕒 {log.timestamp} | PNR: {log.pnr}</small>
                    </div>
                    <div class="action-details">
                        {log.details}
                    </div>
                    <div>
                        <small style="color:#cbd5e1;"><em>Policy: {clean_log_rule}</em></small>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    with tabs[2]:
        st.markdown("#### Human Escalation Handoff Tickets")
        if not conv.logger.escalations:
            st.info("No escalations generated.")
        else:
            for esc in conv.logger.escalations:
                st.markdown(f"""
                <div class="escalation-card">
                    <div>
                        <strong>🚨 {esc.ticket_id} — STATUS: {esc.status}</strong>
                    </div>
                    <div style="color: #fecdd3; margin: 4px 0;">
                        <strong>Customer:</strong> {esc.customer_name} ({esc.loyalty_tier}) | <strong>PNR:</strong> {esc.pnr}
                    </div>
                    <div style="color: #ffe4e6; margin: 4px 0;">
                        <strong>Reason:</strong> {esc.reason}
                    </div>
                    <div style="color: #fda4af; margin: 4px 0;">
                        <strong>Trigger Utterance:</strong> <em>"{esc.trigger_text}"</em>
                    </div>
                    <div>
                        <small style="color: #f43f5e;">🕒 {esc.timestamp}</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    with tabs[3]:
        st.markdown("#### Real-time Policy Decision Trace")
        if current_seg:
            if current_seg.disruption_type == DisruptionType.CANCELLATION:
                st.markdown("""
                **Rule Applied**: `RULE-CANC-01` (Cancellation Rebooking Rule)
                - **Entitlement**: Free rebooking on next available within 24h OR Full refund within 7 business days to original payment method.
                - **Loyalty Benefit**: Priority rebooking for Gold/Platinum (first access to next-available seats).
                - **Upgrade Policy**: Agent prohibited from granting cabin upgrades beyond standard policy.
                """)
            elif current_seg.disruption_type == DisruptionType.DELAY:
                st.markdown(f"""
                **Rule Applied**: `RULE-DELAY-01` (Delay Compensation Rule)
                - **Calculated Delay**: {current_seg.delay_minutes} minutes ({current_seg.delay_minutes / 60:.1f} hours)
                - **Tier Definition**:
                  - `< 180 min`: ₹500 meal voucher
                  - `180 to 300 min`: Meal voucher + lounge access
                  - `> 300 min`: Meal voucher + hotel for delayed hours only (no lounge)
                """)
        st.caption("All evaluations executed deterministically in pure Python without LLM hallucination.")

    with tabs[4]:
        st.markdown("#### Airline Policy Rules & Actions")
        policies = ctx.policies.get("rules", {})
        for r_key, r_val in policies.items():
            st.markdown(f"**{r_val.get('name', r_key)}**")
            if "text" in r_val:
                st.markdown(f"> *{r_val['text']}*")
            if "tiers" in r_val:
                for t_name, t_data in r_val["tiers"].items():
                    st.markdown(f"- **{t_name}**: {t_data.get('text', '')}")
            if "allowed" in r_val:
                st.markdown("**Allowed Actions:**")
                for allow_item in r_val["allowed"]:
                    st.markdown(f"- ✅ {allow_item}")
            if "prohibited" in r_val:
                st.markdown("**Prohibited Actions (Must Escalate):**")
                for prohib_item in r_val["prohibited"]:
                    st.markdown(f"- 🚨 {prohib_item}")
            if "triggers" in r_val:
                for trig in r_val["triggers"]:
                    st.markdown(f"- ⚠️ {trig}")
            st.markdown("---")
