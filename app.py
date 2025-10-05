"""
Dublin Road Safety Dashboard - Enhanced Version
Main Streamlit application with AWS Athena backend and Kepler.gl
Uses SmartHotspotDetectorV2 with advanced features
"""
import streamlit as st
from streamlit_keplergl import keplergl_static
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# Import custom modules - USING V2 DETECTOR
from config import DASHBOARD_CONFIG, PERCEPTION_CONFIG
from src.smart_hotspot_detector_v2 import SmartHotspotDetectorV2 as SmartHotspotDetector
from utils.geocoding_utils import get_location_name_safe, enrich_hotspots_with_locations
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
if 'use_geocoding' not in st.session_state:
    st.session_state.use_geocoding = False

# Title
st.title("🚴‍♂️ Spinovate Safety Dashboard")
st.markdown("### Road Safety Analysis: Athena Sensor Data + Perception Reports")

# ==================== DATA LOADING ====================
@st.cache_data(ttl=3600)
def load_perception_data():
    """Load perception data from CSV files"""
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

# ==================== SIDEBAR ====================
st.sidebar.title("⚙️ Dashboard Settings")
st.sidebar.markdown("---")

# Data overview
st.sidebar.subheader("📊 Data Overview")
st.sidebar.write(f"**Sensor Events (Athena):** {sensor_metrics.get('total_readings', 0):,}")
st.sidebar.write(f"**Abnormal Events:** {sensor_metrics.get('abnormal_events', 0):,}")
st.sidebar.write(f"**Infra Reports:** {len(infra_df):,}")
st.sidebar.write(f"**Ride Reports:** {len(ride_df):,}")

st.sidebar.markdown("---")

# Date Range
st.sidebar.subheader("📅 Date Range")

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
    start_date = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
with col2:
    end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

st.sidebar.markdown("---")

# Event Filters
st.sidebar.subheader("🎯 Event Filters")
available_event_types = ['hard_brake', 'swerve', 'pothole', 'acceleration']
event_types = st.sidebar.multiselect(
    "Event Types",
    options=available_event_types,
    default=available_event_types,
    help="Filter by specific event types"
)

severity_threshold = st.sidebar.slider(
    "Minimum Severity",
    min_value=1,
    max_value=10,
    value=5,
    help="Minimum severity level"
)

st.sidebar.markdown("---")

# Perception Filters
st.sidebar.subheader("📝 Perception Filters")
available_incident_types = ride_df['incidenttype'].unique().tolist()
incident_types = st.sidebar.multiselect(
    "Incident Types",
    options=available_incident_types,
    default=available_incident_types,
    help="Filter perception reports"
)

include_ai_summary = st.sidebar.checkbox("Include AI Sentiment Analysis", value=True)

st.sidebar.markdown("---")

# Clustering Parameters
st.sidebar.subheader("🔍 Detection Parameters")

sensor_cluster_radius = st.sidebar.slider(
    "Sensor Cluster Radius (m)",
    min_value=25,
    max_value=100,
    value=50,
    step=25
)

perception_cluster_radius = st.sidebar.slider(
    "Perception Cluster Radius (m)",
    min_value=25,
    max_value=100,
    value=50,
    step=25
)

min_sensor_events = st.sidebar.slider(
    "Min Events per Sensor Hotspot",
    min_value=2,
    max_value=10,
    value=2
)

min_perception_reports = st.sidebar.slider(
    "Min Reports per Perception Hotspot",
    min_value=2,
    max_value=10,
    value=3
)

perception_match_radius = st.sidebar.slider(
    "Perception Match Radius (m)",
    min_value=10,
    max_value=50,
    value=25,
    help="Radius to match perception reports to sensor hotspots"
)

recency_weight = st.sidebar.slider(
    "Recency Weight",
    min_value=0.0,
    max_value=0.5,
    value=0.2,
    step=0.1,
    help="Weight for recent reports (0=no weight, 0.5=high weight)"
)

max_hotspots = st.sidebar.slider(
    "Max Total Hotspots",
    min_value=10,
    max_value=50,
    value=20
)

st.sidebar.markdown("---")

# Display Options
st.sidebar.subheader("🗺️ Map Display")
show_perception_layer = st.sidebar.checkbox("Show Perception Reports", value=True)
st.sidebar.info("ℹ️ Raw sensor events not shown (data in Athena)")

st.sidebar.markdown("---")

# Geocoding
st.sidebar.subheader("🌍 Location Names")
use_geocoding = st.sidebar.checkbox("Enable Reverse Geocoding", value=False)
st.session_state.use_geocoding = use_geocoding
if use_geocoding:
    st.sidebar.info("⏳ Geocoding adds ~1 sec per hotspot")

st.sidebar.markdown("---")

