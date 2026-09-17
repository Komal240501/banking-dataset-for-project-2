"""
utils.py
Data loading + feature engineering shared across the Streamlit dashboard.
Mirrors the cleaning/derivation logic from the original banking_database_project notebook.
"""

import os
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

TABLE_FILES = {
    "customers": "customers.parquet",
    "branches": "branches.parquet",
    "employees": "employees.parquet",
    "accounts": "accounts.parquet",
    "cards": "cards.parquet",
    "loan": "loan.parquet",
    "loan_payment": "loan_payment.parquet",
    "transaction_list": "transaction_list.parquet",
    "card_transaction": "card_transaction.parquet",
    "support_ticket": "support_ticket.parquet",
}

DATE_COLS = {
    "accounts": ["OPEN_DATE"],
    "branches": ["OPENED_DATE"],
    "cards": ["ISSUE_DATE", "EXPIRY_DATE"],
    "customers": ["JOIN_DATE", "DATE_OF_BIRTH"],
    "employees": ["HIRE_DATE"],
    "loan": ["START_DATE"],
    "loan_payment": ["PAYMENT_DATE"],
    "transaction_list": ["TXN_DATE"],
    "card_transaction": ["TXN_DATE"],
    "support_ticket": ["DATE_OPENED", "DATE_RESOLVED"],
}


@st.cache_data(show_spinner=False)
def load_tables() -> dict[str, pd.DataFrame]:
    """
    Load all 10 tables from the bundled /data folder. Tables are stored as
    Parquet (snappy/brotli-compressed) instead of CSV — much smaller on disk,
    which is what keeps the two large event-level tables (transaction_list,
    card_transaction) under GitHub's file-size limits. See csv_to_parquet.py
    for how these files were produced.

    Columns are also downcast to smaller dtypes on load (int64 -> smallest
    int that fits, float64 -> float32, low-cardinality text -> category).
    This cuts in-memory size roughly 3x for the big event-level tables
    (card_transaction, transaction_list), which matters a lot on Streamlit
    Community Cloud's ~1GB memory limit.
    """
    tables = {}
    for name, filename in TABLE_FILES.items():
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {filename} in /data.")
        df = pd.read_parquet(path)
        df.columns = [c.strip().upper() for c in df.columns]

        date_cols = DATE_COLS.get(name, [])
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        for col in df.columns:
            if col in date_cols:
                continue
            dtype = df[col].dtype
            if dtype == "int64":
                df[col] = pd.to_numeric(df[col], downcast="integer")
            elif dtype == "float64":
                df[col] = df[col].astype("float32")
            elif dtype == "object" or pd.api.types.is_string_dtype(dtype):
                # Low-cardinality text (categories, statuses, channels, etc.)
                # stores far more compactly as a pandas category.
                if df[col].nunique() < max(1000, len(df) * 0.3):
                    df[col] = df[col].astype("category")

        tables[name] = df
    return tables


