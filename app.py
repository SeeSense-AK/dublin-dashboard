"""
Dublin Road Safety Dashboard - Main Application
Lightweight main app with clean tab organization
"""

import streamlit as st
import sys
from pathlib import Path

# --- Ultimate cross-platform import fix ---
# Works even if __file__ is blank or Streamlit clones into a subfolder
cwd = Path(os.getcwd()).resolve()
possible_srcs = [
    cwd / "src",
    cwd.parent / "src",
    Path("/mount/src/src"),  # Streamlit Cloud fallback
]

for src in possible_srcs:
    if src.exists() and str(src) not in sys.path:
        sys.path.append(str(src))
        st.write(f"✅ Added to sys.path: {src}")
        break
else:
    st.error("❌ Could not locate 'src' folder. Check repository layout.")

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

# ────────────────────────────────────────────────
# 3️⃣ Import tab modules safely
# ────────────────────────────────────────────────
try:
    from tab1_hotspots import render_tab1
    tab1_available = True
except ImportError as e:
    tab1_available = False
    st.warning(f"⚠️ Tab 1 module not found ({e}). Ensure src/tab1_hotspots.py exists.")

try:
    from tab2_trends import render_tab2
    tab2_available = True
except ImportError as e:
    tab2_available = False
    st.warning(f"⚠️ Tab 2 module not found ({e}). Ensure src/tab2_trends.py exists.")

# ────────────────────────────────────────────────
# 4️⃣ Page header
# ────────────────────────────────────────────────
st.title("Spinovate Safety Dashboard")
st.markdown("AI-Powered Road Safety Analysis for Dublin")

# ────────────────────────────────────────────────
# 5️⃣ Tabs
# ────────────────────────────────────────────────
tab1, tab2 = st.tabs(["Hotspot Analysis", "Route Popularity Trends"])

with tab1:
    if tab1_available:
        try:
            render_tab1()
        except Exception as e:
            st.error(f"❌ Error in Tab 1: {e}")
    else:
        st.info("Tab 1 (Hotspot Analysis) is not yet available.")

with tab2:
    if tab2_available:
        try:
            render_tab2()
        except Exception as e:
            st.error(f"❌ Error in Tab 2: {e}")
    else:
        st.info("Tab 2 (Route Popularity) is not yet available.")

# ────────────────────────────────────────────────
# 6️⃣ Footer / technical info
# ────────────────────────────────────────────────
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
    - Interactive map with road segment polylines  
    - Route performance metrics and visualizations  
    - Comprehensive analysis of preprocessed data  
    - Data validation between CSV and GeoJSON sources  
    """)

with st.expander("Data Processing Pipeline"):
    st.markdown("""
    **Tab 2 – Route Popularity Trends:**
    1. Load preprocessed route popularity data from CSV file  
    2. Load road segment geometry from GeoJSON  
    3. Match street names between analysis and geometry  
    4. Create interactive color-coded map  
    5. Display comprehensive route summaries  
    6. Provide weather-impact breakdowns  
    7. Validate data consistency between sources  
    """)
