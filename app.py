"""
Dublin Road Safety Dashboard
Main Streamlit application with AWS Athena backend
"""
import streamlit as st
from streamlit_folium import folium_static
import pandas as pd

# Import custom modules (your existing structure)
from config import DASHBOARD_CONFIG, PERCEPTION_CONFIG
from src.data_loader import (
    load_all_data, 
    get_data_summary,
    validate_data
)
from src.hotspot_analysis import (
    detect_hotspots,
    get_hotspot_statistics,
    get_hotspot_details,
    classify_hotspot_severity,
    analyze_event_types
)
from src.perception_matcher import (
    match_perception_to_hotspots,
    get_perception_summary,
    enrich_hotspot_with_perception
)
from src.sentiment_analyzer import analyze_perception_sentiment
from src.trend_analysis import (
    prepare_time_series,
    detect_anomalies,
    calculate_trends,
    find_usage_drops,
    analyze_seasonal_patterns
)
from src.visualizations import (
    create_hotspot_map,
    create_severity_distribution_chart,
    create_time_series_chart,
    create_metric_cards,
    create_incident_heatmap
)
from utils.constants import (
    STREET_VIEW_URL_TEMPLATE,
    MAP_TILES,
    SEVERITY_COLORS
)

# Configure page
st.set_page_config(
    page_title=DASHBOARD_CONFIG["title"],
    page_icon=DASHBOARD_CONFIG["page_icon"],
    layout=DASHBOARD_CONFIG["layout"],
    initial_sidebar_state=DASHBOARD_CONFIG["initial_sidebar_state"]
)

# Title and description
st.title("🚴‍♂️ Spinovate Safety Dashboard")
st.markdown("### Comprehensive Road Safety Analysis using Sensor Data and Perception Reports")

# Sidebar
st.sidebar.title("⚙️ Settings")
st.sidebar.markdown("---")

# Data validation
validation = validate_data()
if not validation['athena_connection']:
    st.error("⚠️ Cannot connect to AWS Athena! Please check your credentials.")
    st.stop()

# Load data
with st.spinner("Loading data..."):
    data = load_all_data()
    sensor_metrics = data['sensor_metrics']
    infra_df = data['infrastructure']
    ride_df = data['ride']

if sensor_metrics['total_readings'] == 0:
    st.error("No sensor data available. Please check your data files.")
    st.stop()

# Sidebar - Data Overview
st.sidebar.subheader("📊 Data Overview")
st.sidebar.write(f"**Sensor Records:** {sensor_metrics['total_readings']:,}")
st.sidebar.write(f"**Infra Reports:** {len(infra_df):,}")
st.sidebar.write(f"**Ride Reports:** {len(ride_df):,}")
st.sidebar.markdown("---")

# Sidebar - Hotspot Settings
st.sidebar.subheader("🎯 Hotspot Detection")
severity_threshold = st.sidebar.slider(
    "Minimum Severity",
    min_value=1,
    max_value=4,
    value=2,
    help="Minimum severity level to consider for hotspot detection"
)

min_incidents = st.sidebar.slider(
    "Minimum Incidents",
    min_value=2,
    max_value=10,
    value=3,
    help="Minimum number of incidents to form a hotspot"
)

perception_radius = st.sidebar.slider(
    "Perception Match Radius (m)",
    min_value=10,
    max_value=50,
    value=25,
    help="Radius in meters to match perception reports to hotspots"
)

# Main content - Tabs
tab1, tab2 = st.tabs(["📍 Hotspot Analysis", "📈 Trend Analysis"])

