"""
Hotspot detection and clustering module
Uses DBSCAN for spatial clustering of high-severity incidents
"""
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import streamlit as st
from config import HOTSPOT_CONFIG


@st.cache_data(ttl=3600)
def detect_hotspots(sensor_df, severity_threshold=None, min_samples=None, eps=None):
    """
    Detect hotspots using DBSCAN clustering on sensor data
    
    Args:
        sensor_df: DataFrame with sensor data
        severity_threshold: Minimum severity to consider (default from config)
        min_samples: Minimum points to form a cluster (default from config)
        eps: DBSCAN epsilon parameter (default from config)
    
    Returns:
        DataFrame with hotspot information
    """
    if sensor_df.empty:
        return pd.DataFrame()
    
    # Use config defaults if not provided
    severity_threshold = severity_threshold or HOTSPOT_CONFIG["severity_threshold"]
    min_samples = min_samples or HOTSPOT_CONFIG["min_samples"]
    eps = eps or HOTSPOT_CONFIG["eps"]
    
    # Filter by severity
    high_severity = sensor_df[sensor_df['max_severity'] >= severity_threshold].copy()
    
    if len(high_severity) < min_samples:
        return pd.DataFrame()
    
    # Prepare features for clustering
    features = high_severity[['position_latitude', 'position_longitude', 'max_severity']].copy()
    
    # Normalize features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)
    
    # Apply DBSCAN
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='euclidean')
    high_severity['cluster'] = clustering.fit_predict(features_scaled)
    
    # Remove noise points (cluster = -1)
    clustered = high_severity[high_severity['cluster'] != -1]
    
    if clustered.empty:
        return pd.DataFrame()
    
    # Aggregate by cluster to create hotspots
    hotspots = clustered.groupby('cluster').agg({
        'position_latitude': 'mean',
        'position_longitude': 'mean',
        'max_severity': ['mean', 'max', 'count'],
        'device_id': 'nunique'  # Number of unique devices
    }).reset_index()
    
    # Flatten column names
    hotspots.columns = [
        'cluster_id',
        'latitude',
        'longitude',
        'avg_severity',
        'max_severity',
        'incident_count',
        'device_count'
    ]
    
    # Sort by incident count
    hotspots = hotspots.sort_values('incident_count', ascending=False)
    
    # Add hotspot ID
    hotspots['hotspot_id'] = range(1, len(hotspots) + 1)
    
    return hotspots


def get_hotspot_details(sensor_df, hotspot_lat, hotspot_lng, radius_m=50):
    """
    Get detailed information about incidents near a hotspot
    
    Args:
        sensor_df: DataFrame with sensor data
        hotspot_lat: Hotspot latitude
        hotspot_lng: Hotspot longitude
        radius_m: Radius in meters to search
    
    Returns:
        DataFrame with incidents near the hotspot
    """
    from utils.geo_utils import find_points_within_radius
    
    if sensor_df.empty:
        return pd.DataFrame()
    
    # Find incidents within radius
    nearby = find_points_within_radius(
        hotspot_lat, 
        hotspot_lng, 
        sensor_df,
        radius_m,
        lat_col='position_latitude',
        lon_col='position_longitude'
    )
    
    return nearby


def classify_hotspot_severity(avg_severity, incident_count):
    """
    Classify hotspot risk level based on severity and frequency
    
    Args:
        avg_severity: Average severity score
        incident_count: Number of incidents
    
    Returns:
        str: Risk level ('Critical', 'High', 'Medium', 'Low')
    """
    # Composite score
    score = (avg_severity * 0.6) + (min(incident_count / 10, 10) * 0.4)
    
    if score >= 3.5:
        return 'Critical'
    elif score >= 2.5:
        return 'High'
    elif score >= 1.5:
        return 'Medium'
    else:
        return 'Low'


def get_hotspot_statistics(hotspots_df):
    """
    Get summary statistics for hotspots
    
    Args:
        hotspots_df: DataFrame with hotspot data
    
    Returns:
        dict with statistics
    """
    if hotspots_df.empty:
        return {
            'total_hotspots': 0,
            'total_incidents': 0,
            'avg_severity': 0,
            'critical_hotspots': 0
        }
    
    # Add risk classification
    hotspots_df['risk_level'] = hotspots_df.apply(
        lambda row: classify_hotspot_severity(row['avg_severity'], row['incident_count']),
        axis=1
    )
    
    stats = {
        'total_hotspots': len(hotspots_df),
        'total_incidents': int(hotspots_df['incident_count'].sum()),
        'avg_severity': float(hotspots_df['avg_severity'].mean()),
        'critical_hotspots': len(hotspots_df[hotspots_df['risk_level'] == 'Critical']),
        'high_risk_hotspots': len(hotspots_df[hotspots_df['risk_level'] == 'High']),
        'top_hotspot_incidents': int(hotspots_df['incident_count'].max()) if not hotspots_df.empty else 0
    }
    
    return stats


def analyze_event_types(sensor_df, hotspot_lat, hotspot_lng, radius_m=50):
    """
    Analyze types of events at a hotspot location
    
    Args:
        sensor_df: DataFrame with sensor data
        hotspot_lat: Hotspot latitude
        hotspot_lng: Hotspot longitude
        radius_m: Radius in meters
    
    Returns:
        dict with event type counts
    """
    nearby = get_hotspot_details(sensor_df, hotspot_lat, hotspot_lng, radius_m)
    
    if nearby.empty or 'primary_event_type' not in nearby.columns:
        return {}
    
    event_counts = nearby['primary_event_type'].value_counts().to_dict()
    return event_counts