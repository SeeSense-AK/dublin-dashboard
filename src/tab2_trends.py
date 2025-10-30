"""
Tab 2: Route Popularity Trends
Professional implementation using GeoJSON road segments for visualization
and CSV data for analysis content
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import plotly.express as px
import json
import re
import os
from pathlib import Path

try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

def load_route_popularity_data():
    """Load preprocessed route popularity data from CSV"""
    try:
        # Use relative path for Streamlit Cloud
        csv_path = "data/processed/tab2_trend/route_popularity/Spinovate Tab 2 - Popularity.csv"
        
        # Alternative paths to try
        alternative_paths = [
            csv_path,
            "Spinovate Tab 2 - Popularity.csv",
            "data/Spinovate Tab 2 - Popularity.csv",
            os.path.join("data", "processed", "tab2_trend", "route_popularity", "Spinovate Tab 2 - Popularity.csv")
        ]
        
        df = None
        for path in alternative_paths:
            if os.path.exists(path):
                df = pd.read_csv(path)
                break
        
        if df is None:
            raise FileNotFoundError("CSV file not found in any expected location")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Parse week dates
        if 'week' in df.columns:
            df['week_date'] = pd.to_datetime(df['week'], format='%d %b %Y', errors='coerce')
        
        # Extract trip numbers for metrics
        def extract_trips_number(text):
            if pd.isna(text):
                return 0
            match = re.search(r'(\d+)\s+trips?', str(text))
            return int(match.group(1)) if match else 0
        
        if 'peak_trips' in df.columns:
            df['trips_count'] = df['peak_trips'].apply(extract_trips_number)
        
        return df
    
    except Exception as e:
        st.error(f"Error loading CSV data: {e}")
        return pd.DataFrame()

def load_road_segments():
    """Load road segment geometry from GeoJSON file"""
    try:
        # Use relative path for Streamlit Cloud
        geojson_path = "data/processed/tab2_trend/route_popularity/active_segments.geojson"
        
        # Alternative paths to try
        alternative_paths = [
            geojson_path,
            "active_segments.geojson",
            "data/active_segments.geojson",
            os.path.join("data", "processed", "tab2_trend", "route_popularity", "active_segments.geojson")
        ]
        
        geojson_file_path = None
        for path in alternative_paths:
            if os.path.exists(path):
                geojson_file_path = path
                break
        
        if geojson_file_path is None:
            raise FileNotFoundError("GeoJSON file not found in any expected location")
        
        if GEOPANDAS_AVAILABLE:
            # Try geopandas first
            try:
                gdf = gpd.read_file(geojson_file_path)
                return gdf
            except Exception as e:
                st.warning(f"Geopandas failed: {e}. Trying fallback method...")
        
        # Fallback: Load GeoJSON directly with json
        with open(geojson_file_path, 'r') as f:
            geojson_data = json.load(f)
        
        # Convert to DataFrame with geometry parsing
        roads_data = []
        for feature in geojson_data['features']:
            properties = feature['properties']
            geometry = feature['geometry']
            
            # Create a simple geometry object
            roads_data.append({
                'street_name': properties.get('street_name', 'Unknown'),
                'geometry_type': geometry['type'],
                'coordinates': geometry['coordinates']
            })
        
        return pd.DataFrame(roads_data)
    
    except Exception as e:
        st.error(f"Error loading GeoJSON data: {e}")
        return pd.DataFrame()

def get_color_for_route(color_name):
    """Convert color name to hex color"""
    color_map = {
        'Green': '#22c55e',
        'Red': '#ef4444',
        'Yellow': '#eab308',
        'Blue': '#3b82f6'
    }
    return color_map.get(color_name, '#6b7280')

def create_trend_visualization(street_name, trips_count, color):
    """Create trend visualization based on available data"""
    weeks = list(range(1, 13))
    
    # Use actual trip count as baseline
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weeks,
        y=[trips_count] * len(weeks),
        mode='lines+markers',
        line=dict(color=get_color_for_route(color), width=3),
        marker=dict(size=6),
        name='Peak Weekly Trips',
        hovertemplate='<b>Week %{x}</b><br>Peak Trips: %{y}<extra></extra>'
    ))
    
    fig.update_layout(
        title=f'{street_name} - Peak Performance',
        xaxis_title='Week',
        yaxis_title='Trip Count',
        height=300,
        margin=dict(l=40, r=40, t=50, b=40),
        font=dict(size=12),
        showlegend=False,
        plot_bgcolor='white'
    )
    
    return fig

def create_route_map(df, road_segments_df):
    """Create map with actual road segment polylines from GeoJSON"""
    dublin_center = [53.3498, -6.2603]
    m = folium.Map(location=dublin_center, zoom_start=12, tiles='CartoDB positron')
    
    routes_added = 0
    
    # Iterate through road segments
    for idx, segment_row in road_segments_df.iterrows():
        street_name = segment_row['street_name']
        
        # Find corresponding data in CSV
        csv_data = df[df['street_name'] == street_name]
        
        if csv_data.empty:
            continue  # Skip if no corresponding data in CSV
        
        route_data = csv_data.iloc[0]
        color = route_data.get('Colour', 'Gray')
        trips_count = route_data.get('trips_count', 0)
        
        # Determine status text
        status_text = "Highly Popular" if color == 'Green' else "Popularity Dropped"
        
        # Create popup with just route information
        popup_html = f"""
        <div style="width: 350px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5;">
            <h4 style="margin: 0 0 16px 0; color: {get_color_for_route(color)}; 
                       font-size: 18px; font-weight: 600;">
                {street_name}
            </h4>
            
            <div style="margin-bottom: 16px;">
                <div style="margin-bottom: 12px;">
                    <strong>Status:</strong> <span style="color: {get_color_for_route(color)}; font-weight: 600;">{status_text}</span>
                </div>
                
                <div style="margin-bottom: 16px;">
                    <strong>Note:</strong><br>
                    <div style="font-size: 14px; color: #374151; line-height: 1.4; margin-top: 8px;">
                        {str(route_data.get('peak_trips', 'No data available'))}
                    </div>
                </div>
            </div>
        </div>
        """
        
        # Handle geometry based on available data
        if GEOPANDAS_AVAILABLE and hasattr(segment_row, 'geometry'):
            # Original geopandas method
            geometry = segment_row['geometry']
            
            if geometry.geom_type == 'MultiLineString':
                for line in geometry.geoms:
                    coords = [[point[1], point[0]] for point in line.coords]
                    folium.PolyLine(
                        locations=coords,
                        color=get_color_for_route(color),
                        weight=5,
                        opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=400),
                        tooltip=street_name
                    ).add_to(m)
            
            elif geometry.geom_type == 'LineString':
                coords = [[point[1], point[0]] for point in geometry.coords]
                folium.PolyLine(
                    locations=coords,
                    color=get_color_for_route(color),
                    weight=5,
                    opacity=0.8,
                    popup=folium.Popup(popup_html, max_width=400),
                    tooltip=street_name
                ).add_to(m)
        
        else:
            # Fallback method using raw coordinates
            geometry_type = segment_row.get('geometry_type', '')
            coordinates = segment_row.get('coordinates', [])
            
            if geometry_type == 'MultiLineString' and coordinates:
                for line_coords in coordinates:
                    coords = [[point[1], point[0]] for point in line_coords]  # Convert to [lat, lng]
                    folium.PolyLine(
                        locations=coords,
                        color=get_color_for_route(color),
                        weight=5,
                        opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=400),
                        tooltip=street_name
                    ).add_to(m)
            
            elif geometry_type == 'LineString' and coordinates:
                coords = [[point[1], point[0]] for point in coordinates]  # Convert to [lat, lng]
                folium.PolyLine(
                    locations=coords,
                    color=get_color_for_route(color),
                    weight=5,
                    opacity=0.8,
                    popup=folium.Popup(popup_html, max_width=400),
                    tooltip=street_name
                ).add_to(m)
        
        routes_added += 1
    
    # Add professional legend
    if routes_added > 0:
        legend_html = """
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 200px; height: 100px; 
                    background-color: white; border: 1px solid #d1d5db; z-index:9999; 
                    font-size: 14px; padding: 16px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <div style="font-weight: 600; margin-bottom: 12px; color: #111827;">Route Performance</div>
        <div style="margin-bottom: 8px;">
            <span style="display: inline-block; width: 16px; height: 3px; background-color: #22c55e; margin-right: 8px;"></span>
            <span style="color: #374151;">Highly Popular</span>
        </div>
        <div style="margin-bottom: 8px;">
            <span style="display: inline-block; width: 16px; height: 3px; background-color: #ef4444; margin-right: 8px;"></span>
            <span style="color: #374151;">Popularity Dropped</span>
        </div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
    
    return m, routes_added

