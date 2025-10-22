"""
Tab 2: Cycling Route Trends Analysis
Displays spatial and temporal changes in cycling route popularity and road safety signals
"""
import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta


def load_trend_data():
    """Load all preprocessed trend data from Parquet files"""
    data_dir = Path("data/processed/tab2_trend")
    
    try:
        # Load all data sources
        hardbrake_files = [
            data_dir / "hardbrake" / "hb1.parquet",
            data_dir / "hardbrake" / "hb2.parquet"
        ]
        hardbrake_dfs = []
        for file in hardbrake_files:
            if file.exists():
                df = pd.read_parquet(file)
                hardbrake_dfs.append(df)
        hardbrake_df = pd.concat(hardbrake_dfs, ignore_index=True) if hardbrake_dfs else pd.DataFrame()

        # Load pothole data
        pothole_files = [
            data_dir / "pothole" / "ph1.parquet",
            data_dir / "pothole" / "ph2.parquet"
        ]
        pothole_dfs = []
        for file in pothole_files:
            if file.exists():
                df = pd.read_parquet(file)
                pothole_dfs.append(df)
        pothole_df = pd.concat(pothole_dfs, ignore_index=True) if pothole_dfs else pd.DataFrame()

        # Load swerve data
        swerve_files = [
            data_dir / "swerve" / "sw1.parquet",
            data_dir / "swerve" / "sw2.parquet"
        ]
        swerve_dfs = []
        for file in swerve_files:
            if file.exists():
                df = pd.read_parquet(file)
                swerve_dfs.append(df)
        swerve_df = pd.concat(swerve_dfs, ignore_index=True) if swerve_dfs else pd.DataFrame()

        # Load route popularity data
        popularity_file = data_dir / "route_popularity" / "dailytop50.parquet"
        popularity_df = pd.read_parquet(popularity_file) if popularity_file.exists() else pd.DataFrame()

        # Parse dates
        for df in [hardbrake_df, pothole_df, swerve_df, popularity_df]:
            if not df.empty and 'ride_date' in df.columns:
                df['ride_date'] = pd.to_datetime(df['ride_date'])

        return {
            'hardbrake': hardbrake_df,
            'pothole': pothole_df, 
            'swerve': swerve_df,
            'popularity': popularity_df
        }
    
    except Exception as e:
        st.error(f"Error loading trend data: {e}")
        return {
            'hardbrake': pd.DataFrame(),
            'pothole': pd.DataFrame(),
            'swerve': pd.DataFrame(),
            'popularity': pd.DataFrame()
        }


def get_date_range(data_dict):
    """Get the available date range across all data sources"""
    all_dates = []
    for df in data_dict.values():
        if not df.empty and 'ride_date' in df.columns:
            all_dates.extend(df['ride_date'].dt.date.tolist())
    
    if all_dates:
        return min(all_dates), max(all_dates)
    else:
        today = datetime.now().date()
        return today - timedelta(days=30), today


def filter_data_by_date(df, selected_date):
    """Filter dataframe to specific date"""
    if df.empty or 'ride_date' not in df.columns:
        return df
    
    return df[df['ride_date'].dt.date == selected_date].copy()