@st.cache_data(show_spinner=False)
def build_derived(_tables_hash, tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    Recreates every derived table used across the notebook's Descriptive / Diagnostic /
    Predictive sections: loan_full, card_txn, card_util, customer bands, etc.
    _tables_hash is a cheap cache-busting key (pass e.g. a tuple of row counts).
    """
    customers = tables["customers"].copy()
    branches = tables["branches"].copy()
    accounts = tables["accounts"].copy()
    cards = tables["cards"].copy()
    loan = tables["loan"].copy()
    loan_payment = tables["loan_payment"].copy()
    transaction_list = tables["transaction_list"].copy()
    card_transaction = tables["card_transaction"].copy()
    support_ticket = tables["support_ticket"].copy()

    today = pd.Timestamp(datetime.now().date())

    # ---- card_txn: card_transaction + card_type + txn_month --------------
    card_txn = card_transaction.merge(cards[["CARD_ID", "CARD_TYPE"]], on="CARD_ID", how="left")
    card_txn["TXN_DATE"] = pd.to_datetime(card_txn["TXN_DATE"], errors="coerce")
    card_txn["txn_month"] = card_txn["TXN_DATE"].dt.to_period("M").astype(str).astype("category")
    card_txn["days_since_txn"] = (today - card_txn["TXN_DATE"]).dt.days.astype("int32")

    # ---- loan_full: ever_late + is_default + tenure_band ------------------
    ever_late = (
        loan_payment.groupby("LOAN_ID")["LATE_PAYMENT_FLAG"].max().rename("ever_late").reset_index()
    )
    loan_full = loan.merge(ever_late, on="LOAN_ID", how="left")
    loan_full["ever_late"] = loan_full["ever_late"].fillna(0)
    loan_full["is_default"] = loan_full["STATUS"].isin(["Defaulted", "Written Off"]).astype(int)
    loan_full["tenure_days"] = (pd.Timestamp.today() - loan_full["START_DATE"]).dt.days
    loan_full["tenure_band"] = pd.cut(
        loan_full["tenure_days"],
        bins=[-1, 180, 365, 730, 1825, 10000],
        labels=["<6m", "6-12m", "1-2y", "2-5y", "5y+"],
    )

    # ---- customer income / credit bands + avg balance ---------------------
    customers = customers.copy()
    customers["income_band"] = pd.qcut(customers["ANNUAL_INCOME"], 4, labels=["Q1", "Q2", "Q3", "Q4"])
    customers["credit_band"] = pd.cut(
        customers["CREDIT_SCORE"], bins=[0, 600, 700, 800, 900],
        labels=["<600", "600-700", "700-800", "800+"],
    )
    cust_acc = accounts.groupby("CUSTOMER_ID")["BALANCE"].mean().reset_index()
    customers_with_balance = customers.merge(cust_acc, on="CUSTOMER_ID", how="left")

    # ---- card utilization ---------------------------------------------------
    card_spend = card_txn.groupby("CARD_ID")["AMOUNT"].sum().rename("total_spend").reset_index()
    card_util = cards.merge(card_spend, on="CARD_ID", how="left")
    card_util["total_spend"] = card_util["total_spend"].fillna(0)
    card_util["utilization_pct"] = np.where(
        card_util["CREDIT_LIMIT"] > 0,
        (card_util["total_spend"] / card_util["CREDIT_LIMIT"] * 100).round(2),
        np.nan,
    )
    card_util["fraud_on_card"] = card_util["CARD_ID"].isin(
        card_txn.loc[card_txn["IS_FRAUD"] == 1, "CARD_ID"]
    ).astype(int)
    card_util["util_band"] = pd.cut(
        card_util["utilization_pct"], bins=[0, 25, 50, 75, 300],
        labels=["0-25%", "25-50%", "50-75%", "75%+"],
    )

    # ---- transaction_list monthly ------------------------------------------
    transaction_list["TXN_DATE"] = pd.to_datetime(transaction_list["TXN_DATE"], errors="coerce")
    transaction_list["txn_month"] = transaction_list["TXN_DATE"].dt.to_period("M").astype(str).astype("category")

    # ---- support tickets: resolution days -----------------------------------
    support_ticket = support_ticket.copy()
    support_ticket["resolution_days"] = (
        support_ticket["DATE_RESOLVED"] - support_ticket["DATE_OPENED"]
    ).dt.days

    # ---- accounts: age band --------------------------------------------------
    accounts = accounts.copy()
    accounts["account_age_days"] = (today - pd.to_datetime(accounts["OPEN_DATE"])).dt.days
    accounts["account_age_band"] = pd.cut(
        accounts["account_age_days"], bins=[0, 365, 730, 3650],
        labels=["0-1yr", "1-2yr", "2yr+"],
    )

    return {
        "today": today,
        "card_txn": card_txn,
        "loan_full": loan_full,
        "customers": customers,
        "customers_with_balance": customers_with_balance,
        "card_util": card_util,
        "transaction_list": transaction_list,
        "support_ticket": support_ticket,
        "accounts": accounts,
        "branches": branches,
    }
