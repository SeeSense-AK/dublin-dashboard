"""
Dublin Road Safety Dashboard - UPDATED WITH KEPLER.GL
Main Streamlit application - Tab 1 Implementation
"""
import streamlit as st
from streamlit_kepler_gl import keplergl_static
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# Import custom modules
from config import DASHBOARD_CONFIG, PERCEPTION_CONFIG
from src.smart_hotspot_detector import SmartHotspotDetector
from src.kepler_config import (
    build_kepler_config,
    prepare_data_for_kepler
)
from utils.geocoding_utils import (
    get_location_name_safe,
    enrich_hotspots_with_locations
)
from utils.constants import STREET_VIEW_URL_TEMPLATE
from src.sentiment_analyzer import analyze_perception_sentiment

# Configure page
st.set_page_config(
    page_title=DASHBOARD_CONFIG["title"],
    page_icon=DASHBOARD_CONFIG["page_icon"],
    layout=DASHBOARD_CONFIG["layout"],
    initial_sidebar_state=DASHBOARD_CONFIG["initial_sidebar_state"]
)

# Initialize session state
if 'hotspots_data' not in st.session_state:
    st.session_state.hotspots_data = None
if 'selected_hotspot' not in st.session_state:
    st.session_state.selected_hotspot = None
if 'use_geocoding' not in st.session_state:
    st.session_state.use_geocoding = False

# Title and description
st.title("🚴‍♂️ Spinovate Safety Dashboard")
st.markdown("### Comprehensive Road Safety Analysis using Sensor Data and Perception Reports")


# ==================== SIDEBAR ====================
st.sidebar.title("⚙️ Dashboard Settings")
st.sidebar.markdown("---")

# Load data function
@st.cache_data(ttl=3600)
def load_perception_data():
    """Load only perception data from CSV files"""
    # Load perception data
    infra_df = pd.read_csv('dublin_infra_reports_dublin2025_upto20250924.csv')
    ride_df = pd.read_csv('dublin_ride_reports_dublin2025_upto20250924.csv')
    
    # Parse dates
    infra_df['datetime'] = pd.to_datetime(
        infra_df['date'] + ' ' + infra_df['time'], 
        format='%d-%m-%Y %H:%M:%S', 
        dayfirst=True, 
        errors='coerce'
    )
    ride_df['datetime'] = pd.to_datetime(
        ride_df['date'] + ' ' + ride_df['time'], 
        format='%d-%m-%Y %H:%M:%S', 
        dayfirst=True, 
        errors='coerce'
    )
    
    return infra_df, ride_df

@st.cache_data(ttl=3600)
def get_sensor_metrics():
    """Get sensor data metrics from Athena"""
    from src.data_loader import load_sensor_data_metrics
    return load_sensor_data_metrics()


# Load data
with st.spinner("Loading datasets..."):
    infra_df, ride_df = load_perception_data()
    sensor_metrics = get_sensor_metrics()

# Data overview
st.sidebar.subheader("📊 Data Overview")
st.sidebar.write(f"**Sensor Events (Athena):** {sensor_metrics.get('total_readings', 0):,}")
st.sidebar.write(f"**Abnormal Events:** {sensor_metrics.get('abnormal_events', 0):,}")
st.sidebar.write(f"**Infra Reports:** {len(infra_df):,}")
st.sidebar.write(f"**Ride Reports:** {len(ride_df):,}")

st.sidebar.markdown("---")

# Date Range Filter
st.sidebar.subheader("📅 Date Range")

# Get date range from sensor metrics
if sensor_metrics.get('earliest_reading') and sensor_metrics.get('latest_reading'):
    try:
        min_date = pd.to_datetime(sensor_metrics['earliest_reading']).date()
        max_date = pd.to_datetime(sensor_metrics['latest_reading']).date()
    except:
        max_date = datetime.now().date()
        min_date = max_date - timedelta(days=90)
