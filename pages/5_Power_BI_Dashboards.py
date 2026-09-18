"""
Power BI Dashboards — all three original Power BI report pages reproduced
here as tabs in a single Streamlit page: Fraud Monitoring, Credit Risk &
Collections, and Customer Risk Overview.
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from common import init_page, get_data, banner

init_page("Power BI Dashboards", "📑")
tables, d, row_hash = get_data()

st.title("📑 Power BI Dashboards")
st.caption("The three original Power BI report pages, reproduced here as tabs.")

tab_fraud, tab_credit, tab_customer = st.tabs(
    ["🚨 Fraud Monitoring", "💳 Credit Risk & Collections", "🧭 Customer Risk Overview"]
)

# ==========================================================================
# TAB 1 — Fraud Monitoring
# ==========================================================================
with tab_fraud:
    banner("Fraud Monitoring")

    card_txn = d["card_txn"].copy()
    cards = tables["cards"]

    with st.expander("Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        card_type_opts = sorted(card_txn["CARD_TYPE"].dropna().unique().tolist())
        card_type_sel = f1.multiselect("Card type", card_type_opts, default=card_type_opts, key="fraud_card_type")

        merchant_opts = sorted(card_txn["MERCHANT_CATEGORY"].dropna().unique().tolist())
        merchant_sel = f2.multiselect("Merchant category", merchant_opts, default=merchant_opts, key="fraud_merchant")

        branch_sel = None
        if "CUSTOMER_ID" in cards.columns and "CUSTOMER_ID" in tables["accounts"].columns:
            acc_branch = tables["accounts"][["CUSTOMER_ID", "BRANCH_ID"]].drop_duplicates()
            card_branch = cards.merge(acc_branch, on="CUSTOMER_ID", how="left").merge(
                tables["branches"][["BRANCH_ID", "BRANCH_NAME"]], on="BRANCH_ID", how="left"
            )[["CARD_ID", "BRANCH_NAME"]]
            branch_opts = sorted(card_branch["BRANCH_NAME"].dropna().unique().tolist())
            if branch_opts:
                branch_sel = f3.multiselect("Branch", branch_opts, default=branch_opts, key="fraud_branch")
                card_txn = card_txn.merge(card_branch, on="CARD_ID", how="left")

        min_date, max_date = card_txn["TXN_DATE"].min(), card_txn["TXN_DATE"].max()
        date_range = f4.date_input("Date", [min_date, max_date], key="fraud_date")

    mask = card_txn["CARD_TYPE"].isin(card_type_sel) & card_txn["MERCHANT_CATEGORY"].isin(merchant_sel)
    if branch_sel is not None:
        mask &= card_txn["BRANCH_NAME"].isin(branch_sel)
    start = pd.to_datetime(date_range[0]) if len(date_range) > 0 else min_date
    end = pd.to_datetime(date_range[1]) if len(date_range) > 1 else max_date
    mask &= (card_txn["TXN_DATE"] >= start) & (card_txn["TXN_DATE"] <= end)
    card_txn_f = card_txn[mask]

    if card_txn_f.empty:
        st.warning("No transactions match the current filters.")
    else:
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

# ==========================================================================
# TAB 2 — Credit Risk & Collections
# ==========================================================================
with tab_credit:
    banner("Credit Risk & Collections")

    loan_full = d["loan_full"].copy()
    loan_payment = tables["loan_payment"].copy()
    customers = tables["customers"]
    branches = tables["branches"]

    loan_full = loan_full.merge(
        customers[[c for c in ["CUSTOMER_ID", "CREDIT_SCORE", "credit_band", "STATE"] if c in customers.columns]],
        on="CUSTOMER_ID", how="left",
    )

    with st.expander("Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        loan_type_opts = sorted(loan_full["LOAN_TYPE"].dropna().unique().tolist())
        loan_type_sel = f1.multiselect("Loan type", loan_type_opts, default=loan_type_opts, key="credit_loan_type")

        band_sel = None
        if "credit_band" in loan_full.columns:
            band_opts = [b for b in ["<600", "600-700", "700-800", "800+"] if b in loan_full["credit_band"].astype(str).unique()]
            band_sel = f2.multiselect("Credit score band", band_opts, default=band_opts, key="credit_band_sel")

        state_sel = None
        if "STATE" in loan_full.columns:
            state_opts = sorted(loan_full["STATE"].dropna().unique().tolist())
            state_sel = f3.multiselect("State", state_opts, default=state_opts, key="credit_state")

        min_date, max_date = loan_full["START_DATE"].min(), loan_full["START_DATE"].max()
        date_range = f4.date_input("Start date", [min_date, max_date], key="credit_date")

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
    else:
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

# ==========================================================================
# TAB 3 — Customer Risk Overview
# ==========================================================================
with tab_customer:
    banner("Customer Risk Overview")
    st.caption(
        "Risk Tier and Composite Risk Score are approximated from credit score, "
        "default history, card fraud, and escalated tickets (the original Power BI "
        "DAX formulas aren't available here) — see code comments for details."
    )

    customers = tables["customers"].copy()
    loan_full2 = d["loan_full"]
    card_txn2 = d["card_txn"]
    support_ticket = d["support_ticket"]

    cust_default = loan_full2.groupby("CUSTOMER_ID")["is_default"].max().rename("has_default")

    card_cust = tables["cards"][["CARD_ID"] + (["CUSTOMER_ID"] if "CUSTOMER_ID" in tables["cards"].columns else [])]
    if "CUSTOMER_ID" in card_cust.columns:
        fraud_cards = card_txn2.loc[card_txn2["IS_FRAUD"] == 1, "CARD_ID"].unique()
        card_cust["had_fraud"] = card_cust["CARD_ID"].isin(fraud_cards)
        cust_fraud = card_cust.groupby("CUSTOMER_ID")["had_fraud"].max()
    else:
        cust_fraud = pd.Series(dtype=bool)

    escalated_status = [s for s in support_ticket["STATUS"].unique() if s not in ["Closed", "Resolved"]]
    cust_escalated_flag = support_ticket["CUSTOMER_ID"].isin(
        support_ticket.loc[support_ticket["STATUS"].isin(escalated_status), "CUSTOMER_ID"]
    )
    cust_escalated = support_ticket.assign(escalated=cust_escalated_flag).groupby("CUSTOMER_ID")["escalated"].max()

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

    with st.expander("Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        tier_opts = ["Low", "Medium", "High", "Critical"]
        tier_sel = f1.multiselect("Risk tier", tier_opts, default=tier_opts, key="cust_tier")

        occ_sel = state_sel2 = gender_sel = None
        if "OCCUPATION" in customers.columns:
            occ_opts = sorted(customers["OCCUPATION"].dropna().unique().tolist())
            occ_sel = f2.multiselect("Occupation", occ_opts, default=occ_opts, key="cust_occ")
        if "STATE" in customers.columns:
            state_opts2 = sorted(customers["STATE"].dropna().unique().tolist())
            state_sel2 = f3.multiselect("State", state_opts2, default=state_opts2, key="cust_state")
        if "GENDER" in customers.columns:
            gender_opts = sorted(customers["GENDER"].dropna().unique().tolist())
            gender_sel = f4.multiselect("Gender", gender_opts, default=gender_opts, key="cust_gender")

    mask = customers["risk_tier"].isin(tier_sel)
    if occ_sel is not None:
        mask &= customers["OCCUPATION"].isin(occ_sel)
    if state_sel2 is not None:
        mask &= customers["STATE"].isin(state_sel2)
    if gender_sel is not None:
        mask &= customers["GENDER"].isin(gender_sel)
    cust_f = customers[mask]

    if cust_f.empty:
        st.warning("No customers match the current filters.")
    else:
        avg_credit = cust_f["CREDIT_SCORE"].mean()
        default_rate = loan_full2[loan_full2["CUSTOMER_ID"].isin(cust_f["CUSTOMER_ID"])]["is_default"].mean() * 100
        fraud_incidents = card_txn2["IS_FRAUD"].sum()
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
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Payment Status Trends by Year")
            lp = tables["loan_payment"].copy()
            lp = lp[lp["LOAN_ID"].isin(loan_full2[loan_full2["CUSTOMER_ID"].isin(cust_f["CUSTOMER_ID"])]["LOAN_ID"])]
            lp = lp.merge(loan_full2[["LOAN_ID", "STATUS"]], on="LOAN_ID", how="left")
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
