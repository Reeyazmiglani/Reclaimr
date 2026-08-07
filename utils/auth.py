"""Self-service login for Reclaimr, with persistent (cookie-backed) sessions.

Anyone can sign up, but new accounts sit unapproved until the owner (the
first person to ever sign up) approves them from Settings. Every page must
call require_auth() at import time (not just inside the render function) —
Streamlit serves numbered pages/ files directly by URL, bypassing app.py
entirely, so a check only in app.py can be walked around by navigating
straight to a page.

Session persistence uses streamlit-authenticator's own cookie mechanism
(it wraps the browser's cookie storage + a signed/expiring token) rather
than a custom one — see get_authenticator() for the cookie_name / cookie_key
/ cookie_expiry_days wiring. The password hashes and cookie signing key
never leave this DB/`.env` pair, both of which are gitignored.
"""
import os
import bcrypt
import streamlit as st
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.exceptions import LoginError

COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "reclaimr_auth")
COOKIE_EXPIRY_DAYS = 30


def _cookie_key() -> str:
    key = os.getenv("AUTH_COOKIE_KEY")
    if not key:
        raise RuntimeError(
            "AUTH_COOKIE_KEY is not set. Add a strong random secret to your .env, e.g.:\n"
            '  python -c "import secrets; print(secrets.token_hex(32))"\n'
            "then AUTH_COOKIE_KEY=<that value> in .env (never commit it)."
        )
    return key


def _ensure_users_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            approved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
        """
    )
    conn.commit()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_user(conn, name: str, username: str, password: str):
    _ensure_users_table(conn)
    username = username.strip().lower()
    if not name.strip() or not username or not password:
        return False, "Fill in all fields."
    if conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
        return False, "That username is already taken."
    is_first = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    role = "owner" if is_first else "member"
    approved = 1 if is_first else 0
    conn.execute(
        "INSERT INTO users (name, username, password_hash, role, approved) VALUES (?,?,?,?,?)",
        (name.strip(), username, hash_password(password), role, approved),
    )
    conn.commit()
    if is_first:
        return True, "Account created — you're the owner. You can log in now."
    return True, "Account created — an owner needs to approve you before you can log in."


def get_pending_users(conn):
    _ensure_users_table(conn)
    return conn.execute(
        "SELECT id, name, username, created_at FROM users WHERE approved=0 ORDER BY created_at"
    ).fetchall()


def get_all_users(conn):
    _ensure_users_table(conn)
    return conn.execute(
        "SELECT id, name, username, role, approved, created_at FROM users ORDER BY created_at"
    ).fetchall()


def approve_user(conn, user_id: int):
    conn.execute("UPDATE users SET approved=1 WHERE id=?", (user_id,))
    conn.commit()


def remove_user(conn, user_id: int):
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()


def _build_credentials(conn):
    """Only approved users are logins-eligible; a stale cookie for someone
    who was removed or un-approved since simply won't match here."""
    _ensure_users_table(conn)
    rows = conn.execute(
        "SELECT username, name, password_hash FROM users WHERE approved=1"
    ).fetchall()
    return {
        "usernames": {
            r["username"]: {"name": r["name"], "password": r["password_hash"], "email": ""}
            for r in rows
        }
    }


def get_authenticator(conn):
    """A fresh Authenticate bound to the current DB state. Cheap — building
    the credentials dict is one indexed query — and must be rebuilt every
    run so approvals/removals take effect immediately instead of only
    after the 30-day cookie expires."""
    return stauth.Authenticate(
        _build_credentials(conn),
        cookie_name=COOKIE_NAME,
        cookie_key=_cookie_key(),
        cookie_expiry_days=COOKIE_EXPIRY_DAYS,
        auto_hash=False,  # our password_hash values are already bcrypt hashes
    )


def _sync_session_user(conn):
    """Once streamlit-authenticator confirms authentication_status, pull the
    full row (id/role/approved) so the rest of the app can use it."""
    if st.session_state.get("authentication_status"):
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND approved=1",
            (st.session_state.get("username"),),
        ).fetchone()
        if row:
            st.session_state["auth_user"] = dict(row)
            return dict(row)
    st.session_state.pop("auth_user", None)
    return None


def render_login_signup(conn):
    """Full login/signup screen. Call from app.py when nobody is logged in,
    after restore_session(conn) has already run — reuses the Authenticate
    instance it cached rather than constructing a second one (its cookie
    component errors on a duplicate key if instantiated twice per run)."""
    _ensure_users_table(conn)
    st.title("Reclaimr")
    st.caption("Log in or create an account to continue. Logging in keeps you "
               f"signed in on this device for {COOKIE_EXPIRY_DAYS} days.")
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        authenticator = st.session_state.get("_authenticator") or get_authenticator(conn)
        try:
            authenticator.login(location="main", key="reclaimr_login_form")
        except LoginError as e:
            st.error(str(e))
        status = st.session_state.get("authentication_status")
        if status is False:
            st.error("Incorrect username or password.")
        elif status:
            _sync_session_user(conn)
            st.rerun()

    with tab_signup:
        st.caption("New accounts need approval from the owner before they can log in "
                    "(the very first account created becomes the owner automatically).")
        with st.form("signup_form"):
            name = st.text_input("Full name")
            su = st.text_input("Choose a username")
            sp = st.text_input("Choose a password", type="password")
            sp2 = st.text_input("Confirm password", type="password")
            signup = st.form_submit_button("Sign up")
        if signup:
            if sp != sp2:
                st.error("Passwords don't match.")
            elif len(sp) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                ok, msg = create_user(conn, name, su, sp)
                (st.success if ok else st.error)(msg)


def restore_session(conn):
    """Silently restores a persistent session from the streamlit-authenticator
    cookie if one is present and still valid (unexpired, names an approved
    user). Returns the user dict, or None if nobody is logged in. Never
    stops the script — callers decide what to do about a None result."""
    authenticator = get_authenticator(conn)
    if not st.session_state.get("authentication_status"):
        try:
            authenticator.login(location="unrendered")
        except LoginError:
            # Cookie names a user who is no longer approved/exists — treat as logged out.
            authenticator.cookie_controller.delete_cookie()
            st.session_state["authentication_status"] = None
    st.session_state["_authenticator"] = authenticator
    return _sync_session_user(conn)


def require_auth(conn):
    """Call at module top level in every page. Restores a persistent session
    from the cookie if present, then blocks rendering and sends
    unauthenticated / no-longer-approved visitors back to the login screen."""
    user = restore_session(conn)
    if not user:
        st.warning("🔒 Please log in to view this page.")
        if st.button("Go to login"):
            st.switch_page("app.py")
        st.stop()
    return user


def render_logout_button():
    user = st.session_state.get("auth_user")
    if not user:
        return
    st.sidebar.markdown(f"👤 **{user['name']}**  \n`{user['role']}`")
    authenticator = st.session_state.get("_authenticator")
    if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True):
        if authenticator is not None:
            # Explicitly clears the persistent cookie, not just session_state,
            # so reopening the browser afterwards does NOT log the user back in.
            authenticator.authentication_controller.logout()
            authenticator.cookie_controller.delete_cookie()
        st.session_state.pop("auth_user", None)
        st.switch_page("app.py")
