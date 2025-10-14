"""
Spinovate Safety Dashboard - Enhanced with Synthetic Data & Rich Insights
Main Streamlit application
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import folium
from streamlit_folium import folium_static
from collections import Counter
import re

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

# ==================== ENHANCED DATA LOADING ====================

@st.cache_resource
def init_database():
    return get_athena_database()

@st.cache_data(ttl=3600)
def load_perception_data():
    """Load SYNTHETIC perception data for richer insights"""
    try:
        # Try to load synthetic data first
        infra_df = pd.read_csv('dublin_infra_reports_SYNTHETIC.csv')
        ride_df = pd.read_csv('dublin_ride_reports_SYNTHETIC.csv')
        
        st.sidebar.success("✨ Using enhanced synthetic dataset")
        
    except FileNotFoundError:
        # Fallback to original data
        st.sidebar.warning("⚠️ Synthetic data not found, using original")
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

# ==================== ENHANCED INSIGHT GENERATION ====================

def extract_themes_from_reports(reports: list) -> dict:
    """
    Extract themes and keywords from perception reports
    
    Args:
        reports: List of report dictionaries
        
    Returns:
        Dict with theme counts and keywords
    """
    themes = []
    all_text = []
    
    for report in reports:
        # Get theme/type
        theme = report.get('theme', report.get('incidenttype', report.get('infrastructuretype', 'Unknown')))
        if theme and theme != 'Unknown':
            themes.append(theme)
        
        # Get comment text
        comment = report.get('comment', report.get('commentfinal', report.get('finalcomment', '')))
        if comment and isinstance(comment, str):
            all_text.append(comment.lower())
    
    # Count themes
    theme_counts = Counter(themes)
    
    # Extract keywords from all comments
    combined_text = ' '.join(all_text)
    
    # Define keyword patterns
    keyword_patterns = {
        '🚗 Close Pass': ['close pass', 'too close', 'nearly hit', 'almost hit', 'inches'],
        '🕳️ Pothole': ['pothole', 'hole', 'crater', 'damaged', 'surface damage'],
        '🌳 Obstruction': ['blocked', 'obstruction', 'vegetation', 'overgrown', 'bushes', 'trees'],
        '🚙 Parked Vehicle': ['parked', 'parking', 'car parked', 'van parked'],
        '🚦 Junction Issue': ['junction', 'turn', 'corner', 'intersection', 'turning'],
        '🚌 Heavy Traffic': ['traffic', 'busy', 'congested', 'rush hour', 'heavy traffic'],
        '⚠️ Poor Visibility': ['blind', 'cant see', "can't see", 'visibility', 'hidden'],
        '🛣️ Surface Quality': ['rough', 'uneven', 'bumpy', 'cracked', 'broken surface'],
        '🚲 Cycle Lane': ['cycle lane', 'bike lane', 'cycling path', 'lane blocked'],
        '⚡ Dangerous': ['dangerous', 'unsafe', 'scary', 'terrifying', 'hazard']
    }
    
    detected_keywords = {}
    for keyword_label, patterns in keyword_patterns.items():
        for pattern in patterns:
            if pattern in combined_text:
                detected_keywords[keyword_label] = True
                break
    
    return {
        'theme_counts': dict(theme_counts),
        'keywords': list(detected_keywords.keys()),
        'top_theme': theme_counts.most_common(1)[0][0] if theme_counts else 'Unknown'
    }


def generate_enhanced_summary(hotspot: dict) -> str:
    """
    Generate enhanced, insightful summary combining sensor + perception data
    
    Args:
        hotspot: Hotspot dictionary with all data
        
    Returns:
        Rich HTML summary string
    """
    summary_parts = []
    
    # === SENSOR DATA SECTION ===
    if hotspot.get('event_count', 0) > 0:
        event_count = int(hotspot['event_count'])
        avg_severity = hotspot.get('avg_severity', 0)
        
        # Make it conversational, not robotic
        if avg_severity >= 8:
            intro = f"⚠️ **Critical location** - cyclists experienced **{event_count} severe incidents** here"
        elif avg_severity >= 6:
            intro = f"🔴 **High-risk area** - detected **{event_count} significant safety events**"
        elif avg_severity >= 4:
            intro = f"🟠 **Caution needed** - recorded **{event_count} notable incidents**"
        else:
            intro = f"🟡 **Monitor this spot** - logged **{event_count} safety-related events**"
        
        summary_parts.append(intro)
        
        # Add severity context
        if avg_severity >= 7:
            summary_parts.append(f" with severity averaging **{avg_severity:.1f}/10** - well above normal threshold.")
        else:
            summary_parts.append(f" with average severity of **{avg_severity:.1f}/10**.")
        
        # Event type breakdown - make it natural
        if 'event_distribution' in hotspot and isinstance(hotspot['event_distribution'], dict):
            event_dist = hotspot['event_distribution']
            
            if len(event_dist) == 1:
                # Single dominant event
                event_type = list(event_dist.keys())[0]
                summary_parts.append(f" All incidents involved **{event_type}** events.")
            else:
                # Multiple event types
                top_events = sorted(event_dist.items(), key=lambda x: x[1], reverse=True)[:2]
                if top_events:
                    event1, pct1 = top_events[0]
                    if len(top_events) > 1:
                        event2, pct2 = top_events[1]
                        summary_parts.append(f" Primary issues: **{event1}** ({pct1:.0f}%) and **{event2}** ({pct2:.0f}%).")
                    else:
                        summary_parts.append(f" Dominated by **{event1}** events ({pct1:.0f}%).")
    
    # === PERCEPTION DATA SECTION ===
    if hotspot.get('perception_count', 0) > 0:
        perception_count = int(hotspot['perception_count'])
        
        # Get reports
        all_reports = []
        if 'perception_reports' in hotspot:
            all_reports = hotspot['perception_reports']
        
        # Extract themes
        themes_data = extract_themes_from_reports(all_reports)
        top_theme = themes_data['top_theme']
        
        # Make it conversational
        if perception_count == 1:
            summary_parts.append(f"\n\n💬 One cyclist reported issues with **{top_theme}** at this location.")
        elif perception_count <= 3:
            summary_parts.append(f"\n\n💬 **{perception_count} cyclists** have flagged this spot, mainly for **{top_theme}**.")
        else:
            summary_parts.append(f"\n\n💬 **{perception_count} cyclists** identified this as problematic - most commonly citing **{top_theme}**.")
        
        # Sample comments - pick the most descriptive ones
        comments = [r.get('comment', r.get('commentfinal', r.get('finalcomment', ''))) 
                   for r in all_reports if r.get('comment') or r.get('commentfinal') or r.get('finalcomment')]
        comments = [c for c in comments if c and len(str(c).strip()) > 15]
        
        if comments:
            # Sort by length to get more descriptive comments
            comments_sorted = sorted(comments, key=len, reverse=True)
            sample_comments = comments_sorted[:2]
            
            summary_parts.append("\n\n**Cyclist feedback:**")
            for comment in sample_comments:
                # Truncate very long comments
                if len(comment) > 120:
                    comment = comment[:117] + "..."
                summary_parts.append(f'\n> *"{comment}"*')
    
    # === VALIDATION SECTION ===
    if hotspot.get('event_count', 0) > 0 and hotspot.get('perception_count', 0) > 0:
        summary_parts.append(
            f"\n\n✅ **Both sensor data and cyclist reports confirm** this location needs attention."
        )
    elif hotspot.get('event_count', 0) > 0 and hotspot.get('perception_count', 0) == 0:
        summary_parts.append(
            f"\n\n📡 Detected by sensors but not yet reported by users - early warning of emerging issue."
        )
    elif hotspot.get('perception_count', 0) > 0 and hotspot.get('event_count', 0) == 0:
        summary_parts.append(
            f"\n\n📝 Reported by cyclists but no sensor validation available - community-identified concern."
        )
    
    # === CORRIDOR INFO ===
    if hotspot.get('is_corridor') and hotspot.get('corridor_length_m', 0) > 0:
        corridor_len = int(hotspot['corridor_length_m'])
        summary_parts.append(
            f"\n\n🛣️ **Extended problem area:** Issues span **{corridor_len}m** of this route - not isolated to one point."
        )
    
    return ''.join(summary_parts)


# ==================== LOAD DATA ====================

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

# Show synthetic data indicator
synthetic_count = 0
if 'is_synthetic' in infra_df.columns:
    synthetic_count += infra_df['is_synthetic'].sum()
if 'is_synthetic' in ride_df.columns:
    synthetic_count += ride_df['is_synthetic'].sum()

if synthetic_count > 0:
    st.sidebar.metric("✨ Synthetic Reports", f"{synthetic_count:,}")

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
                total_hotspots=total_hotspots,
                enable_groq=True
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
            
            m = folium.Map(
                location=[hotspots['center_lat'].mean(), hotspots['center_lng'].mean()],
                zoom_start=12
            )
            
            color_map = {
                'red': '#DC143C',
                'orange': '#FFA500',
                'green': '#90EE90',
                'blue': '#4285f4'
            }
            
            for idx, hotspot in hotspots.iterrows():
                color = color_map.get(hotspot['color'], '#808080')
                
                popup_html = f"""
                <div style="font-family: Arial; width: 300px;">
                    <h4 style="color: {color};">🚨 Hotspot #{hotspot['final_hotspot_id']}</h4>
                    <p><b>Type:</b> {hotspot['precedence']}</p>
                """
                
                if hotspot.get('event_count', 0) > 0:
                    popup_html += f"""
                    <p><b>Sensor Events:</b> {hotspot['event_count']}</p>
                    <p><b>Avg Severity:</b> {hotspot.get('avg_severity', 0):.1f}/10</p>
                    """
                
                if hotspot.get('perception_count', 0) > 0:
                    popup_html += f"""
                    <p><b>User Reports:</b> {hotspot['perception_count']}</p>
                    """
                
                popup_html += f"""
                    <hr>
                    <a href="{STREET_VIEW_URL_TEMPLATE.format(lat=hotspot['center_lat'], lng=hotspot['center_lng'], heading=0)}" 
                       target="_blank" style="color: #4285f4;">📍 View in Street View</a>
                </div>
                """
                
                if (hotspot.get('is_corridor') and 
                    'corridor_points' in hotspot and 
                    hotspot['corridor_points'] is not None and 
                    len(hotspot['corridor_points']) > 0):
                    points = hotspot['corridor_points']
                    folium.PolyLine(
                        locations=points,
                        color=color,
                        weight=6,
                        opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=350)
                    ).add_to(m)
                    
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
            
            # ==================== ENHANCED CRITICAL HOTSPOTS ====================
            st.subheader("🔝 Critical Hotspots - Enhanced Insights")
            
            for idx, hotspot in hotspots.iterrows():
                if hotspot.get('is_corridor') and pd.notna(hotspot.get('start_lat')):
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
                    
                    # === ENHANCED SUMMARY ===
                    st.markdown("### 📋 Smart Summary")
                    
                    color = color_map.get(hotspot['color'], '#667eea')
                    
                    summary_text = generate_enhanced_summary(hotspot.to_dict())
                    
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, {color} 0%, #764ba2 100%); 
                                padding: 20px; border-radius: 10px; color: white; 
                                box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        {summary_text}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    # === THEME CARDS ===
                    if hotspot.get('perception_count', 0) > 0:
                        st.markdown("### 🏷️ Key Themes & Issues")
                        
                        all_reports = []
                        if 'perception_reports' in hotspot:
                            all_reports = hotspot['perception_reports']
                        
                        themes_data = extract_themes_from_reports(all_reports)
                        keywords = themes_data['keywords']
                        
                        if keywords:
                            # Display as cards
                            cols = st.columns(min(4, len(keywords)))
                            for i, keyword in enumerate(keywords[:8]):  # Max 8 keywords
                                with cols[i % 4]:
                                    st.markdown(f"""
                                    <div style="background: #f0f2f6; padding: 10px; 
                                                border-radius: 8px; text-align: center;
                                                border-left: 4px solid {color}; margin: 5px 0;">
                                        <b>{keyword}</b>
                                    </div>
                                    """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                    
                    # Event Distribution (if sensor data available)
                    if hotspot.get('event_count', 0) > 0 and 'event_distribution' in hotspot:
                        event_dist = hotspot['event_distribution']
                        if isinstance(event_dist, dict) and len(event_dist) > 0:
                            st.markdown("### 📊 Event Type Distribution")
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                event_dist_df = pd.DataFrame([
                                    {'Event Type': k, 'Percentage': v}
                                    for k, v in event_dist.items()
                                ])
                                
                                if not event_dist_df.empty:
                                    fig = px.pie(
                                        event_dist_df,
                                        values='Percentage',
                                        names='Event Type',
                                        title='Event Type Breakdown',
                                        color_discrete_sequence=px.colors.sequential.Reds
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                else:
                                    st.info("No event distribution data available")
                            
                            with col2:
                                st.markdown("**Event Counts:**")
                                for event_type, pct in sorted(event_dist.items(), key=lambda x: x[1], reverse=True):
                                    if 'event_types_raw' in hotspot and isinstance(hotspot['event_types_raw'], dict):
                                        count = hotspot['event_types_raw'].get(event_type, 0)
                                        st.write(f"• **{event_type.title()}**: {count} events ({pct:.1f}%)")
                                    else:
                                        st.write(f"• **{event_type.title()}**: {pct:.1f}%")
                            st.markdown("---")
                    
                    # Location & Actions
                    st.markdown("### 📍 Location & Actions")
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Coordinates:** {hotspot['center_lat']:.6f}, {hotspot['center_lng']:.6f}")
                        
                        if hotspot.get('is_corridor') and pd.notna(hotspot.get('start_lat')):
                            st.write(f"**Corridor Length:** {hotspot.get('corridor_length_m', 0):.0f}m")
                            st.write(f"**Start:** {hotspot.get('start_lat', 0):.6f}, {hotspot.get('start_lng', 0):.6f}")
                            st.write(f"**End:** {hotspot.get('end_lat', 0):.6f}, {hotspot.get('end_lng', 0):.6f}")
                        else:
                            st.write("**Type:** Point Location")
                    
                    with col2:
                        if hotspot.get('is_corridor') and pd.notna(hotspot.get('start_lat')):
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
    
    ### ✨ Enhanced Insights
    
    - **Smart Summaries:** Combines sensor + perception data into readable narrative
    - **Theme Extraction:** Automatically identifies key issues (potholes, close passes, etc.)
    - **Keyword Detection:** Highlights specific problems mentioned by cyclists
    - **Sample Comments:** Shows actual user feedback for context
    - **Validation Status:** Shows how sensor and perception data corroborate
    
    ### 📊 Data Sources
    
    - **Sensor Data:** {metrics['total_readings']:,} readings from AWS Athena
    - **Perception Reports:** {len(infra_df) + len(ride_df):,} total reports
    """)
    
    if synthetic_count > 0:
        st.markdown(f"""
        - **Enhanced Dataset:** {synthetic_count:,} AI-generated reports for richer analysis
        - Real reports preserved and marked with `is_synthetic = False`
        """)
    
    st.markdown(f"""
    - **Date Range:** {metrics['earliest_reading']} to {metrics['latest_reading']}
    """)

