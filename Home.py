"""
Home.py (main entry point)
Shown immediately after a successful login. Describes the project and
what each page of the app contains, and gives a live snapshot of the
loaded data so the login -> home hand-off feels like a real product,
not a blank page.
"""

import streamlit as st

from common import init_page, get_data

init_page("Home", "🏠")

tables, d, row_hash = get_data()

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("🏦 Banking Analytics Suite")
st.caption(
    "Descriptive · Diagnostic · Predictive analysis — plus an interactive "
    "Power-BI-style dashboard — over customers, accounts, cards, loans, "
    "transactions and support tickets."
)
st.markdown("---")

st.markdown(
    """
    Welcome, **{username}**. This project reproduces the analysis originally
    built in Power BI (`banking_power_bi.pbix`) as a fully interactive Python
    web app, and extends it with descriptive, diagnostic and predictive
    analytics driven by the same underlying banking data.

    Use the **sidebar** to move between sections.
    """.format(username=st.session_state.get("username", "user"))
)

# --------------------------------------------------------------------------
# Live snapshot of the loaded data
# --------------------------------------------------------------------------
st.subheader("Data currently loaded")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Customers", f"{len(tables['customers']):,}")
c2.metric("Accounts", f"{len(tables['accounts']):,}")
c3.metric("Cards", f"{len(tables['cards']):,}")
c4.metric("Loans", f"{len(tables['loan']):,}")
c5.metric("Card transactions", f"{len(tables['card_transaction']):,}")
st.caption(f"{sum(row_hash):,} total rows loaded across all 10 tables.")

st.markdown("---")

# --------------------------------------------------------------------------
# What's inside — one card per page
# --------------------------------------------------------------------------
st.subheader("What's in this app")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📊 Dashboard")
    st.write(
        "An interactive, Power-BI-style overview: KPI cards, filters by branch/date/"
        "account type, and charts covering balances, loans, fraud and tickets at a glance."
    )
    st.markdown("#### 🔍 Descriptive analytics")
    st.write(
        "**What happened?** Portfolio composition, fraud incidence, default & late-payment "
        "rates, support-ticket volume, card spend, customer segmentation, utilization, "
        "and monthly transaction trends."
    )

with col2:
    st.markdown("#### 🧩 Diagnostic analytics")
    st.write(
        "**Why did it happen?** Credit-band vs default rate, disproportionate fraud by "
        "merchant category, prior fraud reports vs confirmed fraud, branch-level default "
        "drivers, escalated tickets vs account dormancy, and utilization vs fraud."
    )
    st.markdown("#### 🤖 Predictive analytics")
    st.write(
        "**What's likely to happen next?** Three trainable models — card-fraud detection, "
        "credit-default prediction, and next-late-payment prediction — with ROC/AUC, "
        "confusion matrices, and feature importance."
    )

st.markdown("---")
st.info("👈 Pick a page from the sidebar to get started — **Dashboard** is a good first stop.")

st.markdown(
    f"""
    <div style='text-align: center; color: gray; padding-top: 10px;'>
    Banking Analytics Suite · built with Streamlit · logged in as {st.session_state.get('username', 'user')}
    </div>
    """,
    unsafe_allow_html=True,
)