def create_heatmap_layer(df, layer_type):
    """Create heatmap data for the selected layer type"""
    if df.empty:
        return []
    
    # Define metric column based on layer type
    metric_columns = {
        'popularity': 'popularity_score',
        'hardbrake': 'avg_event_severity', 
        'swerve': 'avg_event_severity',
        'pothole': 'avg_event_severity'
    }
    
    metric_col = metric_columns.get(layer_type, 'avg_event_severity')
    
    # Check if required columns exist
    required_cols = ['latitude', 'longitude', metric_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.warning(f"Missing columns for {layer_type}: {missing_cols}")
        return []
    
    # Filter out null values and create heatmap data
    df_filtered = df.dropna(subset=['latitude', 'longitude', metric_col])
    
    if df_filtered.empty:
        return []
    
    # Normalize the metric for heatmap intensity
    if df_filtered[metric_col].max() > 0:
        df_filtered['normalized_intensity'] = df_filtered[metric_col] / df_filtered[metric_col].max()
    else:
        df_filtered['normalized_intensity'] = 0
    
    # Create heatmap data: [lat, lng, intensity]
    heatmap_data = df_filtered[['latitude', 'longitude', 'normalized_intensity']].values.tolist()
    
    return heatmap_data


def create_trend_map(data_dict, selected_layer, selected_date):
    """Create the main interactive map with selected layer"""
    
    # Dublin center coordinates
    dublin_center = [53.3498, -6.2603]
    
    # Create base map
    m = folium.Map(
        location=dublin_center,
        zoom_start=12,
        tiles='OpenStreetMap'
    )
    
    # Get data for selected layer and date
    layer_data = filter_data_by_date(data_dict[selected_layer], selected_date)
    
    if not layer_data.empty:
        # Create heatmap
        heatmap_data = create_heatmap_layer(layer_data, selected_layer)
        
        if heatmap_data:
            # Color schemes for different layers
            layer_colors = {
                'popularity': ['blue', 'cyan', 'lime', 'yellow', 'red'],
                'hardbrake': ['yellow', 'orange', 'red', 'darkred'],
                'swerve': ['yellow', 'orange', 'red', 'darkred'], 
                'pothole': ['yellow', 'orange', 'red', 'darkred']
            }
            
            gradient = {0.0: layer_colors[selected_layer][0]}
            for i, color in enumerate(layer_colors[selected_layer][1:], 1):
                gradient[i / (len(layer_colors[selected_layer]) - 1)] = color
            
            HeatMap(
                heatmap_data,
                min_opacity=0.3,
                radius=15,
                blur=10,
                gradient=gradient
            ).add_to(m)
            
            # Add markers for high-intensity points
            if selected_layer == 'popularity':
                metric_col = 'popularity_score'
                threshold = layer_data[metric_col].quantile(0.8)
            else:
                metric_col = 'avg_event_severity'
                threshold = layer_data[metric_col].quantile(0.8)
            
            high_intensity = layer_data[layer_data[metric_col] >= threshold]
            
            for _, row in high_intensity.iterrows():
                # Create tooltip content
                tooltip_content = create_tooltip_content(row, selected_layer)
                
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=6,
                    popup=folium.Popup(tooltip_content, max_width=300),
                    color='white',
                    weight=2,
                    fillColor=get_marker_color(row[metric_col], selected_layer),
                    fillOpacity=0.8
                ).add_to(m)
    
    return m


def create_tooltip_content(row, layer_type):
    """Create tooltip content for map markers"""
    
    if layer_type == 'popularity':
        return f"""
        <div style="font-family: Arial; width: 250px;">
            <h4 style="color: #1E40AF; margin-bottom: 8px;">Route Popularity</h4>
            <p><b>Location:</b> {row['latitude']:.4f}, {row['longitude']:.4f}</p>
            <p><b>Popularity Score:</b> {row.get('popularity_score', 'N/A')}</p>
            <p><b>Cyclist Count:</b> {row.get('cyclist_count', 'N/A')}</p>
            <p><b>Date:</b> {row['ride_date'].strftime('%Y-%m-%d') if pd.notna(row['ride_date']) else 'N/A'}</p>
        </div>
        """
    else:
        event_names = {
            'hardbrake': 'Hard Braking Events',
            'swerve': 'Swerving Events', 
            'pothole': 'Road Surface Issues'
        }
        
        return f"""
        <div style="font-family: Arial; width: 250px;">
            <h4 style="color: #DC2626; margin-bottom: 8px;">{event_names.get(layer_type, 'Safety Events')}</h4>
            <p><b>Location:</b> {row['latitude']:.4f}, {row['longitude']:.4f}</p>
            <p><b>Average Severity:</b> {row.get('avg_event_severity', 'N/A')}</p>
            <p><b>Event Count:</b> {row.get('event_count', 'N/A')}</p>
            <p><b>Max Severity:</b> {row.get('max_severity', 'N/A')}</p>
            <p><b>Date:</b> {row['ride_date'].strftime('%Y-%m-%d') if pd.notna(row['ride_date']) else 'N/A'}</p>
        </div>
        """


