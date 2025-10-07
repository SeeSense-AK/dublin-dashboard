"""
Spinovate Safety Dashboard - Updated with Enhanced Hotspot Detection
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import folium
from streamlit_folium import folium_static

# Import custom modules
from src.enhanced_hotspot_detector import create_complete_hotspots
from src.athena_database import get_athena_database
from utils.constants import STREET_VIEW_URL_TEMPLATE

# Page config
st.set_page_config(
    page_title="Spinovate Safety Dashboard",
    page_icon="🚴‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("🚴‍♂️ Spinovate Safety Dashboard")
st.markdown("### AI-Powered Road Safety Analysis for Dublin")

# Load data
@st.cache_resource
def init_database():
    return get_athena_database()

@st.cache_data(ttl=3600)
def load_perception_data():
    infra_df = pd.read_csv('dublin_infra_reports_dublin2025_upto20250924.csv')
    ride_df = pd.read_csv('dublin_ride_reports_dublin2025_upto20250924.csv')
    
    for df in [infra_df, ride_df]:
        if 'date' in df.columns and 'time' in df.columns:
            try:
                df['datetime'] = pd.to_datetime(
                    df['date'] + ' ' + df['time'],
                    format='%d-%m-%Y %H:%M:%S',
                    dayfirst=True,
                    errors='coerce'
                )
            except:
                df['datetime'] = pd.to_datetime(
                    df['date'] + ' ' + df['time'],
                    dayfirst=True,
                    errors='coerce'
                )
    
    return infra_df, ride_df

try:
    db = init_database()
    infra_df, ride_df = load_perception_data()
    metrics = db.get_dashboard_metrics()
except Exception as e:
    st.error(f"❌ Error loading data: {e}")
    st.stop()

# Sidebar
st.sidebar.title("⚙️ Settings")
st.sidebar.subheader("📊 Data Overview")
st.sidebar.metric("Total Readings", f"{metrics['total_readings']:,}")
st.sidebar.metric("Unique Cyclists", metrics['unique_devices'])
st.sidebar.metric("Abnormal Events", f"{metrics['abnormal_events']:,}")
st.sidebar.metric("Perception Reports", len(infra_df) + len(ride_df))

st.sidebar.markdown("---")

# Tabs
tab1, tab2 = st.tabs(["📍 Hotspot Analysis", "📈 Trend Analysis"])

# ==================== TAB 1: HOTSPOT ANALYSIS ====================
with tab1:
    st.header("🚨 Hotspot Analysis")
    st.markdown("Combining sensor data with user perception reports")
    
    # Date range selector
    st.subheader("📅 Select Date Range for Sensor Data")
    
    try:
        min_date = pd.to_datetime(metrics['earliest_reading']).date()
        max_date = pd.to_datetime(metrics['latest_reading']).date()
    except:
        max_date = datetime.now().date()
        min_date = max_date - timedelta(days=90)
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
    
    if start_date > end_date:
        st.error("⚠️ Start date must be before end date!")
        st.stop()
    
    days_selected = (end_date - start_date).days + 1
    st.info(f"📊 Analyzing {days_selected} days of sensor data. Perception reports searched across ALL TIME.")
    
    st.markdown("---")
    
    # Detection parameters
    col1, col2 = st.columns(2)
    with col1:
        min_events = st.slider("Minimum Events per Hotspot", 2, 10, 3)
    with col2:
        top_n = st.slider("Number of Hotspots to Analyze", 5, 30, 20)
    
    if st.button("🔍 Detect Hotspots", type="primary", use_container_width=True):
        st.session_state.hotspots_detected = True
    
    if 'hotspots_detected' not in st.session_state:
        st.session_state.hotspots_detected = False
    
    if st.session_state.hotspots_detected:
        with st.spinner("🔬 Detecting hotspots and analyzing with AI..."):
            hotspots = create_complete_hotspots(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                infra_df=infra_df,
                ride_df=ride_df,
                min_events=min_events,
                top_n=top_n
            )
        
        if hotspots.empty:
            st.warning("⚠️ No hotspots found with current parameters. Try reducing minimum events or expanding date range.")
        else:
            st.success(f"✅ Detected {len(hotspots)} critical hotspots")
            
            # Key Metrics
            st.subheader("📊 Overview Metrics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Hotspots", len(hotspots))
            with col2:
                total_events = hotspots['event_count'].sum()
                st.metric("Total Events", int(total_events))
            with col3:
                avg_severity = hotspots['avg_severity'].mean()
                st.metric("Avg Severity", f"{avg_severity:.1f}/10")
            with col4:
                total_reports = hotspots['perception_data'].apply(lambda x: x['total_reports']).sum()
                st.metric("Total User Reports", int(total_reports))
            
            st.markdown("---")
            
            # Interactive Map
            st.subheader("🗺️ Interactive Hotspot Map")
            
            m = folium.Map(
                location=[hotspots['center_lat'].mean(), hotspots['center_lng'].mean()],
                zoom_start=12
            )
            
            for idx, hotspot in hotspots.iterrows():
                # Color by urgency
                urgency = hotspot['urgency_score']
                if urgency >= 80:
                    color = '#DC143C'  # Crimson
                elif urgency >= 60:
                    color = '#FF4500'  # Orange Red
                elif urgency >= 40:
                    color = '#FFA500'  # Orange
                else:
                    color = '#FFD700'  # Gold
                
                # Create popup
                popup_html = f"""
                <div style="font-family: Arial; width: 300px;">
                    <h4 style="color: {color};">🚨 Hotspot #{hotspot['hotspot_id']}</h4>
                    <p><b>Events:</b> {hotspot['event_count']}</p>
                    <p><b>Avg Severity:</b> {hotspot['avg_severity']:.1f}/10</p>
                    <p><b>User Reports:</b> {hotspot['perception_data']['total_reports']}</p>
                    <p><b>Urgency Score:</b> {hotspot['urgency_score']}/100</p>
                    <hr>
                    <p style="font-size: 12px;"><b>Top Event:</b> {max(hotspot['event_distribution'].items(), key=lambda x: x[1])[0]}</p>
                    <a href="{STREET_VIEW_URL_TEMPLATE.format(lat=hotspot['center_lat'], lng=hotspot['center_lng'], heading=0)}" 
                       target="_blank" style="color: #4285f4;">📍 View in Street View</a>
                </div>
                """
                
                folium.CircleMarker(
                    location=[hotspot['center_lat'], hotspot['center_lng']],
                    radius=10,
                    popup=folium.Popup(popup_html, max_width=350),
                    tooltip=f"Hotspot #{hotspot['hotspot_id']}",
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.7,
                    weight=2
                ).add_to(m)
            
            folium_static(m, width=1200, height=600)
            
            st.markdown("---")
            
            # Critical Hotspots Section
            st.subheader("🔝 Critical Hotspots - Detailed Analysis")
            
            for idx, hotspot in hotspots.iterrows():
                with st.expander(
                    f"🚨 Hotspot #{hotspot['hotspot_id']}: {max(hotspot['event_distribution'].items(), key=lambda x: x[1])[0].title()} Issues",
                    expanded=(idx == 0)  # First one expanded
                ):
                    # Overview Metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Sensor Events", int(hotspot['event_count']))
                    with col2:
                        st.metric("User Reports", int(hotspot['perception_data']['total_reports']))
                    with col3:
                        st.metric("Avg Severity", f"{hotspot['avg_severity']:.1f}/10")
                    with col4:
                        st.metric("Urgency Score", f"{hotspot['urgency_score']}/100")
                    
                    st.markdown("---")
                    
                    # Sensor Data Details
                    st.markdown("### 📡 Sensor Data Details")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("**Severity Metrics**")
                        st.write(f"• Avg: {hotspot['avg_severity']:.1f}/10")
                        st.write(f"• Max: {hotspot['max_severity']}/10")
                        st.write(f"• Unique Cyclists: {hotspot['unique_devices']}")
                    
                    with col2:
                        st.markdown("**Accelerometer Data**")
                        st.write(f"• Peak X (lateral): {hotspot['avg_peak_x']:.2f}g")
                        st.write(f"• Peak Y (forward): {hotspot['avg_peak_y']:.2f}g")
                        st.write(f"• Peak Z (vertical): {hotspot['avg_peak_z']:.2f}g")
                    
                    with col3:
                        st.markdown("**Additional Info**")
                        st.write(f"• Avg Speed: {hotspot['avg_speed']:.1f} km/h")
                        st.write(f"• Total Events: {hotspot['event_count']}")
                        st.write(f"• Risk Score: {hotspot['risk_score']:.1f}")
                    
                    st.markdown("---")
                    
                    # User Perception Reports
                    st.markdown("### 💬 User Perception Reports")
                    
                    perception = hotspot['perception_data']
                    
                    if perception['total_reports'] > 0:
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            st.markdown(f"**{perception['total_reports']} reports found (100m radius, all time)**")
                            st.write(f"• Infrastructure reports: {perception['infra_reports']}")
                            st.write(f"• Ride reports: {perception['ride_reports']}")
                            
                            st.markdown("**Reported Issues:**")
                            for theme, count in sorted(perception['themes'].items(), key=lambda x: x[1], reverse=True):
                                st.write(f"• {theme}: {count} reports")
                        
                        with col2:
                            st.markdown("**Sample Comments:**")
                            for i, comment in enumerate(perception['comments'][:5], 1):
                                st.markdown(f"""
                                <div style="background: #f0f0f0; padding: 10px; 
                                            margin: 5px 0; border-radius: 5px; 
                                            border-left: 3px solid #DC143C;">
                                    <i>"{comment}"</i>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            if len(perception['comments']) > 5:
                                st.info(f"+ {len(perception['comments']) - 5} more comments")
                    else:
                        st.info("ℹ️ No user perception reports found within 100m of this location.")
                    
                    st.markdown("---")
                    
                    # Location & Actions
                    st.markdown("### 📍 Location & Actions")
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Coordinates:** {hotspot['center_lat']:.6f}, {hotspot['center_lng']:.6f}")
                        st.write(f"**Date Range:** {hotspot['date_range']}")
                        st.write(f"**First Event:** {hotspot['first_event']}")
                        st.write(f"**Last Event:** {hotspot['last_event']}")
                    
                    with col2:
                        street_view_url = STREET_VIEW_URL_TEMPLATE.format(
                            lat=hotspot['center_lat'],
                            lng=hotspot['center_lng'],
                            heading=0
                        )
                        
                        st.markdown(f"""
                        <a href="{street_view_url}" target="_blank" 
                           style="display: block; text-align: center; 
                                  background: #4285f4; color: white; 
                                  padding: 15px; border-radius: 5px; 
                                  text-decoration: none; font-weight: bold;">
                            📍 Open in Google Street View
                        </a>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        maps_url = f"https://www.google.com/maps?q={hotspot['center_lat']},{hotspot['center_lng']}"
                        st.markdown(f"""
                        <a href="{maps_url}" target="_blank" 
                           style="display: block; text-align: center; 
                                  background: #34A853; color: white; 
                                  padding: 15px; border-radius: 5px; 
                                  text-decoration: none; font-weight: bold;">
                            🗺️ Open in Google Maps
                        </a>
                        """, unsafe_allow_html=True)

# ==================== TAB 2: TREND ANALYSIS ====================
with tab2:
    st.header("📈 Trend Analysis")
    st.markdown("Analyzing road usage patterns and detecting anomalies")
    
    # Date range for trends
    st.subheader("📅 Select Date Range")
    
    col1, col2 = st.columns(2)
    with col1:
        trend_start = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, key="trend_start")
    with col2:
        trend_end = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, key="trend_end")
    
    if trend_start > trend_end:
        st.error("⚠️ Start date must be before end date!")
        st.stop()
    
    # Get trend data
    days_range = (trend_end - trend_start).days + 1
    
    with st.spinner("Loading trend data..."):
        trends_df = db.get_usage_trends(days=days_range)
    
    if trends_df.empty:
        st.warning("⚠️ No trend data available for selected date range.")
    else:
        # Filter by date range
        trends_df['date'] = pd.to_datetime(trends_df['date'])
        trends_filtered = trends_df[
            (trends_df['date'].dt.date >= trend_start) &
            (trends_df['date'].dt.date <= trend_end)
        ]
        
        # Key metrics
        st.subheader("📊 Key Insights")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_users = trends_filtered['unique_users'].mean()
            st.metric("Avg Daily Users", f"{avg_users:.0f}")
        
        with col2:
            total_events = trends_filtered['abnormal_events'].sum()
            st.metric("Total Abnormal Events", f"{total_events:,}")
        
        with col3:
            avg_speed = trends_filtered['avg_speed'].mean()
            st.metric("Avg Speed", f"{avg_speed:.1f} km/h")
        
        with col4:
            avg_severity = trends_filtered['avg_severity'].mean()
            st.metric("Avg Severity", f"{avg_severity:.1f}/10")
        
        st.markdown("---")
        
        # Usage trends chart
        st.subheader("📈 Daily Usage Trends")
        
        fig = go.Figure()
        
        # Add users line
        fig.add_trace(go.Scatter(
            x=trends_filtered['date'],
            y=trends_filtered['unique_users'],
            mode='lines+markers',
            name='Unique Users',
            line=dict(color='#3B82F6', width=2),
            yaxis='y1'
        ))
        
        # Add events line
        fig.add_trace(go.Scatter(
            x=trends_filtered['date'],
            y=trends_filtered['abnormal_events'],
            mode='lines+markers',
            name='Abnormal Events',
            line=dict(color='#EF4444', width=2),
            yaxis='y2'
        ))
        
        fig.update_layout(
            title='Usage and Safety Events Over Time',
            xaxis=dict(title='Date'),
            yaxis=dict(title='Unique Users', side='left', color='#3B82F6'),
            yaxis2=dict(title='Abnormal Events', overlaying='y', side='right', color='#EF4444'),
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Anomaly detection
        st.subheader("⚠️ Usage Anomalies")
        
        anomalies_df = db.detect_usage_anomalies(threshold_pct=30)
        
        if not anomalies_df.empty:
            anomalies_df['date'] = pd.to_datetime(anomalies_df['date'])
            anomalies_filtered = anomalies_df[
                (anomalies_df['date'].dt.date >= trend_start) &
                (anomalies_df['date'].dt.date <= trend_end)
            ]
            
            if not anomalies_filtered.empty:
                st.warning(f"⚠️ **{len(anomalies_filtered)} significant usage drops detected!**")
                
                for idx, anomaly in anomalies_filtered.iterrows():
                    with st.expander(f"📉 Drop on {anomaly['date'].strftime('%Y-%m-%d')}"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric(
                                "Daily Users",
                                f"{anomaly['daily_users']:.0f}",
                                f"{anomaly['day_over_day_change']:.1f}% vs prev day"
                            )
                        
                        with col2:
                            st.metric(
                                "Week over Week",
                                f"{anomaly['week_over_week_change']:.1f}%",
                                help="Change compared to same day last week"
                            )
                        
                        with col3:
                            st.metric(
                                "vs 7-day Average",
                                f"{anomaly['rolling_avg_deviation']:.1f}%",
                                help="Deviation from 7-day rolling average"
                            )
                        
                        st.markdown("**Possible causes to investigate:**")
                        st.write("• Weather events (storms, heavy rain)")
                        st.write("• Road closures or construction")
                        st.write("• Special events or holidays")
                        st.write("• Route diversions")
            else:
                st.success("✅ No significant usage drops detected in selected period")
        else:
            st.success("✅ No significant usage drops detected")
        
        st.markdown("---")
        
        # Severity trends
        st.subheader("📊 Severity Trends")
        
        fig_severity = px.line(
            trends_filtered,
            x='date',
            y='avg_severity',
            title='Average Severity Over Time',
            labels={'avg_severity': 'Average Severity', 'date': 'Date'}
        )
        
        fig_severity.update_traces(line_color='#EF4444', line_width=3)
        fig_severity.update_layout(height=400)
        
        st.plotly_chart(fig_severity, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("### 📌 About This Dashboard")

with st.expander("ℹ️ How It Works"):
    st.markdown("""
    ### 🔬 Enhanced Hotspot Detection
    
    This dashboard uses advanced clustering with accelerometer data:
    
    1. **Date-Filtered Sensor Data**: Select a date range to analyze specific periods
    2. **DBSCAN Clustering**: Groups nearby events using both location AND accelerometer patterns
    3. **Risk Scoring**: Combines event count × severity for objective ranking
    4. **All-Time Perception Reports**: Searches 100m radius across ALL dates for user reports
    5. **AI Analysis**: Groq AI (llama-3.3-70b) analyzes sensor + perception data to paint a complete picture
    
    ### 📊 Data Sources
    
    - **Sensor Data**: {metrics['total_readings']:,} readings from AWS Athena
    - **Infrastructure Reports**: {len(infra_df):,} user reports
    - **Ride Reports**: {len(ride_df):,} incident reports
    
    ### 🎯 Key Features
    
    - **Accelerometer-Enhanced Clustering**: Uses peak forces (X, Y, Z) for better grouping
    - **Context-Rich Analysis**: AI combines sensor patterns with user experiences
    - **Objective Risk Scoring**: Events × Severity = Quantifiable risk
    - **Temporal Flexibility**: Analyze any time period while checking all perception data
    """.format(metrics=metrics, infra_df=infra_df, ride_df=ride_df))

st.caption("🚴‍♂️ Spinovate Safety Dashboard | Powered by Groq AI, AWS Athena & Enhanced DBSCAN")

                    
                    # AI Analysis - THE MAIN HIGHLIGHT
                    st.markdown("### 🤖 AI-Powered Analysis")
                    analysis_method = hotspot['groq_analysis']['method']
                    if analysis_method == 'groq_ai':
                        st.success(f"✅ Analysis by: {hotspot['groq_analysis']['model']}")
                    else:
                        st.info(f"ℹ️ Analysis method: {analysis_method}")
                    
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                padding: 20px; border-radius: 10px; color: white; 
                                box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <p style="font-size: 16px; line-height: 1.6; margin: 0;">
                            {hotspot['groq_analysis']['analysis']}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    # Event Distribution
                    st.markdown("### 📊 Event Type Distribution")
                    
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        # Pie chart
                        event_dist_df = pd.DataFrame([
                            {'Event Type': k, 'Percentage': v}
                            for k, v in hotspot['event_distribution'].items()
                        ])
                        
                        fig = px.pie(
                            event_dist_df,
                            values='Percentage',
                            names='Event Type',
                            title='Event Type Breakdown',
                            color_discrete_sequence=px.colors.sequential.Reds
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.markdown("**Event Counts:**")
                        for event_type, pct in sorted(hotspot['event_distribution'].items(), key=lambda x: x[1], reverse=True):
                            count = hotspot['event_types_raw'][event_type]
                            st.write(f"• **{event_type.title()}**: {count} events ({pct:.1f}%)")
                    
                    st.markdown("---")
