"""
Dashboard — Power-BI-style overview with filters + KPI cards + charts.
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from common import init_page, get_data

init_page("Dashboard", "📊")
tables, d, row_hash = get_data()

accounts = tables["accounts"]
cards = tables["cards"]
loan_full = d["loan_full"]
card_txn = d["card_txn"]
support_ticket = d["support_ticket"]
branches = tables["branches"]

st.title("📊 Dashboard")
st.caption("Filter the data below — every KPI and chart on this page updates together.")

# --------------------------------------------------------------------------
# Filters (sidebar) — like Power BI slicers
# --------------------------------------------------------------------------
st.sidebar.subheader("Filters")

branch_options = sorted(branches["BRANCH_NAME"].dropna().unique().tolist())
branch_sel = st.sidebar.multiselect("Branch", branch_options, default=branch_options)

account_type_options = sorted(accounts["ACCOUNT_TYPE"].dropna().unique().tolist())
account_type_sel = st.sidebar.multiselect("Account type", account_type_options, default=account_type_options)

min_date, max_date = card_txn["TXN_DATE"].min(), card_txn["TXN_DATE"].max()
date_range = st.sidebar.date_input("Transaction date range", [min_date, max_date])

branch_ids = branches.loc[branches["BRANCH_NAME"].isin(branch_sel), "BRANCH_ID"]

accounts_f = accounts[
    accounts["ACCOUNT_TYPE"].isin(account_type_sel) & accounts["BRANCH_ID"].isin(branch_ids)
]
loan_f = loan_full[loan_full["BRANCH_ID"].isin(branch_ids)]

start = pd.to_datetime(date_range[0]) if len(date_range) > 0 else min_date
end = pd.to_datetime(date_range[1]) if len(date_range) > 1 else max_date
card_txn_f = card_txn[(card_txn["TXN_DATE"] >= start) & (card_txn["TXN_DATE"] <= end)]

st.markdown("---")

# --------------------------------------------------------------------------
# KPI cards
# --------------------------------------------------------------------------
total_balance = accounts_f["BALANCE"].sum()
total_disbursed = loan_f["LOAN_AMOUNT"].sum()
default_rate = loan_f["is_default"].mean() * 100 if len(loan_f) else 0
fraud_rate = card_txn_f["IS_FRAUD"].mean() * 100 if len(card_txn_f) else 0
open_tickets = support_ticket[~support_ticket["STATUS"].isin(["Closed", "Resolved"])].shape[0]

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total balance", f"₹{total_balance:,.0f}")
k2.metric("Loans disbursed", f"₹{total_disbursed:,.0f}")
k3.metric("Default rate", f"{default_rate:.2f}%")
k4.metric("Fraud rate", f"{fraud_rate:.2f}%")
k5.metric("Open support tickets", f"{open_tickets:,}")

st.markdown("---")

# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("Balance by account type")
    by_type = accounts_f.groupby("ACCOUNT_TYPE")["BALANCE"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(6, 4))
    by_type.plot.bar(color="steelblue", ax=ax)
    ax.set_ylabel("Total balance")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    st.pyplot(fig)

with c2:
    st.subheader("Monthly transaction volume")
    monthly = card_txn_f.groupby("txn_month").agg(
        txn_count=("CARD_TXN_ID", "count"), total_amount=("AMOUNT", "sum")
    ).reset_index().sort_values("txn_month")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(monthly["txn_month"], monthly["total_amount"], marker="o", color="darkorange")
    ax.set_ylabel("Total spend")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    st.pyplot(fig)

c3, c4 = st.columns(2)

with c3:
    st.subheader("Default rate by loan type")
    by_loan = loan_f.groupby("LOAN_TYPE")["is_default"].mean().mul(100).round(2).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(6, 4))
    by_loan.plot.bar(color="crimson", ax=ax)
    ax.set_ylabel("Default rate %")
    st.pyplot(fig)

with c4:
    st.subheader("Tickets by status")
    by_status = support_ticket["STATUS"].value_counts()
    fig, ax = plt.subplots(figsize=(6, 4))
    by_status.plot.pie(autopct="%1.0f%%", ylabel="", ax=ax)
    st.pyplot(fig)

st.markdown("---")
st.subheader("Branch summary")
branch_summary = loan_f.groupby("BRANCH_ID").agg(
    loans=("LOAN_ID", "count"),
    total_disbursed=("LOAN_AMOUNT", "sum"),
    default_rate_pct=("is_default", lambda x: round(x.mean() * 100, 2)),
).reset_index().merge(branches[["BRANCH_ID", "BRANCH_NAME"]], on="BRANCH_ID")
st.dataframe(
    branch_summary[["BRANCH_NAME", "loans", "total_disbursed", "default_rate_pct"]]
    .sort_values("total_disbursed", ascending=False),
    use_container_width=True,
)
