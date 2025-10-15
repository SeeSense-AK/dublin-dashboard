"""
Spinovate Safety Dashboard
Main Streamlit application
"""
import streamlit as st
from src.tab1_hotspots import render_tab1

# Page config
st.set_page_config(
    page_title="Spinovate Safety Dashboard",
    page_icon="🚴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("Spinovate Safety Dashboard")
st.markdown("Road Safety Analysis for Dublin")

# Sidebar
st.sidebar.title("Navigation")
st.sidebar.markdown("Select analysis type below")

# Create tabs
tab1, tab2 = st.tabs(["Hotspot Analysis", "Trend Analysis"])

# Tab 1: Hotspot Analysis
with tab1:
    try:
        render_tab1()
    except Exception as e:
        st.error(f"Error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

# Tab 2: Trend Analysis (placeholder for now)
with tab2:
    st.header("Trend Analysis")
    st.info("Trend analysis will be implemented next")