def get_marker_color(value, layer_type):
    """Get marker color based on value and layer type"""
    if layer_type == 'popularity':
        if value >= 80:
            return '#FF0000'  # High popularity - red
        elif value >= 60:
            return '#FF8C00'  # Medium - orange  
        elif value >= 40:
            return '#FFD700'  # Low - yellow
        else:
            return '#00CED1'  # Very low - cyan
    else:
        # Safety events - higher severity is more dangerous
        if value >= 7:
            return '#8B0000'  # Dark red
        elif value >= 5:
            return '#FF0000'  # Red
        elif value >= 3:
            return '#FF8C00'  # Orange
        else:
            return '#FFD700'  # Yellow


def create_temporal_chart(data_dict, selected_layer):
    """Create temporal trend chart for selected layer"""
    
    df = data_dict[selected_layer]
    if df.empty:
        return None
    
    # Aggregate by date
    if selected_layer == 'popularity':
        daily_agg = df.groupby('ride_date').agg({
            'popularity_score': ['mean', 'sum'],
            'cyclist_count': 'sum' if 'cyclist_count' in df.columns else 'count'
        }).round(2)
        daily_agg.columns = ['avg_popularity', 'total_popularity', 'total_cyclists']
        metric_col = 'avg_popularity'
        y_label = 'Average Popularity Score'
        title = 'Daily Route Popularity Trends'
    else:
        daily_agg = df.groupby('ride_date').agg({
            'avg_event_severity': 'mean',
            'event_count': 'sum' if 'event_count' in df.columns else 'count',
            'max_severity': 'max' if 'max_severity' in df.columns else 'max'
        }).round(2)
        metric_col = 'avg_event_severity'
        y_label = 'Average Event Severity'
        
        layer_titles = {
            'hardbrake': 'Daily Hard Braking Severity',
            'swerve': 'Daily Swerving Severity',
            'pothole': 'Daily Road Surface Issues Severity'
        }
        title = layer_titles.get(selected_layer, 'Daily Safety Events')
    
    daily_agg = daily_agg.reset_index()
    
    # Create line chart
    fig = px.line(
        daily_agg,
        x='ride_date',
        y=metric_col,
        title=title,
        labels={'ride_date': 'Date', metric_col: y_label}
    )
    
    fig.update_traces(line_width=3)
    fig.update_layout(
        height=400,
        showlegend=False,
        xaxis_title="Date",
        yaxis_title=y_label
    )
    
    return fig


def get_summary_stats(data_dict, selected_layer, selected_date):
    """Get summary statistics for selected layer and date"""
    
    df = filter_data_by_date(data_dict[selected_layer], selected_date)
    
    if df.empty:
        return {
            'total_points': 0,
            'avg_metric': 0,
            'max_metric': 0,
            'coverage_area': 0
        }
    
    if selected_layer == 'popularity':
        metric_col = 'popularity_score'
    else:
        metric_col = 'avg_event_severity'
    
    # Calculate basic stats
    total_points = len(df)
    avg_metric = df[metric_col].mean() if metric_col in df.columns else 0
    max_metric = df[metric_col].max() if metric_col in df.columns else 0
    
    # Estimate coverage area (rough calculation)
    if total_points > 1:
        lat_range = df['latitude'].max() - df['latitude'].min()
        lng_range = df['longitude'].max() - df['longitude'].min()
        coverage_area = lat_range * lng_range * 111 * 85  # Rough km² conversion
    else:
        coverage_area = 0
    
    return {
        'total_points': total_points,
        'avg_metric': round(avg_metric, 2),
        'max_metric': round(max_metric, 2),
        'coverage_area': round(coverage_area, 1)
    }


