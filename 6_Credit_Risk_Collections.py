"""
Credit Risk & Collections — reproduces the "Credit Risk & Collections"
Power BI dashboard: KPIs, default/write-off rate by loan type and branch,
tenure band by status, and late-payment rate trend.
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from common import init_page, get_data, banner

init_page("Credit Risk & Collections", "💳")
tables, d, row_hash = get_data()

banner("Credit Risk & Collections")

loan_full = d["loan_full"].copy()
loan_payment = tables["loan_payment"].copy()
customers = tables["customers"]
branches = tables["branches"]

loan_full = loan_full.merge(
    customers[[c for c in ["CUSTOMER_ID", "CREDIT_SCORE", "credit_band", "STATE"] if c in customers.columns]],
    on="CUSTOMER_ID", how="left",
)

# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------
st.sidebar.subheader("Filters")

loan_type_opts = sorted(loan_full["LOAN_TYPE"].dropna().unique().tolist())
loan_type_sel = st.sidebar.multiselect("Loan type", loan_type_opts, default=loan_type_opts)

if "credit_band" in loan_full.columns:
    band_opts = [b for b in ["<600", "600-700", "700-800", "800+"] if b in loan_full["credit_band"].astype(str).unique()]
    band_sel = st.sidebar.multiselect("Credit score band", band_opts, default=band_opts)
else:
    band_sel = None

if "STATE" in loan_full.columns:
    state_opts = sorted(loan_full["STATE"].dropna().unique().tolist())
    state_sel = st.sidebar.multiselect("State", state_opts, default=state_opts)
else:
    state_sel = None

min_date, max_date = loan_full["START_DATE"].min(), loan_full["START_DATE"].max()
date_range = st.sidebar.date_input("Start date", [min_date, max_date])

# --------------------------------------------------------------------------
# Apply filters
# --------------------------------------------------------------------------
mask = loan_full["LOAN_TYPE"].isin(loan_type_sel)
if band_sel is not None:
    mask &= loan_full["credit_band"].astype(str).isin(band_sel)
if state_sel is not None:
    mask &= loan_full["STATE"].isin(state_sel)
start = pd.to_datetime(date_range[0]) if len(date_range) > 0 else min_date
end = pd.to_datetime(date_range[1]) if len(date_range) > 1 else max_date
mask &= (loan_full["START_DATE"] >= start) & (loan_full["START_DATE"] <= end)
loan_f = loan_full[mask]

if loan_f.empty:
    st.warning("No loans match the current filters.")
    st.stop()

# --------------------------------------------------------------------------
# KPI cards
# --------------------------------------------------------------------------
active = loan_f[loan_f["STATUS"] == "Active"]
active_loans = len(active)
late_rate = loan_f["ever_late"].mean() * 100 if len(loan_f) else 0
total_book_value = active["LOAN_AMOUNT"].sum()
avg_credit_active = active["CREDIT_SCORE"].mean() if "CREDIT_SCORE" in active.columns and len(active) else float("nan")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Active Loan", f"{active_loans:,}")
k2.metric("Late Payment Rate %", f"{late_rate:.2f}%")
k3.metric("Total Loan Book Value (Active)", f"₹{total_book_value:,.0f}")
k4.metric("Avg Credit Score (Active Customers)", f"{avg_credit_active:.2f}" if pd.notna(avg_credit_active) else "N/A")

st.markdown("---")

# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("Default + Write-off Rate % by LOAN_TYPE")
    by_type = loan_f.groupby("LOAN_TYPE")["is_default"].mean().mul(100).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(by_type.index, by_type.values, color="lightcoral")
    ax.set_ylabel("Default + Write-off Rate %")
    ax.bar_label(bars, fmt="%.2f%%")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    st.pyplot(fig)

with c2:
    st.subheader("Top 10 Default + Write-off Rate % by BRANCH_NAME")
    by_branch = loan_f.groupby("BRANCH_ID")["is_default"].mean().mul(100).reset_index()
    by_branch = by_branch.merge(branches[["BRANCH_ID", "BRANCH_NAME"]], on="BRANCH_ID", how="left")
    top10 = by_branch.sort_values("is_default", ascending=False).head(10).sort_values("is_default")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(top10["BRANCH_NAME"], top10["is_default"], color="indianred")
    ax.set_xlabel("Default + Write-off Rate %")
    st.pyplot(fig)

c3, c4 = st.columns(2)

with c3:
    st.subheader("Count of Tenure Band by STATUS")
    ct = pd.crosstab(loan_f["tenure_band"], loan_f["STATUS"], normalize="index") * 100
    fig, ax = plt.subplots(figsize=(6, 4))
    ct.plot(kind="barh", stacked=True, colormap="Reds", ax=ax)
    ax.set_xlabel("% of loans")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=8)
    st.pyplot(fig)

with c4:
    st.subheader("Late-Payment Rate % by Payment Month")
    lp = loan_payment[loan_payment["LOAN_ID"].isin(loan_f["LOAN_ID"])].copy()
    lp["pay_month"] = pd.to_datetime(lp["PAYMENT_DATE"]).dt.to_period("M").astype(str)
    monthly_late = lp.groupby("pay_month")["LATE_PAYMENT_FLAG"].mean().mul(100).sort_index()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(monthly_late.index, monthly_late.values, color="firebrick")
    ax.set_ylabel("Late-Payment Rate %")
    ax.xaxis.set_major_locator(plt.MaxNLocator(8))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    st.pyplot(fig)
