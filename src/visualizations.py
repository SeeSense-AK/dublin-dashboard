"""
Visualization components for the dashboard
"""
import folium
from folium import plugins
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from streamlit_folium import folium_static
from config import VIZ_CONFIG, SEVERITY_COLORS
from utils.geo_utils import generate_street_view_url, calculate_bounding_box


def create_hotspot_map(hotspots_df, infra_reports_df=None, ride_reports_df=None, show_perception=True):
    """
    Create interactive map with hotspots and optional perception reports
    
    Args:
        hotspots_df: DataFrame with hotspot data
        infra_reports_df: DataFrame with infrastructure reports (optional)
        ride_reports_df: DataFrame with ride reports (optional)
        show_perception: Whether to show perception reports
    
    Returns:
        folium Map object
    """
    # Create base map
    m = folium.Map(
        location=VIZ_CONFIG['map_center'],
        zoom_start=VIZ_CONFIG['map_zoom_start'],
        tiles='CartoDB positron'
    )
    
    if hotspots_df.empty:
        return m
    
    # Add hotspots
    for idx, hotspot in hotspots_df.iterrows():
        # Determine color based on severity
        severity = int(hotspot.get('avg_severity', 2))
        color = SEVERITY_COLORS.get(severity, '#FF0000')
        
        # Create popup content
        popup_html = f"""
        <div style="font-family: Arial; width: 250px;">
            <h4 style="margin-bottom: 10px;">Hotspot #{hotspot.get('hotspot_id', idx+1)}</h4>
            <p><b>Incidents:</b> {hotspot.get('incident_count', 0)}</p>
            <p><b>Avg Severity:</b> {hotspot.get('avg_severity', 0):.2f}</p>
            <p><b>Max Severity:</b> {hotspot.get('max_severity', 0)}</p>
            <p><b>Devices:</b> {hotspot.get('device_count', 0)}</p>
        """
        
        # Add perception reports count if available
        if 'total_perception_reports' in hotspot:
            popup_html += f"<p><b>Perception Reports:</b> {hotspot.get('total_perception_reports', 0)}</p>"
        
        # Add Street View link
        street_view_url = generate_street_view_url(hotspot['latitude'], hotspot['longitude'])
        popup_html += f'<p><a href="{street_view_url}" target="_blank">🔍 View in Street View</a></p>'
        
        popup_html += "</div>"
        
        # Add circle marker
        folium.CircleMarker(
            location=[hotspot['latitude'], hotspot['longitude']],
            radius=10 + (hotspot.get('incident_count', 0) / 10),  # Size based on incidents
            popup=folium.Popup(popup_html, max_width=300),
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            weight=2
        ).add_to(m)
    
    # Add perception reports if requested
    if show_perception:
        if infra_reports_df is not None and not infra_reports_df.empty:
            add_perception_markers(m, infra_reports_df, 'infrastructure')
        
        if ride_reports_df is not None and not ride_reports_df.empty:
            add_perception_markers(m, ride_reports_df, 'ride')
    
    # Fit bounds to show all hotspots
    bounds = calculate_bounding_box(hotspots_df, lat_col='latitude', lon_col='longitude')
    if bounds:
        m.fit_bounds(bounds)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    return m


def add_perception_markers(map_obj, reports_df, report_type):
    """
    Add perception report markers to map
    
    Args:
        map_obj: Folium map object
        reports_df: DataFrame with reports
        report_type: 'infrastructure' or 'ride'
    """
    # Create feature group
    fg = folium.FeatureGroup(name=f'{report_type.title()} Reports', show=False)
    
    for idx, report in reports_df.iterrows():
        popup_html = f"<div style='width: 200px;'><b>{report_type.title()} Report</b><br>"
        
        if report_type == 'infrastructure':
            popup_html += f"Type: {report.get('infrastructuretype', 'N/A')}<br>"
            comment = report.get('finalcomment', '')
        else:
            popup_html += f"Incident: {report.get('incidenttype', 'N/A')}<br>"
            popup_html += f"Rating: {report.get('incidentrating', 'N/A')}<br>"
            comment = report.get('commentfinal', '')
        
        if comment and len(str(comment)) > 3:
            popup_html += f"Comment: {comment[:100]}...</div>"
        
        folium.CircleMarker(
            location=[report['lat'], report['lng']],
            radius=5,
            popup=folium.Popup(popup_html, max_width=250),
            color='blue' if report_type == 'infrastructure' else 'green',
            fill=True,
            fillOpacity=0.5
        ).add_to(fg)
    
    fg.add_to(map_obj)


