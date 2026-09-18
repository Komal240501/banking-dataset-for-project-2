"""
Fraud Monitoring — reproduces the "Fraud Monitoring" Power BI dashboard:
KPIs, Fraud Rate % by month, Fraud Rate % by card type, Top 20 highest
fraud transactions, and Fraud Value Share % by merchant category.
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from common import init_page, get_data, banner

init_page("Fraud Monitoring", "🚨")
tables, d, row_hash = get_data()

banner("Fraud Monitoring")

card_txn = d["card_txn"].copy()
cards = tables["cards"]

# --------------------------------------------------------------------------
# Filters (sidebar) — Card_Type, Merchant_Category, Branch_Name, Date
# --------------------------------------------------------------------------
st.sidebar.subheader("Filters")

card_type_opts = sorted(card_txn["CARD_TYPE"].dropna().unique().tolist())
card_type_sel = st.sidebar.multiselect("Card type", card_type_opts, default=card_type_opts)

merchant_opts = sorted(card_txn["MERCHANT_CATEGORY"].dropna().unique().tolist())
merchant_sel = st.sidebar.multiselect("Merchant category", merchant_opts, default=merchant_opts)

# Branch filter only if cards can be traced to a branch (cards -> accounts -> branches).
branch_sel = None
if "CUSTOMER_ID" in cards.columns and "CUSTOMER_ID" in tables["accounts"].columns:
    acc_branch = tables["accounts"][["CUSTOMER_ID", "BRANCH_ID"]].drop_duplicates()
    card_branch = cards.merge(acc_branch, on="CUSTOMER_ID", how="left").merge(
        tables["branches"][["BRANCH_ID", "BRANCH_NAME"]], on="BRANCH_ID", how="left"
    )[["CARD_ID", "BRANCH_NAME"]]
    branch_opts = sorted(card_branch["BRANCH_NAME"].dropna().unique().tolist())
    if branch_opts:
        branch_sel = st.sidebar.multiselect("Branch", branch_opts, default=branch_opts)
        card_txn = card_txn.merge(card_branch, on="CARD_ID", how="left")

min_date, max_date = card_txn["TXN_DATE"].min(), card_txn["TXN_DATE"].max()
date_range = st.sidebar.date_input("Date", [min_date, max_date])

# --------------------------------------------------------------------------
# Apply filters
# --------------------------------------------------------------------------
mask = card_txn["CARD_TYPE"].isin(card_type_sel) & card_txn["MERCHANT_CATEGORY"].isin(merchant_sel)
if branch_sel is not None:
    mask &= card_txn["BRANCH_NAME"].isin(branch_sel)
start = pd.to_datetime(date_range[0]) if len(date_range) > 0 else min_date
end = pd.to_datetime(date_range[1]) if len(date_range) > 1 else max_date
mask &= (card_txn["TXN_DATE"] >= start) & (card_txn["TXN_DATE"] <= end)
card_txn_f = card_txn[mask]

if card_txn_f.empty:
    st.warning("No transactions match the current filters.")
    st.stop()

# --------------------------------------------------------------------------
# KPI cards
# --------------------------------------------------------------------------
fraud_txn = card_txn_f[card_txn_f["IS_FRAUD"] == 1]
total_fraud_txns = len(fraud_txn)
total_fraud_value = fraud_txn["AMOUNT"].sum()
avg_fraud_size = fraud_txn["AMOUNT"].mean() if total_fraud_txns else 0
overall_fraud_rate = card_txn_f["IS_FRAUD"].mean() * 100 if len(card_txn_f) else 0

monthly = card_txn_f.groupby("txn_month")["IS_FRAUD"].mean().mul(100).sort_index()
mom_change = (monthly.iloc[-1] - monthly.iloc[-2]) if len(monthly) >= 2 else 0.0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Fraud Transactions", f"{total_fraud_txns:,}")
k2.metric("Total Fraud Value", f"₹{total_fraud_value:,.0f}")
k3.metric("Avg Fraud Transaction Size", f"₹{avg_fraud_size:,.2f}")
k4.metric("MoM change in Fraud Rate", f"{mom_change:+.2f} pts")
k5.metric("% of Fraud Rate", f"{overall_fraud_rate:.2f}%")

st.markdown("---")

# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("Fraud Rate % by MonthStart")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(monthly.index.astype(str), monthly.values, color="firebrick")
    ax.set_ylabel("Fraud Rate %")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.xaxis.set_major_locator(plt.MaxNLocator(8))
    st.pyplot(fig)

with c2:
    st.subheader("Fraud Rate % by CARD_TYPE")
    by_card = card_txn_f.groupby("CARD_TYPE")["IS_FRAUD"].mean().mul(100).sort_values()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(by_card.index, by_card.values, color="indianred")
    ax.set_xlabel("Fraud Rate %")
    st.pyplot(fig)

c3, c4 = st.columns(2)

with c3:
    st.subheader("Top 20 Highest Fraud Transactions")
    top20 = fraud_txn.sort_values("AMOUNT", ascending=False).head(20)
    cols = [c for c in ["TXN_DATE", "CARD_ID", "MERCHANT_CATEGORY", "AMOUNT"] if c in top20.columns]
    st.dataframe(top20[cols], use_container_width=True, height=320)
    st.caption(f"Top 20 total: ₹{top20['AMOUNT'].sum():,.2f}")

with c4:
    st.subheader("Fraud Value Share % by MERCHANT_CATEGORY")
    share = fraud_txn.groupby("MERCHANT_CATEGORY")["AMOUNT"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(6, 6))
    share.plot.pie(autopct="%1.1f%%", ylabel="", ax=ax, pctdistance=0.8)
    st.pyplot(fig)
