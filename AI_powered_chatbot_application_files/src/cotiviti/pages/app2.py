import streamlit as st

st.set_page_config(
    page_title="Cotiviti Health Plan Ops Assistant",
    page_icon="🏥",
    layout="wide",
)

from assistant import config, ui
from assistant.database import load_claims

ui.inject_styles()
ui.render_header()

# Without a key the chatbot can't function — show setup help and halt.
if not config.API_KEY:
    ui.render_missing_key_error()
    st.stop()

# Load the dataset (seeds the SQLite DB on first run); fail gracefully.
try:
    df = load_claims()
except Exception as e:
    st.error(f"🚨 Failed to load claims data from the database: {e}", icon="🚨")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

ui.render_sidebar(df)

left_col, right_col = st.columns([1, 2])
with left_col:
    ui.render_dashboard(df)
with right_col:
    ui.render_chat()

ui.render_footer()