"""
Descriptive analytics — "what happened?"
"""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from common import init_page, get_data

init_page("Descriptive", "📊")
tables, d, row_hash = get_data()

st.title("📊 Descriptive Analytics")
st.caption("Portfolio, fraud, defaults, tickets, spend, segmentation, utilization and volume trends.")

section = st.selectbox(
    "Choose analysis",
    [
        "1. Portfolio composition (accounts / cards / loans)",
        "2. Fraud incidence by category, card type, month",
        "3. Default & late-payment rate by loan type / branch / tenure",
        "4. Support-ticket volume & resolution time",
        "5. Card spend vs fraud by merchant category",
        "6. Customer segmentation (income × credit score)",
        "7. Card utilization by card type",
        "8. Monthly transaction volume & value trend",
    ],
    key="desc_section",
)

accounts, cards, loan = tables["accounts"], tables["cards"], tables["loan"]
card_txn, loan_full = d["card_txn"], d["loan_full"]

if section.startswith("1."):
    account_mix = accounts.groupby(["ACCOUNT_TYPE", "STATUS"]).agg(
        accounts=("ACCOUNT_ID", "count"), total_balance=("BALANCE", "sum"), avg_balance=("BALANCE", "mean")
    ).reset_index().sort_values("accounts", ascending=False)
    card_mix = cards.groupby("CARD_TYPE").agg(
        cards=("CARD_ID", "count"), total_credit_balance=("CREDIT_LIMIT", "sum"),
        avg_credit_balance=("CREDIT_LIMIT", "mean")
    ).reset_index().sort_values("total_credit_balance", ascending=False)
    loan_mix = loan.groupby("LOAN_TYPE").agg(
        loans=("LOAN_ID", "count"), total_disbursed=("LOAN_AMOUNT", "sum"),
        avg_interest_rate=("INTEREST_RATE", "mean")
    ).reset_index().sort_values("total_disbursed", ascending=False)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Accounts by type")
        fig, ax = plt.subplots(figsize=(4, 4))
        account_mix.groupby("ACCOUNT_TYPE")["accounts"].sum().plot.pie(autopct="%1.0f%%", ylabel="", ax=ax)
        st.pyplot(fig)
    with c2:
        st.subheader("Cards by type")
        fig, ax = plt.subplots(figsize=(4, 4))
        card_mix.set_index("CARD_TYPE")["cards"].plot.bar(color="orange", ax=ax)
        st.pyplot(fig)
    with c3:
        st.subheader("Loan volume by type")
        fig, ax = plt.subplots(figsize=(4, 4))
        loan_mix.set_index("LOAN_TYPE")["total_disbursed"].plot.bar(color="green", ax=ax)
        st.pyplot(fig)

    st.dataframe(account_mix, use_container_width=True)
    st.dataframe(card_mix, use_container_width=True)
    st.dataframe(loan_mix, use_container_width=True)

    top_account, top_loan = account_mix.iloc[0], loan_mix.iloc[0]
    st.info(
        f"**Insight:** '{top_account['ACCOUNT_TYPE']}/{top_account['STATUS']}' is the most common account "
        f"type (₹{top_account['total_balance']:,.0f} total balance). '{top_loan['LOAN_TYPE']}' is the "
        f"largest loan book (₹{top_loan['total_disbursed']:,.0f} disbursed, "
        f"{top_loan['avg_interest_rate']:.2f}% avg rate)."
    )

