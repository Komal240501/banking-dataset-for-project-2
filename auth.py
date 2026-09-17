"""
auth.py
Simple username/password login gate for the Streamlit app.

Credentials live in .streamlit/secrets.toml (NOT committed to git), e.g.:

    [credentials]
    admin = "change-me-123"
    analyst = "another-password"

On Streamlit Community Cloud, set the same thing under
App settings -> Secrets (same TOML format) instead of a local file.

This is a lightweight gate suitable for keeping a dashboard private among a
small trusted team — it is NOT a substitute for real auth/identity provider
if you need audit logs, SSO, per-user roles, password reset, etc.
"""

import streamlit as st


def check_login() -> None:
    """
    Renders a login form and halts the script (st.stop()) until the user
    submits a username/password pair that matches st.secrets["credentials"].
    Call this as the very first thing in app.py, before any other UI.
    """
    if st.session_state.get("authenticated"):
        return

    st.set_page_config(page_title="Banking Analytics Dashboard — Login", page_icon="🔒")
    st.title("🔒 Banking Analytics Dashboard")
    st.caption("Please log in to continue.")

    try:
        credentials = dict(st.secrets["credentials"])
    except Exception:
        st.error(
            "No credentials configured. Add a `[credentials]` section to "
            "`.streamlit/secrets.toml` (locally) or to your app's Secrets "
            "(on Streamlit Cloud). See auth.py for the expected format."
        )
        st.stop()

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")

    if submitted:
        if username in credentials and password == credentials[username]:
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    st.stop()


def logout_button() -> None:
    """Renders a sidebar logout button. Call from app.py after check_login()."""
    with st.sidebar:
        st.caption(f"Logged in as **{st.session_state.get('username', 'user')}**")
        if st.button("Log out"):
            st.session_state["authenticated"] = False
            st.session_state.pop("username", None)
            st.rerun()
