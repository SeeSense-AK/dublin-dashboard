"""
Tab 1: Hotspot Analysis
Displays combined hotspots from sensor data, perception reports, and corridors
"""
import streamlit as st
import pandas as pd
import json
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
from pathlib import Path
from datetime import datetime, timedelta
from utils.constants import STREET_VIEW_URL_TEMPLATE
from src.ai_insights import generate_hotspot_insights, extract_user_comments


def load_preprocessed_data():
    """Load all preprocessed hotspot data"""
    data_dir = Path("data/processed/tab1_hotspots")
    
    # Load sensor hotspots (master)
    sensor_df = pd.read_csv(data_dir / "hotspots_master_with_streets.csv")
    
    # Load perception hotspots (P1)
    perception_df = pd.read_csv(data_dir / "hotspotsperception_with_streets.csv")
    
    # Load corridor hotspots (P2)
    with open(data_dir / "perception_corridors_polys.geojson", 'r') as f:
        corridors_geojson = json.load(f)
    
    # Load abnormal events for heatmap
    abnormal_events_df = pd.read_csv(data_dir / "spinovate_abnormal_events.csv")
    
    # Parse timestamps
    abnormal_events_df['timestamp'] = pd.to_datetime(abnormal_events_df['timestamp'])
    sensor_df['first_seen'] = pd.to_datetime(sensor_df['first_seen'])
    sensor_df['last_seen'] = pd.to_datetime(sensor_df['last_seen'])
    perception_df['first_seen'] = pd.to_datetime(perception_df['first_seen'], errors='coerce')
    perception_df['last_seen'] = pd.to_datetime(perception_df['last_seen'], errors='coerce')
    
    # Convert corridors to DataFrame
    corridors_data = []
    for feature in corridors_geojson['features']:
        props = feature['properties']
        geom = feature['geometry']
        
        # Get centroid for marker placement
        coords = geom['coordinates'][0]
        lats = [coord[1] for coord in coords]
        lngs = [coord[0] for coord in coords]
        center_lat = sum(lats) / len(lats)
        center_lng = sum(lngs) / len(lngs)
        
        corridors_data.append({
            'road_name': props.get('road_name', 'Unknown'),
            'center_lat': center_lat,
            'center_lng': center_lng,
            'report_count': props.get('report_count', 0),
            'weighted_score': props.get('weighted_score', 0),
            'priority_rank': props.get('priority_rank', 999),
            'priority_category': props.get('priority_category', 'MEDIUM'),
            'dominant_category': props.get('dominant_category', 'Unknown'),
            'all_comments': props.get('all_comments', ''),
            'maxspeed': props.get('maxspeed', 'N/A'),
            'lanes': props.get('lanes', 'N/A'),
            'geometry': coords
        })
    
    corridor_df = pd.DataFrame(corridors_data)
    
    return sensor_df, perception_df, corridor_df, abnormal_events_df


def filter_by_date_range(sensor_df, perception_df, corridor_df, start_date, end_date):
    """Filter hotspots by date range"""
    
    # Convert to datetime for comparison
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # Filter sensor hotspots (those that have any activity in date range)
    sensor_filtered = sensor_df[
        (sensor_df['last_seen'] >= start_dt) & 
        (sensor_df['first_seen'] <= end_dt)
    ].copy()
    
    # Filter perception hotspots
    perception_filtered = perception_df[
        (perception_df['last_seen'] >= start_dt) & 
        (perception_df['first_seen'] <= end_dt)
    ].copy()
    
    # Corridors don't have date info, so keep all
    corridor_filtered = corridor_df.copy()
    
    return sensor_filtered, perception_filtered, corridor_filtered


