"""
Dublin Road Safety Dashboard - Enhanced Professional Version
AI-Powered Road Safety Analysis for Dublin
Power BI/Tableau-level professional styling
"""

import streamlit as st
import sys, os
from pathlib import Path
import pandas as pd
import streamlit_authenticator as stauth

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
# Import Tab 1 - Hotspot Analysis
try:
    from tab1_hotspots_enhanced import render_tab1_enhanced
    tab1_available = True
except ImportError as e:
    tab1_available = False
    st.warning(f"Enhanced Tab 1 module not found ({e}). Ensure tab1_hotspots_enhanced.py exists.")

# Import Tab 2 - Abnormal Events
try:
    from tab2_abnormal_events import render_tab2
    tab2_available = True
except ImportError as e:
    tab2_available = False
    st.warning(f"Tab 2 module not found ({e}). Ensure tab2_abnormal_events.py exists.")

# Import Tab 3 - Route Popularity
try:
    from tab3_route_popularity import render_tab3
    tab3_available = True
except ImportError as e:
    tab3_available = False
    st.warning(f"Tab 3 module not found ({e}). Ensure tab3_route_popularity.py exists.")

# Fallback to original tab1 if enhanced version is not available
if not tab1_available:
    try:
        from tab1_hotspots import render_tab1
        tab1_available = True
        st.info("Using original Tab 1 - Enhanced version not available")
    except ImportError:
        tab1_available = False

# ────────────────────────────────────────────────
# 6.5️⃣ Import Report Generator and AI
# ────────────────────────────────────────────────
try:
    from src.report_generator import generate_pdf_report
    from src.tab1_hotspots_enhanced import load_preprocessed_data
    from src.tab3_route_popularity import load_route_popularity_data
    from src.ai_insights import generate_hotspot_insights, extract_user_comments, generate_route_insights
    report_gen_available = True
except ImportError as e:
    report_gen_available = False
    # st.warning(f"Report generator not available: {e}")


