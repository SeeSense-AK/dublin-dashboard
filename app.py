"""
Dublin Road Safety Dashboard - Main Application
AI-Powered Road Safety Analysis for Dublin
Professional Visual Design Implementation
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
# 2️⃣ Professional CSS Styling System
# ────────────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    /* Global background with gradient */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        background-attachment: fixed;
    }

    /* Main content area with glassmorphism */
    .main .block-container {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
        padding: 2rem !important;
        margin-top: 2rem !important;
        margin-bottom: 2rem !important;
    }

    /* Professional header styling */
    .dashboard-header {
        background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
        border-radius: 20px;
        padding: 2.5rem 3rem;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(66, 153, 225, 0.3);
        position: relative;
        overflow: hidden;
    }

    .dashboard-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 300px;
        height: 300px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 50%;
        animation: float 6s ease-in-out infinite;
    }

    .dashboard-header h1 {
        color: white !important;
        font-weight: 700 !important;
        font-size: 3rem !important;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        margin: 0 !important;
        position: relative;
        z-index: 1;
    }

    .dashboard-header .subtitle {
        color: rgba(255, 255, 255, 0.9) !important;
        font-size: 1.3rem !important;
        font-weight: 400 !important;
        margin-top: 0.5rem !important;
        position: relative;
        z-index: 1;
    }

    .bike-icon {
        display: inline-block;
        animation: float 3s ease-in-out infinite;
        margin-right: 1rem;
        font-size: 3.5rem !important;
    }

    /* Modern tab styling */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 0.5rem;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
    }

    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        padding: 1rem 2rem !important;
        transition: all 0.3s ease;
        font-weight: 600;
        border: none !important;
        color: rgba(255, 255, 255, 0.7) !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%) !important;
        color: white !important;
        box-shadow: 0 4px 15px rgba(66, 153, 225, 0.4);
        transform: translateY(-2px);
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.3) !important;
        transform: translateY(-1px);
    }

    .stTabs [aria-selected="true"]:hover {
        background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%) !important;
        box-shadow: 0 6px 20px rgba(66, 153, 225, 0.5);
    }

    /* Professional card styling */
    .metric-card {
        background: linear-gradient(135deg, #ffffff 0%, #f7fafc 100%);
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        border: 1px solid rgba(66, 153, 225, 0.1);
    }

    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
    }

    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(66, 153, 225, 0.3);
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 25px rgba(66, 153, 225, 0.4);
        background: linear-gradient(135deg, #3182ce 0%, #2c5282 100%);
    }

    /* Alert styling */
    .element-container:has([data-testid="stAlert"]) {
        border-radius: 15px;
        overflow: hidden;
    }

    /* Success alerts */
    [data-testid="stAlert"]:has([data-testid="stAlertStatusIcon"]) {
        background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
        color: white;
    }

    /* Error alerts */
    .element-container:has(.stAlert[data-baseweb="alert"][data-theme="error"]) {
        background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
        color: white;
    }

    /* Warning alerts */
    .element-container:has(.stAlert[data-baseweb="alert"][data-theme="warning"]) {
        background: linear-gradient(135deg, #ed8936 0%, #dd6b20 100%);
        color: white;
    }

    /* Info alerts */
    .element-container:has(.stAlert[data-baseweb="alert"][data-theme="info"]) {
        background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
        color: white;
    }

    /* Professional footer */
    .dashboard-footer {
        background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
        border-radius: 20px;
        padding: 2rem;
        margin-top: 2rem;
        color: white;
    }

    .dashboard-footer h3 {
        color: white !important;
        font-weight: 600 !important;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }

    .streamlit-expanderContent {
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 0 0 10px 10px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-top: none !important;
    }

    /* Sidebar styling */
    .css-1d391kg {
        background: rgba(255, 255, 255, 0.95) !important;
        backdrop-filter: blur(10px) !important;
        border-right: 1px solid rgba(66, 153, 225, 0.1) !important;
    }

    /* Animations */
    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-20px); }
        100% { transform: translateY(0px); }
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .fade-in {
        animation: fadeIn 0.6s ease-out;
    }

    /* Responsive design */
    @media (max-width: 768px) {
        .dashboard-header h1 {
            font-size: 2rem !important;
        }

        .dashboard-header {
            padding: 1.5rem !important;
        }

        .main .block-container {
            padding: 1rem !important;
        }

        .stTabs [data-baseweb="tab"] {
            padding: 0.75rem 1rem !important;
            font-size: 0.9rem !important;
        }
    }

    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }

    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb {
        background: rgba(66, 153, 225, 0.5);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: rgba(66, 153, 225, 0.7);
    }
    </style>
    """, unsafe_allow_html=True)

# Inject the CSS
inject_css()

# ────────────────────────────────────────────────
# 3️⃣ Robust import path setup (works local + cloud)
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
# 4️⃣ Import tab modules safely
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
# 5️⃣ Professional Page Header
# ────────────────────────────────────────────────
st.markdown("""
<div class="dashboard-header fade-in">
    <h1><span class="bike-icon">🚴‍♂️</span>Spinovate Safety Dashboard</h1>
    <div class="subtitle">AI-Powered Road Safety Analysis for Dublin</div>
</div>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
# 6️⃣ Modern Tabs with Professional Styling
# ────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🔥 Hotspot Analysis", "📊 Route Popularity Trends"])

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
# 7️⃣ Professional Footer Section
# ────────────────────────────────────────────────
st.markdown("""
<div class="dashboard-footer">
    <h3>🎯 About This Dashboard</h3>
    <p style="margin-bottom: 1rem;">Advanced AI-powered analytics platform providing comprehensive insights into Dublin's cycling safety patterns and route performance metrics.</p>
</div>
""", unsafe_allow_html=True)

# Professional Technical Details
with st.expander("🔧 Technical Architecture", expanded=False):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **📊 Data Sources:**
        - Advanced cycling analytics data
        - Weather correlation metrics
        - Performance trend analysis
        - AI-generated safety insights
        - Real-time sensor processing

        **🤖 AI Capabilities:**
        - Google Gemini 2.0 integration
        - Smart hotspot detection
        - Predictive safety scoring
        - Automated report generation
        """)

    with col2:
        st.markdown("""
        **🗺️ Analysis Methods:**
        - Interactive geospatial mapping
        - Real-time data visualization
        - Multi-layered safety scoring
        - Advanced clustering algorithms
        - Route optimization analytics

        **⚡ Key Features:**
        - Live dashboard updates
        - Customizable safety metrics
        - Export capabilities
        - Responsive design
        """)

with st.expander("📈 Data Processing Pipeline", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        **🔥 Tab 1 – Hotspot Analysis:**
        1. AI-powered safety detection
        2. Multi-source data integration
        3. Smart urgency scoring
        4. Interactive hotspot mapping
        5. Real-time insights generation
        """)

    with col2:
        st.markdown("""
        **📊 Tab 2 – Route Trends:**
        1. Route popularity analysis
        2. Weather impact correlation
        3. Performance classification
        4. Trend visualization
        5. Comparative analytics
        """)

    with col3:
        st.markdown("""
        **🚀 Processing Pipeline:**
        1. Automated data ingestion
        2. Real-time validation
        3. Intelligent data fusion
        4. Advanced analytics engine
        5. Performance optimization
        """)