def select_top_hotspots(sensor_df, perception_df, corridor_df, total_count=10):
    """
    Select top hotspots based on weighted distribution and assign sequential IDs:
    - 50% from sensor data (ranked by per_type_score desc)
    - 30% from perception (ranked by total_perception_count desc)
    - 20% from corridors (ranked by priority_rank asc)
    """
    # Calculate counts for each source
    sensor_count = round(total_count * 0.5)
    perception_count = round(total_count * 0.3)
    corridor_count = total_count - sensor_count - perception_count
    
    # Sort and select top from each source
    sensor_top = sensor_df.nlargest(sensor_count, 'per_type_score').copy()
    sensor_top['source'] = 'sensor'
    sensor_top['source_label'] = 'Core Sensor Data'
    
    perception_top = perception_df.nlargest(perception_count, 'total_perception_count').copy()
    perception_top['source'] = 'perception'
    perception_top['source_label'] = 'Perception + Sensor'
    
    corridor_top = corridor_df.nsmallest(corridor_count, 'priority_rank').copy()
    corridor_top['source'] = 'corridor'
    corridor_top['source_label'] = 'Corridor Reports'
    
    # Assign sequential hotspot IDs
    hotspot_id = 1
    for df in [sensor_top, perception_top, corridor_top]:
        ids = []
        for _ in range(len(df)):
            ids.append(f"Hotspot {hotspot_id}")
            hotspot_id += 1
        df['hotspot_name'] = ids
    
    return sensor_top, perception_top, corridor_top


def get_color_by_score(score, source, priority_category=None):
    """Get color based on concern/weighted score"""
    if source == 'corridor':
        color_map = {
            'CRITICAL': '#DC2626',
            'HIGH': '#F59E0B',
            'MEDIUM': '#10B981',
            'LOW': '#6B7280'
        }
        return color_map.get(priority_category, '#6B7280')
    else:
        if score >= 0.7:
            return '#DC2626'  # Red
        elif score >= 0.5:
            return '#F59E0B'  # Orange
        elif score >= 0.3:
            return '#10B981'  # Green
        else:
            return '#6B7280'  # Gray


def create_popup_html(row, source):
    """Create HTML popup for hotspot markers"""
    
    hotspot_name = row.get('hotspot_name', 'Hotspot')
    
    if source == 'corridor':
        popup_html = f"""
        <div style="font-family: Arial; width: 320px;">
            <h4 style="color: #1E40AF; margin-bottom: 10px;">{hotspot_name}</h4>
            <p><b>Road:</b> {row['road_name']}</p>
            <p><b>Reports:</b> {row['report_count']}</p>
            <p><b>Priority:</b> {row['priority_category']}</p>
            <p><b>Issue Type:</b> {row['dominant_category']}</p>
            <p><b>Speed Limit:</b> {row['maxspeed']}</p>
            <p><b>Lanes:</b> {row['lanes']}</p>
            <hr>
            <a href="{STREET_VIEW_URL_TEMPLATE.format(lat=row['center_lat'], lng=row['center_lng'], heading=0)}" 
               target="_blank" style="color: #4285f4; text-decoration: none;">
               View in Street View
            </a>
        </div>
        """
    else:
        event_type = row.get('event_type', 'Multiple Events')
        device_count = row.get('device_count', 'N/A')
        concern_score = row.get('concern_score', 0)
        street_name = row.get('street_name', 'Unknown Street')
        event_count = row.get('event_count', 'N/A')
        
        popup_html = f"""
        <div style="font-family: Arial; width: 320px;">
            <h4 style="color: #1E40AF; margin-bottom: 10px;">{hotspot_name}</h4>
            <p><b>Location:</b> {street_name}</p>
            <p><b>Event Type:</b> {event_type}</p>
            <p><b>Event Count:</b> {event_count}</p>
            <p><b>Device Count:</b> {device_count}</p>
            <p><b>Concern Score:</b> {concern_score:.3f}</p>
            <hr>
            <a href="{STREET_VIEW_URL_TEMPLATE.format(lat=row['medoid_lat'], lng=row['medoid_lng'], heading=0)}" 
               target="_blank" style="color: #4285f4; text-decoration: none;">
               View in Street View
            </a>
        </div>
        """
    
    return popup_html


