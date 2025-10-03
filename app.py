"""
Dublin Road Safety Dashboard
Main Streamlit application with AWS Athena backend
UPDATED: Strict hotspot filtering (10-20 hotspots max)
"""
import streamlit as st
from streamlit_folium import folium_static
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

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

# Display date range from sensor data
if sensor_metrics['earliest_reading'] and sensor_metrics['latest_reading']:
    st.sidebar.write(f"**Data Range:** {sensor_metrics['earliest_reading']} to {sensor_metrics['latest_reading']}")

st.sidebar.markdown("---")

# Sidebar - Hotspot Settings (UPDATED WITH STRICT DEFAULTS)
st.sidebar.subheader("🎯 Hotspot Detection")
st.sidebar.info("⚠️ **Strict Mode**: Only showing the most dangerous locations")

severity_threshold = st.sidebar.slider(
    "Minimum Severity",
    min_value=2,
    max_value=4,
    value=3,  # CHANGED: Default to 3 (high severity only)
    help="Minimum severity level - set to 3 or 4 to see only dangerous hotspots"
)

min_incidents = st.sidebar.slider(
    "Minimum Incidents",
    min_value=5,
    max_value=50,
    value=15,  # CHANGED: Default to 15 (was 3)
    step=5,
    help="Minimum number of incidents required - higher = fewer but more critical hotspots"
)

top_n_hotspots = st.sidebar.slider(
    "Max Hotspots to Show",
    min_value=5,
    max_value=50,
    value=20,  # NEW: Cap at 20 by default
    step=5,
    help="Show only the top N most dangerous hotspots"
)

perception_radius = st.sidebar.slider(
    "Perception Match Radius (m)",
    min_value=10,
    max_value=50,
    value=25,
    help="Radius in meters to match perception reports to hotspots"
)

# Add filtering explanation
with st.sidebar.expander("ℹ️ How Filtering Works"):
    st.markdown("""
    **Hotspots are filtered using:**
    
    1. **Minimum Incidents**: At least N high-severity events
    2. **Statistical Significance**: 1.5+ standard deviations above average
    3. **Risk Score**: Composite score combining frequency + severity
    4. **Temporal Consistency**: Must occur on 2+ different days
    
    **Result**: Only the 10-20 most critical locations are shown.
    """)

# Main content - Tabs
tab1, tab2 = st.tabs(["📍 Hotspot Analysis", "📈 Trend Analysis"])

