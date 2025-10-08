"""
Spinovate Safety Dashboard - Hybrid Hotspot Detection
Main Streamlit application
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import folium
from streamlit_folium import folium_static

# Import custom modules
from src.hybrid_hotspot_detector import detect_hybrid_hotspots
from src.athena_database import get_athena_database
from src.trend_analysis import (
    prepare_time_series,
    detect_anomalies,
    calculate_trends
)
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

# ==================== DATA LOADING ====================

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

# ==================== SIDEBAR ====================

st.sidebar.title("⚙️ Settings")
st.sidebar.subheader("📊 Data Overview")
st.sidebar.metric("Total Readings", f"{metrics['total_readings']:,}")
st.sidebar.metric("Unique Cyclists", metrics['unique_devices'])
st.sidebar.metric("Abnormal Events", f"{metrics['abnormal_events']:,}")
st.sidebar.metric("Perception Reports", len(infra_df) + len(ride_df))

if metrics['earliest_reading'] and metrics['latest_reading']:
    st.sidebar.write(f"**Date Range:** {metrics['earliest_reading']} to {metrics['latest_reading']}")

st.sidebar.markdown("---")

# ==================== TABS ====================

tab1, tab2 = st.tabs(["📍 Hotspot Analysis", "📈 Trend Analysis"])

# ==================== TAB 1: HOTSPOT ANALYSIS ====================

with tab1:
    st.header("🚨 Hybrid Hotspot Analysis")
    st.markdown("**55% Sensor-Primary | 45% Perception-Primary (3 Precedence Levels)**")
    
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
        total_hotspots = st.slider("Total Hotspots to Detect", 10, 50, 30, 5)
    with col2:
        sensor_count = int(total_hotspots * 0.55)
        perception_count = total_hotspots - sensor_count
        st.info(f"Split: {sensor_count} sensor + {perception_count} perception")
    
    if st.button("🔍 Detect Hotspots", type="primary", use_container_width=True):
        st.session_state.hotspots_detected = True
    
    if 'hotspots_detected' not in st.session_state:
        st.session_state.hotspots_detected = False
    
    if st.session_state.hotspots_detected:
        with st.spinner("🔬 Running hybrid hotspot detection..."):
            hotspots = detect_hybrid_hotspots(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                infra_df=infra_df,
                ride_df=ride_df,
                total_hotspots=total_hotspots
            )
        
        if hotspots.empty:
            st.warning("⚠️ No hotspots found with current parameters.")
        else:
            st.success(f"✅ Detected {len(hotspots)} hotspots")
            
            # ==================== KEY METRICS ====================
            st.subheader("📊 Overview Metrics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Hotspots", len(hotspots))
            with col2:
                sensor_hotspots = len(hotspots[hotspots['source'] == 'sensor_primary'])
                st.metric("Sensor-Primary", sensor_hotspots)
            with col3:
                perception_hotspots = len(hotspots[hotspots['source'] != 'sensor_primary'])
                st.metric("Perception-Primary", perception_hotspots)
            with col4:
                p3_count = len(hotspots[hotspots['precedence'] == 'P3'])
                st.metric("No Sensor Data", p3_count)
            
            st.markdown("---")
            
            # ==================== BREAKDOWN BY TYPE ====================
            st.subheader("📋 Breakdown by Type")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Precedence breakdown
                precedence_counts = hotspots['precedence'].value_counts()
                precedence_labels = {
                    'sensor': 'Sensor-Primary (55%)',
                    'P1': 'P1: Perception + Sensor',
                    'P2': 'P2: Corridors + Sensor',
                    'P3': 'P3: Perception Only'
                }
                
                precedence_df = pd.DataFrame({
                    'Type': [precedence_labels.get(k, k) for k in precedence_counts.index],
                    'Count': precedence_counts.values
                })
                
                fig = px.bar(
                    precedence_df,
                    x='Type',
                    y='Count',
                    title='Hotspots by Precedence',
                    color='Count',
                    color_continuous_scale='Reds'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Color distribution
                color_counts = hotspots['color'].value_counts()
                color_labels = {
                    'red': '🔴 Critical (7+)',
                    'orange': '🟠 Medium (4-6.9)',
                    'green': '🟢 Low (<4)',
                    'blue': '🔵 No Sensor'
                }
                
                color_df = pd.DataFrame({
                    'Severity': [color_labels.get(k, k) for k in color_counts.index],
                    'Count': color_counts.values
                })
                
                fig = px.pie(
                    color_df,
                    values='Count',
                    names='Severity',
                    title='Severity Distribution',
                    color='Severity',
                    color_discrete_map={
                        '🔴 Critical (7+)': '#DC143C',
                        '🟠 Medium (4-6.9)': '#FFA500',
                        '🟢 Low (<4)': '#90EE90',
                        '🔵 No Sensor': '#4285f4'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            # ==================== INTERACTIVE MAP ====================
            st.subheader("🗺️ Interactive Hotspot Map")
            
            # Create map
            m = folium.Map(
                location=[hotspots['center_lat'].mean(), hotspots['center_lng'].mean()],
                zoom_start=12
            )
            
            # Color mapping
            color_map = {
                'red': '#DC143C',
                'orange': '#FFA500',
                'green': '#90EE90',
                'blue': '#4285f4'
            }
            
            for idx, hotspot in hotspots.iterrows():
                color = color_map.get(hotspot['color'], '#808080')
                
                # Build popup
                popup_html = f"""
                <div style="font-family: Arial; width: 300px;">
                    <h4 style="color: {color};">🚨 Hotspot #{hotspot['final_hotspot_id']}</h4>
                    <p><b>Type:</b> {hotspot['precedence']}</p>
                """
                
                if hotspot.get('event_count', 0) > 0:
                    popup_html += f"""
                    <p><b>Sensor Events:</b> {hotspot['event_count']}</p>
                    <p><b>Avg Severity:</b> {hotspot.get('avg_severity', 0):.1f}/10</p>
                    <p><b>Rank Score:</b> {hotspot.get('rank_score', 0):.1f}</p>
                    """
                
                if hotspot.get('perception_count', 0) > 0:
                    popup_html += f"""
                    <p><b>User Reports:</b> {hotspot['perception_count']}</p>
                    """
                
                if hotspot.get('is_corridor'):
                    popup_html += f"""
                    <p><b>🛣️ Corridor:</b> {hotspot.get('corridor_length_m', 0):.0f}m</p>
                    """
                
                popup_html += f"""
                    <hr>
                    <a href="{STREET_VIEW_URL_TEMPLATE.format(lat=hotspot['center_lat'], lng=hotspot['center_lng'], heading=0)}" 
                       target="_blank" style="color: #4285f4;">📍 View in Street View</a>
                </div>
                """
                
                                # Draw corridor or point
                if (hotspot.get('is_corridor') and 
                    'corridor_points' in hotspot and 
                    hotspot['corridor_points'] is not None and 
                    len(hotspot['corridor_points']) > 0):
                    # Draw polyline for corridors
                    points = hotspot['corridor_points']
                    folium.PolyLine(
                        locations=points,
                        color=color,
                        weight=6,
                        opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=350)
                    ).add_to(m)
                    
                    # Add start/end markers
                    folium.CircleMarker(
                        location=points[0],
                        radius=8,
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.7,
                        tooltip="Corridor Start"
                    ).add_to(m)
                    
                    folium.CircleMarker(
                        location=points[-1],
                        radius=8,
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.7,
                        tooltip="Corridor End"
                    ).add_to(m)
                else:
                    # Draw circle marker for point locations
                    folium.CircleMarker(
                        location=[hotspot['center_lat'], hotspot['center_lng']],
                        radius=10,
                        popup=folium.Popup(popup_html, max_width=350),
                        tooltip=f"Hotspot #{hotspot['final_hotspot_id']}",
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.7,
                        weight=2
                    ).add_to(m)
            
            folium_static(m, width=1200, height=600)
            
            st.markdown("---")
            
            # ==================== CRITICAL HOTSPOTS SECTION ====================
            st.subheader("🔝 Critical Hotspots - Detailed Analysis")
            
            for idx, hotspot in hotspots.iterrows():
                # Build expander title
                                # Build expander title
                if hotspot.get('is_corridor') and pd.notna(hotspot.get('start_lat')) and pd.notna(hotspot.get('end_lat')):
                    title_suffix = f"Corridor ({hotspot.get('corridor_length_m', 0):.0f}m)"
                else:
                    title_suffix = "Point Location"
                
                precedence_label = {
                    'sensor': 'Sensor-Primary',
                    'P1': 'Perception + Sensor',
                    'P2': 'Corridor + Sensor',
                    'P3': 'Perception Only'
                }.get(hotspot['precedence'], hotspot['precedence'])
                
                with st.expander(
                    f"🚨 Hotspot #{hotspot['final_hotspot_id']}: {precedence_label} | {title_suffix}",
                    expanded=(idx == 0)
                ):
                    # Overview Metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        if hotspot.get('event_count', 0) > 0:
                            st.metric("Sensor Events", int(hotspot['event_count']))
                        else:
                            st.metric("Sensor Events", "N/A")
                    
                    with col2:
                        if hotspot.get('perception_count', 0) > 0:
                            st.metric("User Reports", int(hotspot['perception_count']))
                        else:
                            st.metric("User Reports", 0)
                    
                    with col3:
                        if hotspot.get('avg_severity') is not None:
                            st.metric("Avg Severity", f"{hotspot['avg_severity']:.1f}/10")
                        else:
                            st.metric("Avg Severity", "No Data")
                    
                    with col4:
                        if hotspot.get('rank_score') is not None:
                            st.metric("Rank Score", f"{hotspot['rank_score']:.1f}")
                        else:
                            st.metric("Rank Score", "N/A")
                    
                    st.markdown("---")
                    
                    # AI Analysis - THE MAIN HIGHLIGHT
                    st.markdown("### 🤖 AI-Powered Analysis")
                    
                    if 'groq_analysis' in hotspot:
                        analysis_method = hotspot['groq_analysis']['method']
                        if analysis_method == 'groq_ai':
                            st.success(f"✅ Analysis by: {hotspot['groq_analysis']['model']}")
                        else:
                            st.info(f"ℹ️ Analysis method: {analysis_method}")
                        
                        # Get color for the gradient box
                        box_color = color_map.get(hotspot['color'], '#667eea')
                        
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, {box_color} 0%, #764ba2 100%); 
                                    padding: 20px; border-radius: 10px; color: white; 
                                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                            <p style="font-size: 16px; line-height: 1.6; margin: 0;">
                                {hotspot['groq_analysis']['analysis']}
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.warning("No AI analysis available")
                    
                    st.markdown("---")
                    
                    # Event Distribution (if sensor data available)
                    if hotspot.get('event_count', 0) > 0 and 'event_distribution' in hotspot:
                        event_dist = hotspot['event_distribution']
                        if isinstance(event_dist, dict):
                            st.markdown("### 📊 Event Type Distribution")
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                event_dist_df = pd.DataFrame([
                                    {'Event Type': k, 'Percentage': v}
                                    for k, v in event_dist.items()
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
                                for event_type, pct in sorted(event_dist.items(), key=lambda x: x[1], reverse=True):
                                    if 'event_types_raw' in hotspot:
                                        count = hotspot['event_types_raw'].get(event_type, 0)
                                        st.write(f"• **{event_type.title()}**: {count} events ({pct:.1f}%)")
                            st.markdown("---")
                        else:
                            st.info("No event distribution data available.")
                    
                    # Sensor Data Details (if available)
                    if hotspot.get('event_count', 0) > 0:
                        st.markdown("### 📡 Sensor Data Details")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.markdown("**Severity Metrics**")
                            st.write(f"• Avg: {hotspot.get('avg_severity', 0):.1f}/10")
                            st.write(f"• Max: {hotspot.get('max_severity', 0)}/10")
                            st.write(f"• Unique Cyclists: {hotspot.get('unique_devices', 0)}")
                        
                        with col2:
                            if 'avg_peak_x' in hotspot:
                                st.markdown("**Accelerometer Data**")
                                st.write(f"• Peak X (lateral): {hotspot['avg_peak_x']:.2f}g")
                                st.write(f"• Peak Y (forward): {hotspot['avg_peak_y']:.2f}g")
                                st.write(f"• Peak Z (vertical): {hotspot['avg_peak_z']:.2f}g")
                        
                        with col3:
                            st.markdown("**Additional Info**")
                            if 'avg_speed' in hotspot:
                                st.write(f"• Avg Speed: {hotspot['avg_speed']:.1f} km/h")
                            st.write(f"• Total Events: {hotspot['event_count']}")
                            if 'rank_score' in hotspot:
                                st.write(f"• Rank Score: {hotspot['rank_score']:.1f}")
                        
                        st.markdown("---")
                    
                    # User Perception Reports (if available)
                    if hotspot.get('perception_count', 0) > 0:
                        st.markdown("### 💬 User Perception Reports")
                        
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            st.markdown(f"**{hotspot['perception_count']} reports found**")
                            
                            if 'perception_reports' in hotspot:
                                reports = hotspot['perception_reports']
                                themes = {}
                                for report in reports:
                                    theme = report.get('theme', 'Unknown')
                                    themes[theme] = themes.get(theme, 0) + 1
                                
                                st.markdown("**Reported Issues:**")
                                for theme, count in sorted(themes.items(), key=lambda x: x[1], reverse=True):
                                    st.write(f"• {theme}: {count} reports")
                        
                        with col2:
                            if 'perception_reports' in hotspot:
                                st.markdown("**Sample Comments:**")
                                reports = hotspot['perception_reports']
                                comments = [r.get('comment', '') for r in reports if r.get('comment')]
                                
                                for i, comment in enumerate(comments[:5], 1):
                                    st.markdown(f"""
                                    <div style="background: #f0f0f0; padding: 10px; 
                                                margin: 5px 0; border-radius: 5px; 
                                                border-left: 3px solid {color_map.get(hotspot['color'], '#DC143C')};">
                                        <i>"{comment}"</i>
                                    </div>
                                    """, unsafe_allow_html=True)
                                
                                if len(comments) > 5:
                                    st.info(f"+ {len(comments) - 5} more comments")
                        
                        st.markdown("---")
                    
                                        # Location & Actions
                    st.markdown("### 📍 Location & Actions")
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Coordinates:** {hotspot['center_lat']:.6f}, {hotspot['center_lng']:.6f}")
                        
                        if hotspot.get('is_corridor') and pd.notna(hotspot.get('start_lat')) and pd.notna(hotspot.get('end_lat')):
                            st.write(f"**Corridor Length:** {hotspot.get('corridor_length_m', 0):.0f}m")
                            st.write(f"**Start:** {hotspot.get('start_lat', 0):.6f}, {hotspot.get('start_lng', 0):.6f}")
                            st.write(f"**End:** {hotspot.get('end_lat', 0):.6f}, {hotspot.get('end_lng', 0):.6f}")
                        else:
                            st.write("**Type:** Point Location")
                        
                        if 'date_range' in hotspot:
                            st.write(f"**Date Range:** {hotspot['date_range']}")
                    
                    with col2:
                        # Street View links
                        if hotspot.get('is_corridor') and pd.notna(hotspot.get('start_lat')) and pd.notna(hotspot.get('end_lat')):
                            # Start point
                            start_url = STREET_VIEW_URL_TEMPLATE.format(
                                lat=hotspot['start_lat'],
                                lng=hotspot['start_lng'],
                                heading=0
                            )
                            st.markdown(f"""
                            <a href="{start_url}" target="_blank" 
                               style="display: block; text-align: center; 
                                      background: #4285f4; color: white; 
                                      padding: 10px; border-radius: 5px; 
                                      text-decoration: none; font-weight: bold; margin-bottom: 5px;">
                                📍 Start Point
                            </a>
                            """, unsafe_allow_html=True)
                            
                            # End point
                            end_url = STREET_VIEW_URL_TEMPLATE.format(
                                lat=hotspot['end_lat'],
                                lng=hotspot['end_lng'],
                                heading=0
                            )
                            st.markdown(f"""
                            <a href="{end_url}" target="_blank" 
                               style="display: block; text-align: center; 
                                      background: #4285f4; color: white; 
                                      padding: 10px; border-radius: 5px; 
                                      text-decoration: none; font-weight: bold;">
                                📍 End Point
                            </a>
                            """, unsafe_allow_html=True)
                        else:
                            # For point locations, use center coordinates
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
                                      text-decoration: none; font-weight: bold; margin-bottom: 10px;">
                                📍 Street View
                            </a>
                            """, unsafe_allow_html=True)
                        
                        # Google Maps link
                        maps_url = f"https://www.google.com/maps?q={hotspot['center_lat']},{hotspot['center_lng']}"
                        st.markdown(f"""
                        <a href="{maps_url}" target="_blank" 
                           style="display: block; text-align: center; 
                                  background: #34A853; color: white; 
                                  padding: 15px; border-radius: 5px; 
                                  text-decoration: none; font-weight: bold;">
                            🗺️ Google Maps
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
        trend_start = st.date_input("Start Date", value=min_date, min_value=min_date, 
                                    max_value=max_date, key="trend_start")
    with col2:
        trend_end = st.date_input("End Date", value=max_date, min_value=min_date, 
                                  max_value=max_date, key="trend_end")
    
    if trend_start > trend_end:
        st.error("⚠️ Start date must be before end date!")
        st.stop()
    
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
            if 'avg_speed' in trends_filtered.columns:
                avg_speed = trends_filtered['avg_speed'].mean()
                st.metric("Avg Speed", f"{avg_speed:.1f} km/h")
            else:
                st.metric("Avg Speed", "N/A")
        
        with col4:
            if 'avg_severity' in trends_filtered.columns:
                avg_severity = trends_filtered['avg_severity'].mean()
                st.metric("Avg Severity", f"{avg_severity:.1f}/10")
            else:
                st.metric("Avg Severity", "N/A")
        
        st.markdown("---")
        
        # Usage trends chart
        st.subheader("📈 Daily Usage Trends")
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=trends_filtered['date'],
            y=trends_filtered['unique_users'],
            mode='lines+markers',
            name='Unique Users',
            line=dict(color='#3B82F6', width=2),
            yaxis='y1'
        ))
        
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

# ==================== FOOTER ====================

st.markdown("---")
st.markdown("### 📌 About This Dashboard")

with st.expander("ℹ️ How It Works"):
    st.markdown(f"""
    ### 🔬 Hybrid Hotspot Detection (55-45 Split)
    
    **Sensor-Primary (55%):**
    - Only events with `is_abnormal_event = true`
    - Severity parsed from `event_details` field
    - Ranked by: `avg_severity + log10(event_count)`
    - Medoid-based centers (actual road locations)
    
    **Perception-Primary (45%):**
    
    **Precedence 1:** Perception + Strong Sensor
    - Perception reports with sensor validation (severity ≥ 2)
    - 30m search radius
    - Ranked by sensor severity
    
    **Precedence 2:** Corridors with Sensor
    - 3+ reports from same user, consecutive < 150m
    - 20m buffer polygon for finding related reports
    - Must have 1+ abnormal sensor event
    - Visualized as polylines
    
    **Precedence 3:** Standalone Perception
    - 3+ reports from different users
    - Point clusters OR corridors
    - No sensor validation required
    - Color coded BLUE (no severity data)
    
    ### 🎨 Color Coding
    
    - 🔴 **Red (Critical):** Rank score ≥ 7
    - 🟠 **Orange (Medium):** Rank score 4-6.9
    - 🟢 **Green (Low):** Rank score < 4
    - 🔵 **Blue (No Sensor):** Perception-only hotspots
    
    ### 🤖 AI Analysis
    
    - All {total_hotspots} hotspots analyzed by Groq AI (llama-3.3-70b)
    - Combines sensor data + user reports
    - Paints complete picture of what's happening
    - No recommendations - only objective analysis
    
    ### 📊 Data Sources
    
    - **Sensor Data:** {metrics['total_readings']:,} readings from AWS Athena
    - **Infrastructure Reports:** {len(infra_df):,} user reports
    - **Ride Reports:** {len(ride_df):,} incident reports
    - **Date Range:** {metrics['earliest_reading']} to {metrics['latest_reading']}
    """)

with st.expander("❓ FAQ"):
    st.markdown("""
    **Q: What's the difference between sensor-primary and perception-primary?**
    
    A: Sensor-primary hotspots are detected purely from bike sensor data (accelerometer events). Perception-primary starts with user reports and validates with sensor data.
    
    **Q: Why are some hotspots blue?**
    
    A: Blue hotspots (Precedence 3) have 3+ user reports but no sensor validation data. They're still important safety concerns reported by cyclists.
    
    **Q: What does "corridor" mean?**
    
    A: A corridor is a stretch of road (typically 100m+) where issues persist along the entire length, not just at one point. Examples: vegetation blocking cycle lane for 500m.
    
    **Q: How is rank score calculated?**
    
    A: `rank_score = avg_severity + log10(event_count)`. This balances severity (how bad) with frequency (how often). A hotspot with 100 events at severity 7 gets higher priority than 2 events at severity 9.
    
    **Q: Can I trust the AI analysis?**
    
    A: The AI (Groq's llama-3.3-70b) synthesizes sensor data + user comments to paint a complete picture. It's trained on billions of examples. You can always verify by reading the raw data shown below each analysis.
    
    **Q: What should I do with this information?**
    
    A: Use hotspot rankings to prioritize road maintenance, investigate usage drops for external factors, and validate user complaints with objective sensor data.
    """)

st.markdown("---")
st.caption("🚴‍♂️ Spinovate Safety Dashboard | Hybrid Detection System | Powered by Groq AI & AWS Athena")