with st.expander("❓ FAQ"):
    st.markdown("""
    **Q: What's the difference between sensor-primary and perception-primary?**
    
    A: Sensor-primary hotspots are detected purely from bike sensor data (accelerometer events). Perception-primary starts with user reports and validates with sensor data.
    
    **Q: Why are some hotspots blue?**
    
    A: Blue hotspots (Precedence 3) have 3+ user reports but no sensor validation data. They're still important safety concerns reported by cyclists.
    
    **Q: What are the theme cards?**
    
    A: Theme cards automatically extract and highlight the main safety issues at each hotspot (e.g., potholes, close passes, obstructions) by analyzing user comments and report types.
    
    **Q: How are the smart summaries generated?**
    
    A: Summaries combine sensor event counts, severity levels, perception report themes, and sample user comments into a readable narrative that explains what's happening at each location.
    
    **Q: What does "corridor" mean?**
    
    A: A corridor is a stretch of road (typically 100m+) where issues persist along the entire length, not just at one point. Examples: vegetation blocking cycle lane for 500m.
    
    **Q: How is rank score calculated?**
    
    A: `rank_score = avg_severity + log10(event_count)`. This balances severity (how bad) with frequency (how often). A hotspot with 100 events at severity 7 gets higher priority than 2 events at severity 9.
    """)
    
    if synthetic_count > 0:
        st.markdown("""
        **Q: What are synthetic reports?**
        
        A: Synthetic reports are AI-generated perception reports created to demonstrate the dashboard's full capabilities. They're based on actual sensor hotspots and use realistic language/themes. Real reports are preserved and can be filtered using the `is_synthetic` flag.
        """)

st.markdown("---")
st.caption("🚴‍♂️ Spinovate Safety Dashboard | Enhanced Insights | Powered by Groq AI & AWS Athena")