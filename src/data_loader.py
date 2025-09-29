"""
Data loading and preprocessing module
Handles loading CSV files with smart caching
"""
import pandas as pd
import streamlit as st
from pathlib import Path
from config import (
    SENSOR_DATA_FILE, 
    INFRA_REPORTS_FILE, 
    RIDE_REPORTS_FILE,
    CACHE_CONFIG
)


@st.cache_data(ttl=CACHE_CONFIG["ttl"])
def load_sensor_data():
    """
    Load and preprocess sensor data
    Returns: pandas DataFrame
    """
    try:
        df = pd.read_csv(SENSOR_DATA_FILE)
        
        # Data cleaning
        df = df.dropna(subset=['position_latitude', 'position_longitude'])
        
        # Convert timestamp to datetime if needed
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        
        # Ensure severity column exists
        if 'max_severity' not in df.columns:
            df['max_severity'] = 0
            
        # Filter out invalid coordinates
        df = df[
            (df['position_latitude'].between(-90, 90)) & 
            (df['position_longitude'].between(-180, 180))
        ]
        
        return df
    
    except FileNotFoundError:
        st.error(f"Sensor data file not found: {SENSOR_DATA_FILE}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading sensor data: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_CONFIG["ttl"])
def load_infrastructure_reports():
    """
    Load infrastructure perception reports
    Returns: pandas DataFrame
    """
    try:
        df = pd.read_csv(INFRA_REPORTS_FILE)
        
        # Data cleaning
        df = df.dropna(subset=['lat', 'lng'])
        
        # Convert date/time to datetime
        if 'date' in df.columns and 'time' in df.columns:
            df['datetime'] = pd.to_datetime(
                df['date'] + ' ' + df['time'], 
                errors='coerce'
            )
        
        # Filter invalid coordinates
        df = df[
            (df['lat'].between(-90, 90)) & 
            (df['lng'].between(-180, 180))
        ]
        
        return df
    
    except FileNotFoundError:
        st.warning(f"Infrastructure reports file not found: {INFRA_REPORTS_FILE}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading infrastructure reports: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_CONFIG["ttl"])
def load_ride_reports():
    """
    Load ride perception reports
    Returns: pandas DataFrame
    """
    try:
        df = pd.read_csv(RIDE_REPORTS_FILE)
        
        # Data cleaning
        df = df.dropna(subset=['lat', 'lng'])
        
        # Convert date/time to datetime
        if 'date' in df.columns and 'time' in df.columns:
            df['datetime'] = pd.to_datetime(
                df['date'] + ' ' + df['time'], 
                errors='coerce'
            )
        
        # Filter invalid coordinates
        df = df[
            (df['lat'].between(-90, 90)) & 
            (df['lng'].between(-180, 180))
        ]
        
        return df
    
    except FileNotFoundError:
        st.warning(f"Ride reports file not found: {RIDE_REPORTS_FILE}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading ride reports: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_CONFIG["ttl"])
def load_all_data():
    """
    Load all datasets at once
    Returns: dict with all dataframes
    """
    return {
        'sensor': load_sensor_data(),
        'infrastructure': load_infrastructure_reports(),
        'ride': load_ride_reports()
    }


def get_data_summary(df, name="Dataset"):
    """
    Get summary statistics for a dataset
    Returns: dict with summary stats
    """
    if df.empty:
        return {
            'name': name,
            'rows': 0,
            'columns': 0,
            'date_range': 'N/A',
            'memory_usage': '0 MB'
        }
    
    summary = {
        'name': name,
        'rows': len(df),
        'columns': len(df.columns),
        'memory_usage': f"{df.memory_usage(deep=True).sum() / 1024**2:.2f} MB"
    }
    
    # Add date range if datetime column exists
    if 'datetime' in df.columns:
        summary['date_range'] = f"{df['datetime'].min()} to {df['datetime'].max()}"
    
    return summary


def validate_data():
    """
    Validate all required data files exist and are readable
    Returns: dict with validation results
    """
    validation = {
        'sensor_data': SENSOR_DATA_FILE.exists(),
        'infrastructure_reports': INFRA_REPORTS_FILE.exists(),
        'ride_reports': RIDE_REPORTS_FILE.exists(),
    }
    
    return validation