"""Streamlit frontend for AI Travel Planner (Phase 1).

Run:
    cd travelling-agent/frontend
    pip install -r requirements.txt
    streamlit run app.py
"""

import os
from datetime import UTC, datetime, timedelta

import streamlit as st
from api_client import ApiError, TravelApiClient

st.set_page_config(
    page_title="AI Travel Planner",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

TRAVEL_STYLES = ["relaxed", "balanced", "adventure", "luxury", "budget", "family"]
INTEREST_CHOICES = [
    "culture",
    "food",
    "nature",
    "nightlife",
    "history",
    "adventure",
    "shopping",
    "beaches",
    "museums",
    "music",
]
CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD"]

# ---------------------------------------------------------------- session
defaults = {
    "token": None,
    "user": None,
    "trips": [],
    "selected_trip_id": None,
    "selected_trip": None,
    "page": "My Trips",
    "api_base": os.getenv("API_BASE_URL", "http://localhost:8000"),
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)


def client() -> TravelApiClient:
    return TravelApiClient(base_url=st.session_state.api_base, token=st.session_state.token)


def logout():
    for k in ("token", "user", "trips", "selected_trip_id", "selected_trip"):
        st.session_state[k] = [] if k == "trips" else None
    st.session_state.page = "My Trips"


def refresh_trips(show_spinner: bool = True):
    try:
        if show_spinner:
            with st.spinner("Loading trips..."):
                st.session_state.trips = client().list_trips()
        else:
            st.session_state.trips = client().list_trips()
    except ApiError as e:
        st.error(f"Could not load trips: {e}")


def refresh_selected_trip():
    if st.session_state.selected_trip_id:
        try:
            st.session_state.selected_trip = client().get_trip(st.session_state.selected_trip_id)
        except ApiError as e:
            st.error(f"Could not load trip: {e}")


# ---------------------------------------------------------------- styles
st.markdown(
    """
<style>
  .trip-card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 1rem 1.2rem;
               margin-bottom: 0.8rem; background: #ffffff; }
  .small-muted { color: #6b7280; font-size: 0.85rem; }
  .stButton>button { border-radius: 8px; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("✈️ AI Travel Planner")
    st.caption("Phase 1 · FastAPI + Streamlit")

    st.session_state.api_base = st.text_input(
        "Backend URL",
        value=st.session_state.api_base,
        help="FastAPI base, e.g. http://localhost:8000",
    )
    col_h, col_r = st.columns(2)
    with col_h:
        if st.button("🏥 Health", use_container_width=True):
            try:
                st.success(client().health())
            except ApiError as e:
                st.error(e)
    with col_r:
        if st.button("🔄 Trips", use_container_width=True, disabled=not st.session_state.token):
            refresh_trips()

    st.divider()

    if st.session_state.user:
        st.markdown(f"**👤 {st.session_state.user.get('full_name') or st.session_state.user.get('email')}**")
        st.caption(st.session_state.user.get("email", ""))
        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()
        st.divider()
        st.session_state.page = st.radio(
            "Navigate",
            ["My Trips", "＋ New Trip", "🧾 Trip Details"],
            index=["My Trips", "＋ New Trip", "🧾 Trip Details"].index(st.session_state.page)
            if st.session_state.page in ["My Trips", "＋ New Trip", "🧾 Trip Details"]
            else 0,
        )
    else:
        st.info("Login or create an account to plan trips.")
        st.session_state.page = st.radio("Navigate", ["My Trips", "＋ New Trip"], index=0)

    st.divider()
    st.caption("Backend: `POST /api/v1/trips` generates a day-by-day itinerary via Groq/OpenAI with offline fallback.")

# ---------------------------------------------------------------- auth gate
if not st.session_state.token:
    st.header("Welcome to AI Travel Planner 🌍")
    st.write("Plan day-by-day itineraries with budget, style, and interests. Login to continue.")
    login_tab, register_tab = st.tabs(["🔑 Login", "📝 Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", value="demo@example.com")
            password = st.text_input("Password", type="password", value="demo1234")
            submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
        if submitted:
            if not email or not password:
                st.warning("Enter email and password.")
            else:
                try:
                    with st.spinner("Logging in..."):
                        token = client().login(email.strip(), password)
                        st.session_state.token = token
                        st.session_state.user = TravelApiClient(base_url=st.session_state.api_base, token=token).me()
                        refresh_trips(show_spinner=False)
                    st.success(f"Welcome back, {st.session_state.user.get('email')}!")
                    st.rerun()
                except ApiError as e:
                    st.error(f"Login failed: {e}")

    with register_tab:
        with st.form("register_form"):
            r_name = st.text_input("Full name (optional)")
            r_email = st.text_input("Email", key="reg_email")
            r_pw = st.text_input("Password", type="password", key="reg_pw")
            r_pw2 = st.text_input("Confirm password", type="password")
            r_sub = st.form_submit_button("Create account", use_container_width=True)
        if r_sub:
            if not r_email or not r_pw:
                st.warning("Email and password are required.")
            elif r_pw != r_pw2:
                st.warning("Passwords do not match.")
            else:
                try:
                    with st.spinner("Creating account..."):
                        client().register(r_email.strip(), r_pw, r_name.strip() or None)
                        token = client().login(r_email.strip(), r_pw)
                        st.session_state.token = token
                        st.session_state.user = TravelApiClient(base_url=st.session_state.api_base, token=token).me()
                        refresh_trips(show_spinner=False)
                    st.success("Account created — you're logged in!")
                    st.rerun()
                except ApiError as e:
                    st.error(f"Registration failed: {e}")
    st.stop()


# ---------------------------------------------------------------- helpers
def trip_dates(t: dict) -> str:
    return f"{t.get('start_date')} → {t.get('end_date')}"


def render_itinerary(trip: dict):
    itin = trip.get("itinerary")
    if not itin:
        st.info("No itinerary yet. Click **Regenerate itinerary** to generate one.")
        return
    st.subheader("🗺️ Itinerary")
    st.write(itin.get("summary", ""))
    c1, c2, c3 = st.columns(3)
    c1.metric("Est. total cost", f"{itin.get('total_estimated_cost', 0):,.2f} {itin.get('currency', '')}")
    c2.metric("Trip budget", f"{trip.get('budget')} {trip.get('currency')}")
    c3.metric("Days", len(itin.get("days", [])))
    for day in itin.get("days", []):
        title = f"Day {day.get('day_number')} · {day.get('date')} — {day.get('theme', '')}"
        with st.expander(title, expanded=(day.get("day_number") == 1)):
            if day.get("notes"):
                st.caption(f"📝 {day['notes']}")
            for a in day.get("activities", []):
                st.markdown(f"**{a.get('time', '')} · {a.get('title', '')}**")
                if a.get("description"):
                    st.write(a["description"])
                meta = " · ".join(
                    x
                    for x in [
                        f"📍 {a['location']}" if a.get("location") else "",
                        f"🏷️ {a['category']}" if a.get("category") else "",
                        f"💰 ~{a['cost_estimate']}" if a.get("cost_estimate") else "",
                    ]
                    if x
                )
                if meta:
                    st.caption(meta)
            meals = day.get("meals") or []
            if meals:
                st.caption("🍽️ " + " | ".join(meals))


# ================================================================ MY TRIPS
if st.session_state.page == "My Trips":
    st.header("My Trips 🧳")
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.caption("All trips for the logged-in user. Click **Open** to see the full itinerary.")
    with col_b:
        if st.button("＋ Plan new trip", type="primary", use_container_width=True):
            st.session_state.page = "＋ New Trip"
            st.rerun()

    if not st.session_state.trips:
        refresh_trips(show_spinner=False)

    trips = st.session_state.trips or []
    if not trips:
        st.info("No trips yet — create your first one!")
    else:
        search = st.text_input("🔍 Filter by destination", "")
        if search:
            trips = [t for t in trips if search.lower() in t.get("destination", "").lower()]
        for t in trips:
            with st.container():
                st.markdown('<div class="trip-card">', unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1.4])
                with c1:
                    st.markdown(f"### {t.get('destination')}")
                    st.markdown(
                        f"<span class='small-muted'>{trip_dates(t)} · {t.get('travelers')} traveler(s) · "
                        f"{t.get('travel_style')} · {t.get('status')}</span>",
                        unsafe_allow_html=True,
                    )
                    interests = ", ".join(t.get("interests") or [])
                    if interests:
                        st.caption(f"Interests: {interests}")
                with c2:
                    st.metric("Budget", f"{t.get('budget')} {t.get('currency')}")
                with c3:
                    itin = t.get("itinerary") or {}
                    st.metric("Est. cost", f"{itin.get('total_estimated_cost', '—')}")
                with c4:
                    st.write("")
                    if st.button("Open →", key=f"open_{t['id']}", use_container_width=True):
                        st.session_state.selected_trip_id = t["id"]
                        st.session_state.selected_trip = t
                        refresh_selected_trip()
                        st.session_state.page = "🧾 Trip Details"
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

# ================================================================ NEW TRIP
elif st.session_state.page == "＋ New Trip":
    st.header("Plan a new trip ＋")
    st.caption("This calls `POST /api/v1/trips` — itinerary generation can take up to ~60s with an LLM key.")

    with st.form("new_trip_form"):
        c1, c2 = st.columns(2)
        with c1:
            destination = st.text_input("Destination *", placeholder="e.g. Kyoto")
            start = st.date_input("Start date", value=datetime.now(UTC).date() + timedelta(days=30))
            budget = st.number_input("Budget", min_value=1.0, value=2200.0, step=50.0)
            travelers = st.number_input("Travelers", min_value=1, max_value=50, value=2, step=1)
        with c2:
            currency = st.selectbox("Currency", CURRENCIES, index=0)
            end = st.date_input("End date", value=datetime.now(UTC).date() + timedelta(days=33))
            style = st.selectbox("Travel style", TRAVEL_STYLES, index=1)
            interests = st.multiselect("Interests", INTEREST_CHOICES, default=["culture", "food"])
        custom_interest = st.text_input("Other interests (comma-separated, optional)", "")
        submitted = st.form_submit_button("✨ Create trip + generate itinerary", type="primary", use_container_width=True)

    if submitted:
        if not destination.strip():
            st.warning("Destination is required.")
        elif end < start:
            st.warning("End date must be on or after start date.")
        elif (end - start).days > 60:
            st.warning("Phase 1 supports trips up to 60 days.")
        else:
            all_interests = list(interests)
            if custom_interest.strip():
                all_interests += [x.strip() for x in custom_interest.split(",") if x.strip()]
            payload = {
                "destination": destination.strip(),
                "start_date": str(start),
                "end_date": str(end),
                "budget": str(budget),
                "currency": currency,
                "travelers": int(travelers),
                "travel_style": style,
                "interests": all_interests,
            }
            try:
                with st.spinner("Generating your itinerary... (LLM or template fallback)"):
                    trip = client().create_trip(payload)
                st.session_state.selected_trip_id = trip["id"]
                st.session_state.selected_trip = trip
                refresh_trips(show_spinner=False)
                st.success(f"Trip to {trip['destination']} created!")
                st.session_state.page = "🧾 Trip Details"
                st.rerun()
            except ApiError as e:
                st.error(f"Could not create trip: {e}")

# ================================================================ DETAILS
elif st.session_state.page == "🧾 Trip Details":
    if not st.session_state.selected_trip_id:
        st.warning("Select a trip from **My Trips** first.")
        if st.button("Go to My Trips"):
            st.session_state.page = "My Trips"
            st.rerun()
        st.stop()

    refresh_col, back_col = st.columns([1, 4])
    with back_col:
        if st.button("← Back to My Trips"):
            st.session_state.page = "My Trips"
            st.rerun()
    with refresh_col:
        if st.button("🔄 Refresh"):
            refresh_selected_trip()
            st.rerun()

    trip = st.session_state.selected_trip or {}
    if not trip or trip.get("id") != st.session_state.selected_trip_id:
        refresh_selected_trip()
        trip = st.session_state.selected_trip or {}

    if not trip:
        st.error("Trip not found.")
        st.stop()

    st.header(f"{trip.get('destination')} 🧾")
    st.caption(
        f"{trip_dates(trip)} · {trip.get('travelers')} traveler(s) · "
        f"{trip.get('travel_style')} · status: `{trip.get('status')}` · id: `{trip.get('id')}`"
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Budget", f"{trip.get('budget')} {trip.get('currency')}")
    m2.metric("Travelers", trip.get("travelers"))
    m3.metric("Style", trip.get("travel_style"))
    m4.metric("Interests", ", ".join(trip.get("interests") or ["—"]))

    render_itinerary(trip)
    st.divider()

    act1, act2 = st.columns(2)
    with act1:
        if st.button("✨ Regenerate itinerary", use_container_width=True, type="primary"):
            try:
                with st.spinner("Regenerating..."):
                    updated = client().regenerate(trip["id"])
                st.session_state.selected_trip = updated
                refresh_trips(show_spinner=False)
                st.success("Itinerary regenerated!")
                st.rerun()
            except ApiError as e:
                st.error(f"Regeneration failed: {e}")
    with act2:
        if st.button("🗑️ Delete trip", use_container_width=True):
            st.session_state["confirm_delete"] = True
        if st.session_state.get("confirm_delete"):
            st.warning("Are you sure? This cannot be undone.")
            dc1, dc2 = st.columns(2)
            with dc1:
                if st.button("Yes, delete", use_container_width=True):
                    try:
                        client().delete_trip(trip["id"])
                        st.session_state.selected_trip_id = None
                        st.session_state.selected_trip = None
                        st.session_state["confirm_delete"] = False
                        refresh_trips(show_spinner=False)
                        st.session_state.page = "My Trips"
                        st.rerun()
                    except ApiError as e:
                        st.error(f"Delete failed: {e}")
            with dc2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state["confirm_delete"] = False
                    st.rerun()

    with st.expander("✏️ Edit trip constraints (PATCH)"), st.form("edit_trip_form"):
        e1, e2 = st.columns(2)
        with e1:
            new_dest = st.text_input("Destination", value=trip.get("destination", ""))
            new_budget = st.number_input("Budget", min_value=0.0, value=float(trip.get("budget", 0)), step=50.0)
            new_travelers = st.number_input("Travelers", min_value=1, max_value=50, value=int(trip.get("travelers", 1)))
        with e2:
            new_style = st.selectbox(
                "Travel style",
                TRAVEL_STYLES,
                index=TRAVEL_STYLES.index(trip.get("travel_style", "balanced"))
                if trip.get("travel_style") in TRAVEL_STYLES
                else 1,
            )
            new_interests = st.multiselect("Interests", INTEREST_CHOICES, default=trip.get("interests") or [])
            new_status = st.text_input("Status", value=trip.get("status", ""))
        if st.form_submit_button("Save changes", use_container_width=True):
            payload = {}
            if new_dest.strip() and new_dest.strip() != trip.get("destination"):
                payload["destination"] = new_dest.strip()
            if str(new_budget) != str(trip.get("budget")):
                payload["budget"] = new_budget
            if int(new_travelers) != int(trip.get("travelers")):
                payload["travelers"] = int(new_travelers)
            if new_style != trip.get("travel_style"):
                payload["travel_style"] = new_style
            if new_interests != (trip.get("interests") or []):
                payload["interests"] = new_interests
            if new_status.strip() and new_status.strip() != trip.get("status"):
                payload["status"] = new_status.strip()
            if not payload:
                st.info("No changes to save.")
            else:
                try:
                    with st.spinner("Updating..."):
                        updated = client().update_trip(trip["id"], payload)
                    st.session_state.selected_trip = updated
                    refresh_trips(show_spinner=False)
                    st.success("Trip updated! Regenerate the itinerary to apply new constraints.")
                    st.rerun()
                except ApiError as e:
                    st.error(f"Update failed: {e}")

    with st.expander("🔍 Raw JSON"):
        st.json(trip)