def create_hotspot_map(sensor_hotspots, perception_hotspots, corridor_hotspots, 
                       abnormal_events_df=None, show_heatmap=False, 
                       start_date=None, end_date=None):
    """Create Folium map with all hotspots and optional heatmap"""
    
    # Initialize map centered on Dublin
    m = folium.Map(
        location=[53.3498, -6.2603],
        zoom_start=12,
        tiles='CartoDB positron'
    )
    
    # Add heatmap layer if enabled
    if show_heatmap and abnormal_events_df is not None:
        # Filter events by date range
        if start_date and end_date:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            events_filtered = abnormal_events_df[
                (abnormal_events_df['timestamp'] >= start_dt) & 
                (abnormal_events_df['timestamp'] <= end_dt)
            ]
        else:
            events_filtered = abnormal_events_df
        
        # Prepare heatmap data
        heat_data = [[row['lat'], row['lng'], row['max_severity']] 
                     for idx, row in events_filtered.iterrows() 
                     if pd.notna(row['lat']) and pd.notna(row['lng'])]
        
        # Add heatmap
        HeatMap(
            heat_data,
            min_opacity=0.3,
            max_zoom=13,
            radius=15,
            blur=20,
            gradient={0.4: 'blue', 0.6: 'yellow', 0.8: 'orange', 1: 'red'}
        ).add_to(m)
    
    # Add sensor hotspots
    for idx, row in sensor_hotspots.iterrows():
        color = get_color_by_score(row['concern_score'], 'sensor')
        popup_html = create_popup_html(row, 'sensor')
        
        folium.CircleMarker(
            location=[row['medoid_lat'], row['medoid_lng']],
            radius=8,
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"{row['source_label']}: {row['street_name']}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            weight=2
        ).add_to(m)
    
    # Add perception hotspots
    for idx, row in perception_hotspots.iterrows():
        color = get_color_by_score(row['concern_score'], 'perception')
        popup_html = create_popup_html(row, 'perception')
        
        folium.CircleMarker(
            location=[row['medoid_lat'], row['medoid_lng']],
            radius=8,
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"{row['source_label']}: {row['street_name']}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            weight=2
        ).add_to(m)
    
    # Add corridor hotspots (as polygons)
    for idx, row in corridor_hotspots.iterrows():
        color = get_color_by_score(
            row['weighted_score'], 
            'corridor', 
            row['priority_category']
        )
        popup_html = create_popup_html(row, 'corridor')
        
        # Draw polygon
        coords_folium = [(coord[1], coord[0]) for coord in row['geometry']]
        
        folium.Polygon(
            locations=coords_folium,
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"Corridor: {row['road_name']}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.4,
            weight=3
        ).add_to(m)
        
        # Add center marker for easier identification
        folium.CircleMarker(
            location=[row['center_lat'], row['center_lng']],
            radius=6,
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"Corridor: {row['road_name']}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.8,
            weight=2
        ).add_to(m)
    
    return m


