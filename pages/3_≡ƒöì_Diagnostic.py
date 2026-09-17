"""
Diagnostic analytics — "why did it happen?"
"""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from common import init_page, get_data

init_page("Diagnostic", "🔍")
tables, d, row_hash = get_data()

st.title("🔍 Diagnostic Analytics")
st.caption("Credit bands, fraud drivers, branch effects, tickets vs dormancy, utilization vs fraud.")

section = st.selectbox(
    "Choose analysis",
    [
        "1. Credit-score band vs default & late-payment rate",
        "2. Merchant category disproportionate fraud rate",
        "3. Prior fraud-report ticket vs subsequent confirmed fraud",
        "4. Branch actual vs expected default rate (loan-mix adjusted)",
        "5. Escalated tickets vs account dormancy/closure",
        "6. Card utilization band vs fraud rate",
        "7. Account tenure vs dormancy/closure",
    ],
    key="diag_section",
)

loan_full, card_txn = d["loan_full"], d["card_txn"]
customers, card_util = d["customers"], d["card_util"]
accounts, support_ticket = d["accounts"], d["support_ticket"]
cards = tables["cards"]

if section.startswith("1."):
    loan_cust = loan_full.merge(customers[["CUSTOMER_ID", "credit_band"]], on="CUSTOMER_ID", how="left")
    loan1 = loan_cust.groupby("credit_band", observed=True).agg(
        loans=("LOAN_ID", "count"),
        defaults_rate_pct=("is_default", lambda x: round(x.mean() * 100, 2)),
        late_rate_pct=("ever_late", lambda x: round(x.mean() * 100, 2)),
    ).reset_index()

    c1, c2 = st.columns(2)
    with c1:
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.barplot(x="credit_band", y="defaults_rate_pct", data=loan1, ax=ax)
        ax.set_title("Default Rate by Credit Score Band")
        st.pyplot(fig)
    with c2:
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.barplot(x="credit_band", y="late_rate_pct", data=loan1, ax=ax)
        ax.set_title("Late Payment Rate by Credit Score Band")
        st.pyplot(fig)
    st.dataframe(loan1, use_container_width=True)

    top_def = loan1.sort_values("defaults_rate_pct", ascending=False).iloc[0]
    top_late = loan1.sort_values("late_rate_pct", ascending=False).iloc[0]
    st.info(
        f"**Insight:** Highest default rate ({top_def['defaults_rate_pct']}%) comes from credit band "
        f"'{top_def['credit_band']}'. Highest late-payment rate ({top_late['late_rate_pct']}%) comes "
        f"from credit band '{top_late['credit_band']}'."
    )

elif section.startswith("2."):
    fraud_by_category = card_txn.groupby("MERCHANT_CATEGORY").agg(
        total_txn=("CARD_TXN_ID", "count"), fraud_txn=("IS_FRAUD", "sum")
    ).reset_index()
    fraud_by_category["fraud_rate_pct"] = (fraud_by_category["fraud_txn"] / fraud_by_category["total_txn"] * 100).round(2)
    overall_fraud_rate = card_txn["IS_FRAUD"].mean() * 100
    cat_fraud = fraud_by_category.copy()
    cat_fraud["disproportionate"] = cat_fraud["fraud_rate_pct"] - overall_fraud_rate
    cat_fraud = cat_fraud.sort_values("disproportionate", ascending=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(x="MERCHANT_CATEGORY", y="disproportionate", data=cat_fraud, ax=ax)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_title("Disproportionate Fraud Rate vs Overall Baseline")
    st.pyplot(fig)
    st.dataframe(cat_fraud, use_container_width=True)
    st.caption(f"Overall baseline fraud rate: {overall_fraud_rate:.2f}%")

elif section.startswith("3."):
    fraud_reporters = support_ticket[support_ticket["ISSUE_TYPE"] == "Fraud Report"][
        ["CUSTOMER_ID", "DATE_OPENED"]
    ].rename(columns={"DATE_OPENED": "fraud_report_date"})
    card_cust = cards[["CARD_ID", "CUSTOMER_ID"]]
    card_txn_cust = card_txn.merge(card_cust, on="CARD_ID", how="left")
    txn_with_reports = card_txn_cust.merge(fraud_reporters, on="CUSTOMER_ID", how="left")
    txn_with_reports["had_prior_fraud_report"] = (
        ~txn_with_reports["fraud_report_date"].isna()
    ) & (txn_with_reports["TXN_DATE"] >= txn_with_reports["fraud_report_date"])

    fraud_correlation = txn_with_reports.groupby("had_prior_fraud_report").agg(
        transactions=("CARD_TXN_ID", "count"), fraud_count=("IS_FRAUD", "sum"),
        fraud_rate_pct=("IS_FRAUD", lambda x: round(x.mean() * 100, 2)),
    ).reset_index()

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["No Prior Report", "Had Prior Report"], fraud_correlation["fraud_rate_pct"],
           color=["steelblue", "coral"])
    ax.set_title("Fraud Rate: With vs Without Prior Fraud Report")
    st.pyplot(fig)
    st.dataframe(fraud_correlation, use_container_width=True)

    if len(fraud_correlation) == 2:
        rate_with = fraud_correlation.loc[fraud_correlation["had_prior_fraud_report"] == True, "fraud_rate_pct"].values[0]
        rate_without = fraud_correlation.loc[fraud_correlation["had_prior_fraud_report"] == False, "fraud_rate_pct"].values[0]
        lift = rate_with - rate_without
        st.info(
            f"**Insight:** Prior reporters show a {rate_with}% fraud rate vs {rate_without}% for others "
            f"(lift: {lift:.2f} pts). "
            + ("Prior fraud reporting is a strong predictor of subsequent confirmed fraud."
               if lift > 0 else "No meaningful link found.")
        )

