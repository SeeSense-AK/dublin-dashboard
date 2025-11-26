"""
Tab 1: Hotspot Analysis - Enhanced Professional Version
Displays combined hotspots from Top 30 analysis and corridors
Power BI/Tableau-level professional styling using CSS classes
"""

import streamlit as st
import pandas as pd
import json
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
from pathlib import Path
from datetime import datetime, timedelta

# Import your original utilities and functions
try:
    from utils.constants import STREET_VIEW_URL_TEMPLATE
    from src.ai_insights import generate_hotspot_insights, extract_user_comments
except ImportError:
    # Fallback for any missing imports
    STREET_VIEW_URL_TEMPLATE = "https://www.google.com/maps?layer=c&cbll={lat},{lng}&cbp=12,{heading},0,0,0"

# ────────────────────────────────────────────────
# PROFESSIONAL COMPONENTS USING CSS CLASSES
# ────────────────────────────────────────────────

def create_section_header(title, description=None):
    """Create professional section headers using CSS classes"""
    if description:
        st.markdown(f"""
        <div class="section-header">
            <h2>{title}</h2>
            <p class="section-description">{description}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="section-header">
            <h2>{title}</h2>
        </div>
        """, unsafe_allow_html=True)

def render_summary_panel(top_30_selected, corridor_selected):
    """Render high-level summary panel with color-coded metrics"""
    
    total_hotspots = len(top_30_selected) + len(corridor_selected)
    
    # Calculate counts based on urgency/priority
    critical_count = 0
    medium_count = 0
    low_count = 0
    
    # Process Top 30
    for _, row in top_30_selected.iterrows():
        score = row.get('scores.composite_score', 0)
        if score >= 0.7:
            critical_count += 1
        elif score >= 0.3:
            medium_count += 1
        else:
            low_count += 1
            
    # Process Corridors
    for _, row in corridor_selected.iterrows():
        priority = row.get('priority_category', 'MEDIUM')
        if priority == 'CRITICAL' or priority == 'HIGH':
            critical_count += 1
        elif priority == 'MEDIUM':
            medium_count += 1
        else:
            low_count += 1

    # Add the hover card CSS
    st.markdown("""
    <style>
    .summary-card-hover {
        text-align: center; 
        background: #f8fafc; 
        padding: 1.5rem; 
        border-radius: 8px; 
        margin: 0.5rem;
        transition: all 0.3s;
        cursor: pointer;
        border: 1px solid #e5e7eb;  /* Light grey border */
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);  /* Subtle shadow by default */
    }
    .summary-card-hover:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);  /* Increased shadow on hover */
        background: #f1f5f9;
        border: 1px solid #e5e7eb;  /* Keep light grey border on hover */
    }
    
    .summary-value {
        font-size: 36px;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .summary-label {
        font-size: 14px;
        font-weight: bold;
        color: #888;
    }
    .text-red { color: #DC2626; }
    .text-amber { color: #F59E0B; }
    .text-blue { color: #3B82F6; }
    .text-white { color: #1f2937; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="summary-card-hover">
            <div class="summary-value text-white">{total_hotspots}</div>
            <div class="summary-label">Total Hotspots</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="summary-card-hover">
            <div class="summary-value text-red">{critical_count}</div>
            <div class="summary-label">Critical Priority</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="summary-card-hover">
            <div class="summary-value text-amber">{medium_count}</div>
            <div class="summary-label">Medium Priority</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class="summary-card-hover">
            <div class="summary-value text-blue">{low_count}</div>
            <div class="summary-label">Low Priority</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")

def render_compact_hotspot_list(top_30_selected, corridor_selected):
    """Render hotspots in a compact list format"""
    
    # Combine and sort all hotspots
    all_hotspots = []
    for idx, row in top_30_selected.iterrows():
        all_hotspots.append((row, 'top_30'))
    for idx, row in corridor_selected.iterrows():
        all_hotspots.append((row, 'corridor'))
        
    # Header Row
    st.markdown("""
    <div style="display: grid; grid-template-columns: 0.5fr 2fr 1fr 2fr 1.5fr 1fr 1fr 1.5fr; gap: 10px; padding: 10px; background-color: #262626; border-radius: 5px; font-weight: bold; font-size: 0.9em; color: #CCC;">
        <div>Pri</div>
        <div>Hotspot Name</div>
        <div>Score</div>
        <div>Location</div>
        <div>Event Type</div>
        <div>Devices</div>
        <div>Reports</div>
        <div>Actions</div>
    </div>
    """, unsafe_allow_html=True)
    
    # List Items
    for i, (row, source) in enumerate(all_hotspots):
        # Extract Data
        hotspot_name = row.get('hotspot_name', 'Hotspot')
        
        if source == 'corridor':
            urgency_val = float(row.get('weighted_score', 0))
            urgency_score = f"{urgency_val:.1f}%"
            location = row.get('road_name', 'Unknown')
            event_type = row.get('dominant_category', 'N/A')
            device_count = "-"
            user_reports = row.get('report_count', 0)
            lat, lng = row.get('center_lat'), row.get('center_lng')
            priority_cat = row.get('priority_category', 'MEDIUM')
            
            # Determine Color
            if priority_cat in ['CRITICAL', 'HIGH']:
                color = "#DC2626" # Red
            elif priority_cat == 'MEDIUM':
                color = "#F59E0B" # Amber
            else:
                color = "#3B82F6" # Blue
                
        else: # Top 30
            score_val = row.get('scores.composite_score', 0)
            urgency_val = score_val * 100
            urgency_score = f"{urgency_val:.1f}%"
            location = row.get('identification.street_name', 'Unknown')
            event_type = row.get('sensor_data.event_type', 'N/A')
            device_count = row.get('sensor_data.device_count', 0)
            user_reports = row.get('collision_reports.total_count', 0)
            lat, lng = row.get('identification.latitude'), row.get('identification.longitude')
            
            # Determine Color
            if urgency_val >= 70:
                color = "#DC2626"
            elif urgency_val >= 30:
                color = "#F59E0B"
            else:
                color = "#3B82F6"

        # Clean Event Type
        if event_type and event_type != 'N/A':
            event_type = event_type.replace('_', ' ').title()
            
        # Render Row
        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([0.5, 2, 1, 2, 1.5, 1, 1, 1.5])
        
        with col1:
            st.markdown(f'<div style="background-color: {color}; width: 12px; height: 12px; border-radius: 50%; margin-top: 8px;"></div>', unsafe_allow_html=True)
        with col2:
            st.write(hotspot_name)
        with col3:
            st.write(urgency_score)
        with col4:
            st.write(location)
        with col5:
            st.write(event_type)
        with col6:
            st.write(str(device_count))
        with col7:
            st.write(str(user_reports))
        with col8:
            if st.button("View Analysis", key=f"btn_{i}", use_container_width=True):
                st.session_state['selected_hotspot'] = row
                st.session_state['selected_source'] = source
                st.session_state['view_mode'] = 'detail'
                st.rerun()
                
        st.markdown("<hr style='margin: 5px 0; border-color: #333;'>", unsafe_allow_html=True)

def render_hotspot_details_page():
    """Render dedicated full-page view for hotspot analysis"""
    
    row = st.session_state.get('selected_hotspot')
    source = st.session_state.get('selected_source')
    
    if row is None:
        st.session_state['view_mode'] = 'list'
        st.rerun()
        return

    # Back Button at the top
    if st.button("← Back to List"):
        st.session_state['view_mode'] = 'list'
        st.rerun()
        
    # Extract Data
    hotspot_name = row.get('hotspot_name', 'Hotspot')
    
    if source == 'corridor':
        location = row.get('road_name', 'Unknown')
        lat, lng = row.get('center_lat'), row.get('center_lng')
        urgency_score = f"{row.get('weighted_score', 0):.1f}%"
        event_type = row.get('dominant_category', 'N/A')
        reports = row.get('report_count', 0)
        priority = row.get('priority_category', 'N/A')
    else:
        location = row.get('identification.street_name', 'Unknown')
        lat, lng = row.get('identification.latitude'), row.get('identification.longitude')
        urgency_score = f"{row.get('scores.composite_score', 0) * 100:.1f}%"
        event_type = row.get('sensor_data.event_type', 'N/A')
        reports = row.get('collision_reports.total_count', 0)
        priority = "Top 30"

    # Header Section
    st.header(f"{hotspot_name}")
    st.subheader(f"Location: {location}")
    
    # Map Section - Full width on top
    st.markdown("#### Location Map")
    try:
        m = folium.Map(location=[lat, lng], zoom_start=16, tiles='CartoDB positron')
        folium.Marker([lat, lng], popup=hotspot_name).add_to(m)
        folium_static(m, height=350)
    except Exception as e:
        st.error(f"Could not render map: {e}")
    
    # Street View Link below map
    street_view_url = STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lng, heading=0)
    st.link_button("🌐 Open Google Street View", street_view_url, use_container_width=True)
    
    # Statistics Section - Below the map with hover cards
    st.markdown("---")
    st.markdown("### Key Statistics")
    
    # Add the hover card CSS for detail page
    st.markdown("""
    <style>
    .detail-card-hover {
        text-align: center; 
        background: #f8fafc; 
        padding: 1.5rem; 
        border-radius: 8px; 
        margin: 0.5rem;
        transition: all 0.3s;
        cursor: pointer;
        border: 1px solid #e5e7eb;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }
    .detail-card-hover:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        background: #f1f5f9;
        border: 1px solid #e5e7eb;
    }
    .detail-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #1f2937;
        margin: 0.5rem 0;
    }
    .detail-label {
        font-size: 0.9rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create stats in columns with hover cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="detail-card-hover">
            <div class="detail-label">Urgency Score</div>
            <div class="detail-value">{urgency_score}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="detail-card-hover">
            <div class="detail-label">Priority Level</div>
            <div class="detail-value">{priority}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="detail-card-hover">
            <div class="detail-label">Event Type</div>
            <div class="detail-value">{event_type}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class="detail-card-hover">
            <div class="detail-label">Reports</div>
            <div class="detail-value">{reports}</div>
        </div>
        """, unsafe_allow_html=True)

    # Rest of the function remains the same (no hover effects on other components)
    # Quick Summary below statistics
    if source == 'top_30':
        theme_summary = row.get('narrative.theme_summary')
        if theme_summary:
            st.markdown("### Quick Summary")
            st.info(theme_summary)

    # Bottom Section: AI Analysis
    st.markdown("---")
    st.markdown("## AI Safety Analysis")
    
    # Generate/Display Full Insights
    with st.spinner("Generating detailed advisory report..."):
        hotspot_data = row.to_dict()
        hotspot_data['source'] = source
        
        try:
            if source == 'top_30':
                user_comments = row.get('narrative.sample_descriptions', [])
            else:
                user_comments = extract_user_comments(hotspot_data)
                
            insights = generate_hotspot_insights(hotspot_data, user_comments)
            
            # Summary Section
            st.markdown("### Analysis Summary")
            st.write(insights['summary'])
            
            # Themes and Recommendations in columns
            st.markdown("<br>", unsafe_allow_html=True)
            col_a, col_b = st.columns(2, gap="large")
            
            with col_a:
                if insights.get('themes'):
                    st.markdown("### Key Safety Themes")
                    for theme in insights['themes']:
                        st.markdown(f"• {theme}")
                else:
                    st.markdown("### Key Safety Themes")
                    st.info("No specific themes identified")
            
            with col_b:
                if insights.get('recommendations'):
                    st.markdown("### Recommended Mitigation Actions")
                    for rec in insights['recommendations']:
                        st.markdown(f"• {rec}")
                else:
                    st.markdown("### Recommended Mitigation Actions")
                    st.info("No specific recommendations available")
                    
        except Exception as e:
            st.error(f"Analysis unavailable: {e}")
            st.info("This feature requires the AI insights module to be properly configured.")

    # Additional spacing at bottom
    st.markdown("<br><br>", unsafe_allow_html=True)

# ────────────────────────────────────────────────
# DATA LOADING AND PROCESSING
# ────────────────────────────────────────────────

def load_preprocessed_data():
    """Load Top 30 hotspots and Corridor data"""
    data_dir = Path("data/processed/tab1_hotspots")
    
    # Load Top 30 Hotspots (JSON)
    try:
        with open(data_dir / "top_30_hotspots.json", 'r') as f:
            top_30_data = json.load(f)
        # Normalize nested JSON to flat DataFrame
        top_30_df = pd.json_normalize(top_30_data)
    except FileNotFoundError:
        st.error("top_30_hotspots.json not found. Please check data directory.")
        top_30_df = pd.DataFrame()

    # Load corridor hotspots (P2)
    with open(data_dir / "perception_corridors_polys.geojson", 'r') as f:
        corridors_geojson = json.load(f)
    
    # Load abnormal events for heatmap
    abnormal_events_df = pd.read_csv(data_dir / "spinovate_abnormal_events.csv")
    
    # Parse timestamps
    abnormal_events_df['timestamp'] = pd.to_datetime(abnormal_events_df['timestamp'])
    
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
    
    return top_30_df, corridor_df, abnormal_events_df

def select_top_hotspots(top_30_df, corridor_df, total_count=10):
    """
    Select top hotspots based on weighted distribution:
    - 70% from Top 30 Hotspots (already ranked)
    - 30% from Corridors (ranked by priority_rank)
    """
    if top_30_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Calculate counts for each source
    top_30_count = round(total_count * 0.7)
    corridor_count = total_count - top_30_count
    
    # Select top from Top 30 (already sorted by rank in JSON usually, but ensure sort)
    if 'rank' in top_30_df.columns:
        top_30_selected = top_30_df.sort_values('rank').head(top_30_count).copy()
    else:
        top_30_selected = top_30_df.head(top_30_count).copy()
        
    top_30_selected['source'] = 'top_30'
    top_30_selected['source_label'] = 'Top 30 Priority'
    
    # Select top from Corridors
    corridor_selected = corridor_df.nsmallest(corridor_count, 'priority_rank').copy()
    corridor_selected['source'] = 'corridor'
    corridor_selected['source_label'] = 'Corridor Reports'
    
    # Assign sequential hotspot IDs for display
    hotspot_id = 1
    for df in [top_30_selected, corridor_selected]:
        ids = []
        for _ in range(len(df)):
            ids.append(f"Hotspot {hotspot_id}")
            hotspot_id += 1
        df['hotspot_name'] = ids
    
    return top_30_selected, corridor_selected

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
        # Top 30 score is 0-1
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
        <div class="popup-content">
            <h4 class="popup-title">{hotspot_name}</h4>
            <p><b>Road:</b> {row['road_name']}</p>
            <p><b>Reports:</b> {row['report_count']}</p>
            <p><b>Priority:</b> {row['priority_category']}</p>
            <p><b>Issue Type:</b> {row['dominant_category']}</p>
            <hr>
            <a href="{STREET_VIEW_URL_TEMPLATE.format(lat=row['center_lat'], lng=row['center_lng'], heading=0)}" 
               target="_blank" class="street-view-link">
               View in Street View
            </a>
        </div>
        """
    else:
        # Top 30
        event_type = row.get('sensor_data.event_type', 'Multiple Events')
        device_count = row.get('sensor_data.device_count', 'N/A')
        concern_score = row.get('scores.composite_score', 0)
        street_name = row.get('identification.street_name', 'Unknown Street')
        event_count = row.get('sensor_data.event_count', 'N/A')
        collision_count = row.get('collision_reports.total_count', 0)
        
        popup_html = f"""
        <div class="popup-content">
            <h4 class="popup-title">{hotspot_name}</h4>
            <p><b>Location:</b> {street_name}</p>
            <p><b>Event Type:</b> {event_type}</p>
            <p><b>Sensor Events:</b> {event_count}</p>
            <p><b>Collisions:</b> {collision_count}</p>
            <p><b>Score:</b> {concern_score:.3f}</p>
            <hr>
            <a href="{STREET_VIEW_URL_TEMPLATE.format(lat=row['identification.latitude'], lng=row['identification.longitude'], heading=0)}" 
               target="_blank" class="street-view-link">
               View in Street View
            </a>
        </div>
        """
    
    return popup_html

def create_hotspot_map(top_30_selected, corridor_selected, 
                       abnormal_events_df=None, show_heatmap=False):
    """Create Folium map with all hotspots and optional heatmap"""
    
    # Initialize map centered on Dublin
    m = folium.Map(
        location=[53.3498, -6.2603],
        zoom_start=12,
        tiles='CartoDB positron'
    )
    
    # Add heatmap layer if enabled
    if show_heatmap and abnormal_events_df is not None:
        # Prepare heatmap data
        heat_data = [[row['lat'], row['lng'], row['max_severity']] 
                     for idx, row in abnormal_events_df.iterrows() 
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
    
    # Add Top 30 hotspots
    for idx, row in top_30_selected.iterrows():
        color = get_color_by_score(row.get('scores.composite_score', 0), 'top_30')
        popup_html = create_popup_html(row, 'top_30')
        
        folium.CircleMarker(
            location=[row['identification.latitude'], row['identification.longitude']],
            radius=8,
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"{row['source_label']}: {row['identification.street_name']}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            weight=2
        ).add_to(m)
    
    # Add corridor hotspots (as polygons)
    for idx, row in corridor_selected.iterrows():
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

# ────────────────────────────────────────────────
# ENHANCED MAIN RENDER FUNCTION
# ────────────────────────────────────────────────

def render_tab1_enhanced():
    """Enhanced main function to render Tab 1 with professional styling"""
    
    # Initialize Session State
    if 'view_mode' not in st.session_state:
        st.session_state['view_mode'] = 'list'
    if 'selected_hotspot' not in st.session_state:
        st.session_state['selected_hotspot'] = None
        
    # Check View Mode
    if st.session_state['view_mode'] == 'detail':
        render_hotspot_details_page()
        return

    create_section_header("Hotspot Analysis", "Analysis combining Top 30 Priority Hotspots and Corridor Surveys")
    
    # Load data
    try:
        top_30_df, corridor_df, abnormal_events_df = load_preprocessed_data()
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return
    
    # Enhanced sidebar controls
    st.sidebar.markdown("---")
    st.sidebar.subheader("Display Settings")
    
    # Hotspot count selector
    total_hotspots = st.sidebar.selectbox(
        "Number of hotspots to display",
        options=[10, 20, 30],
        index=0
    )
    
    # Heatmap toggle
    show_heatmap = st.sidebar.checkbox("Show Heatmap Layer", value=False)
    
    # Select top hotspots (70/30 split)
    top_30_selected, corridor_selected = select_top_hotspots(
        top_30_df, corridor_df, total_hotspots
    )
    
    # 1. Summary Panel
    render_summary_panel(top_30_selected, corridor_selected)
    
    # 2. Map Section
    create_section_header("Interactive Map", "Visual representation of safety hotspots across Dublin")
    
    if show_heatmap:
        st.info("Heatmap shows density and severity of all abnormal events")
    
    st.markdown('<div class="map-container">', unsafe_allow_html=True)
    with st.spinner("Loading enhanced map visualization..."):
        m = create_hotspot_map(
            top_30_selected, corridor_selected,
            abnormal_events_df, show_heatmap
        )
        folium_static(m, width=1200, height=600)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 3. Compact List Section
    st.markdown("---")
    create_section_header("Hotspot Action List", "Prioritized list of safety concerns requiring attention")
    
    render_compact_hotspot_list(top_30_selected, corridor_selected)

# For testing
if __name__ == "__main__":
    render_tab1_enhanced()