# Buttons
apply_filters = st.sidebar.button("🔄 Apply Filters", use_container_width=True, type="primary")
if st.sidebar.button("↺ Reset to Defaults", use_container_width=True):
    st.session_state.clear()
    st.rerun()

# ==================== TABS ====================
tab1, tab2 = st.tabs(["📍 Hotspot Insights", "📈 Trend Analysis"])

# ==================== TAB 1: HOTSPOT INSIGHTS ====================
with tab1:
    st.header("Hotspot Insights")
    st.markdown("Combining Athena sensor data and perception reports")
    
    # Filter perception data
    filtered_infra = infra_df[
        (infra_df['datetime'] >= pd.Timestamp(start_date)) &
        (infra_df['datetime'] <= pd.Timestamp(end_date))
    ].copy()
    
    filtered_ride = ride_df[
        (ride_df['datetime'] >= pd.Timestamp(start_date)) &
        (ride_df['datetime'] <= pd.Timestamp(end_date))
    ].copy()
    
    if incident_types:
        filtered_ride = filtered_ride[filtered_ride['incidenttype'].isin(incident_types)]
    
    # Detect hotspots
    if apply_filters or st.session_state.hotspots_data is None:
        with st.spinner("🔍 Detecting hotspots with advanced algorithms (Haversine DBSCAN, Spatial Indexing)..."):
            detector = SmartHotspotDetector(filtered_infra, filtered_ride)
            
            hotspots = detector.get_combined_hotspots(
                sensor_params={
                    'min_severity': severity_threshold,
                    'min_events': min_sensor_events,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'perception_radius_m': perception_match_radius
                },
                perception_params={
                    'cluster_radius_m': perception_cluster_radius,
                    'min_reports': min_perception_reports,
                    'sensor_radius_m': sensor_cluster_radius,
                    'recency_weight': recency_weight
                },
                max_total_hotspots=max_hotspots
            )
            
            # Geocoding
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
        st.warning("⚠️ No hotspots detected. Try adjusting parameters.")
        st.info("**Suggestions:**\n- Lower severity threshold\n- Reduce min events/reports\n- Expand date range")
    else:
        st.success(f"✅ Detected **{len(hotspots)}** hotspots using enhanced algorithms")
        
        # Show enhancement features
        with st.expander("ℹ️ Enhanced Features Used"):
            st.markdown("""
            - **Haversine DBSCAN**: Accurate geospatial clustering
            - **Spatial Indexing (cKDTree)**: O(log n) lookups for performance
            - **Event Type Normalization**: Fair severity comparison across event types
            - **Recency Weighting**: Recent reports weighted higher
            - **Semantic Validation**: Theme-to-sensor mapping for cross-validation
            - **Temporal Aggregation**: Ready for time-series analysis
            """)
        
        # Key Metrics
        st.subheader("📊 Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_events = hotspots['event_count'].sum() if 'event_count' in hotspots.columns else 0
            total_reports = hotspots['report_count'].sum() if 'report_count' in hotspots.columns else 0
            st.metric("Total Issues", int(total_events + total_reports))
        
        with col2:
            sensor_count = len(hotspots[hotspots['source'] == 'sensor']) if 'source' in hotspots.columns else 0
            st.metric("Sensor Hotspots", sensor_count)
        
        with col3:
            perception_count = len(hotspots[hotspots['source'] == 'perception']) if 'source' in hotspots.columns else 0
            st.metric("Perception Hotspots", perception_count)
        
        with col4:
            avg_priority = hotspots['priority_score'].mean() if 'priority_score' in hotspots.columns else 0
            st.metric("Avg Priority", f"{avg_priority:.1f}")
        
        st.markdown("---")
        
        # Kepler Map
        st.subheader("🗺️ Interactive Safety Map")
        col_map, col_stats = st.columns([2, 1])
        
        with col_map:
            try:
                from keplergl import KeplerGl
                
                # Create KeplerGl map object
                map_1 = KeplerGl(height=600)
                
                # Prepare data for Kepler (convert timestamps and clean data)
                if not hotspots.empty:
                    hotspots_clean = hotspots.copy()
                    # Convert any datetime columns to strings
                    for col in hotspots_clean.columns:
                        if pd.api.types.is_datetime64_any_dtype(hotspots_clean[col]):
                            hotspots_clean[col] = hotspots_clean[col].astype(str)
                        # Convert dict/list columns to strings
                        elif hotspots_clean[col].dtype == 'object':
                            hotspots_clean[col] = hotspots_clean[col].apply(
                                lambda x: str(x) if isinstance(x, (dict, list)) else x
                            )
                    map_1.add_data(data=hotspots_clean, name='Hotspots')
                
                if show_perception_layer and not filtered_ride.empty:
                    ride_clean = filtered_ride.copy()
                    # Convert datetime columns to strings
                    for col in ride_clean.columns:
                        if pd.api.types.is_datetime64_any_dtype(ride_clean[col]):
                            ride_clean[col] = ride_clean[col].astype(str)
                        elif ride_clean[col].dtype == 'object':
                            ride_clean[col] = ride_clean[col].apply(
                                lambda x: str(x) if isinstance(x, (dict, list)) else x
                            )
                    map_1.add_data(data=ride_clean, name='Perception Reports')
                
                # Render map
                keplergl_static(map_1)
                
            except Exception as e:
                st.error(f"Kepler error: {e}")
                st.info("Showing data table instead")
                st.dataframe(hotspots.head(10))
        
        with col_stats:
            st.markdown("#### 📈 Statistics")
            
            if 'priority_score' in hotspots.columns:
                fig = px.histogram(hotspots, x='priority_score', nbins=10, title='Priority Distribution')
                fig.update_layout(height=250, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
            if 'source' in hotspots.columns:
                source_counts = hotspots['source'].value_counts()
                fig = px.pie(values=source_counts.values, names=source_counts.index, title='Sources')
                fig.update_layout(height=250)
                st.plotly_chart(fig, use_container_width=True)
            
            # Show validation status breakdown (V2 feature)
            if 'sensor_validation' in hotspots.columns:
                st.markdown("##### ✅ Validation Status")
                validation_counts = hotspots['sensor_validation'].value_counts()
                for status, count in validation_counts.items():
                    emoji = {'confirmed': '✅', 'partial': '⚠️', 'conflicted': '❌', 'no_sensor_data': '📭'}.get(status, '❓')
                    st.write(f"{emoji} {status.title()}: {count}")
            
            # Show temporal distribution (V2 feature)
            if 'time_period_str' in hotspots.columns and hotspots['time_period_str'].nunique() > 1:
                st.markdown("##### 📅 Temporal")
                period_counts = hotspots['time_period_str'].value_counts().head(5)
                for period, count in period_counts.items():
                    if period != 'Unknown':
                        st.write(f"📆 {period}: {count}")
        
        st.markdown("---")
        
        # Top 10 Hotspots
        st.subheader("🔝 Top 10 Critical Hotspots")
        
        for idx, hotspot in hotspots.head(10).iterrows():
            with st.expander(
                f"🚨 Hotspot #{hotspot.get('final_hotspot_id', idx+1)}: {hotspot.get('location_name', 'Unknown')}",
                expanded=(idx == 0)
            ):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Source", hotspot.get('source', 'N/A').title())
                with col2:
                    if hotspot.get('source') == 'sensor':
                        st.metric("Events", int(hotspot.get('event_count', 0)))
                    else:
                        st.metric("Reports", int(hotspot.get('report_count', 0)))
                with col3:
                    st.metric("Priority", f"{hotspot.get('priority_score', 0):.1f}")
                with col4:
                    if hotspot.get('source') == 'sensor':
                        st.metric("Avg Severity", f"{hotspot.get('avg_severity', 0):.1f}")
                    else:
                        st.metric("Urgency", f"{hotspot.get('urgency_score', 0)}/100")
                
                # Location
                st.markdown("##### 📍 Location")
                lat, lng = hotspot['center_lat'], hotspot['center_lng']
                st.write(f"**Coordinates:** {lat:.5f}, {lng:.5f}")
                
                # Show context summary if available (V2 feature)
                if hotspot.get('context_summary'):
                    st.info(f"📋 Context: {hotspot['context_summary']}")
                
                # Show temporal info if available (V2 feature)
                if hotspot.get('time_period_str') and hotspot['time_period_str'] != 'Unknown':
                    st.write(f"**Time Period:** {hotspot['time_period_str']}")
                
                # Show validation details if available (V2 feature)
                if hotspot.get('validation_reasoning'):
                    st.markdown("##### 🔍 Validation Details")
                    st.write(f"**Status:** {hotspot.get('sensor_validation', 'N/A').title()}")
                    st.write(f"**Confidence:** {hotspot.get('validation_confidence', 0):.1%}")
                    st.write(f"**Reasoning:** {hotspot.get('validation_reasoning', 'N/A')}")
                
                street_view_url = STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lng, heading=0)
                st.markdown(f"[🔍 Open in Google Street View]({street_view_url})")
                
                # Show recency factor if available
                if hotspot.get('recency_factor') and hotspot['recency_factor'] != 1.0:
                    st.caption(f"Recency factor: {hotspot['recency_factor']:.2f}x")

# ==================== TAB 2: TREND ANALYSIS ====================
with tab2:
    st.header("Trend Analysis")
    st.info("Coming soon: Time series analysis and anomaly detection")