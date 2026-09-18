"""
Predictive analytics — "what's likely to happen next?"
"""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from common import init_page, get_data

init_page("Predictive", "🤖")
tables, d, row_hash = get_data()

st.title("🤖 Predictive Analytics")
st.caption("Train fraud-detection, credit-default and late-payment models on the loaded data.")

st.write(
    "Train the three notebook models on the currently loaded data. Models train in-memory "
    "each run (fast on sample data; may take longer on large real exports)."
)
model_choice = st.selectbox(
    "Choose model",
    [
        "1. Fraud detection (card transactions)",
        "2. Credit-default prediction (loans)",
        "3. Next-late-payment prediction (active loans)",
    ],
)
train_btn = st.button("Train model", type="primary")

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    roc_auc_score, confusion_matrix, classification_report,
    precision_score, recall_score, roc_curve,
)

def plot_confusion(cm, title, labels=("Legit/On-time", "Fraud/Late")):
    fig, ax = plt.subplots(figsize=(4, 3.5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Greens", xticklabels=labels, yticklabels=labels, ax=ax)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(title)
    st.pyplot(fig)

def metrics_table(names, roc_aucs, y_tests, y_preds):
    rows = []
    for n, auc, yt, yp in zip(names, roc_aucs, y_tests, y_preds):
        rows.append({
            "Model": n, "ROC-AUC": round(auc, 4),
            "Recall (positive class)": round(recall_score(yt, yp, pos_label=1), 4),
            "Precision (positive class)": round(precision_score(yt, yp, pos_label=1, zero_division=0), 4),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

MAX_TRAIN_ROWS = 400_000  # cap so training doesn't blow the memory budget on big exports

if train_btn:
    if model_choice.startswith("1."):
        card_txn = d["card_txn"]
        feature_cols = ["AMOUNT", "CARD_TYPE", "MERCHANT_CATEGORY", "days_since_txn"]
        model_df = card_txn[feature_cols + ["IS_FRAUD"]].dropna().copy()
        if len(model_df) > MAX_TRAIN_ROWS:
            # Stratified sample keeps the fraud/legit ratio intact so metrics stay meaningful.
            # (Built with pd.concat rather than groupby().apply() — pandas 3.x drops the
            # grouping column from apply() results, which silently breaks that approach.)
            parts = []
            for cls, group in model_df.groupby("IS_FRAUD"):
                n = min(len(group), int(MAX_TRAIN_ROWS * len(group) / len(model_df)))
                parts.append(group.sample(n=n, random_state=42))
            model_df = pd.concat(parts, ignore_index=True)
            st.caption(
                f"Training on a random stratified sample of {len(model_df):,} rows "
                f"(out of {len(card_txn):,}) to stay within memory limits."
            )
        le1, le2 = LabelEncoder(), LabelEncoder()
        model_df["CARD_TYPE"] = le1.fit_transform(model_df["CARD_TYPE"])
        model_df["MERCHANT_CATEGORY"] = le2.fit_transform(model_df["MERCHANT_CATEGORY"])
        X, y = model_df.drop(columns="IS_FRAUD"), model_df["IS_FRAUD"]
        if y.nunique() < 2:
            st.error("Not enough class variety in IS_FRAUD to train — check your data.")
        else:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
            scaler = StandardScaler()
            X_train_s, X_test_s = scaler.fit_transform(X_train), scaler.transform(X_test)

            lr = LogisticRegression().fit(X_train_s, y_train)
            y_pred_lr, y_prob_lr = lr.predict(X_test_s), lr.predict_proba(X_test_s)[:, 1]
            roc_lr = roc_auc_score(y_test, y_prob_lr)

            rf_fraud = RandomForestClassifier(n_estimators=100, max_depth=5, class_weight="balanced", random_state=42)
            rf_fraud.fit(X_train, y_train)
            y_pred_rf, y_prob_rf = rf_fraud.predict(X_test), rf_fraud.predict_proba(X_test)[:, 1]
            roc_rf = roc_auc_score(y_test, y_prob_rf)

            st.subheader("Model performance")
            metrics_table(["Logistic Regression", "Random Forest"], [roc_lr, roc_rf],
                           [y_test, y_test], [y_pred_lr, y_pred_rf])

            c1, c2 = st.columns(2)
            with c1:
                fig, ax = plt.subplots(figsize=(5, 4))
                fpr_lr, tpr_lr, _ = roc_curve(y_test, y_prob_lr)
                fpr_rf, tpr_rf, _ = roc_curve(y_test, y_prob_rf)
                ax.plot(fpr_lr, tpr_lr, label=f"LR (AUC {roc_lr:.3f})")
                ax.plot(fpr_rf, tpr_rf, label=f"RF (AUC {roc_rf:.3f})")
                ax.plot([0, 1], [0, 1], "k--", linewidth=0.7)
                ax.set_xlabel("FPR"); ax.set_ylabel("TPR"); ax.set_title("ROC Curve"); ax.legend()
                st.pyplot(fig)
            with c2:
                plot_confusion(confusion_matrix(y_test, y_pred_rf), "Random Forest — Confusion Matrix",
                                labels=("Legit", "Fraud"))

    elif model_choice.startswith("2."):
        loan_full, customers = d["loan_full"], tables["customers"]
        default_df = loan_full.merge(customers[["CUSTOMER_ID", "CREDIT_SCORE", "ANNUAL_INCOME"]], on="CUSTOMER_ID")
        default_df["tenure_days"] = default_df["tenure_days"].fillna(0)
        feature_cols = ["ANNUAL_INCOME", "CREDIT_SCORE", "tenure_days", "LOAN_AMOUNT", "INTEREST_RATE", "ever_late"]
        model_df = default_df[feature_cols + ["is_default"]].dropna()
        X, y = model_df.drop(columns="is_default"), model_df["is_default"]
        if y.nunique() < 2:
            st.error("Not enough class variety in is_default to train — check your data.")
        else:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
            scaler = StandardScaler()
            X_train_s, X_test_s = scaler.fit_transform(X_train), scaler.transform(X_test)

            lr = LogisticRegression().fit(X_train_s, y_train)
            y_pred_lr, y_prob_lr = lr.predict(X_test_s), lr.predict_proba(X_test_s)[:, 1]
            roc_lr = roc_auc_score(y_test, y_prob_lr)

            rf_default = RandomForestClassifier(n_estimators=200, max_depth=6, class_weight="balanced", random_state=42)
            rf_default.fit(X_train, y_train)
            y_pred_rf, y_prob_rf = rf_default.predict(X_test), rf_default.predict_proba(X_test)[:, 1]
            roc_rf = roc_auc_score(y_test, y_prob_rf)

            st.subheader("Model performance")
            metrics_table(["Logistic Regression", "Random Forest"], [roc_lr, roc_rf],
                           [y_test, y_test], [y_pred_lr, y_pred_rf])
            plot_confusion(confusion_matrix(y_test, y_pred_rf), "Random Forest — Confusion Matrix",
                            labels=("No Default", "Default"))

            importance = pd.Series(rf_default.feature_importances_, index=X.columns).sort_values(ascending=False)
            st.subheader("Feature importance (Random Forest)")
            st.bar_chart(importance)
            st.info(f"**Insight:** '{importance.index[0]}' is the strongest driver of default risk, "
                    f"contributing {importance.iloc[0]*100:.1f}% of the model's decision weight.")

    else:  # model 3
        loan_full, customers = d["loan_full"], tables["customers"]
        loan_payment = tables["loan_payment"]
        pay_stats = loan_payment.groupby("LOAN_ID").agg(
            payments_made=("PAYMENT_ID", "count"), late_payments=("LATE_PAYMENT_FLAG", "sum")
        ).reset_index()
        pay_stats["late_ratio"] = pay_stats["late_payments"] / pay_stats["payments_made"]

        p3_df = loan_full.merge(pay_stats, on="LOAN_ID", how="left")
        for c in ["payments_made", "late_payments", "late_ratio"]:
            p3_df[c] = p3_df[c].fillna(0)
        p3_df = p3_df.merge(customers[["CUSTOMER_ID", "CREDIT_SCORE"]], on="CUSTOMER_ID")

        feat_cols = ["CREDIT_SCORE", "LOAN_AMOUNT", "INTEREST_RATE", "payments_made", "late_ratio"]
        model_df = p3_df[feat_cols + ["ever_late"]].dropna()
        X, y = model_df.drop(columns="ever_late"), model_df["ever_late"]
        if y.nunique() < 2:
            st.error("Not enough class variety in ever_late to train — check your data.")
        else:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
            scaler = StandardScaler()
            X_train_s, X_test_s = scaler.fit_transform(X_train), scaler.transform(X_test)

            lr = LogisticRegression().fit(X_train_s, y_train)
            y_pred_lr, y_prob_lr = lr.predict(X_test_s), lr.predict_proba(X_test_s)[:, 1]
            roc_lr = roc_auc_score(y_test, y_prob_lr)

            rf_latepay = RandomForestClassifier(n_estimators=200, max_depth=6, class_weight="balanced", random_state=42)
            rf_latepay.fit(X_train, y_train)
            y_pred_rf, y_prob_rf = rf_latepay.predict(X_test), rf_latepay.predict_proba(X_test)[:, 1]
            roc_rf = roc_auc_score(y_test, y_prob_rf)

            st.subheader("Model performance")
            metrics_table(["Logistic Regression", "Random Forest"], [roc_lr, roc_rf],
                           [y_test, y_test], [y_pred_lr, y_pred_rf])
            plot_confusion(confusion_matrix(y_test, y_pred_rf), "Random Forest — Confusion Matrix",
                            labels=("On Time", "Late"))

            active_loans = p3_df[p3_df["STATUS"] == "Active"].copy()
            if len(active_loans):
                active_loans["late_risk_score"] = rf_latepay.predict_proba(active_loans[feat_cols].fillna(0))[:, 1]
                st.subheader("Top 10 highest-risk active loans")
                st.dataframe(
                    active_loans[["LOAN_ID", "CUSTOMER_ID", "late_risk_score"]]
                    .sort_values("late_risk_score", ascending=False).head(10),
                    use_container_width=True,
                )
else:
    st.info("Pick a model above and click **Train model** to run it on the loaded data.")
