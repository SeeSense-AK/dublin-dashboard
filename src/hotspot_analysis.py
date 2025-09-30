"""
Hotspot detection and clustering module
Now uses AWS Athena for spatial clustering of high-severity incidents
"""
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import streamlit as st
from config import HOTSPOT_CONFIG
from src.athena_database import get_athena_database


@st.cache_data(ttl=3600)
def detect_hotspots(sensor_df=None, severity_threshold=None, min_samples=None, eps=None, 
                   start_date=None, end_date=None):
    """
    Detect hotspots using AWS Athena instead of local DataFrame
    
    Args:
        sensor_df: Ignored - we use Athena now
        severity_threshold: Minimum severity to consider (default from config)
        min_samples: Minimum points to form a cluster (default from config)
        eps: DBSCAN epsilon parameter (default from config)
        start_date: Start date for analysis (YYYY-MM-DD)
        end_date: End date for analysis (YYYY-MM-DD)
    
    Returns:
        DataFrame with hotspot information
    """
    severity_threshold = severity_threshold or HOTSPOT_CONFIG["severity_threshold"]
    min_samples = min_samples or HOTSPOT_CONFIG["min_samples"]
    eps = eps or HOTSPOT_CONFIG["eps"]
    
    try:
        db = get_athena_database()
        hotspots_df = db.detect_sensor_hotspots(
            min_events=min_samples,
            severity_threshold=severity_threshold,
            start_date=start_date,
            end_date=end_date
        )
        
        if hotspots_df.empty:
            return pd.DataFrame()
        
        formatted_hotspots = hotspots_df.copy()
        formatted_hotspots = formatted_hotspots.rename(columns={
            'lat': 'latitude',
            'lng': 'longitude',
            'event_count': 'incident_count',
            'severity_score': 'avg_severity'
        })
        
        formatted_hotspots['max_severity'] = formatted_hotspots['avg_severity']
        formatted_hotspots['device_count'] = 1
        formatted_hotspots['cluster_id'] = range(len(formatted_hotspots))
        formatted_hotspots['hotspot_id'] = range(1, len(formatted_hotspots) + 1)
        
        return formatted_hotspots
        
    except Exception as e:
        st.error(f"Error detecting hotspots with Athena: {e}")
        return pd.DataFrame()


def get_hotspot_details(sensor_df, hotspot_lat, hotspot_lng, radius_m=50):
    """
    Get detailed information about incidents near a hotspot
    """
    from utils.geo_utils import find_points_within_radius
    
    try:
        db = get_athena_database()
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error getting hotspot details: {e}")
        return pd.DataFrame()


def classify_hotspot_severity(avg_severity, incident_count):
    """
    Classify hotspot risk level based on severity and frequency
    
    Args:
        avg_severity: Average severity score
        incident_count: Number of incidents
    
    Returns:
        str: Risk level ('Critical', 'High', 'Medium', 'Low')
    """
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