def create_severity_distribution_chart(hotspots_df):
    """
    Create bar chart showing severity distribution
    
    Args:
        hotspots_df: DataFrame with hotspot data
    
    Returns:
        plotly figure
    """
    if hotspots_df.empty:
        return go.Figure()
    
    # Bin severity scores
    hotspots_df['severity_category'] = pd.cut(
        hotspots_df['avg_severity'],
        bins=[0, 1, 2, 3, 5],
        labels=['Low', 'Medium', 'High', 'Critical']
    )
    
    severity_counts = hotspots_df['severity_category'].value_counts().sort_index()
    
    fig = px.bar(
        x=severity_counts.index,
        y=severity_counts.values,
        labels={'x': 'Severity Level', 'y': 'Number of Hotspots'},
        title='Hotspot Severity Distribution',
        color=severity_counts.index,
        color_discrete_map={
            'Low': '#90EE90',
            'Medium': '#FFD700',
            'High': '#FF4500',
            'Critical': '#DC143C'
        }
    )
    
    fig.update_layout(showlegend=False, height=400)
    
    return fig


def create_time_series_chart(time_series_df, column='reading_count', anomalies_df=None):
    """
    Create time series line chart with optional anomaly highlighting
    
    Args:
        time_series_df: DataFrame with time series data
        column: Column to plot
        anomalies_df: DataFrame with anomaly data (optional)
    
    Returns:
        plotly figure
    """
    if time_series_df.empty:
        return go.Figure()
    
    fig = go.Figure()
    
    # Add main time series
    fig.add_trace(go.Scatter(
        x=time_series_df['datetime'],
        y=time_series_df[column],
        mode='lines+markers',
        name='Actual',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=4)
    ))
    
    # Add rolling average if available
    if 'rolling_mean' in time_series_df.columns:
        fig.add_trace(go.Scatter(
            x=time_series_df['datetime'],
            y=time_series_df['rolling_mean'],
            mode='lines',
            name='7-day Average',
            line=dict(color='orange', width=2, dash='dash')
        ))
    
    # Highlight anomalies
    if anomalies_df is not None and not anomalies_df.empty:
        # Drops
        drops = anomalies_df[anomalies_df['anomaly_type'] == 'drop']
        if not drops.empty:
            fig.add_trace(go.Scatter(
                x=drops['datetime'],
                y=drops[column],
                mode='markers',
                name='Usage Drops',
                marker=dict(color='red', size=12, symbol='x')
            ))
        
        # Spikes
        spikes = anomalies_df[anomalies_df['anomaly_type'] == 'spike']
        if not spikes.empty:
            fig.add_trace(go.Scatter(
                x=spikes['datetime'],
                y=spikes[column],
                mode='markers',
                name='Usage Spikes',
                marker=dict(color='green', size=12, symbol='triangle-up')
            ))
    
    fig.update_layout(
        title='Road Usage Trends Over Time',
        xaxis_title='Date',
        yaxis_title=column.replace('_', ' ').title(),
        hovermode='x unified',
        height=500
    )
    
    return fig


def create_incident_heatmap(sensor_df):
    """
    Create heatmap of incident locations
    
    Args:
        sensor_df: DataFrame with sensor data
    
    Returns:
        folium Map with heatmap layer
    """
    if sensor_df.empty:
        return folium.Map(location=VIZ_CONFIG['map_center'], zoom_start=12)
    
    # Create base map
    m = folium.Map(
        location=VIZ_CONFIG['map_center'],
        zoom_start=VIZ_CONFIG['map_zoom_start'],
        tiles='CartoDB positron'
    )
    
    # Prepare heatmap data
    heat_data = [[row['position_latitude'], row['position_longitude'], row.get('max_severity', 1)] 
                 for idx, row in sensor_df.iterrows()]
    
    # Add heatmap
    plugins.HeatMap(heat_data, radius=15, blur=25, max_zoom=13).add_to(m)
    
    return m


def create_metric_cards(stats_dict):
    """
    Create metric cards for dashboard overview
    
    Args:
        stats_dict: Dictionary with metric values
    
    Returns:
        None (displays metrics in Streamlit)
    """
    cols = st.columns(len(stats_dict))
    
    for idx, (label, value) in enumerate(stats_dict.items()):
        with cols[idx]:
            # Format value based on type
            if isinstance(value, float):
                display_value = f"{value:.2f}"
            elif isinstance(value, int):
                display_value = f"{value:,}"
            else:
                display_value = str(value)
            
            st.metric(label=label, value=display_value)


def create_comparison_chart(period_comparison):
    """
    Create comparison chart for two time periods
    
    Args:
        period_comparison: Dict with comparison metrics
    
    Returns:
        plotly figure
    """
    if not period_comparison:
        return go.Figure()
    
    categories = ['Incident Count', 'Avg Severity']
    period1_values = [period_comparison['period1_count'], period_comparison['period1_avg_severity']]
    period2_values = [period_comparison['period2_count'], period_comparison['period2_avg_severity']]
    
    fig = go.Figure(data=[
        go.Bar(name='Period 1', x=categories, y=period1_values, marker_color='lightblue'),
        go.Bar(name='Period 2', x=categories, y=period2_values, marker_color='darkblue')
    ])
    
    fig.update_layout(
        title='Period Comparison',
        barmode='group',
        height=400
    )
    
    return fig