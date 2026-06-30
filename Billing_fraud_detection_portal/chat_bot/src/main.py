import streamlit as st

app2 = st.Page("pages/app2.py",
              title="APP2",
              url_path="app-2")


group = {
    " ": [
        app2,
    ],
}

sidebar = st.navigation(group)
sidebar.run()