elif section.startswith("2."):
    fraud_by_category = card_txn.groupby("MERCHANT_CATEGORY").agg(
        total_txn=("CARD_TXN_ID", "count"), fraud_txn=("IS_FRAUD", "sum")
    ).reset_index()
    fraud_by_category["fraud_rate_pct"] = (fraud_by_category["fraud_txn"] / fraud_by_category["total_txn"] * 100).round(2)
    fraud_by_category = fraud_by_category.sort_values("fraud_rate_pct", ascending=False)

    fraud_by_card_type = card_txn.groupby("CARD_TYPE").agg(
        total_txn=("CARD_TXN_ID", "count"), fraud_txn=("IS_FRAUD", "sum")
    ).reset_index()
    fraud_by_card_type["fraud_rate_pct"] = (fraud_by_card_type["fraud_txn"] / fraud_by_card_type["total_txn"] * 100).round(2)
    fraud_by_card_type = fraud_by_card_type.sort_values("fraud_rate_pct", ascending=False)

    fraud_by_month = card_txn.groupby("txn_month").agg(
        total_txn=("CARD_TXN_ID", "count"), fraud_txn=("IS_FRAUD", "sum")
    ).reset_index()
    fraud_by_month["fraud_rate_pct"] = (fraud_by_month["fraud_txn"] / fraud_by_month["total_txn"] * 100).round(2)
    fraud_by_month = fraud_by_month.sort_values("txn_month")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Fraud rate % by merchant category")
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(fraud_by_category["MERCHANT_CATEGORY"], fraud_by_category["fraud_rate_pct"], color="crimson")
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        st.pyplot(fig)
    with c2:
        st.subheader("Fraud rate % by card type")
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(fraud_by_card_type["CARD_TYPE"], fraud_by_card_type["fraud_rate_pct"], color="darkorange")
        st.pyplot(fig)

    st.subheader("Fraud rate % trend by month")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(fraud_by_month["txn_month"], fraud_by_month["fraud_rate_pct"], marker="o", color="firebrick")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    st.pyplot(fig)

    top_cat, top_card = fraud_by_category.iloc[0], fraud_by_card_type.iloc[0]
    st.info(
        f"**Insight:** '{top_cat['MERCHANT_CATEGORY']}' is the riskiest merchant category "
        f"({top_cat['fraud_rate_pct']}% fraud rate). '{top_card['CARD_TYPE']}' cards show the highest "
        f"fraud rate among card types ({top_card['fraud_rate_pct']}%)."
    )

elif section.startswith("3."):
    by_loan_type = loan_full.groupby("LOAN_TYPE").agg(
        loans=("LOAN_ID", "count"), default_rate_pct=("is_default", "mean"), late_rate_pct=("ever_late", "mean")
    ).reset_index()
    by_loan_type[["default_rate_pct", "late_rate_pct"]] = (by_loan_type[["default_rate_pct", "late_rate_pct"]] * 100).round(2)

    by_branch = loan_full.groupby("BRANCH_ID").agg(
        loans=("LOAN_ID", "count"), default_rate_pct=("is_default", "mean"), late_rate_pct=("ever_late", "mean")
    ).reset_index()
    by_branch[["default_rate_pct", "late_rate_pct"]] = (by_branch[["default_rate_pct", "late_rate_pct"]] * 100).round(2)

    by_tenure = loan_full.groupby("tenure_band", observed=True).agg(
        loans=("LOAN_ID", "count"), default_rate_pct=("is_default", "mean"), late_rate_pct=("ever_late", "mean")
    ).reset_index()
    by_tenure[["default_rate_pct", "late_rate_pct"]] = (by_tenure[["default_rate_pct", "late_rate_pct"]] * 100).round(2)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Default rate % by loan type")
        fig, ax = plt.subplots(figsize=(6, 4))
        by_loan_type.set_index("LOAN_TYPE")["default_rate_pct"].plot.bar(color="steelblue", ax=ax)
        st.pyplot(fig)
    with c2:
        st.subheader("Default rate % by tenure band")
        fig, ax = plt.subplots(figsize=(6, 4))
        by_tenure.set_index("tenure_band")["default_rate_pct"].plot.bar(color="darkred", ax=ax)
        st.pyplot(fig)

    st.subheader("Worst 10 branches by default rate")
    st.dataframe(by_branch.sort_values("default_rate_pct", ascending=False).head(10), use_container_width=True)

    worst = by_loan_type.sort_values("default_rate_pct", ascending=False).iloc[0]
    st.info(
        f"**Insight:** '{worst['LOAN_TYPE']}' loans have the worst default rate "
        f"({worst['default_rate_pct']}%) and a {worst['late_rate_pct']}% late-payment rate."
    )