else:
    max_date = datetime.now().date()
    min_date = max_date - timedelta(days=90)

col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input(
        "From",
        value=min_date,
        min_value=min_date,
        max_value=max_date
    )

with col2:
    end_date = st.date_input(
        "To",
        value=max_date,
        min_value=min_date,
        max_value=max_date
    )

st.sidebar.markdown("---")

# Event Filters
st.sidebar.subheader("🎯 Event Filters")

# Common event types from your Athena data
available_event_types = ['hard_brake', 'swerve', 'pothole', 'acceleration']

event_types = st.sidebar.multiselect(
    "Event Types",
    options=available_event_types,
    default=available_event_types,
    help="Filter by specific event types (from Athena)"
)

severity_threshold = st.sidebar.slider(
    "Minimum Severity",
    min_value=1,
    max_value=10,
    value=5,
    help="Minimum severity level for sensor events"
)

show_only_abnormal = st.sidebar.checkbox(
    "Show only abnormal events",
    value=True,
    disabled=True,
    help="Always enabled - Athena queries only abnormal events"
)

st.sidebar.markdown("---")

# Perception Filters
st.sidebar.subheader("📝 Perception Filters")

# Get available incident types
available_incident_types = ride_df['incidenttype'].unique().tolist()

incident_types = st.sidebar.multiselect(
    "Incident Types",
    options=available_incident_types,
    default=available_incident_types,
    help="Filter perception reports by incident type"
)

include_ai_summary = st.sidebar.checkbox(
    "Include AI Sentiment Analysis",
    value=True,
    help="Analyze perception reports using Groq AI"
)

st.sidebar.markdown("---")

# Clustering Parameters
st.sidebar.subheader("🔍 Detection Parameters")

sensor_cluster_radius = st.sidebar.slider(
    "Sensor Cluster Radius (m)",
    min_value=25,
    max_value=100,
    value=50,
    step=25,
    help="Radius for grouping sensor events"
)

perception_cluster_radius = st.sidebar.slider(
    "Perception Cluster Radius (m)",
    min_value=25,
    max_value=100,
    value=50,
    step=25,
    help="Radius for grouping perception reports"
)

min_sensor_events = st.sidebar.slider(
    "Min Events per Sensor Hotspot",
    min_value=2,
    max_value=10,
    value=2,
    help="Minimum sensor events to form a hotspot"
)

min_perception_reports = st.sidebar.slider(
    "Min Reports per Perception Hotspot",
    min_value=2,
    max_value=10,
    value=3,
    help="Minimum perception reports to form a hotspot"
)

perception_match_radius = st.sidebar.slider(
    "Perception Match Radius (m)",
    min_value=10,
    max_value=50,
    value=25,
    help="Radius to match perception reports to sensor hotspots"
)

max_hotspots = st.sidebar.slider(
    "Max Total Hotspots",
    min_value=10,
    max_value=50,
    value=20,
    help="Maximum number of hotspots to display"
)

st.sidebar.markdown("---")

# Display Options
st.sidebar.subheader("🗺️ Map Display")

show_perception_layer = st.sidebar.checkbox(
    "Show Perception Reports",
    value=True,
    help="Display individual perception reports on map"
)

st.sidebar.info("ℹ️ Raw sensor events not shown (data in Athena)")

st.sidebar.markdown("---")

# Geocoding toggle
st.sidebar.subheader("🌍 Location Names")
use_geocoding = st.sidebar.checkbox(
    "Enable Reverse Geocoding",
    value=False,
    help="Get location names from coordinates (slow, requires internet)"
)
st.session_state.use_geocoding = use_geocoding

if use_geocoding:
    st.sidebar.info("⏳ Geocoding will add ~1 second per hotspot")

st.sidebar.markdown("---")

# Apply Filters Button
apply_filters = st.sidebar.button("🔄 Apply Filters", use_container_width=True, type="primary")

