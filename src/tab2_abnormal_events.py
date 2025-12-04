"""
Tab 2: Abnormal Events Analysis - Enhanced Professional Version
Safety incidents and risk assessment across routes
"""

import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import plotly.graph_objects as go
import json
import os
from shapely.geometry import Polygon
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

def create_abnormal_metrics(abnormal_df):
    """Create professional metrics for abnormal events analysis"""
    col1, col2, col3, col4 = st.columns(4)
    
    total_abnormal = len(abnormal_df['street_name'].unique()) if not abnormal_df.empty else 0
    high_risk_routes = len(abnormal_df[abnormal_df['Colour'] == 'Red']) if not abnormal_df.empty else 0
    improved_routes = len(abnormal_df[abnormal_df['Colour'] == 'Green']) if not abnormal_df.empty else 0
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Total Routes</div>
            <div class="kpi-value">{total_abnormal}</div>
            <div class="kpi-change">With Abnormal Events</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Increased Risk</div>
            <div class="kpi-value">{high_risk_routes}</div>
            <div class="kpi-change negative">Require Attention</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Improved Safety</div>
            <div class="kpi-value">{improved_routes}</div>
            <div class="kpi-change positive">Positive Trend</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        improvement_rate = int((improved_routes / total_abnormal * 100)) if total_abnormal > 0 else 0
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Improvement Rate</div>
            <div class="kpi-value">{improvement_rate}%</div>
            <div class="kpi-change positive">Safety Progress</div>
        </div>
        """, unsafe_allow_html=True)

def create_abnormal_detail_card(street_name, row):
    """Create professional abnormal event detail cards"""
    
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
        safety_status = "Improved Safety" if color == 'Green' else "Increased Risk"
        trend = row.get('Trend', 'No trend data available')
        observation = row.get('Observation', 'No observation data available')
        
        # Metrics using columns
        col1, col2 = st.columns(2)
        
        with col1:
            safety_color = "#059669" if safety_status == "Improved Safety" else "#dc2626"
            st.markdown(f"""
            <div style="text-align: center; background: #f8fafc; padding: 1.5rem; border-radius: 8px; margin: 0.5rem;">
                <div style="font-size: 1rem; color: #6b7280; font-weight: 500; margin-bottom: 0.75rem;">Safety Status</div>
                <div style="font-size: 1.75rem; font-weight: 700; color: {safety_color};">{safety_status}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            risk_level = "Low" if color == 'Green' else "High"
            risk_color = "#059669" if risk_level == "Low" else "#dc2626"
            st.markdown(f"""
            <div style="text-align: center; background: #f8fafc; padding: 1.5rem; border-radius: 8px; margin: 0.5rem;">
                <div style="font-size: 1rem; color: #6b7280; font-weight: 500; margin-bottom: 0.75rem;">Risk Level</div>
                <div style="font-size: 2rem; font-weight: 700; color: {risk_color};">{risk_level}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Close the card container
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Content sections with spacing
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("**Observation**")
        st.write(observation)
        
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("**Trend Analysis**")
        st.write(trend)
        
        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("**Possible Contributing Factors**")
        factors = row.get('Possible Contributing Factors', '')
        if pd.notna(factors) and factors.strip() != '':
            st.write(factors)
        else:
            st.write("No contributing factors data available")

# ════════════════════════════════════════════════════════════════════════════════
# DATA LOADING FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_abnormal_events_data():
    """Load preprocessed abnormal events data from CSV"""
    try:
        alternative_paths = [
            "abnormal-events-data.csv",
            "data/abnormal-events-data.csv",
            "data/processed/tab2_trend/abnormal_events/abnormal-events-data.csv",
            os.path.join("data", "processed", "tab2_trend", "abnormal_events", "abnormal-events-data.csv"),
            os.path.join(".", "data", "processed", "tab2_trend", "abnormal_events", "abnormal-events-data.csv")
        ]
        
        df = None
        for path in alternative_paths:
            if os.path.exists(path):
                df = pd.read_csv(path)
                break
        
        if df is None:
            raise FileNotFoundError("Abnormal events CSV file not found in any expected location")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Remove rows where street_name is empty or NaN
        df = df.dropna(subset=['street_name'])
        df = df[df['street_name'].str.strip() != '']
        
        # Clean up any encoding issues in street names
        df['street_name'] = df['street_name'].str.replace('â€™', "'", regex=False)
        df['street_name'] = df['street_name'].str.replace('Ãƒ', 'á', regex=False)
        
        return df
    
    except Exception as e:
        st.error(f"Error loading abnormal events CSV data: {e}")
        return pd.DataFrame()

@st.cache_data
def load_abnormal_events_segments():
    """Load abnormal events segment geometry from GeoJSON file"""
    try:
        alternative_paths = [
            "abnormal-events-segments.geojson",
            "data/abnormal-events-segments.geojson",
            "data/processed/tab2_trend/abnormal_events/abnormal-events-segments.geojson",
            os.path.join("data", "processed", "tab2_trend", "abnormal_events", "abnormal-events-segments.geojson"),
            os.path.join(".", "data", "processed", "tab2_trend", "abnormal_events", "abnormal-events-segments.geojson")
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

def smooth_polygon(polygon, factor=0.0001):
    """Smooth polygon using buffer technique"""
    try:
        return polygon.buffer(factor).buffer(-factor*0.8)
    except:
        return polygon

def get_color_for_route(color_name):
    """Convert color name to hex color"""
    color_map = {
        'Green': '#22c55e',
        'Red': '#ef4444',
        'Yellow': '#eab308',
        'Blue': '#3b82f6'
    }
    return color_map.get(color_name, '#6b7280')

def create_abnormal_events_map(df, road_segments_df, show_cycleways=False):
    """Create map with abnormal events road segment polylines from GeoJSON"""
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
    
    # Get unique street names from CSV to avoid duplicates
    unique_streets = df['street_name'].dropna().unique()
    
    # Iterate through each unique street
    for street_name in unique_streets:
        csv_data = df[df['street_name'] == street_name]
        
        if csv_data.empty:
            continue
        
        route_data = csv_data.iloc[0]
        color = route_data.get('Colour', 'Gray')
        
        if color not in ['Red', 'Green']:
            color = 'Red'
        
        matching_segments = road_segments_df[road_segments_df['street_name'] == street_name]
        
        if matching_segments.empty:
            continue
        
        status_text = "Increased Risk" if color == 'Red' else "Improved Safety"
        
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
                    <strong>Trend:</strong><br>
                    <div style="font-size: 14px; color: #374151; line-height: 1.4; margin-top: 8px;">
                        {str(route_data.get('Trend', 'No trend data available'))}
                    </div>
                </div>
            </div>
        </div>
        """
        
        # Add ALL segments for this street name
        for _, segment_row in matching_segments.iterrows():
            
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
                
                elif geometry.geom_type == 'Polygon':
                    smoothed_geom = smooth_polygon(geometry, factor=0.0001)
                    coords = [[point[1], point[0]] for point in smoothed_geom.exterior.coords]
                    folium.Polygon(
                        locations=coords,
                        color=get_color_for_route(color),
                        weight=3,
                        opacity=0.8,
                        fill=True,
                        fillColor=get_color_for_route(color),
                        fillOpacity=0.3,
                        popup=folium.Popup(popup_html, max_width=400),
                        tooltip=street_name
                    ).add_to(m)
            
            else:
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
                
                elif geometry_type == 'Polygon' and coordinates:
                    if coordinates and len(coordinates) > 0:
                        outer_ring = coordinates[0]
                        try:
                            original_coords = [(point[0], point[1]) for point in outer_ring]
                            shapely_polygon = Polygon(original_coords)
                            smoothed_polygon = smooth_polygon(shapely_polygon, factor=0.0001)
                            coords = [[point[1], point[0]] for point in smoothed_polygon.exterior.coords]
                        except:
                            coords = [[point[1], point[0]] for point in outer_ring]
                        
                        folium.Polygon(
                            locations=coords,
                            color=get_color_for_route(color),
                            weight=3,
                            opacity=0.8,
                            fill=True,
                            fillColor=get_color_for_route(color),
                            fillOpacity=0.3,
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
        <div style="font-weight: 600; margin-bottom: 12px; color: #111827;">Abnormal Events</div>
        <div style="margin-bottom: 8px;">
            <span style="display: inline-block; width: 16px; height: 3px; background-color: #22c55e; margin-right: 8px;"></span>
            <span style="color: #374151;">Improved Safety</span>
        </div>
        <div style="margin-bottom: 8px;">
            <span style="display: inline-block; width: 16px; height: 3px; background-color: #ef4444; margin-right: 8px;"></span>
            <span style="color: #374151;">Increased Risk</span>
        </div>
        {cycleway_legend}
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add dynamic polygon scaling
        template = """
        {% macro script(this, kwargs) %}
        <script>
        (function() {
            console.log('[Polygon Scaling] Initializing...');
            var polygonBaseStyles = {};
            var polygonCounter = 0;
            
            function updatePolygonSizes() {
                var map = {{this._parent.get_name()}};
                if (!map) return;
                
                var zoom = map.getZoom();
                var scaleFactor = Math.pow(2, (12 - zoom)) * 0.5;
                
                map.eachLayer(function(layer) {
                    if (layer instanceof L.Polygon) {
                        if (!layer._polyScaleId) {
                            layer._polyScaleId = 'poly_' + polygonCounter++;
                            polygonBaseStyles[layer._polyScaleId] = {
                                weight: layer.options.weight || 3,
                                fillOpacity: layer.options.fillOpacity || 0.3,
                                opacity: layer.options.opacity || 0.8
                            };
                        }
                        
                        var baseStyles = polygonBaseStyles[layer._polyScaleId];
                        if (baseStyles) {
                            layer.setStyle({
                                weight: Math.max(1, baseStyles.weight * scaleFactor),
                                fillOpacity: Math.min(0.6, baseStyles.fillOpacity + (scaleFactor - 1) * 0.1),
                                opacity: Math.min(1, baseStyles.opacity + (scaleFactor - 1) * 0.1)
                            });
                        }
                    }
                });
            }
            
            {{this._parent.get_name()}}.on('zoomend', updatePolygonSizes);
            {{this._parent.get_name()}}.whenReady(function() {
                setTimeout(updatePolygonSizes, 100);
            });
        })();
        </script>
        {% endmacro %}
        """
        
        macro = MacroElement()
        macro._template = Template(template)
        m.get_root().add_child(macro)
    
    return m, routes_added

def show_abnormal_events_details(df, selected_street):
    """Display detailed analysis for selected abnormal events route"""
    if not selected_street:
        return
    
    street_data = df[df['street_name'] == selected_street]
    if street_data.empty:
        st.error(f"No data found for {selected_street}")
        return
    
    main_row = street_data.iloc[0]
    create_abnormal_detail_card(selected_street, main_row)

# ════════════════════════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ════════════════════════════════════════════════════════════════════════════════

def render_tab2():
    """Render Tab 2 - Abnormal Events Analysis"""
    
    abnormal_df = load_abnormal_events_data()
    abnormal_segments_df = load_abnormal_events_segments()
    
    if abnormal_df.empty:
        st.error("Could not load abnormal events data")
        st.info("Please ensure the abnormal-events-data.csv file exists")
        return
    
    if abnormal_segments_df.empty:
        st.error("Could not load abnormal events segment geometry")
        st.info("Please ensure the abnormal-events-segments.geojson file exists")
        return
    
    # Initialize session state
    if 'abnormal_analysis' not in st.session_state:
        st.session_state.abnormal_analysis = None
    
    # Section header
    create_section_header("Abnormal Events Analysis", "Safety incidents and risk assessment across routes")
    
    # Professional metrics
    create_abnormal_metrics(abnormal_df)
    
    # Sidebar controls
    st.sidebar.markdown("---")
    st.sidebar.subheader("Tab 2: Abnormal Events Settings")
    show_cycleways = st.sidebar.checkbox("Show Cycleways", key="cycleways_abnormal", value=False)
    
    # Map section
    create_section_header("Abnormal Events Map", "Visual representation of safety incidents and risk levels")
    
    abnormal_map, routes_added = create_abnormal_events_map(abnormal_df, abnormal_segments_df, show_cycleways)
    
    if routes_added > 0:
        st.markdown('<div class="map-container">', unsafe_allow_html=True)
        map_data = st_folium(abnormal_map, height=500, width=None, key="abnormal_events_map")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Check if user clicked on a popup
        clicked_street = None
        if map_data and 'last_object_clicked_popup' in map_data and map_data['last_object_clicked_popup']:
            popup_content = str(map_data['last_object_clicked_popup'])
            
            for street_name in abnormal_df['street_name'].dropna().tolist():
                if popup_content.strip().startswith(street_name):
                    clicked_street = street_name
                    break
            
            if not clicked_street:
                earliest_position = len(popup_content)
                for street_name in abnormal_df['street_name'].dropna().tolist():
                    position = popup_content.find(street_name)
                    if position != -1 and position < earliest_position:
                        clicked_street = street_name
                        earliest_position = position
    
        if clicked_street:
            st.markdown("---")
            
            if st.button(f"View Detailed Analysis for {clicked_street}", 
                        type="primary", 
                        use_column_width=True,
                        key=f"analyze_abnormal_{clicked_street}"):
                st.session_state.abnormal_analysis = clicked_street
    else:
        st.warning("No abnormal events routes could be displayed. Please check data consistency between CSV and GeoJSON files.")
    
    # Display analysis
    if st.session_state.abnormal_analysis:
        street_name = st.session_state.abnormal_analysis
        
        if st.session_state.get('abnormal_analysis_loaded') != street_name:
            with st.spinner("Generating AI insights..."):
                import time
                time.sleep(2)
            st.session_state.abnormal_analysis_loaded = street_name
        
        show_abnormal_events_details(abnormal_df, street_name)
        
        if st.button("Close Analysis", key="close_abnormal_analysis", use_column_width=True):
            st.session_state.abnormal_analysis = None
            st.session_state.abnormal_analysis_loaded = None

if __name__ == "__main__":
    render_tab2()
