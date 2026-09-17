"""
common.py
Shared boilerplate every page in the app calls first:
  1) enforce login (auth.check_login halts the script with a login form
     until the user is authenticated — this runs on EVERY page, not just
     Home, so a direct link to any page is also protected)
  2) set that page's tab title/icon
  3) show the sidebar logout button + branding
  4) load + cache the 10 source tables and derived tables

Every page file (Home and everything in /pages) should start with:

    from common import init_page, get_data
    tables_d = init_page("Page Title", "🏦")
    tables, d, row_hash = get_data()
"""

import streamlit as st

from auth import check_login, logout_button
from utils import load_tables, build_derived

APP_NAME = "Banking Analytics Suite"


def init_page(title: str, icon: str = "🏦") -> None:
    # Must run before any other Streamlit call. If not authenticated yet,
    # this renders the login form and st.stop()s the script right here —
    # nothing below it (on any page) ever executes for an unauthenticated user.
    check_login()

    st.set_page_config(page_title=f"{title} | {APP_NAME}", layout="wide", page_icon=icon)

    with st.sidebar:
        st.title("🏦 Banking Analytics Suite")
        st.caption(
            "10 linked tables: Customers · Accounts · Cards · Loans · Loan payments · "
            "Branches · Employees · Transactions · Card transactions · Support tickets"
        )
        st.markdown("---")
    logout_button()


def banner(title: str) -> None:
    """Pink/maroon title banner matching the original Power BI report style."""
    st.markdown(
        f"""
        <div style='background-color:#d98a8a;padding:16px 12px;border-radius:8px;
                    border:3px solid #7a1f2b;text-align:center;margin-bottom:14px;'>
            <span style='color:#4a0e14;font-style:italic;font-weight:800;
                         font-size:2rem;'>{title}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _row_counts(tables: dict) -> tuple:
    return tuple(len(df) for df in tables.values())


def get_data():
    """Loads + caches all source tables and derived tables. Call after init_page()."""
    try:
        tables = load_tables()
    except FileNotFoundError as e:
        st.error(str(e))
        st.info(
            "Put your Parquet exports in /data using the exact filenames "
            "listed in TABLE_FILES (utils.py)."
        )
        st.stop()

    row_hash = tuple(len(df) for df in tables.values())
    d = build_derived(row_hash, tables)
    return tables, d, row_hash
