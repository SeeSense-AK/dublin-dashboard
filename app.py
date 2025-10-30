"""
Dublin Road Safety Dashboard - Main Application
Lightweight main app with clean tab organization
"""
import streamlit as st
import sys, os
from pathlib import Path

# Fix for Streamlit Cloud import paths
os.chdir(os.path.dirname(__file__))

# Add src directory to path for imports
src_path = Path(__file__).parent / "src"
sys.path.append(str(src_path))


# Page configuration
st.set_page_config(
    page_title="Spinovate Safety Dashboard",
    page_icon="🚴‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Main header
st.title("Spinovate Safety Dashboard")
st.markdown("AI-Powered Road Safety Analysis for Dublin")

# Import tab modules
try:
    from src.tab1_hotspots import render_tab1
    tab1_available = True
except ImportError:
    tab1_available = False
    st.warning("Tab 1 module not found. Please ensure src/tab1_hotspots.py exists.")

try:
    from src.tab2_trends import render_tab2
    tab2_available = True
    # note: you had tab2_route_popularity in the comment — ensure naming matches your file
except ImportError:
    tab2_available = False
    st.warning("Tab 2 module not found. Please ensure src/tab2_trends.py exists.")

# Create tabs
tab1, tab2 = st.tabs(["Hotspot Analysis", "Route Popularity"])

# Tab 1
with tab1:
    if tab1_available:
        try:
            render_tab1()
        except Exception as e:
            st.error(f"Error in Tab 1: {e}")
    else:
        st.info("Tab 1 (Hotspot Analysis) is not yet available")

# Tab 2
with tab2:
    if tab2_available:
        try:
            render_tab2()
        except Exception as e:
            st.error(f"Error in Tab 2: {e}")
    else:
        st.info("Tab 2 (Route Popularity) is not yet available")

# Footer
st.markdown("---")
st.markdown("### About This Dashboard")

with st.expander("Technical Details"):
    st.markdown("""
    **Data Sources:**
    - Route popularity analysis from cycling trip data
    - Weather impact correlations
    - Performance trend analysis
    - Preprocessed route insights and summaries
    - Actual road segment geometry from GeoJSON
    
    **Analysis Methods:**
    - Real road segment visualization using MultiLineString geometry
    - Interactive folium-based mapping with actual street shapes
    - Performance classification (Green/Red status)
    - Comprehensive route analysis display
    
    **Features:**
    - Interactive map with actual road segment polylines
    - Route performance metrics and visualizations
    - Comprehensive analysis of preprocessed data
    - Professional interface design
    - Data validation between CSV and GeoJSON sources
    """)

with st.expander("Data Processing Pipeline"):
    st.markdown("""
    **Tab 2 - Route Popularity Trends:**
    1. Load preprocessed route popularity data from CSV file
    2. Load actual road segment geometry from GeoJSON file
    3. Match street names between CSV analysis data and GeoJSON geometry
    4. Create interactive map with color-coded MultiLineString polylines
    5. Display comprehensive route analysis and summaries
    6. Provide detailed breakdowns of weather impact and performance data
    7. Validate data consistency between sources
    """)
