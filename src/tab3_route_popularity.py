"""
Tab 3: Route Popularity Analysis - Enhanced Professional Version
Performance trends and popularity metrics for cycling routes
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import plotly.graph_objects as go
import json
import re
import os
from branca.element import MacroElement, Template

try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

# ════════════════════════════════════════════════════════════════════════════════
# PROFESSIONAL COMPONENTS
# ════════════════════════════════════════════════════════════════════════════════

def create_section_header(title, description=None):
    """Create professional section headers"""
    st.markdown(f"""
    <div style="margin-bottom: 1.5rem;">
        <h2 style="color: #1f2937; margin-bottom: 0.5rem; font-weight: 600;">{title}</h2>
        {f'<p style="color: #6b7280; margin: 0;">{description}</p>' if description else ''}
    </div>
    """, unsafe_allow_html=True)

def create_route_metrics(df):
    """Create professional metrics for route analysis"""
    col1, col2, col3, col4 = st.columns(4)
    
    total_routes = len(df['street_name'].unique()) if not df.empty else 0
    popular_routes = len(df[df['Colour'] == 'Green']) if not df.empty else 0
    declined_routes = len(df[df['Colour'] == 'Red']) if not df.empty else 0
    avg_trips = int(df['trips_count'].mean()) if not df.empty and 'trips_count' in df.columns else 0
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Total Routes</div>
            <div class="kpi-value">{total_routes}</div>
            <div class="kpi-change">Active Monitoring</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Popular Routes</div>
            <div class="kpi-value">{popular_routes}</div>
            <div class="kpi-change positive">High Traffic</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Declined Routes</div>
            <div class="kpi-value">{declined_routes}</div>
            <div class="kpi-change negative">Lower Traffic</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Avg Weekly Trips</div>
            <div class="kpi-value">{avg_trips:,}</div>
            <div class="kpi-change">Per Route</div>
        </div>
        """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# DATA LOADING FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_time_of_day_data():
    """Load time of day data from JSON"""
    try:
        alternative_paths = [
            "time-of-the-day.json",
            "data/time-of-the-day.json",
            "data/processed/tab2_trend/route_popularity/time-of-the-day.json",
            os.path.join("data", "processed", "tab2_trend", "time-of-the-day.json"),
        ]
        
        for path in alternative_paths:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
        
        return []
    except Exception as e:
        st.warning(f"Could not load time of day data: {e}")
        return []

@st.cache_data
def load_day_of_week_data():
    """Load day of week data from JSON"""
    try:
        alternative_paths = [
            "day_of_week_simple_12_streets.json",
            "data/day_of_week_simple_12_streets.json",
            "data/processed/tab2_trend/route_popularity/day_of_week_simple_12_streets.json",
            os.path.join("data", "processed", "tab2_trend", "day_of_week_simple_12_streets.json"),
        ]
        
        for path in alternative_paths:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
        
        return {}
    except Exception as e:
        st.warning(f"Could not load day of week data: {e}")
        return {}

@st.cache_data
def load_street_trends_data():
    """Load street trends data from JSON"""
    try:
        alternative_paths = [
            "clean_street_trends.json",
            "data/clean_street_trends.json",
            "data/processed/tab2_trend/route_popularity/clean_street_trends.json",
            os.path.join("data", "processed", "tab2_trend", "clean_street_trends.json"),
        ]
        
        for path in alternative_paths:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
        
        return {}
    except Exception as e:
        st.warning(f"Could not load street trends data: {e}")
        return {}

