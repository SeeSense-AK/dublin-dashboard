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
from utils.constants import MAP_TILES, STREET_VIEW_URL_TEMPLATE


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
        tiles=None
    )
    
    # Add custom tile layer
    folium.TileLayer(
        tiles=MAP_TILES["CartoDB Positron"],
        name="CartoDB Positron",
        attr='Map data'
    ).add_to(m)
    
    if hotspots_df.empty:
        return m
    
    # Add hotspots
    for idx, hotspot in hotspots_df.iterrows():
        # Handle both Athena format (latitude/longitude) and original format (lat/lng)
        lat = hotspot.get('latitude', hotspot.get('lat', 0))
        lng = hotspot.get('longitude', hotspot.get('lng', 0))
        
        # Determine color based on severity
        severity = hotspot.get('avg_severity', hotspot.get('severity_score', 2))
        severity_level = min(4, max(0, int(severity)))
        color_hex = SEVERITY_COLORS.get(severity_level, SEVERITY_COLORS[2])
        
        # Map severity to folium colors
        if severity >= 4:
            marker_color = 'red'
        elif severity >= 3:
            marker_color = 'orange'
        elif severity >= 2:
            marker_color = 'yellow'
        else:
            marker_color = 'green'
        
        # Create popup content
        incident_count = hotspot.get('incident_count', hotspot.get('event_count', 0))
        perception_reports = hotspot.get('total_perception_reports', 0)
        
        popup_html = f"""
        <div style="font-family: Arial; width: 280px;">
            <h4 style="margin-bottom: 10px; color: {color_hex};">🚨 Hotspot #{hotspot.get('hotspot_id', idx+1)}</h4>
            <p><b>📊 Incidents:</b> {incident_count}</p>
            <p><b>⚠️ Avg Severity:</b> {severity:.2f}/5</p>
            <p><b>🏆 Max Severity:</b> {hotspot.get('max_severity', severity)}</p>
            <p><b>📱 Devices:</b> {hotspot.get('device_count', 'Unknown')}</p>
        """
        
        # Add perception reports count if available
        if perception_reports > 0:
            popup_html += f"<p><b>📝 Perception Reports:</b> {perception_reports}</p>"
        
        # Add Street View link using your template
        street_view_url = STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lng, heading=0)
        popup_html += f'<br><a href="{street_view_url}" target="_blank" style="color: #4285f4;">📍 View in Street View</a>'
        popup_html += "</div>"
        
        # Add circle marker
        folium.CircleMarker(
            location=[lat, lng],
            radius=8 + (incident_count / 5),  # Size based on incidents
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"Hotspot #{hotspot.get('hotspot_id', idx+1)}: {incident_count} incidents",
            color=marker_color,
            fill=True,
            fillColor=color_hex,
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
    if not hotspots_df.empty:
        # Handle both coordinate formats
        lat_col = 'latitude' if 'latitude' in hotspots_df.columns else 'lat'
        lng_col = 'longitude' if 'longitude' in hotspots_df.columns else 'lng'
        
        bounds = calculate_bounding_box(hotspots_df, lat_col=lat_col, lon_col=lng_col)
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
        if pd.notna(report['lat']) and pd.notna(report['lng']):
            popup_html = f"<div style='width: 200px;'><b>{report_type.title()} Report</b><br>"
            
            if report_type == 'infrastructure':
                popup_html += f"Type: {report.get('infrastructuretype', 'N/A')}<br>"
                comment = report.get('finalcomment', '')
            else:
                popup_html += f"Incident: {report.get('incidenttype', 'N/A')}<br>"
                popup_html += f"Rating: {report.get('incidentrating', 'N/A')}<br>"
                comment = report.get('commentfinal', '')
            
            if comment and len(str(comment)) > 3:
                popup_html += f"Comment: {str(comment)[:100]}...</div>"
            
            color = 'blue' if report_type == 'infrastructure' else 'green'
            
            folium.CircleMarker(
                location=[report['lat'], report['lng']],
                radius=4,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{report_type.title()} Report",
                color=color,
                fill=True,
                fillOpacity=0.6
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
    
    # Handle both severity column formats
    severity_col = 'avg_severity' if 'avg_severity' in hotspots_df.columns else 'severity_score'
    
    if severity_col not in hotspots_df.columns:
        return go.Figure()
    
    # Bin severity scores
    hotspots_df = hotspots_df.copy()
    hotspots_df['severity_category'] = pd.cut(
        hotspots_df[severity_col],
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
            'Low': SEVERITY_COLORS[1],
            'Medium': SEVERITY_COLORS[2],
            'High': SEVERITY_COLORS[3],
            'Critical': SEVERITY_COLORS[4]
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
    
    # Handle column name mapping
    if column == 'reading_count':
        if 'unique_users' in time_series_df.columns:
            column = 'unique_users'
        elif 'total_readings' in time_series_df.columns:
            column = 'total_readings'
    
    if column not in time_series_df.columns:
        return go.Figure()
    
    # Handle datetime column
    datetime_col = 'datetime' if 'datetime' in time_series_df.columns else 'date'
    
    fig = go.Figure()
    
    # Add main time series
    fig.add_trace(go.Scatter(
        x=time_series_df[datetime_col],
        y=time_series_df[column],
        mode='lines+markers',
        name='Actual',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=4)
    ))
    
    # Add rolling average if available
    if 'rolling_mean' in time_series_df.columns:
        fig.add_trace(go.Scatter(
            x=time_series_df[datetime_col],
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
                x=drops[datetime_col],
                y=drops[column],
                mode='markers',
                name='Usage Drops',
                marker=dict(color='red', size=12, symbol='x')
            ))
        
        # Spikes
        spikes = anomalies_df[anomalies_df['anomaly_type'] == 'spike']
        if not spikes.empty:
            fig.add_trace(go.Scatter(
                x=spikes[datetime_col],
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
    Note: This function is kept for compatibility but needs sensor data
    
    Args:
        sensor_df: DataFrame with sensor data (ignored for now)
    
    Returns:
        folium Map with placeholder
    """
    # Create base map
    m = folium.Map(
        location=VIZ_CONFIG['map_center'], 
        zoom_start=VIZ_CONFIG['map_zoom_start'],
        tiles=None
    )
    
    # Add tile layer
    folium.TileLayer(
        tiles=MAP_TILES["CartoDB Positron"],
        name="CartoDB Positron",
        attr='Map data'
    ).add_to(m)
    
    # TODO: Implement heatmap with Athena data
    # For now, return basic map
    return m


def create_metric_cards(stats_dict):
    """
    Create metric cards for dashboard overview
    
    Args:
        stats_dict: Dictionary with metric values
    
    Returns:
        None (displays metrics in Streamlit)
    """
    if not stats_dict:
        return
    
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
    period1_values = [
        period_comparison.get('period1_count', 0), 
        period_comparison.get('period1_avg_severity', 0)
    ]
    period2_values = [
        period_comparison.get('period2_count', 0), 
        period_comparison.get('period2_avg_severity', 0)
    ]
    
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
