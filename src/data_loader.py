"""
Data loading module - Hybrid approach
Uses AWS Athena for sensor data and local CSV for perception reports
"""
import pandas as pd
import streamlit as st
from pathlib import Path
from src.athena_database import get_athena_database
from config import INFRA_REPORTS_FILE, RIDE_REPORTS_FILE, CACHE_CONFIG


# Initialize Athena connection
@st.cache_resource
def get_data_connection():
    """Get Athena database connection"""
    return get_athena_database()


@st.cache_data(ttl=CACHE_CONFIG["ttl"])
def load_sensor_data_metrics():
    """
    Load sensor data metrics from Athena (not full data, just metrics)
    Returns: dict with metrics
    """
    try:
        db = get_data_connection()
        return db.get_dashboard_metrics()
    except Exception as e:
        st.error(f"Error loading sensor metrics: {str(e)}")
        return {
            'total_readings': 0,
            'unique_devices': 0,
            'abnormal_events': 0,
            'avg_speed': 0,
            'latest_reading': None,
            'earliest_reading': None
        }


@st.cache_data(ttl=CACHE_CONFIG["ttl"])
def load_infrastructure_reports():
    """
    Load infrastructure perception reports from local CSV
    Returns: pandas DataFrame
    """
    try:
        if INFRA_REPORTS_FILE.exists():
            df = pd.read_csv(INFRA_REPORTS_FILE)
            
            # Data cleaning
            df = df.dropna(subset=['lat', 'lng'])
            
            # Convert date/time to datetime if possible
            if 'date' in df.columns and 'time' in df.columns:
                try:
                    df['datetime'] = pd.to_datetime(
                        df['date'] + ' ' + df['time'], 
                        errors='coerce'
                    )
                except:
                    pass
            
            # Filter invalid coordinates
            df = df[
                (df['lat'].between(-90, 90)) & 
                (df['lng'].between(-180, 180))
            ]
            
            return df
        else:
            st.warning(f"Infrastructure reports file not found: {INFRA_REPORTS_FILE}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error loading infrastructure reports: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_CONFIG["ttl"])
def load_ride_reports():
    """
    Load ride perception reports from local CSV
    Returns: pandas DataFrame
    """
    try:
        if RIDE_REPORTS_FILE.exists():
            df = pd.read_csv(RIDE_REPORTS_FILE)
            
            # Data cleaning
            df = df.dropna(subset=['lat', 'lng'])
            
            # Convert date/time to datetime if possible
            if 'date' in df.columns and 'time' in df.columns:
                try:
                    df['datetime'] = pd.to_datetime(
                        df['date'] + ' ' + df['time'], 
                        errors='coerce'
                    )
                except:
                    pass
            
            # Filter invalid coordinates
            df = df[
                (df['lat'].between(-90, 90)) & 
                (df['lng'].between(-180, 180))
            ]
            
            return df
        else:
            st.warning(f"Ride reports file not found: {RIDE_REPORTS_FILE}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error loading ride reports: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_CONFIG["ttl"])
def load_all_data():
    """
    Load all datasets - hybrid approach
    Returns: dict with all dataframes and metrics
    """
    return {
        'sensor_metrics': load_sensor_data_metrics(),  # Just metrics, not full data
        'infrastructure': load_infrastructure_reports(),
        'ride': load_ride_reports()
    }


def get_data_summary():
    """
    Get summary statistics for all datasets
    Returns: dict with summary stats
    """
    data = load_all_data()
    
    return {
        'sensor': {
            'source': 'AWS Athena (Parquet)',
            'total_readings': data['sensor_metrics']['total_readings'],
            'unique_devices': data['sensor_metrics']['unique_devices'],
            'abnormal_events': data['sensor_metrics']['abnormal_events'],
            'date_range': f"{data['sensor_metrics']['earliest_reading']} to {data['sensor_metrics']['latest_reading']}"
        },
        'infrastructure': {
            'source': 'Local CSV',
            'rows': len(data['infrastructure']),
            'columns': len(data['infrastructure'].columns) if not data['infrastructure'].empty else 0,
            'memory_usage': f"{data['infrastructure'].memory_usage(deep=True).sum() / 1024:.2f} KB"
        },
        'ride': {
            'source': 'Local CSV', 
            'rows': len(data['ride']),
            'columns': len(data['ride'].columns) if not data['ride'].empty else 0,
            'memory_usage': f"{data['ride'].memory_usage(deep=True).sum() / 1024:.2f} KB"
        }
    }


def validate_data():
    """
    Validate that all data sources are accessible
    Returns: dict with validation results
    """
    validation = {
        'athena_connection': False,
        'infrastructure_reports': INFRA_REPORTS_FILE.exists(),
        'ride_reports': RIDE_REPORTS_FILE.exists(),
    }
    
    # Test Athena connection
    try:
        db = get_data_connection()
        metrics = db.get_dashboard_metrics()
        validation['athena_connection'] = metrics['total_readings'] > 0
    except Exception as e:
        st.error(f"Athena connection failed: {e}")
        validation['athena_connection'] = False
    
    return validation


# Helper functions for data access
def get_sensor_hotspots(min_events=3, severity_threshold=2, start_date=None, end_date=None):
    """
    Get sensor hotspots from Athena
    """
    try:
        db = get_data_connection()
        return db.detect_sensor_hotspots(min_events, severity_threshold, start_date, end_date)
    except Exception as e:
        st.error(f"Error getting sensor hotspots: {e}")
        return pd.DataFrame()


def get_usage_trends(days=30):
    """
    Get usage trends from Athena
    """
    try:
        db = get_data_connection()
        return db.get_usage_trends(days)
    except Exception as e:
        st.error(f"Error getting usage trends: {e}")
        return pd.DataFrame()


def get_usage_anomalies():
    """
    Get usage anomalies from Athena
    """
    try:
        db = get_data_connection()
        return db.detect_usage_anomalies()
    except Exception as e:
        st.error(f"Error getting usage anomalies: {e}")
        return pd.DataFrame()