def display_hotspot_card(row, source):
    """Display a single hotspot as a professional card"""

    hotspot_name = row.get('hotspot_name', 'Hotspot')

    # Calculate urgency score
    if source == 'corridor':
        urgency_score = f"{row.get('weighted_score', 0):.1f}%"
        location = row.get('road_name', 'Unknown')
        event_type = row.get('dominant_category', 'N/A')
        device_count = 0
        user_reports = row.get('report_count', 0)
        lat, lng = row.get('center_lat'), row.get('center_lng')
        source_label = "🚧 Corridor Reports"
    else:
        urgency_score = f"{row.get('concern_score', 0) * 100:.1f}%"
        location = row.get('street_name', 'Unknown')
        event_type = row.get('event_type', 'N/A')
        device_count = row.get('device_count', 0)
        user_reports = row.get('total_perception_count', 0) if source == 'perception' else 0
        lat, lng = row.get('medoid_lat'), row.get('medoid_lng')
        source_label = "📊 Core Sensor Data" if source == 'sensor' else "👁️ Perception + Sensor"

    # Capitalize event type properly
    if event_type and event_type != 'N/A':
        event_type = event_type.replace('_', ' ').title()

    # Color based on urgency
    urgency_value = float(urgency_score.replace('%', ''))
    if urgency_value >= 70:
        urgency_color = '#dc2626'  # Red
        urgency_bg = 'linear-gradient(135deg, #fee2e2 0%, #fecaca 100%)'
        status_text = '🚨 HIGH URGENCY'
    elif urgency_value >= 50:
        urgency_color = '#f59e0b'  # Orange
        urgency_bg = 'linear-gradient(135deg, #fed7aa 0%, #fdba74 100%)'
        status_text = '⚠️ MEDIUM URGENCY'
    else:
        urgency_color = '#10b981'  # Green
        urgency_bg = 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)'
        status_text = '✅ LOW URGENCY'

    # Professional card HTML
    card_html = f"""
    <div class="metric-card fade-in" style="margin-bottom: 2rem; animation-delay: 0.1s;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem;">
            <div>
                <h3 style="margin: 0; color: #1a202c; font-weight: 700; font-size: 1.5rem;">{hotspot_name}</h3>
                <div style="background: {urgency_bg}; color: {urgency_color};
                           padding: 0.25rem 0.75rem; border-radius: 20px;
                           font-size: 0.8rem; font-weight: 600; display: inline-block;
                           margin-top: 0.5rem;">{status_text}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 2rem; font-weight: 700; color: {urgency_color}; margin: 0;">{urgency_score}</div>
                <div style="font-size: 0.8rem; color: #718096; text-transform: uppercase; letter-spacing: 0.5px;">Urgency Score</div>
            </div>
        </div>

        <div style="background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
                   border-radius: 12px; padding: 1rem; margin-bottom: 1.5rem;">
            <div style="color: #4a5568; font-weight: 600; margin-bottom: 0.5rem; font-size: 0.9rem;">📍 {source_label}</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                <div>
                    <div style="color: #718096; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px;">Location</div>
                    <div style="color: #2d3748; font-weight: 600; font-size: 1rem;">{location}</div>
                </div>
                <div>
                    <div style="color: #718096; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px;">Event Type</div>
                    <div style="color: #2d3748; font-weight: 600; font-size: 1rem;">{event_type}</div>
                </div>
                <div>
                    <div style="color: #718096; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px;">Devices</div>
                    <div style="color: #2d3748; font-weight: 600; font-size: 1rem;">{device_count}</div>
                </div>
                <div>
                    <div style="color: #718096; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px;">User Reports</div>
                    <div style="color: #2d3748; font-weight: 600; font-size: 1rem;">{user_reports}</div>
                </div>
            </div>
        </div>
    </div>
    """

    st.markdown(card_html, unsafe_allow_html=True)

    # Action buttons
    col1, col2 = st.columns(2)

    with col1:
        view_details = st.button(
            f"🔍 View Details",
            key=f"details_{hotspot_name}",
            use_container_width=True,
            help="Generate AI-powered safety analysis"
        )

    with col2:
        street_view_url = STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lng, heading=0)
        st.link_button(
            f"🗺️ Street View",
            street_view_url,
            use_container_width=True,
            help="Open location in Google Street View"
        )

    # Show details if button clicked
    if view_details:
        display_hotspot_details(row, source)


