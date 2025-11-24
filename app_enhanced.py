"""
Dublin Road Safety Dashboard - Enhanced Professional Version
AI-Powered Road Safety Analysis for Dublin
Power BI/Tableau-level professional styling
"""

import streamlit as st
import sys, os
from pathlib import Path

# ────────────────────────────────────────────────
# 1️⃣ MUST be the first Streamlit command
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="Spinovate Safety Dashboard",
    page_icon="🚴‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ────────────────────────────────────────────────
# 2️⃣ Load Professional CSS
# ────────────────────────────────────────────────
def load_professional_css():
    """Load the professional CSS styles"""
    css_file = Path("styles.css")
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    else:
        st.warning("Professional CSS file not found. Using default styling.")

# Load CSS immediately
load_professional_css()


# ────────────────────────────────────────────────
# 3️⃣ Professional Header Component
# ────────────────────────────────────────────────
def create_professional_header():
    """Create Power BI-style professional header"""
    st.markdown("""
    <div class="dashboard-header">
        <div class="header-title">Spinovate Safety Dashboard</div>
        <div class="header-subtitle">AI-Powered Road Safety Analysis for Dublin</div>
    </div>
    """, unsafe_allow_html=True)


# ────────────────────────────────────────────────
# 5️⃣ Robust import path setup (works local + cloud)
# ────────────────────────────────────────────────
try:
    app_dir = Path(__file__).resolve().parent
except NameError:
    app_dir = Path(os.getcwd()).resolve()

# normally src is beside app.py
src_path = app_dir / "src"
# sometimes Streamlit Cloud nests one level deeper
if not src_path.exists():
    src_path = app_dir.parent / "src"

if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

# ────────────────────────────────────────────────
# 6️⃣ Import ENHANCED tab modules safely
# ────────────────────────────────────────────────
try:
    from tab1_hotspots_enhanced import render_tab1_enhanced
    tab1_available = True
except ImportError as e:
    tab1_available = False
    st.warning(f"Enhanced Tab 1 module not found ({e}). Ensure tab1_hotspots_enhanced.py exists.")

try:
    from tab2_trends_enhanced import render_tab2_enhanced
    tab2_available = True
except ImportError as e:
    tab2_available = False
    st.warning(f"Enhanced Tab 2 module not found ({e}). Ensure tab2_trends_enhanced.py exists.")

# Fallback to original tabs if enhanced versions are not available
if not tab1_available:
    try:
        from tab1_hotspots import render_tab1
        tab1_available = True
        st.info("Using original Tab 1 - Enhanced version not available")
    except ImportError:
        tab1_available = False

if not tab2_available:
    try:
        from tab2_trends import render_tab2
        tab2_available = True
        st.info("Using original Tab 2 - Enhanced version not available")
    except ImportError:
        tab2_available = False

# ────────────────────────────────────────────────
# 7️⃣ Enhanced Main Layout
# ────────────────────────────────────────────────
def main():
    """Enhanced main application with professional styling"""
    
    # Professional Header
    create_professional_header()
    

    # Content Card Container
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    
    # ────────────────────────────────────────────────
    # 8️⃣ Tabs with ENHANCED functionality
    # ────────────────────────────────────────────────
    tab1, tab2 = st.tabs(["Hotspot Analysis", "Trend Analysis"])

    with tab1:
        if tab1_available:
            try:
                # Use enhanced tab 1 if available, otherwise fallback to original
                if 'render_tab1_enhanced' in globals():
                    render_tab1_enhanced()
                else:
                    render_tab1()
            except Exception as e:
                st.error(f"Error in Tab 1: {e}")
        else:
            st.info("Tab 1 (Hotspot Analysis) is not yet available.")

    with tab2:
        if tab2_available:
            try:
                # Use enhanced tab 2 if available, otherwise fallback to original
                if 'render_tab2_enhanced' in globals():
                    render_tab2_enhanced()
                else:
                    render_tab2()
            except Exception as e:
                st.error(f"Error in Tab 2: {e}")
        else:
            st.info("Tab 2 (Route Popularity) is not yet available.")
    
    # Close content card container
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ────────────────────────────────────────────────
    # 9️⃣ Footer / technical info (Enhanced styling)
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

# ────────────────────────────────────────────────
# 🔟 Run the application
# ────────────────────────────────────────────────
if __name__ == "__main__":
    main()