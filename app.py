"""
Spinovate Safety Dashboard
Complete rewrite with enhanced AI analysis display
"""
import streamlit as st
from streamlit_folium import folium_static
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import folium

# Import custom modules
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
    analyze_seasonal_patterns,
    get_time_series_summary
)
from src.visualizations import (
    create_hotspot_map,
    create_severity_distribution_chart,
    create_time_series_chart,
    create_metric_cards,
    create_incident_heatmap
)
from src.perception_hotspot_analyzer import create_enriched_perception_hotspots
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
st.markdown("### AI-Powered Road Safety Analysis")

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

# Display date range
if sensor_metrics['earliest_reading'] and sensor_metrics['latest_reading']:
    st.sidebar.write(f"**Data Range:** {sensor_metrics['earliest_reading']} to {sensor_metrics['latest_reading']}")

st.sidebar.markdown("---")

# Main content - Tabs
tab1, tab2 = st.tabs(["📍 AI-Powered Hotspot Analysis", "📈 Trend Analysis"])

# ==================== TAB 1: AI-POWERED HOTSPOT ANALYSIS ====================
with tab1:
    st.header("🤖 AI-Powered Perception Analysis")
    st.markdown("**User reports analyzed by AI, validated with sensor data**")
    
    # ========== DATE SLICER ==========
    st.subheader("📅 Date Range Filter")
    
    try:
        earliest = pd.to_datetime(sensor_metrics['earliest_reading']).date()
        latest = pd.to_datetime(sensor_metrics['latest_reading']).date()
    except:
        latest = datetime.now().date()
        earliest = latest - timedelta(days=90)
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=earliest,
            min_value=earliest,
            max_value=latest,
            help="Select the start date"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=latest,
            min_value=earliest,
            max_value=latest,
            help="Select the end date"
        )
    
    with col3:
        st.write("")
        st.write("")
        if st.button("🔄 Reset", use_container_width=True):
            st.rerun()
    
    if start_date > end_date:
        st.error("⚠️ Start date must be before end date!")
        st.stop()
    
    days_selected = (end_date - start_date).days + 1
    st.info(f"📊 Analyzing data from **{start_date.strftime('%d %b %Y')}** to **{end_date.strftime('%d %b %Y')}** ({days_selected} days)")
    
    st.markdown("---")
    
    # ========== CLUSTERING SETTINGS ==========
    st.subheader("⚙️ Clustering Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        cluster_radius = st.slider(
            "Clustering Radius (m)",
            min_value=25,
            max_value=100,
            value=50,
            step=25,
            help="Group reports within this radius"
        )
    
    with col2:
        min_reports_per_cluster = st.slider(
            "Minimum Reports per Hotspot",
            min_value=2,
            max_value=10,
            value=3,
            help="Minimum reports needed to form a hotspot"
        )
    
    st.markdown("---")
    
    # ========== PERCEPTION ANALYSIS WITH AI ==========
    
    # Filter perception reports by date
    infra_filtered = infra_df.copy()
    ride_filtered = ride_df.copy()
    
    if 'datetime' in infra_filtered.columns:
        infra_filtered = infra_filtered[
            (pd.to_datetime(infra_filtered['datetime']).dt.date >= start_date) &
            (pd.to_datetime(infra_filtered['datetime']).dt.date <= end_date)
        ]
    
    if 'datetime' in ride_filtered.columns:
        ride_filtered = ride_filtered[
            (pd.to_datetime(ride_filtered['datetime']).dt.date >= start_date) &
            (pd.to_datetime(ride_filtered['datetime']).dt.date <= end_date)
        ]
    
    # Store date range in session state for sensor validation
    if 'selected_start_date' not in st.session_state:
        st.session_state.selected_start_date = start_date
        st.session_state.selected_end_date = end_date
    else:
        st.session_state.selected_start_date = start_date
        st.session_state.selected_end_date = end_date
    
    with st.spinner("🤖 Running AI analysis on perception reports..."):
        perception_hotspots = create_enriched_perception_hotspots(
            infra_filtered,
            ride_filtered,
            eps_meters=cluster_radius,
            min_reports=min_reports_per_cluster,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
    
    if perception_hotspots.empty:
        st.warning("⚠️ No perception hotspots found with current settings.")
        st.info("💡 Try: Reducing minimum reports or increasing clustering radius")
    else:
        st.success(f"✅ Found **{len(perception_hotspots)}** AI-analyzed hotspots")
        
        # ========== KEY METRICS ==========
        st.subheader("📊 Key Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_reports = perception_hotspots['total_reports'].sum()
            st.metric("Total Reports", int(total_reports))
        
        with col2:
            confirmed = len(perception_hotspots[perception_hotspots['validation'].apply(
                lambda x: x['validation_status'] in ['CONFIRMED', 'STRONGLY_CONFIRMED'])])
            st.metric("Sensor Confirmed", confirmed)
        
        with col3:
            avg_urgency = perception_hotspots['urgency_score'].mean()
            st.metric("Avg Urgency", f"{avg_urgency:.0f}/100")
        
        with col4:
            critical = len(perception_hotspots[perception_hotspots['ai_analysis'].apply(
                lambda x: x['severity'] == 'critical')])
            st.metric("AI Critical Issues", critical)
        
        st.markdown("---")
        
        # ========== INTERACTIVE MAP WITH FIXED SIZE MARKERS ==========
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🗺️ Hotspot Map")
            
            # Create map with fixed-size markers
            m = folium.Map(
                location=[perception_hotspots['center_lat'].mean(), 
                         perception_hotspots['center_lng'].mean()],
                zoom_start=12
            )
            
            # Add hotspots with FIXED SIZE
            for idx, hotspot in perception_hotspots.iterrows():
                # Color by validation status
                validation_status = hotspot['validation']['validation_status']
                if validation_status == 'STRONGLY_CONFIRMED':
                    color = 'red'
                    icon_color = 'white'
                elif validation_status == 'CONFIRMED':
                    color = 'orange'
                    icon_color = 'white'
                elif validation_status == 'PARTIALLY_CONFIRMED':
                    color = 'lightblue'
                    icon_color = 'black'
                else:
                    color = 'gray'
                    icon_color = 'white'
                
                # Create popup
                popup_html = f"""
                <div style="font-family: Arial; width: 300px;">
                    <h4>🚨 Hotspot #{hotspot['hotspot_id']}</h4>
                    <p><b>Primary Issue:</b> {hotspot['primary_theme']}</p>
                    <p><b>Reports:</b> {hotspot['total_reports']}</p>
                    <p><b>Urgency:</b> {hotspot['urgency_score']}/100</p>
                    <p><b>AI Sentiment:</b> {hotspot['ai_analysis']['sentiment'].title()}</p>
                    <p><b>AI Severity:</b> {hotspot['ai_analysis']['severity'].title()}</p>
                    <p><b>Validation:</b> {validation_status.replace('_', ' ').title()}</p>
                    <hr>
                    <p><b>Sensor Data:</b><br>
                    {hotspot['sensor_data']['abnormal_events']} abnormal events<br>
                    {hotspot['sensor_data']['brake_events']} brakes, 
                    {hotspot['sensor_data']['swerve_events']} swerves</p>
                </div>
                """
                
                # FIXED SIZE MARKER - radius is constant at 10
                folium.CircleMarker(
                    location=[hotspot['center_lat'], hotspot['center_lng']],
                    radius=10,  # FIXED SIZE FOR ALL HOTSPOTS
                    popup=folium.Popup(popup_html, max_width=350),
                    tooltip=f"Hotspot #{hotspot['hotspot_id']}: {hotspot['primary_theme']}",
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.7,
                    weight=2
                ).add_to(m)
            
            folium_static(m, width=800, height=600)
        
        with col2:
            st.subheader("📊 Statistics")
            
            # Validation status pie chart
            validation_counts = perception_hotspots['validation'].apply(
                lambda x: x['validation_status']).value_counts()
            
            fig = px.pie(
                values=validation_counts.values,
                names=validation_counts.index,
                title='Sensor Validation',
                color_discrete_map={
                    'STRONGLY_CONFIRMED': '#DC143C',
                    'CONFIRMED': '#FF4500',
                    'PARTIALLY_CONFIRMED': '#FFA500',
                    'INCONCLUSIVE': '#FFD700',
                    'NO_SENSOR_DATA': '#808080'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Top themes
            st.subheader("🔝 Top Issues")
            theme_counts = perception_hotspots['primary_theme'].value_counts().head(5)
            for theme, count in theme_counts.items():
                st.write(f"**{theme}:** {count}")
        
        st.markdown("---")
        
        # ========== ENHANCED AI ANALYSIS DISPLAY ==========
        st.subheader("🔍 Detailed AI Analysis")
        
        # Debug toggle
        show_debug = st.checkbox("🐛 Show Debug Info", value=False, 
                                help="Show technical details about AI analysis")
        
        selected_hotspot = st.selectbox(
            "Select a hotspot to analyze",
            options=perception_hotspots['hotspot_id'].tolist(),
            format_func=lambda x: f"Hotspot #{x} - {perception_hotspots[perception_hotspots['hotspot_id']==x]['primary_theme'].iloc[0]}"
        )
        
        if selected_hotspot:
            hotspot_data = perception_hotspots[perception_hotspots['hotspot_id'] == selected_hotspot].iloc[0]
            
            # ========== HEADER WITH KEY INFO ==========
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"### 🚨 Hotspot #{selected_hotspot}")
                st.markdown(f"**Primary Issue:** {hotspot_data['primary_theme']}")
            
            with col2:
                validation_status = hotspot_data['validation']['validation_status']
                status_emoji = {
                    'STRONGLY_CONFIRMED': '🔴',
                    'CONFIRMED': '🟠',
                    'PARTIALLY_CONFIRMED': '🟡',
                    'INCONCLUSIVE': '⚪',
                    'NO_SENSOR_DATA': '⚫'
                }.get(validation_status, '⚪')
                st.metric("Validation", f"{status_emoji} {validation_status.replace('_', ' ').title()}")
            
            with col3:
                st.metric("Urgency Score", f"{hotspot_data['urgency_score']}/100")
            
            st.markdown("---")
            
            # ========== AI ANALYSIS - PROMINENT DISPLAY ==========
            st.markdown("### 🤖 AI-Powered Sentiment Analysis")
            
            ai_analysis = hotspot_data['ai_analysis']
            
            # Check if AI was actually used
            analysis_method = ai_analysis.get('method', 'unknown')
            
            if analysis_method == 'groq_ai':
                st.success("✅ **Analysis Method:** Groq AI (llama-3.3-70b)")
            elif analysis_method == 'keyword_fallback':
                st.warning("⚠️ **Analysis Method:** Keyword-based fallback (Groq not available)")
            else:
                st.info(f"ℹ️ **Analysis Method:** {analysis_method}")
            
            # Display AI analysis in a nice card
            with st.container():
                col1, col2 = st.columns(2)
                
                with col1:
                    # Sentiment with emoji
                    sentiment_emoji = {
                        'very_negative': '😢',
                        'negative': '😟',
                        'neutral': '😐',
                        'positive': '🙂',
                        'very_positive': '😊'
                    }.get(ai_analysis['sentiment'], '❓')
                    
                    st.markdown(f"**Sentiment:** {sentiment_emoji} {ai_analysis['sentiment'].replace('_', ' ').title()}")
                    
                    # Severity with color
                    severity = ai_analysis['severity']
                    severity_emoji = {
                        'critical': '🔴',
                        'high': '🟠',
                        'medium': '🟡',
                        'low': '🟢'
                    }.get(severity, '⚪')
                    
                    st.markdown(f"**Severity:** {severity_emoji} {severity.title()}")
                
                with col2:
                    st.markdown(f"**Reports Analyzed:** {hotspot_data['total_reports']}")
                    date_range = hotspot_data['date_range']
                    if date_range['first_report'] and date_range['last_report']:
                        days_span = (date_range['last_report'] - date_range['first_report']).days
                        st.markdown(f"**Date Span:** {days_span} days")
            
            # Summary in highlighted box
            st.info(f"**📝 AI Summary:** {ai_analysis['summary']}")
            
            # Key issues as colored tags
            if ai_analysis['key_issues']:
                st.markdown("**🏷️ Key Issues Identified by AI:**")
                
                # Create a nice tag display
                issues_html = ""
                for issue in ai_analysis['key_issues']:
                    issue_display = issue.replace('_', ' ').title()
                    issues_html += f'<span style="background-color: #ff4b4b; color: white; padding: 5px 10px; margin: 5px; border-radius: 5px; display: inline-block;">{issue_display}</span>'
                
                st.markdown(issues_html, unsafe_allow_html=True)
            
            # Debug info if enabled
            if show_debug:
                with st.expander("🐛 Debug: Raw AI Response"):
                    st.json(ai_analysis)
            
            st.markdown("---")
            
            # ========== OVERVIEW METRICS ==========
            st.subheader("📊 Overview Metrics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Reports", int(hotspot_data['total_reports']))
            
            with col2:
                st.metric("Urgency", f"{hotspot_data['urgency_score']}/100")
            
            with col3:
                st.metric("Validation", hotspot_data['validation']['validation_status'].replace('_', ' ').title())
            
            with col4:
                st.metric("Sensor Events", hotspot_data['sensor_data']['abnormal_events'])
            
            st.markdown("---")
            
            # ========== THEME BREAKDOWN ==========
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📋 Report Themes")
                theme_df = pd.DataFrame(
                    list(hotspot_data['theme_counts'].items()),
                    columns=['Theme', 'Count']
                ).sort_values('Count', ascending=False)
                
                fig = px.bar(
                    theme_df,
                    x='Count',
                    y='Theme',
                    orientation='h',
                    title='Issues Reported',
                    color='Count',
                    color_continuous_scale='Reds'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### 📱 Report Types")
                for rtype, count in hotspot_data['report_types'].items():
                    st.write(f"**{rtype.title()}:** {count} reports")
                
                # Show average rating if available
                if hotspot_data.get('avg_rating'):
                    st.metric("Average Rating", f"{hotspot_data['avg_rating']:.1f}/5", 
                             help="Lower rating = worse condition")
            
            st.markdown("---")
            
            # ========== SENSOR DATA VALIDATION ==========
            st.subheader("📡 Sensor Data Validation")
            
            sensor_data = hotspot_data['sensor_data']
            validation = hotspot_data['validation']
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Hard Brakes", sensor_data['brake_events'])
                st.metric("Swerves", sensor_data['swerve_events'])
            
            with col2:
                st.metric("Pothole Events", sensor_data['pothole_events'])
                st.metric("Max Severity", sensor_data['max_severity'])
            
            with col3:
                st.metric("Unique Cyclists", sensor_data['unique_devices'])
                st.metric("Avg Severity", f"{sensor_data['avg_severity']:.1f}")
            
            # Validation details
            st.markdown(f"**Validation Status:** {validation['validation_status'].replace('_', ' ')} ({validation['confidence']} confidence)")
            
            if validation['matches']:
                st.success("**✅ Evidence Supporting Reports:**")
                for match in validation['matches']:
                    st.write(f"• {match}")
            
            if validation['conflicts']:
                st.warning("**⚠️ Conflicting Evidence:**")
                for conflict in validation['conflicts']:
                    st.write(f"• {conflict}")
            
            st.markdown("---")
            
            # ========== USER COMMENTS ==========
            st.subheader("💬 User Comments")
            
            comments = hotspot_data['comments']
            
            if comments:
                # Show first 5 comments prominently
                for i, comment in enumerate(comments[:5], 1):
                    with st.container():
                        st.markdown(f"**Comment {i}:**")
                        st.write(f"_{comment}_")
                        st.markdown("---")
                
                # Show remaining in expander
                if len(comments) > 5:
                    with st.expander(f"📄 View {len(comments) - 5} more comments"):
                        for i, comment in enumerate(comments[5:], 6):
                            st.write(f"**{i}.** {comment}")
            else:
                st.info("No comments available for this hotspot")
            
            st.markdown("---")
            
            # ========== LOCATION ==========
            st.subheader("📍 Location & Street View")
            
            lat = hotspot_data['center_lat']
            lng = hotspot_data['center_lng']
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Create mini map
                mini_map = folium.Map(location=[lat, lng], zoom_start=16)
                folium.Marker(
                    [lat, lng],
                    popup=f"Hotspot #{selected_hotspot}",
                    icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
                ).add_to(mini_map)
                folium_static(mini_map, width=400, height=300)
            
            with col2:
                st.write(f"**Coordinates:**")
                st.write(f"Lat: {lat:.6f}")
                st.write(f"Lng: {lng:.6f}")
                
                street_view_url = STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lng, heading=0)
                st.markdown(f"### [🔍 Open in Street View]({street_view_url})")
                st.markdown(f"### [🗺️ Open in Google Maps](https://www.google.com/maps?q={lat},{lng})")

# ==================== TAB 2: TREND ANALYSIS ====================
with tab2:
    st.header("📈 Trend Analysis")
    st.markdown("Analyzing road usage patterns and detecting anomalies over time")
    
    # Get time series data
    with st.spinner("Preparing time series data from Athena..."):
        time_series = prepare_time_series(freq='D')
    
    if time_series.empty:
        st.warning("⚠️ No time series data available for trend analysis.")
        st.info("This might be due to:")
        st.write("- No data in the Athena table")
        st.write("- AWS connection issues")
        st.write("- Insufficient data for time series analysis")
    else:
        # Date range selector
        st.subheader("📅 Date Range Selection")
        col1, col2 = st.columns(2)
        
        datetime_col = 'datetime' if 'datetime' in time_series.columns else 'date'
        min_date = pd.to_datetime(time_series[datetime_col].min()).date()
        max_date = pd.to_datetime(time_series[datetime_col].max()).date()
        
        with col1:
            start_date_ts = st.date_input(
                "Start Date",
                value=min_date,
                min_value=min_date,
                max_value=max_date,
                key="ts_start_date"
            )
        
        with col2:
            end_date_ts = st.date_input(
                "End Date",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                key="ts_end_date"
            )
        
        # Filter time series
        filtered_ts = time_series[
            (pd.to_datetime(time_series[datetime_col]).dt.date >= start_date_ts) &
            (pd.to_datetime(time_series[datetime_col]).dt.date <= end_date_ts)
        ]
        
        if filtered_ts.empty:
            st.warning("⚠️ No data available for selected date range.")
        else:
            # Detect anomalies
            with st.spinner("Detecting anomalies..."):
                ts_with_anomalies = detect_anomalies(filtered_ts, column='unique_users')
            
            # Calculate trends
            trend_stats = calculate_trends(filtered_ts, column='unique_users')
            
            # Display key insights
            st.subheader("📊 Key Insights")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Trend Direction",
                    trend_stats.get('trend_direction', 'N/A').title()
                )
            
            with col2:
                pct_change = trend_stats.get('percent_change', 0)
                st.metric(
                    "Overall Change",
                    f"{pct_change:+.1f}%",
                    delta=f"{pct_change:.1f}%"
                )
            
            with col3:
                anomaly_count = len(ts_with_anomalies[ts_with_anomalies.get('is_anomaly', False) == True]) if not ts_with_anomalies.empty else 0
                st.metric("Anomalies Detected", anomaly_count)
            
            with col4:
                avg_daily = trend_stats.get('mean_value', 0)
                st.metric("Avg Daily Users", f"{avg_daily:.0f}")
            
            st.markdown("---")
            
            # Time series chart
            st.subheader("📈 Usage Trends Over Time")
            
            anomalies = ts_with_anomalies[ts_with_anomalies.get('is_anomaly', False) == True] if not ts_with_anomalies.empty else pd.DataFrame()
            ts_chart = create_time_series_chart(
                ts_with_anomalies,
                column='unique_users',
                anomalies_df=anomalies if not anomalies.empty else None
            )
            st.plotly_chart(ts_chart, use_container_width=True)
            
            st.markdown("---")
            
            # Anomaly Analysis
            st.subheader("⚠️ Anomaly Analysis")
            
            if not anomalies.empty:
                # Find usage drops
                drops = find_usage_drops(filtered_ts, column='unique_users', drop_threshold=0.3)
                
                if not drops.empty:
                    st.markdown("#### 📉 Significant Usage Drops")
                    st.write("These dates show significant drops in road usage and may warrant investigation:")
                    
                    # Display top drops
                    top_drops = drops.nlargest(5, 'deviation_pct', keep='all')[
                        [datetime_col, 'unique_users', 'baseline', 'deviation_pct']
                    ].copy()
                    top_drops['deviation_pct'] = top_drops['deviation_pct'].round(1)
                    top_drops.columns = ['Date', 'Actual Users', 'Expected (Baseline)', 'Drop %']
                    
                    st.dataframe(top_drops, use_container_width=True, hide_index=True)
                    
                    # Investigate button
                    st.markdown("**Possible reasons for drops:**")
                    st.write("- Weather events (storms, snow)")
                    st.write("- Road closures or construction")
                    st.write("- Public holidays or special events")
                    st.write("- Data collection issues")
                else:
                    st.info("✅ No significant usage drops detected in the selected period.")
                
                # Spikes
                spikes = ts_with_anomalies[ts_with_anomalies.get('anomaly_type', '') == 'spike'] if not ts_with_anomalies.empty else pd.DataFrame()
                if not spikes.empty:
                    st.markdown("#### 📈 Usage Spikes")
                    st.write(f"Detected {len(spikes)} dates with unusually high activity")
                    
                    with st.expander("View spike details"):
                        spike_details = spikes[[datetime_col, 'unique_users', 'rolling_mean']].copy()
                        spike_details.columns = ['Date', 'Count', 'Expected (7-day avg)']
                        st.dataframe(spike_details, use_container_width=True, hide_index=True)
            else:
                st.info("✅ No anomalies detected in the selected period.")
            
            st.markdown("---")
            
            # Seasonal Patterns
            st.subheader("📆 Seasonal Patterns")
            
            seasonal = analyze_seasonal_patterns(filtered_ts, column='unique_users')
            
            if seasonal and 'weekly_pattern' in seasonal:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### Day of Week Pattern")
                    weekly_df = pd.DataFrame(
                        list(seasonal['weekly_pattern'].items()),
                        columns=['Day', 'Avg Users']
                    )
                    weekly_df['Day'] = weekly_df['Day'].map({
                        0: 'Monday', 1: 'Tuesday', 2: 'Wednesday',
                        3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'
                    })
                    
                    weekly_chart = px.bar(
                        weekly_df,
                        x='Day',
                        y='Avg Users',
                        title='Average Users by Day of Week',
                        color='Avg Users',
                        color_continuous_scale='Blues'
                    )
                    st.plotly_chart(weekly_chart, use_container_width=True)
                
                with col2:
                    st.markdown("#### Weekday vs Weekend")
                    weekday_avg = seasonal.get('weekday_avg', 0)
                    weekend_avg = seasonal.get('weekend_avg', 0)
                    
                    comparison_df = pd.DataFrame({
                        'Period': ['Weekday', 'Weekend'],
                        'Avg Users': [weekday_avg, weekend_avg]
                    })
                    
                    comparison_chart = px.bar(
                        comparison_df,
                        x='Period',
                        y='Avg Users',
                        title='Weekday vs Weekend Comparison',
                        color='Period',
                        color_discrete_map={'Weekday': '#1f77b4', 'Weekend': '#ff7f0e'}
                    )
                    st.plotly_chart(comparison_chart, use_container_width=True)
                    
                    # Calculate difference
                    if weekend_avg > 0:
                        diff_pct = ((weekday_avg - weekend_avg) / weekend_avg) * 100
                        if diff_pct > 10:
                            st.success(f"Weekdays show {diff_pct:.1f}% more activity than weekends")
                        elif diff_pct < -10:
                            st.info(f"Weekends show {abs(diff_pct):.1f}% more activity than weekdays")
                        else:
                            st.info("Similar activity levels on weekdays and weekends")
            
            st.markdown("---")
            
            # Additional Insights
            st.subheader("💡 Additional Insights")
            
            with st.expander("📊 Statistical Summary"):
                summary = get_time_series_summary(filtered_ts, column='unique_users')
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Total Observations:** {summary.get('total_observations', 0):,}")
                    st.write(f"**Mean:** {summary.get('mean', 0):.2f}")
                    st.write(f"**Median:** {summary.get('median', 0):.2f}")
                    st.write(f"**Std Dev:** {summary.get('std', 0):.2f}")
                
                with col2:
                    st.write(f"**Min:** {summary.get('min', 0):.0f}")
                    st.write(f"**Max:** {summary.get('max', 0):.0f}")
                    st.write(f"**Range:** {summary.get('range', 0):.0f}")
                    st.write(f"**CV:** {summary.get('coefficient_of_variation', 0):.2f}%")
            
            with st.expander("🔍 Investigative Questions"):
                st.markdown("""
                Based on the trend analysis, here are some questions worth investigating:
                
                **For Usage Drops:**
                - Were there any road closures or construction during these periods?
                - Did weather conditions impact road usage?
                - Were there any major events or holidays?
                - Are there patterns in specific routes or areas?
                
                **For Usage Spikes:**
                - What caused the increased activity?
                - Were there any special events or diversions?
                - Is this a recurring pattern?
                
                **For Trend Changes:**
                - What factors might explain the overall trend direction?
                - Are there infrastructure changes or new routes?
                - Has population or traffic pattern shifted?
                """)

# ==================== FOOTER ==========
st.markdown("---")
st.markdown("### 📌 About This Dashboard")

with st.expander("ℹ️ How It Works"):
    st.markdown("""
    ### 🤖 AI-Powered Analysis
    
    This dashboard uses **Groq AI (llama-3.3-70b)** to analyze user perception reports:
    
    1. **Clustering:** Groups nearby reports (within 25-100m radius)
    2. **AI Analysis:** Groq AI analyzes the sentiment and severity of reports
    3. **Sensor Validation:** Cross-references with accelerometer data from cyclists
    4. **Urgency Scoring:** Combines AI insights with frequency and sensor data
    
    ### 📊 Data Sources
    
    - **Sensor Data:** {sensor_metrics['total_readings']:,} readings from AWS Athena
    - **Infrastructure Reports:** {len(infra_df):,} user reports
    - **Ride Reports:** {len(ride_df):,} incident reports
    
    ### 🎯 Validation Levels
    
    - 🔴 **Strongly Confirmed:** Multiple sensor events match user reports
    - 🟠 **Confirmed:** Sensor data supports reports
    - 🟡 **Partially Confirmed:** Some evidence in sensor data
    - ⚪ **Inconclusive:** Limited sensor data available
    - ⚫ **No Sensor Data:** No sensor readings in area
    
    ### 🔧 Settings
    
    Adjust clustering radius and minimum reports in the sidebar to fine-tune hotspot detection.
    """.format(sensor_metrics=sensor_metrics, infra_df=infra_df, ride_df=ride_df))

with st.expander("❓ FAQ"):
    st.markdown("""
    **Q: What is the difference between perception reports and sensor data?**
    
    A: Perception reports are submitted by users describing what they experienced. Sensor data comes from accelerometers on bikes measuring actual road conditions objectively.
    
    **Q: Why do some hotspots show "No Sensor Data"?**
    
    A: This means no cyclists with sensors rode through that area during the selected time period.
    
    **Q: How is urgency score calculated?**
    
    A: Urgency combines AI-detected severity, number of reports, user ratings, and how long the issue has persisted.
    
    **Q: Can I trust the AI analysis?**
    
    A: The AI (Groq's llama-3.3-70b) is trained on billions of text examples and provides sentiment analysis. We also show you the original comments so you can verify the AI's interpretation.
    
    **Q: What should I do with this information?**
    
    A: Use the hotspots to prioritize road maintenance, investigate causes of usage drops, and validate user complaints with objective sensor data.
    """)

st.markdown("---")
st.caption("🚴‍♂️ Spinovate Safety Dashboard | Powered by Groq AI & AWS Athena")