# ────────────────────────────────────────────────
# 7️⃣ Enhanced Main Layout
# ────────────────────────────────────────────────
def main():
    """Enhanced main application with professional styling"""
    
    # Professional Header
    create_professional_header()
    
    # ────────────────────────────────────────────────
    # Sidebar - Logo & Report Generation
    # ────────────────────────────────────────────────
    
    # Display Logo
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        st.sidebar.image(str(logo_path), use_column_width=True)
        st.sidebar.markdown("---")
    
    if report_gen_available:
        st.sidebar.title("Actions")
        
        # Create a container for the report generation to keep it distinct
        with st.sidebar.container():
            st.markdown("""
            <div style="background-color: #f0f9ff; padding: 15px; border-radius: 10px; border: 1px solid #bae6fd; margin-bottom: 20px;">
                <h4 style="margin-top: 0; color: #0369a1;">Detailed Report</h4>
                <p style="font-size: 0.9em; color: #555;">Generate a detailed PDF report of all dashboard insights.</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.sidebar.button("Generate Report", type="primary", use_container_width=True):
                # Create a progress bar
                progress_bar = st.sidebar.progress(0)
                status_text = st.sidebar.empty()
                
                def update_progress(msg):
                    status_text.text(msg)
                    # Increment progress slightly (simulated)
                    if progress_bar:
                        try:
                            curr = progress_bar.progress
                            # This is tricky because we don't know total steps easily, 
                            # so we'll just let the user know it's working
                        except:
                            pass

                with st.spinner("Generating professional report with AI analysis..."):
                    try:
                        # Load data
                        status_text.text("Loading data...")
                        # UPDATED: Unpack 3 values instead of 4
                        top_30_df, corridor_df, abnormal_events_df = load_preprocessed_data()
                        
                        # Prepare data for report generator (Map Top 30 to Sensor format)
                        sensor_df = top_30_df.copy()
                        if not sensor_df.empty:
                            # Map nested JSON fields to expected column names
                            sensor_df['concern_score'] = sensor_df.get('scores.composite_score', 0)
                            sensor_df['street_name'] = sensor_df.get('identification.street_name', 'Unknown')
                            sensor_df['event_type'] = sensor_df.get('sensor_data.event_type', 'N/A')
                            sensor_df['device_count'] = sensor_df.get('sensor_data.device_count', 0)
                        
                        perception_df = pd.DataFrame() # Perception is now integrated into Top 30 or Corridors
                        
                        route_df = load_route_popularity_data()
                        progress_bar.progress(20)
                        
                        # Generate PDF
                        # We pass a lambda to update progress bar roughly
                        step_counter = {'val': 20}
                        def progress_wrapper(msg):
                            step_counter['val'] = min(step_counter['val'] + 5, 95)
                            progress_bar.progress(step_counter['val'])
                            status_text.text(msg)
                            
                        pdf_bytes = generate_pdf_report(
                            sensor_df, perception_df, corridor_df, route_df, abnormal_events_df,
                            ai_hotspot_func=generate_hotspot_insights,
                            ai_route_func=generate_route_insights,
                            user_comments_func=extract_user_comments,
                            progress_callback=progress_wrapper
                        )
                        
                        progress_bar.progress(100)
                        status_text.text("Report ready!")
                        
                        # Offer download
                        st.sidebar.download_button(
                            label="📥 Download PDF Report",
                            data=pdf_bytes,
                            file_name="spinovate_safety_report.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                        st.sidebar.success("Report generated successfully!")
                        
                    except Exception as e:
                        st.sidebar.error(f"Error generating report: {str(e)}")
                        import traceback
                        st.sidebar.code(traceback.format_exc())
        
        st.sidebar.markdown("---")

    # Content Card Container
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    
    # ────────────────────────────────────────────────
    # 8️⃣ Tabs with ENHANCED functionality
    # ────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["Hotspot Analysis", "Abnormal Events", "Change in Route Popularity"])

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
                render_tab2()
            except Exception as e:
                st.error(f"Error in Tab 2: {e}")
        else:
            st.info("Tab 2 (Abnormal Events) is not yet available.")
    
    with tab3:
        if tab3_available:
            try:
                render_tab3()
            except Exception as e:
                st.error(f"Error in Tab 3: {e}")
        else:
            st.info("Tab 3 (Route Popularity) is not yet available.")
    
    # Chrome map rendering fix - detects when map becomes visible and triggers resize
    st.markdown("""
    <script>
    // Fix for Chrome map rendering in hidden Streamlit tabs
    document.addEventListener('DOMContentLoaded', function() {
        console.log('[Map Fix] Initializing Chrome map rendering fix...');
        
        // Listen for tab changes
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    // Check if any folium map container became visible
                    const mapContainers = document.querySelectorAll('.folium-map');
                    mapContainers.forEach(function(mapContainer) {
                        if (mapContainer.offsetParent !== null && !mapContainer.dataset.fixed) {
                            console.log('[Map Fix] Found visible map container, fixing...');
                            mapContainer.dataset.fixed = 'true';
                            
                            // Force map resize after a delay
                            setTimeout(function() {
                                const iframe = mapContainer.querySelector('iframe');
                                if (iframe && iframe.contentWindow) {
                                    try {
                                        iframe.contentWindow.postMessage('invalidateSize', '*');
                                    } catch(e) {
                                        console.log('[Map Fix] Could not post message to iframe');
                                    }
                                }
                                // Trigger window resize which Leaflet responds to
                                window.dispatchEvent(new Event('resize'));
                            }, 500);
                        }
                    });
                }
            });
        });
        
        // Start observing the document
        observer.observe(document.body, { childList: true, subtree: true });
        
        // Also check on visibility change
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) {
                setTimeout(function() {
                    window.dispatchEvent(new Event('resize'));
                }, 300);
            }
        });
        
        console.log('[Map Fix] Observer initialized');
    });
    </script>
    """, unsafe_allow_html=True)
    
    # Close content card container
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ────────────────────────────────────────────────
    # Logout button at the bottom of sidebar
    # ────────────────────────────────────────────────
    if 'authenticator' in st.session_state:
        st.sidebar.markdown("---")
        st.session_state['authenticator'].logout('Logout', 'sidebar', key='logout_button')
    
    # ────────────────────────────────────────────────
    # 9️⃣ Footer / technical info (Enhanced styling)
    # ────────────────────────────────────────────────
    # st.markdown("---")
    # st.markdown("### About This Dashboard")

    # with st.expander("Technical Details"):
    #     st.markdown("""
    #     **Data Sources:**
    #     - Route popularity analysis from cycling trip data  
    #     - Weather impact correlations  
    #     - Performance trend analysis  
    #     - Preprocessed route insights and summaries  
    #     - Actual road segment geometry from GeoJSON  

    #     **Analysis Methods:**
    #     - Real road segment visualization using MultiLineString geometry  
    #     - Interactive folium-based mapping with actual street shapes  
    #     - Performance classification (Green/Red status)  
    #     - Comprehensive route analysis display  

    #     **Features:**
    #     - Interactive map with road segment polylines  
    #     - Route performance metrics and visualizations  
    #     - Comprehensive analysis of preprocessed data  
    #     - Data validation between CSV and GeoJSON sources  
    #     """)

    # with st.expander("Data Processing Pipeline"):
    #     st.markdown("""
    #     **Tab 2 – Route Popularity Trends:**
    #     1. Load preprocessed route popularity data from CSV file  
    #     2. Load road segment geometry from GeoJSON  
    #     3. Match street names between analysis and geometry  
    #     4. Create interactive color-coded map  
    #     5. Display comprehensive route summaries  
    #     6. Provide weather-impact breakdowns  
    #     7. Validate data consistency between sources  
    #     """)