def render_tab2():
    """Main function to render Tab 2 content"""
    
    st.header("Cycling Route Trends Analysis")
    st.markdown("Explore spatial and temporal changes in cycling route popularity and road safety signals")
    
    # Load data
    with st.spinner("Loading trend data..."):
        data_dict = load_trend_data()
    
    # Check if any data is available
    if all(df.empty for df in data_dict.values()):
        st.error("No trend data available. Please check that data files exist in data/processed/tab2_trend/")
        return
    
    # Get date range
    min_date, max_date = get_date_range(data_dict)
    
    # Sidebar controls
    st.sidebar.header("Controls")
    
    # Layer selector
    layer_options = {
        'popularity': 'Route Popularity',
        'hardbrake': 'Hard Braking Events', 
        'swerve': 'Swerving Events',
        'pothole': 'Road Surface Issues'
    }
    
    # Filter out empty datasets
    available_layers = {k: v for k, v in layer_options.items() if not data_dict[k].empty}
    
    if not available_layers:
        st.error("No data available for any layer")
        return
    
    selected_layer = st.sidebar.selectbox(
        "Select Layer",
        options=list(available_layers.keys()),
        format_func=lambda x: available_layers[x],
        index=0
    )
    
    # Date selector
    selected_date = st.sidebar.date_input(
        "Select Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date
    )
    
    # Playback controls (placeholder for future implementation)
    st.sidebar.markdown("---")
    playback_speed = st.sidebar.select_slider(
        "Playback Speed",
        options=[0.5, 1.0, 2.0, 5.0],
        value=1.0,
        format_func=lambda x: f"{x}x"
    )
    
    play_button = st.sidebar.button("Play All Days", disabled=True)
    if play_button:
        st.sidebar.info("Playback feature coming soon")
    
    # Main content area
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Create and display map
        with st.spinner(f"Generating map for {available_layers[selected_layer]}..."):
            trend_map = create_trend_map(data_dict, selected_layer, selected_date)
            folium_static(trend_map, width=800, height=600)
    
    with col2:
        # Summary statistics
        st.subheader("Daily Summary")
        stats = get_summary_stats(data_dict, selected_layer, selected_date)
        
        st.metric("Data Points", f"{stats['total_points']:,}")
        
        if selected_layer == 'popularity':
            st.metric("Avg Popularity", stats['avg_metric'])
            st.metric("Peak Popularity", stats['max_metric'])
        else:
            st.metric("Avg Severity", stats['avg_metric'])
            st.metric("Max Severity", stats['max_metric'])
        
        st.metric("Coverage Area", f"{stats['coverage_area']} km²")
        
        # Data source info
        st.markdown("---")
        st.markdown("**Data Source**")
        st.write(f"Layer: {available_layers[selected_layer]}")
        st.write(f"Date: {selected_date}")
        st.write(f"Grid: 6m resolution")
    
    # Temporal trends section
    st.markdown("---")
    st.subheader("Temporal Trends")
    
    temporal_chart = create_temporal_chart(data_dict, selected_layer)
    if temporal_chart:
        st.plotly_chart(temporal_chart, use_container_width=True)
    else:
        st.info("No temporal data available for this layer")
    
    # Layer information
    with st.expander("Layer Information"):
        if selected_layer == 'popularity':
            st.markdown("""
            **Route Popularity Layer**
            - Shows daily cycling activity on Dublin routes
            - Higher scores indicate more popular cycling corridors
            - Based on aggregated device readings
            - Grid resolution: 6m x 6m squares
            """)
        else:
            layer_descriptions = {
                'hardbrake': """
                **Hard Braking Events Layer**
                - Sudden deceleration events indicating potential hazards
                - Higher severity suggests more dangerous conditions
                - Could indicate traffic conflicts or road obstacles
                """,
                'swerve': """
                **Swerving Events Layer** 
                - Sudden lateral movements by cyclists
                - May indicate avoidance of obstacles or poor road conditions
                - Higher frequency suggests problematic road sections
                """,
                'pothole': """
                **Road Surface Issues Layer**
                - Events indicating poor road surface quality
                - Includes potholes, cracks, and surface irregularities
                - Based on accelerometer data patterns
                """
            }
            st.markdown(layer_descriptions.get(selected_layer, ""))
        
        st.markdown("**Data Processing:**")
        st.markdown("- Daily aggregation on 6m grid")
        st.markdown("- Stored as compressed Parquet files")
        st.markdown("- Spatial clustering for visualization")