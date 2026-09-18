"""
Customer Risk Overview — reproduces the "Customer Risk Overview" Power BI
dashboard: KPIs, payment status trends, risk tier breakdown, a
credit-score-vs-risk matrix, and a composite risk score gauge.

NOTE: "Risk Tier" and "Composite Risk Score" were DAX measures in the
original Power BI model, not raw columns — their exact formulas aren't
available here, so this page computes an equivalent composite score from
credit score, default history, card fraud, and escalated tickets, then
buckets it into Low/Medium/High/Critical quartiles. Treat the exact
numbers as an approximation of the original, not an identical replica.
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from common import init_page, get_data, banner

init_page("Customer Risk Overview", "🧭")
tables, d, row_hash = get_data()

banner("Customer Risk Overview")

customers = tables["customers"].copy()
loan_full = d["loan_full"]
card_txn = d["card_txn"]
support_ticket = d["support_ticket"]

# --------------------------------------------------------------------------
# Build a per-customer composite risk score (approximation — see note above)
# --------------------------------------------------------------------------
cust_default = loan_full.groupby("CUSTOMER_ID")["is_default"].max().rename("has_default")

card_cust = tables["cards"][["CARD_ID"] + (["CUSTOMER_ID"] if "CUSTOMER_ID" in tables["cards"].columns else [])]
if "CUSTOMER_ID" in card_cust.columns:
    fraud_cards = card_txn.loc[card_txn["IS_FRAUD"] == 1, "CARD_ID"].unique()
    card_cust["had_fraud"] = card_cust["CARD_ID"].isin(fraud_cards)
    cust_fraud = card_cust.groupby("CUSTOMER_ID")["had_fraud"].max()
else:
    cust_fraud = pd.Series(dtype=bool)

escalated_status = [s for s in support_ticket["STATUS"].unique() if s not in ["Closed", "Resolved"]]
cust_escalated = support_ticket["CUSTOMER_ID"].isin(
    support_ticket.loc[support_ticket["STATUS"].isin(escalated_status), "CUSTOMER_ID"]
)
cust_escalated = support_ticket.assign(escalated=cust_escalated).groupby("CUSTOMER_ID")["escalated"].max()

risk_df = customers.set_index("CUSTOMER_ID")[["CREDIT_SCORE"]].copy()
risk_df["has_default"] = cust_default.reindex(risk_df.index).fillna(0)
risk_df["had_fraud"] = cust_fraud.reindex(risk_df.index).fillna(False).astype(int)
risk_df["escalated"] = cust_escalated.reindex(risk_df.index).fillna(False).astype(int)

risk_df["credit_risk"] = (900 - risk_df["CREDIT_SCORE"].clip(300, 900)) / (900 - 300) * 100
risk_df["composite_risk_score"] = (
    risk_df["credit_risk"] * 0.40
    + risk_df["has_default"] * 100 * 0.30
    + risk_df["had_fraud"] * 100 * 0.15
    + risk_df["escalated"] * 100 * 0.15
).round(2)

risk_df["risk_tier"] = pd.qcut(
    risk_df["composite_risk_score"], 4, labels=["Low", "Medium", "High", "Critical"], duplicates="drop"
)

customers = customers.merge(
    risk_df[["composite_risk_score", "risk_tier"]], left_on="CUSTOMER_ID", right_index=True, how="left"
)

# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------
st.sidebar.subheader("Filters")

tier_opts = ["Low", "Medium", "High", "Critical"]
tier_sel = st.sidebar.multiselect("Risk tier", tier_opts, default=tier_opts)

occ_sel = state_sel = gender_sel = None
if "OCCUPATION" in customers.columns:
    occ_opts = sorted(customers["OCCUPATION"].dropna().unique().tolist())
    occ_sel = st.sidebar.multiselect("Occupation", occ_opts, default=occ_opts)
if "STATE" in customers.columns:
    state_opts = sorted(customers["STATE"].dropna().unique().tolist())
    state_sel = st.sidebar.multiselect("State", state_opts, default=state_opts)
if "GENDER" in customers.columns:
    gender_opts = sorted(customers["GENDER"].dropna().unique().tolist())
    gender_sel = st.sidebar.multiselect("Gender", gender_opts, default=gender_opts)

mask = customers["risk_tier"].isin(tier_sel)
if occ_sel is not None:
    mask &= customers["OCCUPATION"].isin(occ_sel)
if state_sel is not None:
    mask &= customers["STATE"].isin(state_sel)
if gender_sel is not None:
    mask &= customers["GENDER"].isin(gender_sel)
cust_f = customers[mask]

if cust_f.empty:
    st.warning("No customers match the current filters.")
    st.stop()

# --------------------------------------------------------------------------
# KPI cards
# --------------------------------------------------------------------------
avg_credit = cust_f["CREDIT_SCORE"].mean()
default_rate = loan_full[loan_full["CUSTOMER_ID"].isin(cust_f["CUSTOMER_ID"])]["is_default"].mean() * 100
fraud_incidents = card_txn["IS_FRAUD"].sum()
open_tickets = support_ticket[
    support_ticket["CUSTOMER_ID"].isin(cust_f["CUSTOMER_ID"])
    & ~support_ticket["STATUS"].isin(["Closed", "Resolved"])
].shape[0]
high_risk_pct = cust_f["risk_tier"].isin(["High", "Critical"]).mean() * 100

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Average Credit Score", f"{avg_credit:.2f}")
k2.metric("Default Rate %", f"{default_rate:.2f}")
k3.metric("Fraud Incidents on Cards", f"{fraud_incidents:,}")
k4.metric("Open/Escalated Support Tickets", f"{open_tickets:,}")
k5.metric("High Risk Customer %", f"{high_risk_pct:.0f}%")

st.markdown("---")

# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("Payment Status Trends by Year")
    lp = tables["loan_payment"].copy()
    lp = lp[lp["LOAN_ID"].isin(loan_full[loan_full["CUSTOMER_ID"].isin(cust_f["CUSTOMER_ID"])]["LOAN_ID"])]
    lp = lp.merge(loan_full[["LOAN_ID", "STATUS"]], on="LOAN_ID", how="left")
    if "AMOUNT_PAID" in lp.columns and "PAYMENT_DATE" in lp.columns:
        lp["year"] = pd.to_datetime(lp["PAYMENT_DATE"]).dt.year
        trend = lp.groupby(["year", "STATUS"])["AMOUNT_PAID"].sum().unstack(fill_value=0)
        fig, ax = plt.subplots(figsize=(6, 4))
        trend.plot(kind="bar", ax=ax, colormap="Reds")
        ax.set_ylabel("Amount paid")
        ax.legend(fontsize=7)
        st.pyplot(fig)
    else:
        st.info("Payment-amount/date columns not found in loan_payment — chart skipped.")

with c2:
    st.subheader("Risk Tier Breakdown by Occupation")
    if "OCCUPATION" in cust_f.columns:
        ct = pd.crosstab(cust_f["OCCUPATION"], cust_f["risk_tier"], normalize="index") * 100
        fig, ax = plt.subplots(figsize=(6, 4))
        ct.plot(kind="barh", stacked=True, colormap="Reds", ax=ax)
        ax.set_xlabel("% of customers")
        ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4)
        st.pyplot(fig)
    else:
        st.info("OCCUPATION column not found in customers — chart skipped.")

c3, c4 = st.columns(2)

with c3:
    st.subheader("Customer Risk Matrix (Credit Score vs Risk Score)")
    if "OCCUPATION" in cust_f.columns:
        matrix = cust_f.groupby("OCCUPATION").agg(
            avg_credit=("CREDIT_SCORE", "mean"), avg_risk=("composite_risk_score", "mean")
        ).reset_index()
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(matrix["avg_credit"], matrix["avg_risk"], s=120, color="firebrick")
        for _, row in matrix.iterrows():
            ax.annotate(row["OCCUPATION"], (row["avg_credit"], row["avg_risk"]), fontsize=8, ha="center", va="bottom")
        ax.set_xlabel("Average Credit Score")
        ax.set_ylabel("Average Composite Risk Score")
        st.pyplot(fig)
    else:
        st.info("OCCUPATION column not found in customers — chart skipped.")

with c4:
    st.subheader("Composite Risk Score")
    composite = cust_f["composite_risk_score"].mean()
    target = customers["composite_risk_score"].quantile(0.75)
    fig, ax = plt.subplots(figsize=(5, 3), subplot_kw={"aspect": "equal"})
    ax.pie(
        [composite, 100 - composite],
        startangle=180, counterclock=False,
        colors=["#a01c1c", "#f2dede"], wedgeprops=dict(width=0.35),
    )
    ax.text(0, -0.2, f"{composite:.2f}", ha="center", fontsize=22, fontweight="bold")
    ax.text(0, -0.55, f"Target: {target:.2f}", ha="center", fontsize=10, color="gray")
    st.pyplot(fig)
