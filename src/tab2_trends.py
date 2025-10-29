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

try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

def load_route_popularity_data():
    """Load preprocessed route popularity data from CSV"""
    try:
        csv_path = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/data/processed/tab2_trend/route_popularity/Spinovate Tab 2 - Popularity.csv"
        df = pd.read_csv(csv_path)
        
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
        geojson_path = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/data/processed/tab2_trend/route_popularity/active_segments.geojson"
        
        if GEOPANDAS_AVAILABLE:
            # Try geopandas first
            try:
                gdf = gpd.read_file(geojson_path)
                return gdf
            except Exception as e:
                st.warning(f"Geopandas failed: {e}. Trying fallback method...")
        
        # Fallback: Load GeoJSON directly with json
        with open(geojson_path, 'r') as f:
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
    m = folium.Map(location=dublin_center, zoom_start=12, tiles='OpenStreetMap')
    
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
        
        # Create popup with preprocessed data
        popup_html = f"""
        <div style="width: 400px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5;">
            <h4 style="margin: 0 0 16px 0; color: {get_color_for_route(color)}; 
                       border-bottom: 2px solid {get_color_for_route(color)}; padding-bottom: 8px; font-size: 16px;">
                {street_name}
            </h4>
            
            <div style="background: #f8f9fa; padding: 12px; border-radius: 8px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="font-weight: 600;">Status:</span>
                    <span style="color: {get_color_for_route(color)}; font-weight: 600;">{color}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="font-weight: 600;">Peak Trips:</span>
                    <span style="font-weight: 600;">{trips_count:,}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="font-weight: 600;">Peak Week:</span>
                    <span>{route_data.get('week', 'N/A')}</span>
                </div>
            </div>
            
            <div style="margin-bottom: 16px;">
                <div style="font-weight: 600; margin-bottom: 8px;">Weather Impact:</div>
                <div style="font-size: 14px; color: #6b7280; line-height: 1.4;">
                    {str(route_data.get('weather_impact_note', ''))[:200]}{'...' if len(str(route_data.get('weather_impact_note', ''))) > 200 else ''}
                </div>
            </div>
            
            <div style="text-align: center; padding-top: 12px; border-top: 1px solid #e5e7eb;">
                <small style="color: #6b7280;">Select route below for detailed analysis</small>
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
                        popup=folium.Popup(popup_html, max_width=450),
                        tooltip=f"{street_name}: {color} status"
                    ).add_to(m)
            
            elif geometry.geom_type == 'LineString':
                coords = [[point[1], point[0]] for point in geometry.coords]
                folium.PolyLine(
                    locations=coords,
                    color=get_color_for_route(color),
                    weight=5,
                    opacity=0.8,
                    popup=folium.Popup(popup_html, max_width=450),
                    tooltip=f"{street_name}: {color} status"
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
                        popup=folium.Popup(popup_html, max_width=450),
                        tooltip=f"{street_name}: {color} status"
                    ).add_to(m)
            
            elif geometry_type == 'LineString' and coordinates:
                coords = [[point[1], point[0]] for point in coordinates]  # Convert to [lat, lng]
                folium.PolyLine(
                    locations=coords,
                    color=get_color_for_route(color),
                    weight=5,
                    opacity=0.8,
                    popup=folium.Popup(popup_html, max_width=450),
                    tooltip=f"{street_name}: {color} status"
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
            <span style="color: #374151;">Strong Performance</span>
        </div>
        <div style="margin-bottom: 8px;">
            <span style="display: inline-block; width: 16px; height: 3px; background-color: #ef4444; margin-right: 8px;"></span>
            <span style="color: #374151;">Needs Attention</span>
        </div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
    
    return m, routes_added

def show_route_details(df, selected_street):
    """Display detailed analysis for selected route"""
    if not selected_street:
        st.info("Select a route from the dropdown above to view detailed analysis")
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
    
    # Visualization
    st.plotly_chart(
        create_trend_visualization(selected_street, row.get('trips_count', 0), row.get('Colour', 'Gray')),
        use_container_width=True
    )
    
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
    st.header("Route Popularity Trends")
    st.markdown("Analysis of cycling route performance and usage patterns across Dublin")
    
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
    
    # Data validation
    csv_streets = set(df['street_name'].unique())
    
    if GEOPANDAS_AVAILABLE and hasattr(road_segments_df, 'empty') and not road_segments_df.empty:
        geojson_streets = set(road_segments_df['street_name'].unique())
    else:
        geojson_streets = set(road_segments_df['street_name'].unique()) if not road_segments_df.empty else set()
    
    matching_streets = csv_streets.intersection(geojson_streets)
    missing_from_geojson = csv_streets - geojson_streets
    missing_from_csv = geojson_streets - csv_streets
    
    if missing_from_geojson:
        st.warning(f"Streets in CSV but not in GeoJSON: {missing_from_geojson}")
    if missing_from_csv:
        st.warning(f"Streets in GeoJSON but not in CSV: {missing_from_csv}")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_routes = len(df)
        st.metric("Total Routes", total_routes)
    
    with col2:
        green_routes = len(df[df['Colour'] == 'Green'])
        st.metric("Strong Performance", green_routes)
    
    with col3:
        red_routes = len(df[df['Colour'] == 'Red'])
        st.metric("Needs Attention", red_routes)
    
    with col4:
        avg_trips = df['trips_count'].mean() if 'trips_count' in df.columns else 0
        st.metric("Average Peak Trips", f"{avg_trips:.0f}")
    
    st.markdown("---")
    
    # Map section
    st.subheader("Interactive Route Map")
    st.markdown("Click on route lines or markers to view summary information")
    
    route_map, routes_added = create_route_map(df, road_segments_df)
    
    if routes_added > 0:
        st.markdown(f"Displaying {routes_added} routes with matching data ({len(matching_streets)} streets matched)")
        map_data = st_folium(route_map, height=500, width=None, key="route_map")
    else:
        st.warning("No routes could be displayed. Please check data consistency between CSV and GeoJSON files.")
    
    st.markdown("---")
    
    # Route selector for detailed analysis
    st.subheader("Detailed Route Analysis")
    selected_street = st.selectbox(
        "Select a route for comprehensive analysis:",
        options=[''] + df['street_name'].tolist(),
        help="Choose a route to view detailed performance metrics and analysis"
    )
    
    if selected_street:
        show_route_details(df, selected_street)
    else:
        # Overview section
        st.markdown("### Performance Overview")
        
        # Create summary table
        display_df = df[['street_name', 'week', 'trips_count', 'Colour']].copy()
        display_df.columns = ['Street Name', 'Peak Week', 'Peak Trips', 'Status']
        display_df = display_df.sort_values('Peak Trips', ascending=False)
        
        # Style the table
        def color_status(val):
            if val == 'Green':
                return 'background-color: #dcfce7; color: #166534; font-weight: 600; text-align: center;'
            elif val == 'Red':
                return 'background-color: #fecaca; color: #dc2626; font-weight: 600; text-align: center;'
            return 'text-align: center;'
        
        styled_df = display_df.style.applymap(color_status, subset=['Status'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # Performance charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Status distribution
            status_counts = df['Colour'].value_counts()
            fig_pie = px.pie(
                values=status_counts.values, 
                names=status_counts.index,
                title="Performance Distribution",
                color_discrete_map={'Green': '#22c55e', 'Red': '#ef4444'}
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(font=dict(size=12))
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Trip count comparison
            fig_bar = px.bar(
                df.sort_values('trips_count', ascending=True), 
                x='trips_count', 
                y='street_name',
                color='Colour',
                title="Peak Weekly Trips by Route",
                color_discrete_map={'Green': '#22c55e', 'Red': '#ef4444'},
                orientation='h'
            )
            fig_bar.update_layout(
                yaxis_title="Route",
                xaxis_title="Peak Weekly Trips",
                font=dict(size=12)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

# For testing
if __name__ == "__main__":
    render_tab2()