# ==================== TAB 1: HOTSPOT ANALYSIS ====================
with tab1:
    st.header("Hotspot Analysis")
    st.markdown("Identifying dangerous road segments using sensor data and perception reports")
    
    # Detect hotspots using your existing module
    with st.spinner("Detecting hotspots..."):
        hotspots = detect_hotspots(
            severity_threshold=severity_threshold,
            min_samples=min_incidents
        )
    
    if hotspots.empty:
        st.warning("No hotspots detected with current settings. Try adjusting the parameters in the sidebar.")
    else:
        # Match perception reports using your existing module
        with st.spinner("Matching perception reports to hotspots..."):
            matched_hotspots = match_perception_to_hotspots(
                hotspots,
                infra_df,
                ride_df,
                radius_m=perception_radius
            )
        
        # Get statistics using your existing module
        stats = get_hotspot_statistics(matched_hotspots)
        
        # Display metrics using your existing module
        st.subheader("📊 Key Metrics")
        metrics = {
            "Total Hotspots": stats['total_hotspots'],
            "Total Incidents": stats['total_incidents'],
            "Avg Severity": f"{stats['avg_severity']:.2f}",
            "Critical Hotspots": stats['critical_hotspots']
        }
        create_metric_cards(metrics)
        
        st.markdown("---")
        
        # Layout: Map and Charts
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🗺️ Interactive Hotspot Map")
            show_perception = st.checkbox("Show Perception Reports", value=True)
            
            # Create map using your existing module
            hotspot_map = create_hotspot_map(
                matched_hotspots,
                infra_df if show_perception else None,
                ride_df if show_perception else None,
                show_perception=show_perception
            )
            folium_static(hotspot_map, width=800, height=600)
        
        with col2:
            st.subheader("📊 Severity Distribution")
            severity_chart = create_severity_distribution_chart(matched_hotspots)
            st.plotly_chart(severity_chart, use_container_width=True)
            
            # Top hotspots
            st.subheader("🔝 Top 5 Hotspots")
            top_hotspots = matched_hotspots.nlargest(5, 'incident_count')[
                ['hotspot_id', 'incident_count', 'avg_severity', 'total_perception_reports']
            ]
            st.dataframe(top_hotspots, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Detailed hotspot analysis
        st.subheader("🔍 Detailed Hotspot Analysis")
        
        selected_hotspot = st.selectbox(
            "Select a hotspot to analyze",
            options=matched_hotspots['hotspot_id'].tolist(),
            format_func=lambda x: f"Hotspot #{x}"
        )
        
        if selected_hotspot:
            hotspot_data = matched_hotspots[matched_hotspots['hotspot_id'] == selected_hotspot].iloc[0]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Incidents", int(hotspot_data['incident_count']))
                st.metric("Avg Severity", f"{hotspot_data['avg_severity']:.2f}")
            
            with col2:
                st.metric("Max Severity", int(hotspot_data.get('max_severity', 0)))
                st.metric("Devices", int(hotspot_data.get('device_count', 0)))
            
            with col3:
                st.metric("Perception Reports", int(hotspot_data['total_perception_reports']))
                
                # Street View link using your constants
                lat = hotspot_data['latitude']
                lng = hotspot_data['longitude']
                street_view_url = STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lng, heading=0)
                st.markdown(f"[🔍 View in Google Street View]({street_view_url})")
            
            # Perception reports details using your existing module
            if hotspot_data['total_perception_reports'] > 0:
                st.markdown("#### 💬 Perception Reports")
                
                perception_summary = get_perception_summary(matched_hotspots, selected_hotspot)
                
                if perception_summary:
                    infra_reports = perception_summary['infra_details']
                    ride_reports = perception_summary['ride_details']
                    
                    # Display reports
                    if infra_reports:
                        with st.expander(f"📋 Infrastructure Reports ({len(infra_reports)})"):
                            for report in infra_reports[:5]:
                                st.write(f"**Type:** {report.get('infrastructuretype', 'N/A')}")
                                comment = report.get('finalcomment', '')
                                if comment:
                                    st.write(f"**Comment:** {comment}")
                                st.write(f"**Date:** {report.get('date', 'N/A')}")
                                st.markdown("---")
                    
                    if ride_reports:
                        with st.expander(f"🚴 Ride Reports ({len(ride_reports)})"):
                            for report in ride_reports[:5]:
                                st.write(f"**Incident:** {report.get('incidenttype', 'N/A')}")
                                st.write(f"**Rating:** {report.get('incidentrating', 'N/A')}/5")
                                comment = report.get('commentfinal', '')
                                if comment:
                                    st.write(f"**Comment:** {comment}")
                                st.write(f"**Date:** {report.get('date', 'N/A')}")
                                st.markdown("---")
                    
                    # Sentiment Analysis using your existing module
                    if st.button("🤖 Analyze Sentiment with AI"):
                        with st.spinner("Analyzing perception reports..."):
                            # Collect comments
                            comments = []
                            for report in infra_reports:
                                comment = report.get('finalcomment', '')
                                if comment:
                                    comments.append(comment)
                            for report in ride_reports:
                                comment = report.get('commentfinal', '')
                                if comment:
                                    comments.append(comment)
                            
                            if comments:
                                sentiment_result = analyze_perception_sentiment(comments)
                                
                                st.markdown("#### 🎯 AI Sentiment Analysis")
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Sentiment:** {sentiment_result['sentiment'].title()}")
                                with col2:
                                    st.write(f"**Severity:** {sentiment_result['severity'].title()}")
                                
                                st.write(f"**Summary:** {sentiment_result['summary']}")
                                
                                if sentiment_result['key_issues']:
                                    st.write("**Key Issues:**")
                                    for issue in sentiment_result['key_issues']:
                                        st.write(f"- {issue}")
                            else:
                                st.info("No comments available for sentiment analysis")

# ==================== TAB 2: TREND ANALYSIS ====================
with tab2:
    st.header("Trend Analysis")
    st.markdown("Analyzing road usage patterns and detecting anomalies over time")
    
    # Check if datetime data is available
    st.warning("Trend analysis requires refactoring for Athena backend. Coming soon!")
    
    # Placeholder for when trend_analysis.py is updated
    st.info("""
    **Next Steps for Trend Analysis:**
    
    1. Update trend_analysis.py to use Athena backend
    2. Implement time series queries for usage patterns
    3. Add anomaly detection for sudden usage drops
    4. Display weekly/monthly cycling patterns
    
    This will be completed in the next refactoring step.
    """)

# Footer
st.divider()
st.markdown("""
### 🔧 How This Works

**Hotspot Detection:**
- **Sensor-based hotspots** (red markers): Use clustering to find locations where multiple abnormal events occurred
- **Report-based hotspots** (orange markers): Cluster user reports of incidents and infrastructure issues  
- **Report matching**: Find perception reports within specified radius of each hotspot to add context

**Data Sources:**
- Sensor readings: {total_readings:,} records from AWS Athena
- User reports: {ride_reports} ride reports + {infra_reports} infrastructure reports (local CSV)

**Architecture:**
- **Backend**: AWS Athena (Parquet optimized) + Local CSV files
- **Modules**: Using your existing hotspot_analysis.py, perception_matcher.py, visualizations.py
""".format(
    total_readings=sensor_metrics['total_readings'],
    ride_reports=len(ride_df),
    infra_reports=len(infra_df)
))