# ==================== TAB 1: HOTSPOT ANALYSIS WITH DATE SLICER ====================
with tab1:
    st.header("Hotspot Analysis")
    st.markdown("Identifying dangerous road segments using sensor data and perception reports")
    
    # ========== DATE SLICER SECTION ==========
    st.subheader("📅 Date Range Filter")
    
    # Get date range from sensor data
    try:
        earliest = pd.to_datetime(sensor_metrics['earliest_reading']).date()
        latest = pd.to_datetime(sensor_metrics['latest_reading']).date()
    except:
        # Fallback to reasonable defaults if dates not available
        latest = datetime.now().date()
        earliest = latest - timedelta(days=90)
    
    # Create date input columns
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=earliest,
            min_value=earliest,
            max_value=latest,
            help="Select the start date for hotspot analysis"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=latest,
            min_value=earliest,
            max_value=latest,
            help="Select the end date for hotspot analysis"
        )
    
    with col3:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("🔄 Reset Dates", use_container_width=True):
            st.rerun()
    
    # Validate date range
    if start_date > end_date:
        st.error("⚠️ Start date must be before end date!")
        st.stop()
    
    # Show selected date range
    days_selected = (end_date - start_date).days + 1
    st.info(f"📊 Analyzing data from **{start_date.strftime('%d %b %Y')}** to **{end_date.strftime('%d %b %Y')}** ({days_selected} days)")
    
    st.markdown("---")
    
    # ========== HOTSPOT DETECTION WITH STRICT FILTERING ==========
    with st.spinner("Detecting critical hotspots for selected date range..."):
        hotspots = detect_hotspots(
            severity_threshold=severity_threshold,
            min_samples=min_incidents,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        # Apply top_n limit
        if not hotspots.empty and len(hotspots) > top_n_hotspots:
            # Sort by risk_score if available, otherwise by incident_count
            if 'risk_score' in hotspots.columns:
                hotspots = hotspots.nlargest(top_n_hotspots, 'risk_score')
            else:
                hotspots = hotspots.nlargest(top_n_hotspots, 'incident_count')
    
    if hotspots.empty:
        st.warning("No critical hotspots detected with current settings.")
        
        # Enhanced suggestions
        with st.expander("💡 Why no hotspots found?"):
            st.write("**Your current settings are very strict. This could mean:**")
            st.write("✅ Good news! No extremely dangerous spots in this period")
            st.write("OR")
            st.write("⚙️ Settings might be too restrictive")
            st.write("")
            st.write("**To see more hotspots, try:**")
            st.write(f"- Lower 'Minimum Severity' (currently: {severity_threshold})")
            st.write(f"- Reduce 'Minimum Incidents' (currently: {min_incidents})")
            st.write(f"- Increase 'Max Hotspots' (currently: {top_n_hotspots})")
            st.write("- Select a longer date range")
    else:
        # Show filtering summary
        st.success(f"✅ Found **{len(hotspots)}** critical hotspots using strict filtering")
        
        # Show filtering stats if available
        if 'risk_score' in hotspots.columns:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Avg Risk Score", f"{hotspots['risk_score'].mean():.1f}")
            with col2:
                if 'event_zscore' in hotspots.columns:
                    above_avg = (hotspots['event_zscore'] >= 1.5).sum()
                    st.metric("Statistically Significant", f"{above_avg}/{len(hotspots)}")
            with col3:
                if 'days_with_events' in hotspots.columns:
                    st.metric("Avg Days Active", f"{hotspots['days_with_events'].mean():.1f}")
        
        # Filter perception reports by date range
        infra_df_filtered = infra_df.copy()
        ride_df_filtered = ride_df.copy()
        
        if 'datetime' in infra_df_filtered.columns:
            infra_df_filtered = infra_df_filtered[
                (pd.to_datetime(infra_df_filtered['datetime']).dt.date >= start_date) &
                (pd.to_datetime(infra_df_filtered['datetime']).dt.date <= end_date)
            ]
        
        if 'datetime' in ride_df_filtered.columns:
            ride_df_filtered = ride_df_filtered[
                (pd.to_datetime(ride_df_filtered['datetime']).dt.date >= start_date) &
                (pd.to_datetime(ride_df_filtered['datetime']).dt.date <= end_date)
            ]
        
        # Match perception reports using filtered data
        with st.spinner("Matching perception reports to hotspots..."):
            matched_hotspots = match_perception_to_hotspots(
                hotspots,
                infra_df_filtered,
                ride_df_filtered,
                radius_m=perception_radius
            )
        
        # Get statistics
        stats = get_hotspot_statistics(matched_hotspots)
        
        # Display metrics
        st.subheader("📊 Key Metrics for Selected Period")
        metrics = {
            "Critical Hotspots": stats['total_hotspots'],
            "Total Incidents": stats['total_incidents'],
            "Avg Severity": f"{stats['avg_severity']:.2f}",
            "High Risk": stats.get('critical_hotspots', 0)
        }
        create_metric_cards(metrics)
        
        # Show perception reports stats for the filtered period
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Infrastructure Reports (Period)", len(infra_df_filtered))
        with col2:
            st.metric("Ride Reports (Period)", len(ride_df_filtered))
        
        st.markdown("---")
        
        # Layout: Map and Charts
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🗺️ Critical Hotspot Map")
            show_perception = st.checkbox("Show Perception Reports", value=True)
            
            # Create map with filtered data
            hotspot_map = create_hotspot_map(
                matched_hotspots,
                infra_df_filtered if show_perception else None,
                ride_df_filtered if show_perception else None,
                show_perception=show_perception
            )
            folium_static(hotspot_map, width=800, height=600)
        
        with col2:
            st.subheader("📊 Risk Distribution")
            
            # Show risk categories if available
            if 'risk_category' in matched_hotspots.columns:
                risk_counts = matched_hotspots['risk_category'].value_counts()
                
                fig = px.bar(
                    x=risk_counts.index,
                    y=risk_counts.values,
                    labels={'x': 'Risk Category', 'y': 'Count'},
                    title='Hotspots by Risk Level',
                    color=risk_counts.index,
                    color_discrete_map={
                        'Medium': '#FFD700',
                        'High': '#FFA500', 
                        'Critical': '#FF4500',
                        'Extreme': '#DC143C'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                severity_chart = create_severity_distribution_chart(matched_hotspots)
                st.plotly_chart(severity_chart, use_container_width=True)
            
            # Top hotspots for the period
            st.subheader("🔝 Top 5 Critical Hotspots")
            
            # Sort by risk_score if available
            if 'risk_score' in matched_hotspots.columns:
                top_cols = ['hotspot_id', 'incident_count', 'risk_score', 'total_perception_reports']
                top_hotspots = matched_hotspots.nlargest(5, 'risk_score')[top_cols].copy()
                top_hotspots['risk_score'] = top_hotspots['risk_score'].round(1)
            else:
                top_cols = ['hotspot_id', 'incident_count', 'avg_severity', 'total_perception_reports']
                top_hotspots = matched_hotspots.nlargest(5, 'incident_count')[top_cols]
            
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
                if 'risk_score' in hotspot_data:
                    st.metric("Risk Score", f"{hotspot_data['risk_score']:.1f}")
                else:
                    st.metric("Devices", int(hotspot_data.get('device_count', 0)))
            
            with col3:
                st.metric("Perception Reports", int(hotspot_data['total_perception_reports']))
                
                # Street View link
                lat = hotspot_data['latitude']
                lng = hotspot_data['longitude']
                street_view_url = STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lng, heading=0)
                st.markdown(f"[🔍 View in Google Street View]({street_view_url})")
            
            # Show additional metrics if available
            if 'days_with_events' in hotspot_data:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Days with Events", int(hotspot_data['days_with_events']))
                with col2:
                    if 'unique_devices' in hotspot_data:
                        st.metric("Unique Cyclists Affected", int(hotspot_data['unique_devices']))
            
            # Perception reports details
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
                    
                    # Sentiment Analysis
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
    
    # Get time series data
    with st.spinner("Preparing time series data from Athena..."):
        time_series = prepare_time_series(freq='D')
    
    if time_series.empty:
        st.warning("No time series data available for trend analysis.")
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
            st.warning("No data available for selected date range.")
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
                    st.info("No significant usage drops detected in the selected period.")
                
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
                st.info("No anomalies detected in the selected period.")
            
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