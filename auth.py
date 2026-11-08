import streamlit as st
from authlib.integrations.requests_client import OAuth2Session

AUTH0_DOMAIN = st.secrets["auth0"]["domain"]
CLIENT_ID = st.secrets["auth0"]["client_id"]
CLIENT_SECRET = st.secrets["auth0"]["client_secret"]
REDIRECT_URI = st.secrets["auth0"]["redirect_uri"]

AUTHORIZATION_URL = f"https://{AUTH0_DOMAIN}/authorize"
TOKEN_URL = f"https://{AUTH0_DOMAIN}/oauth/token"
USERINFO_URL = f"https://{AUTH0_DOMAIN}/userinfo"
LOGOUT_URL = f"https://{AUTH0_DOMAIN}/v2/logout"


def get_login_url():
    session = OAuth2Session(
        CLIENT_ID, CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope="openid profile email"
    )
    uri, state = session.create_authorization_url(AUTHORIZATION_URL)
    return uri


def get_logout_url():
    return f"{LOGOUT_URL}?client_id={CLIENT_ID}&returnTo={REDIRECT_URI}"


def _exchange_code_for_user(code):
    session = OAuth2Session(CLIENT_ID, CLIENT_SECRET, redirect_uri=REDIRECT_URI)
    session.fetch_token(TOKEN_URL, code=code)
    response = session.get(USERINFO_URL)
    return response.json()


def get_current_user():
    """
    Returns the logged-in user's info dict if authenticated, else None.
    Handles the redirect back from Auth0 automatically.
    """
    if "user" in st.session_state:
        return st.session_state["user"]

    code = st.query_params.get("code")
    if code:
        try:
            user_info = _exchange_code_for_user(code)
            st.session_state["user"] = user_info
            st.query_params.clear()
            st.rerun()
        except Exception as exc:
            st.error(f"Login failed: {exc}")

    return None


def logout():
    st.session_state.pop("user", None)