def display_hotspot_details(row, source):
    """Display detailed AI analysis for a hotspot"""
    
    with st.spinner("Generating AI insights..."):
        # Prepare hotspot data
        hotspot_data = row.to_dict()
        hotspot_data['source'] = source
        
        # Extract user comments
        user_comments = extract_user_comments(hotspot_data)
        
        # Generate insights
        insights = generate_hotspot_insights(hotspot_data, user_comments)
        
        # Display summary
        st.markdown("#### AI Analysis")
        st.info(insights['summary'])
        
        # Display themes as pills using columns
        if insights['themes']:
            st.markdown("#### Safety Themes")
            # Create columns based on number of themes
            theme_cols = st.columns(len(insights['themes']))
            for idx, theme in enumerate(insights['themes']):
                with theme_cols[idx]:
                    st.markdown(
                        f"<div style='background: #dbeafe; color: #1e40af; padding: 8px 12px; "
                        f"border-radius: 16px; text-align: center; font-weight: 500;'>{theme}</div>",
                        unsafe_allow_html=True
                    )
            st.markdown("<br>", unsafe_allow_html=True)
        
        # Display recommendations
        if insights['recommendations']:
            st.markdown("#### Recommendations")
            for rec in insights['recommendations']:
                st.markdown(f"- {rec}")
        
        # Display user comments
        if user_comments and len(user_comments) > 0:
            st.markdown("#### User Comments")
            # Show top 3 meaningful comments
            for i, comment in enumerate(user_comments[:3], 1):
                st.markdown(
                    f"<div style='background: #f9fafb; border-left: 4px solid #3b82f6; "
                    f"padding: 12px; margin-bottom: 12px; border-radius: 4px;'>"
                    f"<p style='margin: 0; color: #374151;'><strong>Comment {i}:</strong> {comment}</p></div>",
                    unsafe_allow_html=True
                )
        
        st.markdown("---")


def render_tab1():
    """Main function to render Tab 1"""
    
    st.header("Hotspot Analysis")
    st.markdown("Analysis combining sensor data, perception reports, and corridor surveys")
    
    # Load data
    try:
        sensor_df, perception_df, corridor_df, abnormal_events_df = load_preprocessed_data()
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return
    
    # Sidebar controls
    st.sidebar.subheader("Display Settings")
    
    # Hotspot count selector
    total_hotspots = st.sidebar.selectbox(
        "Number of hotspots to display",
        options=[10, 20, 30],
        index=0
    )
    
    # Heatmap toggle
    show_heatmap = st.sidebar.checkbox("Show Heatmap Layer", value=False)
    
    # Display data distribution info
    sensor_count = round(total_hotspots * 0.5)
    perception_count = round(total_hotspots * 0.3)
    corridor_count = total_hotspots - sensor_count - perception_count
    
    st.sidebar.info(
        f"**Distribution:**\n\n"
        f"Sensor Data: {sensor_count}\n\n"
        f"Perception + Sensor: {perception_count}\n\n"
        f"Corridor Reports: {corridor_count}"
    )
    
    # Select top hotspots
    sensor_top, perception_top, corridor_top = select_top_hotspots(
        sensor_df, perception_df, corridor_df, total_hotspots
    )
    
    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Sensor Hotspots", len(sensor_df))
        st.metric("Displaying", len(sensor_top))
    
    with col2:
        st.metric("Total Perception Hotspots", len(perception_df))
        st.metric("Displaying", len(perception_top))
    
    with col3:
        st.metric("Total Corridor Hotspots", len(corridor_df))
        st.metric("Displaying", len(corridor_top))
    
    # Create and display map
    st.subheader("Interactive Map")
    
    if show_heatmap:
        st.info("Heatmap shows density and severity of all abnormal events")
    
    with st.spinner("Loading map..."):
        m = create_hotspot_map(
            sensor_top, perception_top, corridor_top,
            abnormal_events_df, show_heatmap,
            None, None
        )
        folium_static(m, width=1200, height=600)
    
    # Display hotspot details
    st.markdown("---")
    st.subheader("Hotspot Details")
    
    # Combine all hotspots for display
    all_hotspots = []
    for idx, row in sensor_top.iterrows():
        all_hotspots.append((row, 'sensor'))
    for idx, row in perception_top.iterrows():
        all_hotspots.append((row, 'perception'))
    for idx, row in corridor_top.iterrows():
        all_hotspots.append((row, 'corridor'))
    
    # Display as cards
    for row, source in all_hotspots:
        display_hotspot_card(row, source)