# Reset button
if st.sidebar.button("↺ Reset to Defaults", use_container_width=True):
    st.session_state.clear()
    st.rerun()


# ==================== MAIN CONTENT ====================

# Create tabs
tab1, tab2 = st.tabs(["📍 Hotspot Insights", "📈 Trend Analysis"])

# ==================== TAB 1: HOTSPOT INSIGHTS ====================
with tab1:
    st.header("Hotspot Insights")
    st.markdown("Combining Athena sensor data and perception reports for comprehensive safety analysis")
    
    # Filter perception data by date
    filtered_infra = infra_df[
        (infra_df['datetime'] >= pd.Timestamp(start_date)) &
        (infra_df['datetime'] <= pd.Timestamp(end_date))
    ].copy()
    
    filtered_ride = ride_df[
        (ride_df['datetime'] >= pd.Timestamp(start_date)) &
        (ride_df['datetime'] <= pd.Timestamp(end_date))
    ].copy()
    
    # Apply incident type filter
    if incident_types:
        filtered_ride = filtered_ride[filtered_ride['incidenttype'].isin(incident_types)]
    
    # Detect hotspots using Athena
    if apply_filters or st.session_state.hotspots_data is None:
        with st.spinner("Detecting hotspots from Athena..."):
            detector = SmartHotspotDetector(filtered_infra, filtered_ride)
            
            hotspots = detector.get_combined_hotspots(
                sensor_params={
                    'min_severity': severity_threshold,
                    'min_events': min_sensor_events,
                    'perception_radius_m': perception_match_radius,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d')
                },
                perception_params={
                    'cluster_radius_m': perception_cluster_radius,
                    'min_reports': min_perception_reports,
                    'sensor_radius_m': sensor_cluster_radius
                },
                max_total_hotspots=max_hotspots
            )_m': sensor_cluster_radius
                },
                max_total_hotspots=max_hotspots
            )_m': sensor_cluster_radius
                },
                max_total_hotspots=max_hotspots
            )
            
            # Enrich with location names if geocoding enabled
            if use_geocoding and not hotspots.empty:
                with st.spinner("Geocoding locations..."):
                    hotspots = enrich_hotspots_with_locations(hotspots, use_geocoding=True)
            elif not hotspots.empty:
                hotspots['location_name'] = hotspots.apply(
                    lambda row: f"Lat: {row['center_lat']:.4f}, Lng: {row['center_lng']:.4f}",
                    axis=1
                )
            
            st.session_state.hotspots_data = hotspots
    
    hotspots = st.session_state.hotspots_data
    
    if hotspots is None or hotspots.empty:
        st.warning("⚠️ No hotspots detected with current filters. Try adjusting parameters.")
        st.info("**Suggestions:**\n- Lower the minimum severity threshold\n- Reduce minimum events/reports\n- Expand the date range\n- Increase cluster radius")
    else:
        st.success(f"✅ Detected **{len(hotspots)}** hotspots")
        
        # ==================== KEY METRICS ====================
        st.subheader("📊 Key Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_events = hotspots['event_count'].sum() if 'event_count' in hotspots.columns else 0
            total_reports = hotspots['report_count'].sum() if 'report_count' in hotspots.columns else 0
            st.metric("Total Issues", int(total_events + total_reports))
        
        with col2:
            sensor_hotspots = len(hotspots[hotspots['source'] == 'sensor']) if 'source' in hotspots.columns else 0
            st.metric("Sensor Hotspots", sensor_hotspots)
        
        with col3:
            perception_hotspots = len(hotspots[hotspots['source'] == 'perception']) if 'source' in hotspots.columns else 0
            st.metric("Perception Hotspots", perception_hotspots)
        
        with col4:
            avg_priority = hotspots['priority_score'].mean() if 'priority_score' in hotspots.columns else 0
            st.metric("Avg Priority", f"{avg_priority:.1f}")
        
        st.markdown("---")
        
        # ==================== KEPLER.GL MAP ====================
        st.subheader("🗺️ Interactive Safety Map")
        
        col_map, col_stats = st.columns([2, 1])
        
        with col_map:
            # Prepare data for Kepler
            # Note: For Athena data, we don't show raw sensor events layer (too large)
            kepler_data = prepare_data_for_kepler(
                hotspots_df=hotspots,
                perception_df=filtered_ride if show_perception_layer else None,
                sensor_df=None  # Don't load all sensor data from Athena
            )
            
            # Build Kepler config
            kepler_config = build_kepler_config(
                include_perception=show_perception_layer,
                include_sensor=False,  # Can't show raw sensor events from Athena
                include_heatmap=False  # Can't create heatmap without raw data
            )
            
            # Render Kepler map
            try:
                keplergl_static(kepler_data, config=kepler_config, height=600)
            except Exception as e:
                st.error(f"Error rendering Kepler map: {e}")
                st.info("Falling back to data table view")
                st.dataframe(hotspots.head(10))
        
        with col_stats:
            st.markdown("#### 📈 Hotspot Statistics")
            
            # Priority distribution
            if 'priority_score' in hotspots.columns:
                fig_priority = px.histogram(
                    hotspots,
                    x='priority_score',
                    nbins=10,
                    title='Priority Score Distribution',
                    labels={'priority_score': 'Priority Score', 'count': 'Count'},
                    color_discrete_sequence=['#DC143C']
                )
                fig_priority.update_layout(height=250, showlegend=False)
                st.plotly_chart(fig_priority, use_container_width=True)
            
            # Source breakdown
            if 'source' in hotspots.columns:
                source_counts = hotspots['source'].value_counts()
                fig_source = px.pie(
                    values=source_counts.values,
                    names=source_counts.index,
                    title='Hotspot Sources',
                    color_discrete_map={'sensor': '#FF4500', 'perception': '#1E90FF'}
                )
                fig_source.update_layout(height=250)
                st.plotly_chart(fig_source, use_container_width=True)
        
        st.markdown("---")
        
        # ==================== TOP HOTSPOTS ====================
        st.subheader("🔝 Top 10 Critical Hotspots")
        
        top_hotspots = hotspots.head(10)
        
        for idx, hotspot in top_hotspots.iterrows():
            with st.expander(
                f"🚨 Hotspot #{hotspot.get('final_hotspot_id', idx+1)}: {hotspot.get('location_name', 'Unknown')}",
                expanded=(idx == 0)  # Expand first one by default
            ):
                # Overview metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Source", hotspot.get('source', 'N/A').title())
                
                with col2:
                    if hotspot.get('source') == 'sensor':
                        st.metric("Events", int(hotspot.get('event_count', 0)))
                    else:
                        st.metric("Reports", int(hotspot.get('report_count', 0)))
                
                with col3:
                    priority = hotspot.get('priority_score', 0)
                    st.metric("Priority", f"{priority:.1f}")
                
                with col4:
                    if hotspot.get('source') == 'sensor':
                        severity = hotspot.get('avg_severity', 0)
                        st.metric("Avg Severity", f"{severity:.1f}")
                    else:
                        urgency = hotspot.get('urgency_score', 0)
                        st.metric("Urgency", f"{urgency}/100")
                
                # Details based on source
                if hotspot.get('source') == 'sensor':
                    # Sensor hotspot details
                    st.markdown("##### 📡 Sensor Data")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Max Severity:** {hotspot.get('max_severity', 0)}")
                        st.write(f"**Unique Devices:** {hotspot.get('device_count', 0)}")
                    
                    with col2:
                        event_types_dict = hotspot.get('event_types', {})
                        if isinstance(event_types_dict, str):
                            import ast
                            try:
                                event_types_dict = ast.literal_eval(event_types_dict)
                            except:
                                event_types_dict = {}
                        
                        if event_types_dict:
                            st.write("**Event Types:**")
                            for etype, count in event_types_dict.items():
                                st.write(f"- {etype}: {count}")
                    
                    # Perception enrichment
                    if hotspot.get('perception_count', 0) > 0:
                        st.markdown("##### 📝 Perception Reports")
                        st.write(f"Found **{hotspot['perception_count']}** nearby reports")
                        
                        if hotspot.get('perception_sentiment'):
                            sentiment = hotspot['perception_sentiment']
                            if isinstance(sentiment, str):
                                import ast
                                try:
                                    sentiment = ast.literal_eval(sentiment)
                                except:
                                    sentiment = {}
                            
                            if sentiment:
                                st.write(f"**Sentiment:** {sentiment.get('sentiment', 'N/A').title()}")
                                st.write(f"**Severity:** {sentiment.get('severity', 'N/A').title()}")
                                st.write(f"**Summary:** {sentiment.get('summary', 'N/A')}")
                
                else:
                    # Perception hotspot details
                    st.markdown("##### 📝 Perception Reports")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Primary Theme:** {hotspot.get('primary_theme', 'N/A')}")
                        
                        themes_dict = hotspot.get('themes', {})
                        if isinstance(themes_dict, str):
                            import ast
                            try:
                                themes_dict = ast.literal_eval(themes_dict)
                            except:
                                themes_dict = {}
                        
                        if themes_dict:
                            st.write("**All Themes:**")
                            for theme, count in themes_dict.items():
                                st.write(f"- {theme}: {count}")
                    
                    with col2:
                        avg_rating = hotspot.get('avg_rating')
                        if avg_rating and not pd.isna(avg_rating):
                            st.write(f"**Avg Rating:** {avg_rating:.1f}/5")
                        
                        report_types = hotspot.get('report_types', {})
                        if isinstance(report_types, str):
                            import ast
                            try:
                                report_types = ast.literal_eval(report_types)
                            except:
                                report_types = {}
                        
                        if report_types:
                            st.write("**Report Types:**")
                            for rtype, count in report_types.items():
                                st.write(f"- {rtype}: {count}")
                    
                    # Sensor validation
                    if hotspot.get('sensor_count', 0) > 0:
                        st.markdown("##### 📡 Sensor Validation")
                        st.write(f"Found **{hotspot['sensor_count']}** nearby sensor events")
                        
                        validation = hotspot.get('sensor_validation', 'no_sensor_data')
                        validation_emoji = {
                            'confirmed': '✅',
                            'partial': '⚠️',
                            'conflicted': '❌',
                            'no_sensor_data': '📭'
                        }
                        st.write(f"{validation_emoji.get(validation, '❓')} **Status:** {validation.title()}")
                
                # Location and Street View
                st.markdown("##### 📍 Location")
                lat = hotspot['center_lat']
                lng = hotspot['center_lng']
                
                st.write(f"**Coordinates:** {lat:.5f}, {lng:.5f}")
                
                street_view_url = STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lng, heading=0)
                st.markdown(f"[🔍 Open in Google Street View]({street_view_url})")
                
                # Sample comments if available
                comments = hotspot.get('comments', [])
                if isinstance(comments, str):
                    import ast
                    try:
                        comments = ast.literal_eval(comments)
                    except:
                        comments = []
                
                if comments and len(comments) > 0:
                    with st.expander("💬 View User Comments"):
                        for i, comment in enumerate(comments[:5], 1):
                            if comment and str(comment).strip():
                                st.write(f"{i}. {comment}")
                        
                        if len(comments) > 5:
                            st.info(f"... and {len(comments) - 5} more comments")


# ==================== TAB 2: TREND ANALYSIS ====================
with tab2:
    st.header("Trend Analysis")
    st.markdown("*Coming soon: Time series analysis and anomaly detection*")
    
    st.info("This tab will show usage trends, anomalies, and temporal patterns in the data.")
