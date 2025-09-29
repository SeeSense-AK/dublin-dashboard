"""
Dublin Road Safety Dashboard
Main Streamlit application
"""
import streamlit as st
from config import DASHBOARD_CONFIG

# Configure page
st.set_page_config(
    page_title=DASHBOARD_CONFIG["title"],
    page_icon=DASHBOARD_CONFIG["page_icon"],
    layout=DASHBOARD_CONFIG["layout"],
    initial_sidebar_state=DASHBOARD_CONFIG["initial_sidebar_state"]
)

st.title("🚗 Dublin Road Safety Dashboard")
st.markdown("### Comprehensive Road Safety Analysis")

st.info("Dashboard under construction. Core modules coming soon!")

# TODO: Implement tabs and functionality
