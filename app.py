"""
Dublin Road Safety Dashboard - Main Application
"""
import streamlit as st
import sys
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent / "src"
sys.path.append(str(src_path))

from src.tab1_hotspots import render_tab1
from src.tab2_trends import render_tab2

# Page configuration
st.set_page_config(
    page_title="Dublin Road Safety Dashboard",
    page_icon="🚴‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Main header
st.title("Dublin Road Safety Dashboard")
st.markdown("Comprehensive analysis of cycling route safety and usage patterns in Dublin")

# Create tabs
tab1, tab2 = st.tabs(["Hotspot Analysis", "Trend Analysis"])

# Tab 1: Hotspot Analysis
with tab1:
    try:
        render_tab1()
    except Exception as e:
        st.error(f"Error in Tab 1: {e}")
        st.info("Please ensure all required data files are available in data/processed/")

# Tab 2: Trend Analysis  
with tab2:
    try:
        render_tab2()
    except Exception as e:
        st.error(f"Error in Tab 2: {e}")
        st.info("Please ensure trend data files are available in data/processed/tab2_trend/")

# Footer
st.markdown("---")
st.markdown("### About This Dashboard")

with st.expander("Technical Details"):
    st.markdown("""
    **Data Sources:**
    - Sensor-based abnormal event detection
    - Community perception reports
    - Cycling route usage patterns
    - Daily aggregated safety metrics
    
    **Analysis Methods:**
    - Spatial clustering for hotspot identification
    - Temporal trend analysis
    - Multi-layer data fusion
    - Grid-based aggregation (6m resolution)
    
    **Privacy:**
    - All location data is aggregated
    - Individual cyclist tracking is anonymized
    - Reports are processed to remove personal identifiers
    """)

with st.expander("Data Processing Pipeline"):
    st.markdown("""
    **Tab 1 - Hotspot Analysis:**
    1. Load preprocessed sensor hotspots, perception reports, and corridor data
    2. Apply date range filtering
    3. Select top hotspots using weighted distribution (50% sensor, 30% perception, 20% corridors)
    4. Combine data sources with color coding by severity
    5. Generate interactive map with detailed tooltips
    
    **Tab 2 - Trend Analysis:**
    1. Load daily aggregated data from Parquet files
    2. Filter by selected date and layer type
    3. Create spatial heatmaps on 6m grid
    4. Generate temporal trend visualizations
    5. Provide summary statistics and coverage metrics
    """)