elif section.startswith("4."):
    support_ticket = d["support_ticket"]
    ticket_summary = support_ticket.groupby("ISSUE_TYPE").agg(
        tickets=("TICKET_ID", "count"), avg_resolution_days=("resolution_days", "mean")
    ).reset_index().sort_values("tickets", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Ticket volume by issue type")
        fig, ax = plt.subplots(figsize=(6, 4))
        ticket_summary.set_index("ISSUE_TYPE")["tickets"].plot.bar(color="teal", ax=ax)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        st.pyplot(fig)
    with c2:
        st.subheader("Avg resolution days by issue type")
        fig, ax = plt.subplots(figsize=(6, 4))
        ticket_summary.set_index("ISSUE_TYPE")["avg_resolution_days"].plot.bar(color="slateblue", ax=ax)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        st.pyplot(fig)

    top_ticket = ticket_summary.iloc[0]
    slowest_ticket = ticket_summary.sort_values("avg_resolution_days", ascending=False).iloc[0]
    st.info(
        f"**Insight:** '{top_ticket['ISSUE_TYPE']}' generates the most tickets ({top_ticket['tickets']}). "
        f"'{slowest_ticket['ISSUE_TYPE']}' takes the longest to resolve "
        f"({slowest_ticket['avg_resolution_days']:.1f} days)."
    )

elif section.startswith("5."):
    spend_fraud = card_txn.groupby("MERCHANT_CATEGORY").agg(
        total_spend=("AMOUNT", "sum"), total_txn=("CARD_TXN_ID", "count"),
        fraud_rate_pct=("IS_FRAUD", lambda x: round(x.mean() * 100, 2)),
    ).reset_index().sort_values("total_spend", ascending=False)

    st.subheader("Spend vs fraud rate by merchant category")
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(spend_fraud["MERCHANT_CATEGORY"], spend_fraud["total_spend"], color="steelblue")
    ax1.set_ylabel("Total spend")
    plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")
    ax2 = ax1.twinx()
    ax2.plot(spend_fraud["MERCHANT_CATEGORY"], spend_fraud["fraud_rate_pct"], color="red", marker="o")
    ax2.set_ylabel("Fraud rate %")
    st.pyplot(fig)
    st.dataframe(spend_fraud, use_container_width=True)

    top_spend = spend_fraud.iloc[0]
    top_fraud = spend_fraud.sort_values("fraud_rate_pct", ascending=False).iloc[0]
    st.info(
        f"**Insight:** '{top_spend['MERCHANT_CATEGORY']}' drives the most spend "
        f"(₹{top_spend['total_spend']:,.0f}). '{top_fraud['MERCHANT_CATEGORY']}' has the highest fraud "
        f"rate ({top_fraud['fraud_rate_pct']}%)."
    )

elif section.startswith("6."):
    customers_with_balance = d["customers_with_balance"]
    segmentation = customers_with_balance.groupby(["income_band", "credit_band"], observed=True).agg(
        customers=("CUSTOMER_ID", "count"), avg_balance=("BALANCE", "mean")
    ).reset_index().sort_values(["income_band", "credit_band"])

    st.subheader("Avg account balance by income & credit-score band")
    pivot = segmentation.pivot(index="income_band", columns="credit_band", values="avg_balance")
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="Blues", ax=ax)
    ax.set_ylabel("Income Band"); ax.set_xlabel("Credit Score Band")
    st.pyplot(fig)
    st.dataframe(segmentation, use_container_width=True)

    top_seg = segmentation.sort_values("avg_balance", ascending=False).iloc[0]
    st.info(
        f"**Insight:** Highest avg balance ({top_seg['avg_balance']:.0f}) comes from income band "
        f"'{top_seg['income_band']}' and credit band '{top_seg['credit_band']}'."
    )

elif section.startswith("7."):
    card_util = d["card_util"]
    util_by_type = card_util.groupby("CARD_TYPE")["utilization_pct"].mean().round(2).reset_index().sort_values(
        "utilization_pct", ascending=False
    )

    st.subheader("Avg utilization % by card type")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(util_by_type["CARD_TYPE"], util_by_type["utilization_pct"], color="darkcyan")
    ax.set_ylabel("Utilization %")
    st.pyplot(fig)
    st.dataframe(util_by_type, use_container_width=True)

    top_util = util_by_type.iloc[0]
    st.info(
        f"**Insight:** '{top_util['CARD_TYPE']}' cards run the highest average utilization "
        f"({top_util['utilization_pct']}%) — candidates for credit-limit review or targeted offers."
    )

elif section.startswith("8."):
    transaction_list = d["transaction_list"]
    monthly_trend = transaction_list.groupby("txn_month").agg(
        txn_count=("TRANSACTION_ID", "count"), total_amount=("AMOUNT", "sum")
    ).reset_index().sort_values("txn_month")

    st.subheader("Monthly transaction value trend")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(monthly_trend["txn_month"], monthly_trend["total_amount"], marker="o")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    st.pyplot(fig)
    st.dataframe(monthly_trend, use_container_width=True)