def create_route_detail_card(street_name, row):
    """Create professional route detail cards with matplotlib trend visualization"""
    
    # Load additional data for new cards
    time_of_day_data = load_time_of_day_data()
    day_of_week_data = load_day_of_week_data()
    street_trends_data = load_street_trends_data()
    
    # Get peak vs non-peak data for this street
    traffic_type = "N/A"
    peak_percentage = 0
    non_peak_percentage = 0
    for item in time_of_day_data:
        if item.get('street') == street_name:
            peak_percentage = item.get('peak_non_peak', {}).get('peak', 0)
            non_peak_percentage = item.get('peak_non_peak', {}).get('non_peak', 0)
            traffic_type = "Commuter" if peak_percentage >= non_peak_percentage else "Leisure"
            break
    
    # Get day of week data for this street
    busiest_day = "N/A"
    day_of_week_street_data = day_of_week_data.get(street_name, {})
    if day_of_week_street_data:
        busiest_day = max(day_of_week_street_data, key=day_of_week_street_data.get)
    
    # Create the main card container
    with st.container():
        # Card header with centered road name
        st.markdown(f"""
        <div style="background: light grey; border-radius: 8px; padding: 2rem; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 2rem;">
            <div style="text-align: center;">
                <h3 style="margin: 0 0 0rem 0; color: #1f2937; font-weight: 600; font-size: 2.5rem;">{street_name}</h3>
            </div>
        """, unsafe_allow_html=True)
        
        color = row.get('Colour', 'Gray')
        trips_count = row.get('trips_count', 0)
        popularity_status = "Improved" if color == 'Green' else "Dropped"
        peak_info = row.get('peak_trips', 'No data available')
        summary = row.get('summary', 'No summary available')
        weather_impact = row.get('weather_impact_note', 'No weather data available')
        
        # Card hover style
        card_hover_style = """
        <style>
        .metric-card-hover {
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
        .metric-card-hover:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            background: #f1f5f9;
            border: 1px solid #e5e7eb;
        }
        </style>
        """
        st.markdown(card_hover_style, unsafe_allow_html=True)
        
        # Metrics using 4 columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card-hover">
                <div style="font-size: 1.05rem; color: #6b7280; font-weight: 600; margin-bottom: 0.75rem;">Peak Weekly Trips</div>
                <div style="font-size: 1.50rem; font-weight: 700; color: #1f2937;">{trips_count:,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card-hover">
                <div style="font-size: 1.05rem; color: #6b7280; font-weight: 600; margin-bottom: 0.75rem;">Traffic Type</div>
                <div style="font-size: 1.50rem; font-weight: 700; color: #1f2937;">{traffic_type}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card-hover">
                <div style="font-size: 1.05rem; color: #6b7280; font-weight: 600; margin-bottom: 0.75rem;">Busiest Day</div>
                <div style="font-size: 1.50rem; font-weight: 700; color: #1f2937;">{busiest_day}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="metric-card-hover">
                <div style="font-size: 1.05rem; color: #6b7280; font-weight: 600; margin-bottom: 0.75rem;">Popularity</div>
                <div style="font-size: 1.50rem; font-weight: 700; color: #1f2937;">{popularity_status}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Close the card container
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Content sections with spacing
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("**Peak Performance Details**")
        st.write(peak_info)
        
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("**Weather Impact Analysis**")
        st.write(weather_impact)
        
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("**Route Summary**")
        st.write(summary)
        
        # MATPLOTLIB TREND ANALYSIS SECTION
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("### Trend Analysis")
        
        # Check if we have trend data for this street
        if street_name in street_trends_data:
            street_data = street_trends_data[street_name]
            weekly_data = street_data.get('weekly', [])
            
            if weekly_data:
                weekly_df = pd.DataFrame(weekly_data)
                weekly_df['date'] = pd.to_datetime(weekly_df['date'])
                weekly_df = weekly_df.sort_values('date')
                
                # Apply 3-week rolling average
                weekly_df['smoothed'] = weekly_df['popularity_score'].rolling(
                    window=3, center=True, min_periods=1
                ).mean()
                
                # Find peaks on smoothed data
                rolling_values = weekly_df['smoothed'].values
                peak_indices = []
                for i in range(1, len(rolling_values) - 1):
                    if rolling_values[i] > rolling_values[i-1] and rolling_values[i] > rolling_values[i+1]:
                        peak_indices.append(i)
                
                # Create matplotlib figure
                fig, ax = plt.subplots(figsize=(10, 4))
                
                # Plot original data (faint)
                ax.plot(weekly_df['date'], weekly_df['popularity_score'], 
                        color="#b7bc27f4", alpha=0.3, linewidth=1, marker='o', markersize=2)
                
                # Plot smoothed trend (bold)
                ax.plot(weekly_df['date'], weekly_df['smoothed'], 
                        color='#2563eb', linewidth=3)
                
                # Highlight peak
                if peak_indices:
                    peak_dates = weekly_df.iloc[peak_indices]['date']
                    peak_values = weekly_df.iloc[peak_indices]['smoothed']
                    ax.scatter(peak_dates, peak_values, 
                              color='#dc2626', s=25, zorder=5, marker='D')
                
                # Customize the plot
                ax.set_title(f'{street_name} - Popularity Trend', fontsize=12, fontweight='normal', pad=20)
                ax.set_ylabel('Popularity Score', fontsize=10, color='#6b7280')
                ax.set_xlabel('Date', fontsize=10, color='#6b7280')
                ax.grid(True, alpha=0.3)

                # Make axis borders grey
                ax.spines['bottom'].set_color('#6b7280')
                ax.spines['top'].set_color('#6b7280') 
                ax.spines['right'].set_color('#6b7280')
                ax.spines['left'].set_color('#6b7280')
                
                # Make tick labels grey
                ax.tick_params(axis='both', colors='#6b7280')

                # Format x-axis dates nicely
                plt.xticks(rotation=0, ha='center')
                
                # Set background to white
                fig.patch.set_facecolor('white')
                ax.set_facecolor('white')
                
                # Adjust layout
                plt.tight_layout()
                
                # Display the matplotlib figure
                st.pyplot(fig)
                
                # Clear the figure
                plt.close(fig)
                
            else:
                st.info("No weekly trend data available for this street")
        else:
            st.info("No trend data available for this street")
        
        # Temporal Analysis Section
        st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
        st.markdown("### Temporal Analysis")
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Day of Week Bar Chart
            if day_of_week_street_data:
                # Map full day names to abbreviated names
                day_abbr_map = {
                    'Monday': 'Mon',
                    'Tuesday': 'Tue', 
                    'Wednesday': 'Wed',
                    'Thursday': 'Thu',
                    'Friday': 'Fri',
                    'Saturday': 'Sat',
                    'Sunday': 'Sun'
                }
                
                days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                days_full = [day for day in days_order if day in day_of_week_street_data]
                days_abbr = [day_abbr_map[day] for day in days_full]
                values = [day_of_week_street_data[day] for day in days_full]
                
                fig_bar = go.Figure(data=[
                    go.Bar(
                        x=days_abbr,
                        y=values,
                        marker_color='#3b82f6',
                        hovertemplate='<b>%{x}</b><br>Trips: %{y:,}<extra></extra>'
                    )
                ])
                
                fig_bar.update_layout(
                    title='Trips Volume by Day of Week',
                    xaxis_title='Day',
                    yaxis_title='Trip Count',
                    height=350,
                    margin=dict(l=40, r=40, t=50, b=40),
                    font=dict(size=12),
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                
                fig_bar.update_xaxes(tickangle=0)
                
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("No day of week data available for this street")
        
        with chart_col2:
            # Peak vs Non-Peak Pie Chart
            if peak_percentage > 0 or non_peak_percentage > 0:
                fig_pie = go.Figure(data=[
                    go.Pie(
                        labels=['Peak', 'Non Peak'],
                        values=[peak_percentage, non_peak_percentage],
                        hole=0.4,
                        marker_colors=['#3b82f6', '#8b5cf6'],
                        hovertemplate='<b>%{label}</b><br>%{value}%<extra></extra>'
                    )
                ])
                
                fig_pie.update_layout(
                    title='Peak vs Non Peak Traffic Distribution',
                    height=350,
                    margin=dict(l=40, r=40, t=50, b=40),
                    font=dict(size=12),
                    paper_bgcolor='white'
                )
                
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No peak/non-peak data available for this street")

@st.cache_data
def load_route_popularity_data():
    """Load preprocessed route popularity data from CSV"""
    try:
        alternative_paths = [
            "data/processed/tab2_trend/route_popularity/Spinovate Tab 2 - Popularity.csv",
            "Spinovate Tab 2 - Popularity.csv",
            "data/Spinovate Tab 2 - Popularity.csv",
            os.path.join("data", "processed", "tab2_trend", "route_popularity", "Spinovate Tab 2 - Popularity.csv"),
            os.path.join(".", "data", "processed", "tab2_trend", "route_popularity", "Spinovate Tab 2 - Popularity.csv")
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
            return int(match.group(1)) if match else 112
        
        if 'peak_trips' in df.columns:
            df['trips_count'] = df['peak_trips'].apply(extract_trips_number)
        
        return df
    
    except Exception as e:
        st.error(f"Error loading CSV data: {e}")
        return pd.DataFrame()

@st.cache_data
def load_road_segments():
    """Load road segment geometry from GeoJSON file"""
    try:
        alternative_paths = [
            "data/processed/tab2_trend/route_popularity/active_segments.geojson",
            "active_segments.geojson",
            "data/active_segments.geojson",
            os.path.join("data", "processed", "tab2_trend", "route_popularity", "active_segments.geojson"),
            os.path.join(".", "data", "processed", "tab2_trend", "route_popularity", "active_segments.geojson")
        ]
        
        geojson_path = None
        for path in alternative_paths:
            if os.path.exists(path):
                geojson_path = path
                break
        
        if geojson_path is None:
            raise FileNotFoundError("GeoJSON file not found in any expected location")
        
        if GEOPANDAS_AVAILABLE:
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
            
            roads_data.append({
                'street_name': properties.get('street_name', 'Unknown'),
                'geometry_type': geometry['type'],
                'coordinates': geometry['coordinates']
            })
        
        return pd.DataFrame(roads_data)
    
    except Exception as e:
        st.error(f"Error loading GeoJSON data: {e}")
        return pd.DataFrame()

@st.cache_data
def load_minimal_cycleways_geojson():
    """Load and return minimal GeoJSON object for maximum performance"""
    try:
        alternative_paths = [
            "dublin-cycleways.geojson",
            "data/dublin-cycleways.geojson",
            "data/processed/tab2_trend/dublin-cycleways.geojson",
            os.path.join("data", "processed", "tab2_trend", "dublin-cycleways.geojson"),
            os.path.join(".", "data", "processed", "tab2_trend", "dublin-cycleways.geojson")
        ]
        
        geojson_path = None
        for path in alternative_paths:
            if os.path.exists(path):
                geojson_path = path
                break
        
        if geojson_path is None:
            st.warning("Cycleways GeoJSON file not found - cycleways will not be available")
            return None
        
        with open(geojson_path, 'r') as f:
            original_geojson = json.load(f)
        
        # Create ultra-minimal GeoJSON
        minimal_features = []
        for feature in original_geojson['features']:
            minimal_feature = {
                "type": "Feature", 
                "geometry": feature['geometry'],
                "properties": {}
            }
            minimal_features.append(minimal_feature)
        
        return {
            "type": "FeatureCollection",
            "features": minimal_features
        }
    
    except Exception as e:
        st.warning(f"Could not load cycleways GeoJSON: {e}")
        return None

def get_color_for_route(color_name):
    """Convert color name to hex color"""
    color_map = {
        'Green': '#22c55e',
        'Red': '#ef4444',
        'Yellow': '#eab308',
        'Blue': '#3b82f6'
    }
    return color_map.get(color_name, '#6b7280')

def create_route_map(df, road_segments_df, show_cycleways=False):
    """Create map with actual road segment polylines from GeoJSON"""
    dublin_center = [53.3498, -6.2603]
    m = folium.Map(location=dublin_center, zoom_start=12, tiles='CartoDB positron')
    
    routes_added = 0
    
    # Add cycleways
    cycleways_added = 0
    if show_cycleways:
        minimal_geojson = load_minimal_cycleways_geojson()
        if minimal_geojson:
            folium.GeoJson(
                minimal_geojson,
                style_function=lambda x: {
                    'color': '#1f77b4',
                    'weight': 2,
                    'opacity': 0.7
                },
                tooltip=None,
                popup=None
            ).add_to(m)
            cycleways_added = len(minimal_geojson['features'])
    
    # Iterate through road segments
    for idx, segment_row in road_segments_df.iterrows():
        street_name = segment_row['street_name']
        
        # Find corresponding data in CSV
        csv_data = df[df['street_name'] == street_name]
        
        if csv_data.empty:
            continue
        
        route_data = csv_data.iloc[0]
        color = route_data.get('Colour', 'Gray')
        trips_count = route_data.get('trips_count', 0)
        
        # Determine status text
        status_text = "Highly Popular" if color == 'Green' else "Popularity Dropped"
        
        # Create popup with route information
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
        
        # Handle geometry
        if GEOPANDAS_AVAILABLE and hasattr(segment_row, 'geometry'):
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
                    coords = [[point[1], point[0]] for point in line_coords]
                    folium.PolyLine(
                        locations=coords,
                        color=get_color_for_route(color),
                        weight=5,
                        opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=400),
                        tooltip=street_name
                    ).add_to(m)
            
            elif geometry_type == 'LineString' and coordinates:
                coords = [[point[1], point[0]] for point in coordinates]
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
        cycleway_legend = ""
        if show_cycleways and cycleways_added > 0:
            cycleway_legend = """
            <div style="margin-bottom: 8px;">
                <span style="display: inline-block; width: 16px; height: 3px; background-color: #1f77b4; margin-right: 8px;"></span>
                <span style="color: #374151;">Cycleways</span>
            </div>
            """
        
        legend_html = f"""
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 200px; 
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
        {cycleway_legend}
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add Chrome visibility fix - invalidate map size when visible
        visibility_template = """
        {% macro script(this, kwargs) %}
        <script>
        (function() {
            console.log('[Tab3 Map Init] Initializing...');
            var map = {{this._parent.get_name()}};
            
            // Chrome visibility fix - invalidate size when map becomes visible
            function invalidateMapSize() {
                if (map && map._container) {
                    setTimeout(function() {
                        map.invalidateSize();
                        console.log('[Tab3 Map Init] Size invalidated');
                    }, 100);
                }
            }
            
            // Use IntersectionObserver to detect when map becomes visible
            if (window.IntersectionObserver && map._container) {
                var observer = new IntersectionObserver(function(entries) {
                    entries.forEach(function(entry) {
                        if (entry.isIntersecting) {
                            invalidateMapSize();
                        }
                    });
                }, { threshold: 0.1 });
                observer.observe(map._container);
            }
            
            // Also invalidate on window focus and resize
            window.addEventListener('focus', invalidateMapSize);
            window.addEventListener('resize', invalidateMapSize);
            
            // Invalidate immediately and after delays
            invalidateMapSize();
            setTimeout(invalidateMapSize, 500);
            setTimeout(invalidateMapSize, 1000);
        })();
        </script>
        {% endmacro %}
        """
        
        macro = MacroElement()
        macro._template = Template(visibility_template)
        m.get_root().add_child(macro)
    
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
    create_route_detail_card(selected_street, row)

# ════════════════════════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ════════════════════════════════════════════════════════════════════════════════

def render_tab3():
    """Render Tab 3 - Route Popularity Analysis"""
    
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
    
    # Initialize session state
    if 'route_analysis' not in st.session_state:
        st.session_state.route_analysis = None
    
    # Section header
    create_section_header("Change in Route Popularity Analysis", "Performance trends and popularity metrics for cycling routes")
    
    # Professional metrics
    create_route_metrics(df)
    
    # Sidebar controls
    st.sidebar.markdown("---")
    st.sidebar.subheader("Tab 3: Change in Route Popularity Settings")
    show_cycleways = st.sidebar.checkbox("Show Cycleways", key="tab3_cycleways_route", value=False)
    
    # Map section
    create_section_header("Route Performance Map", "Visual representation of route popularity and performance")
    
    route_map, routes_added = create_route_map(df, road_segments_df, show_cycleways)
    
    if routes_added > 0:
        st.markdown('<div class="map-container">', unsafe_allow_html=True)
        # Use explicit width for Chrome compatibility in hidden tabs
        map_data = st_folium(
            route_map, 
            width=None,
            height=500,
            returned_objects=["last_object_clicked_popup"],
            key="tab3_route_map"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Check if user clicked on a popup
        clicked_street = None
        if map_data and 'last_object_clicked_popup' in map_data and map_data['last_object_clicked_popup']:
            popup_content = str(map_data['last_object_clicked_popup'])
            
            for street_name in df['street_name'].tolist():
                if popup_content.strip().startswith(street_name):
                    clicked_street = street_name
                    break
            
            if not clicked_street:
                earliest_position = len(popup_content)
                for street_name in df['street_name'].tolist():
                    position = popup_content.find(street_name)
                    if position != -1 and position < earliest_position:
                        clicked_street = street_name
                        earliest_position = position
        
        if clicked_street:
            st.markdown("---")
            
            if st.button(f"View Detailed Analysis for {clicked_street}", 
                        type="primary", 
                        use_container_width=True,
                        key=f"analyze_{clicked_street}"):
                st.session_state.route_analysis = clicked_street
    
    else:
        st.warning("No routes could be displayed. Please check data consistency between CSV and GeoJSON files.")
    
    # Display analysis
    if st.session_state.route_analysis:
        street_name = st.session_state.route_analysis
        
        if st.session_state.get('route_analysis_loaded') != street_name:
            with st.spinner("Generating AI insights..."):
                import time
                time.sleep(2)
            st.session_state.route_analysis_loaded = street_name
        
        show_route_details(df, street_name)
        
        if st.button("Close Analysis", key="close_route_analysis", use_container_width=True):
            st.session_state.route_analysis = None
            st.session_state.route_analysis_loaded = None

if __name__ == "__main__":
    render_tab3()