def show_route_details(df, selected_street):
    """Display detailed analysis for selected route"""
    if not selected_street:
        return
    
    street_data = df[df['street_name'] == selected_street]
    if street_data.empty:
        st.error(f"No data found for {selected_street}")
        return
    
    row = street_data.iloc[0]
    
    st.subheader(f"Route Analysis: {selected_street}")
    
    # Key metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Peak Weekly Trips", f"{row.get('trips_count', 0):,}")
    
    with col2:
        st.metric("Performance Status", f"{row.get('Colour', 'Unknown')}")
    
    with col3:
        st.metric("Peak Week", row.get('week', 'N/A'))
    
    # Weather impact analysis
    st.subheader("Weather Impact Analysis")
    st.write(row.get('weather_impact_note', 'No weather data available'))
    
    # Peak performance details
    st.subheader("Peak Performance Details")
    st.write(row.get('peak_trips', 'No peak data available'))
    
    # Route summary
    st.subheader("Route Summary")
    st.write(row.get('summary', 'No summary available'))

def render_tab2():
    """Main function to render Tab 2"""
    
    # Load data
    df = load_route_popularity_data()
    road_segments_df = load_road_segments()
    
    if df.empty:
        st.error("Could not load route popularity data")
        st.info("Please ensure the CSV file exists and contains the required data")
        return
    
    if road_segments_df.empty:
        st.error("Could not load road segment geometry")
        st.info("Please ensure the active_segments.geojson file exists")
        return
    
    # Map section (first thing on the page)
    st.subheader("Route Popularity")
    
    route_map, routes_added = create_route_map(df, road_segments_df)
    
    if routes_added > 0:
        map_data = st_folium(route_map, height=500, width=None, key="route_map")
        
        # Check if user clicked on a popup and extract street name
        clicked_street = None
        if map_data and 'last_object_clicked_popup' in map_data and map_data['last_object_clicked_popup']:
            popup_content = str(map_data['last_object_clicked_popup'])
            
            # The popup content is plain text, street name appears first
            # Check which street name appears at the very beginning
            for street_name in df['street_name'].tolist():
                if popup_content.strip().startswith(street_name):
                    clicked_street = street_name
                    break
            
            # Fallback: if no street starts the content, find the one that appears earliest
            if not clicked_street:
                earliest_position = len(popup_content)
                for street_name in df['street_name'].tolist():
                    position = popup_content.find(street_name)
                    if position != -1 and position < earliest_position:
                        clicked_street = street_name
                        earliest_position = position
        
        # Show button only if a street popup was clicked
        if clicked_street:
            st.markdown("---")
            if st.button(f"🔍 View Detailed AI Analysis for {clicked_street}", 
                        type="primary", 
                        use_container_width=True,
                        key=f"analyze_{clicked_street}"):
                
                # Show spinner and loading
                with st.spinner("Generating AI insights..."):
                    import time
                    time.sleep(4)  # 4 second delay
                
                # Show detailed analysis
                show_route_details(df, clicked_street)
    else:
        st.warning("No routes could be displayed. Please check data consistency between CSV and GeoJSON files.")

# For testing
if __name__ == "__main__":
    render_tab2()