elif section.startswith("4."):
    branches = tables["branches"]
    network_avg = loan_full.groupby("LOAN_TYPE")["is_default"].mean().reset_index().rename(
        columns={"is_default": "network_default_rate"}
    )
    loan_with_expected = loan_full.merge(network_avg, on="LOAN_TYPE", how="left")
    branch_analysis = loan_with_expected.groupby("BRANCH_ID").agg(
        loans=("LOAN_ID", "count"), actual_default_rate=("is_default", "mean"),
        expected_default_rate=("network_default_rate", "mean"),
    ).reset_index().merge(branches[["BRANCH_ID", "BRANCH_NAME"]], on="BRANCH_ID")
    branch_analysis["excess_default_pct"] = (
        (branch_analysis["actual_default_rate"] - branch_analysis["expected_default_rate"]) * 100
    ).round(2)
    branch_analysis["actual_default_pct"] = (branch_analysis["actual_default_rate"] * 100).round(2)
    branch_analysis["expected_default_pct"] = (branch_analysis["expected_default_rate"] * 100).round(2)

    top_n = branch_analysis.reindex(
        branch_analysis["excess_default_pct"].abs().sort_values(ascending=False).index
    ).head(15).sort_values("excess_default_pct")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top_n["BRANCH_NAME"], top_n["excess_default_pct"],
            color=["red" if x > 0 else "blue" for x in top_n["excess_default_pct"]])
    ax.axhline(y=0, color="black", linewidth=0.8)
    ax.set_title("Top 15 Branches by |Excess Default Rate| (red=worse, blue=better)")
    st.pyplot(fig)
    st.dataframe(
        branch_analysis[["BRANCH_ID", "BRANCH_NAME", "loans", "actual_default_pct",
                          "expected_default_pct", "excess_default_pct"]].sort_values(
            "excess_default_pct", ascending=False
        ),
        use_container_width=True,
    )

elif section.startswith("5."):
    customers_tbl = tables["customers"]
    escalated_status = [s for s in support_ticket["STATUS"].unique() if s not in ["closed", "resolved"]]
    escalated_customers = set(support_ticket[support_ticket["STATUS"].isin(escalated_status)]["CUSTOMER_ID"].unique())

    account_cust = accounts.merge(customers_tbl[["CUSTOMER_ID"]], on="CUSTOMER_ID")
    account_cust["had_escalated_ticket"] = account_cust["CUSTOMER_ID"].isin(escalated_customers)
    account_mix = pd.crosstab(account_cust["STATUS"], account_cust["had_escalated_ticket"], normalize="index") * 100

    fig, ax = plt.subplots(figsize=(9, 5))
    account_mix.plot(kind="bar", stacked=True, colormap="coolwarm", ax=ax)
    ax.set_title("Account Status Mix: Escalated-Ticket Customers vs Others")
    st.pyplot(fig)
    st.dataframe(account_mix.round(2), use_container_width=True)

elif section.startswith("6."):
    card_util_fraud = card_util.groupby("util_band", observed=True)["fraud_on_card"].mean().mul(100).round(2)
    fig, ax = plt.subplots(figsize=(9, 5))
    card_util_fraud.plot(kind="bar", color="orange", ax=ax)
    ax.set_title("Card Fraud Rate by Utilization Band")
    st.pyplot(fig)
    st.dataframe(card_util_fraud.reset_index(name="fraud_rate_pct"), use_container_width=True)
    top_band = card_util_fraud.idxmax()
    st.info(f"**Insight:** Utilization band **{top_band}** has the highest fraud rate ({card_util_fraud[top_band]}%).")

elif section.startswith("7."):
    acc_age = pd.crosstab(accounts["account_age_band"], accounts["STATUS"], normalize="index") * 100
    fig, ax = plt.subplots(figsize=(9, 5))
    acc_age.plot(kind="bar", stacked=True, colormap="coolwarm", ax=ax)
    ax.set_title("Account Status Mix by Age Band")
    st.pyplot(fig)
    st.dataframe(acc_age.round(2), use_container_width=True)