# ────────────────────────────────────────────────
# 🔟 Authentication and Run the application
# ────────────────────────────────────────────────
if __name__ == "__main__":
    # Configure authenticator from secrets
    import copy
    credentials = {'usernames': {}}
    for username, user_data in st.secrets["credentials"]["usernames"].items():
        credentials['usernames'][username] = dict(user_data)
    
    authenticator = stauth.Authenticate(
        credentials,
        st.secrets["credentials"]["cookie_name"],
        st.secrets["credentials"]["cookie_key"],
        st.secrets["credentials"]["cookie_expiry_days"]
    )
    
    
    # Check if we are already authenticated via session state (persisting from previous run)
    if st.session_state.get("authentication_status"):
        # ────────────────────────────────────────────────
        # LOGGED IN STATE
        # ────────────────────────────────────────────────
        st.session_state['authenticator'] = authenticator
        main()
        
        # Add Footer to Main Page (Bottom)
        st.markdown("---")
        st.markdown(
            """
            <div style="text-align: center; color: #666; font-size: 0.8em; padding-bottom: 2rem;">
                © See.Sense 2025 (All rights reserved)
            </div>
            """, 
            unsafe_allow_html=True
        )
        
    else:
        # ────────────────────────────────────────────────
        # LOGIN STATE (Unauthenticated)
        # ────────────────────────────────────────────────
        
        # 1. Styles
        st.markdown("""
        <style>
            header {visibility: hidden;}
            footer {visibility: hidden;}
            [data-testid="stSidebar"] {display: none;}
            
            .stApp {
                background-color: #f8fafc;
            }
            
            .main .block-container {
                max_width: 500px;
                padding-top: 4rem;
                padding-bottom: 2rem;
            }
            
            div[data-testid="stForm"] {
                background-color: white;
                padding: 2.5rem;
                border-radius: 12px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                border: 1px solid #e2e8f0;
            }
            
            input {
                border-radius: 6px !important;
                border: 1px solid #cbd5e1 !important;
                padding: 0.5rem 1rem !important;
            }
            
            button[kind="primary"] {
                width: 100%;
                border-radius: 6px;
                background-color: #2563eb;
                font-weight: 600;
                margin-top: 1rem;
            }
            
            .login-header {
                text-align: center;
                margin-bottom: 2rem;
            }
            .login-title {
                font-size: 1.875rem;
                font-weight: 700;
                color: #0f172a;
                margin-bottom: 0.5rem;
            }
            .login-subtitle {
                color: #64748b;
                font-size: 1rem;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # 2. Render Header Content FIRST
        logo_path = Path("assets/logo.png")
        if logo_path.exists():
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(str(logo_path), use_column_width=True)
        
        st.markdown("""
        <div class="login-header">
            <div class="login-title">Welcome Back</div>
            <div class="login-subtitle">Please sign in to access the Safety Dashboard</div>
        </div>
        """, unsafe_allow_html=True)

        # 3. Render Login Form BELOW Header
        authenticator.login()
        
        # 4. Handle State Transition
        # If login succeeded during this run, rerun immediately to show dashboard
        if st.session_state.get("authentication_status"):
            st.rerun()
        
        # 5. Error Handling
        elif st.session_state.get("authentication_status") is False:
            st.error('Incorrect username or password')

