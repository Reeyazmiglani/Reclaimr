"""Self-service login for Reclaimr.

Anyone can sign up, but new accounts sit unapproved until the owner
(the first person to ever sign up) approves them from Settings. Every
page must call require_auth() at import time (not just inside the
render function) — Streamlit serves numbered pages/ files directly by
URL, bypassing app.py entirely, so a check only in app.py can be
walked around by navigating straight to a page.
"""
import bcrypt
import streamlit as st


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


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


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


def authenticate(conn, username: str, password: str):
    _ensure_users_table(conn)
    row = conn.execute(
        "SELECT * FROM users WHERE username=?", (username.strip().lower(),)
    ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None, "Incorrect username or password."
    if not row["approved"]:
        return None, "Your account is waiting for owner approval."
    return dict(row), None


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


def render_login_signup(conn):
    """Full login/signup screen. Call from app.py when nobody is logged in."""
    _ensure_users_table(conn)
    st.title("Reclaimr")
    st.caption("Log in or create an account to continue.")
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            go = st.form_submit_button("Log in")
        if go:
            user, err = authenticate(conn, u, p)
            if err:
                st.error(err)
            else:
                st.session_state["auth_user"] = user
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


def require_auth(conn=None):
    """Call at module top level in every page. Blocks rendering and sends
    unauthenticated / no-longer-approved visitors back to the login screen."""
    user = st.session_state.get("auth_user")
    if user and conn is not None:
        _ensure_users_table(conn)
        row = conn.execute(
            "SELECT * FROM users WHERE id=? AND username=?", (user["id"], user["username"])
        ).fetchone()
        if not row or not row["approved"]:
            user = None
            st.session_state.pop("auth_user", None)
        elif dict(row) != user:
            st.session_state["auth_user"] = user = dict(row)

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
    if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True):
        st.session_state.pop("auth_user", None)
        st.switch_page("app.py")
