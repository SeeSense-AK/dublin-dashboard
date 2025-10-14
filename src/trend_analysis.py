"""
Time series and trend analysis module
Detects anomalies, usage patterns, and temporal trends using Duck DB
"""
import pandas as pd
import numpy as np
import streamlit as st
from scipy import stats
from config import TIMESERIES_CONFIG
from src.duckdb_database import get_duckdb_database


@st.cache_data(ttl=3600)
def prepare_time_series(sensor_df=None, freq='D'):
    """
    Prepare time series data from duckdb sensor readings
    
    Args:
        sensor_df: Ignored - we use duckdb now
        freq: Frequency for aggregation ('D'=daily, 'W'=weekly, 'M'=monthly)
    
    Returns:
        DataFrame with time series aggregated by frequency
    """
    try:
        db = get_duckdb_database()
        
        # Map frequency to days for duckdb query
        if freq == 'D':
            days = 90  # Default to 90 days for daily analysis
        elif freq == 'W':
            days = 365  # Full year for weekly analysis
        elif freq == 'M':
            days = 730  # 2 years for monthly analysis
        else:
            days = 90
        
        # Get usage trends from duckdb
        time_series_df = db.get_usage_trends(days)
        
        if time_series_df.empty:
            return pd.DataFrame()
        
        # Rename columns to match original format
        if 'date' in time_series_df.columns:
            time_series_df = time_series_df.rename(columns={'date': 'datetime'})
        
        # Add missing columns with default values
        if 'reading_count' not in time_series_df.columns:
            time_series_df['reading_count'] = time_series_df.get('total_readings', 0)
        if 'avg_severity' not in time_series_df.columns:
            time_series_df['avg_severity'] = 2.0  # Default severity
        if 'max_severity' not in time_series_df.columns:
            time_series_df['max_severity'] = time_series_df.get('avg_severity', 2.0)
        
        return time_series_df
        
    except Exception as e:
        st.error(f"Error preparing time series from duckdb: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def detect_anomalies(time_series_df, column='reading_count', threshold=None):
    """
    Detect anomalies in time series using z-score method
    
    Args:
        time_series_df: DataFrame with time series data
        column: Column to analyze for anomalies
        threshold: Z-score threshold (default from config)
    
    Returns:
        DataFrame with anomaly flags and scores
    """
    threshold = threshold or TIMESERIES_CONFIG['anomaly_threshold']
    
    # Map column names for compatibility
    if column == 'reading_count' and 'total_readings' in time_series_df.columns:
        column = 'total_readings'
    elif column == 'reading_count' and 'unique_users' in time_series_df.columns:
        column = 'unique_users'
    
    if time_series_df.empty or column not in time_series_df.columns:
        return pd.DataFrame()
    
    df = time_series_df.copy()
    
    # Calculate rolling statistics
    window = TIMESERIES_CONFIG['rolling_window']
    df['rolling_mean'] = df[column].rolling(window=window, center=True).mean()
    df['rolling_std'] = df[column].rolling(window=window, center=True).std()
    
    # Calculate z-score
    df['z_score'] = np.abs((df[column] - df['rolling_mean']) / (df['rolling_std'] + 1e-6))
    
    # Flag anomalies
    df['is_anomaly'] = df['z_score'] > threshold
    df['anomaly_type'] = df.apply(
        lambda row: 'spike' if row[column] > row['rolling_mean'] else 'drop' if row['is_anomaly'] else 'normal',
        axis=1
    )
    
    return df


@st.cache_data(ttl=3600)
def calculate_trends(time_series_df, column='reading_count'):
    """
    Calculate trend statistics (trend direction, change percentage)
    
    Args:
        time_series_df: DataFrame with time series data
        column: Column to analyze
    
    Returns:
        dict with trend statistics
    """
    # Map column names for compatibility
    if column == 'reading_count' and 'total_readings' in time_series_df.columns:
        column = 'total_readings'
    elif column == 'reading_count' and 'unique_users' in time_series_df.columns:
        column = 'unique_users'
    
    if time_series_df.empty or column not in time_series_df.columns:
        return {}
    
    values = time_series_df[column].values
    
    # Linear regression for trend
    x = np.arange(len(values))
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)
    
    # Calculate percentage change
    first_value = values[0]
    last_value = values[-1]
    pct_change = ((last_value - first_value) / first_value) * 100 if first_value != 0 else 0
    
    # Determine trend direction
    if slope > 0 and p_value < 0.05:
        trend_direction = 'increasing'
    elif slope < 0 and p_value < 0.05:
        trend_direction = 'decreasing'
    else:
        trend_direction = 'stable'
    
    return {
        'slope': slope,
        'r_squared': r_value ** 2,
        'p_value': p_value,
        'trend_direction': trend_direction,
        'percent_change': pct_change,
        'mean_value': np.mean(values),
        'std_value': np.std(values)
    }


@st.cache_data(ttl=3600)
def find_usage_drops(time_series_df, column='reading_count', drop_threshold=0.3):
    """
    Find periods with significant usage drops
    
    Args:
        time_series_df: DataFrame with time series data
        column: Column to analyze
        drop_threshold: Minimum percentage drop to flag (default 30%)
    
    Returns:
        DataFrame with significant drops
    """
    # Map column names for compatibility
    if column == 'reading_count' and 'total_readings' in time_series_df.columns:
        column = 'total_readings'
    elif column == 'reading_count' and 'unique_users' in time_series_df.columns:
        column = 'unique_users'
    
    if time_series_df.empty or column not in time_series_df.columns:
        return pd.DataFrame()
    
    df = time_series_df.copy()
    
    # Calculate rolling average
    window = TIMESERIES_CONFIG['rolling_window']
    df['baseline'] = df[column].rolling(window=window, min_periods=1).mean()
    
    # Calculate deviation from baseline
    df['deviation_pct'] = ((df[column] - df['baseline']) / df['baseline']) * 100
    
    # Flag significant drops
    drops = df[df['deviation_pct'] < -drop_threshold * 100].copy()
    drops = drops.sort_values('deviation_pct')
    
    return drops


@st.cache_data(ttl=3600)
def analyze_seasonal_patterns(time_series_df, column='reading_count'):
    """
    Analyze seasonal/periodic patterns in the data
    
    Args:
        time_series_df: DataFrame with time series data
        column: Column to analyze
    
    Returns:
        dict with seasonal statistics
    """
    # Map column names for compatibility
    if column == 'reading_count' and 'total_readings' in time_series_df.columns:
        column = 'total_readings'
    elif column == 'reading_count' and 'unique_users' in time_series_df.columns:
        column = 'unique_users'
    
    if time_series_df.empty or column not in time_series_df.columns:
        return {}
    
    df = time_series_df.copy()
    
    # Extract time features if datetime column exists
    datetime_col = 'datetime' if 'datetime' in df.columns else 'date'
    
    if datetime_col in df.columns:
        df['day_of_week'] = pd.to_datetime(df[datetime_col]).dt.dayofweek
        df['month'] = pd.to_datetime(df[datetime_col]).dt.month
        df['hour'] = pd.to_datetime(df[datetime_col]).dt.hour if pd.to_datetime(df[datetime_col]).dt.hour.nunique() > 1 else None
        
        # Weekly pattern
        weekly_pattern = df.groupby('day_of_week')[column].mean().to_dict()
        
        # Monthly pattern
        monthly_pattern = df.groupby('month')[column].mean().to_dict()
        
        return {
            'weekly_pattern': weekly_pattern,
            'monthly_pattern': monthly_pattern,
            'weekday_avg': df[df['day_of_week'] < 5][column].mean(),
            'weekend_avg': df[df['day_of_week'] >= 5][column].mean()
        }
    
    return {}


@st.cache_data(ttl=3600)
def compare_time_periods(sensor_df, period1_start, period1_end, period2_start, period2_end):
    """
    Compare two time periods to identify changes
    Note: This function needs duckdb implementation for period comparison
    
    Args:
        sensor_df: Ignored - we use duckdb now
        period1_start: Start date of first period
        period1_end: End date of first period
        period2_start: Start date of second period
        period2_end: End date of second period
    
    Returns:
        dict with comparison metrics
    """
    try:
        db = get_duckdb_database()
        
        # Get data for period 1
        period1_df = db.get_usage_trends(90)  # Get recent data
        if not period1_df.empty:
            period1_df = period1_df[
                (pd.to_datetime(period1_df['date']) >= pd.to_datetime(period1_start)) &
                (pd.to_datetime(period1_df['date']) <= pd.to_datetime(period1_end))
            ]
        
        # Get data for period 2
        period2_df = db.get_usage_trends(90)  # Get recent data
        if not period2_df.empty:
            period2_df = period2_df[
                (pd.to_datetime(period2_df['date']) >= pd.to_datetime(period2_start)) &
                (pd.to_datetime(period2_df['date']) <= pd.to_datetime(period2_end))
            ]
        
        if period1_df.empty or period2_df.empty:
            return {}
        
        # Calculate metrics for each period
        comparison = {
            'period1_count': period1_df['unique_users'].sum(),
            'period2_count': period2_df['unique_users'].sum(),
            'count_change_pct': ((period2_df['unique_users'].sum() - period1_df['unique_users'].sum()) / period1_df['unique_users'].sum()) * 100,
            'period1_avg_severity': 2.0,  # Default since we don't have severity in trends
            'period2_avg_severity': 2.0,  # Default since we don't have severity in trends
            'severity_change': 0.0
        }
        
        return comparison
        
    except Exception as e:
        st.error(f"Error comparing time periods: {e}")
        return {}


def identify_trend_changes(time_series_df, column='reading_count', sensitivity=0.2):
    """
    Identify points where trends change direction
    
    Args:
        time_series_df: DataFrame with time series data
        column: Column to analyze
        sensitivity: Minimum change to consider significant
    
    Returns:
        DataFrame with trend change points
    """
    # Map column names for compatibility
    if column == 'reading_count' and 'total_readings' in time_series_df.columns:
        column = 'total_readings'
    elif column == 'reading_count' and 'unique_users' in time_series_df.columns:
        column = 'unique_users'
    
    if time_series_df.empty or column not in time_series_df.columns:
        return pd.DataFrame()
    
    df = time_series_df.copy()
    
    # Calculate first derivative (rate of change)
    df['rate_of_change'] = df[column].diff()
    
    # Calculate second derivative (acceleration)
    df['acceleration'] = df['rate_of_change'].diff()
    
    # Find sign changes in acceleration (trend reversals)
    df['trend_change'] = (np.sign(df['acceleration'].shift(1)) != np.sign(df['acceleration']))
    
    # Filter significant changes
    significant_changes = df[
        (df['trend_change'] == True) & 
        (np.abs(df['acceleration']) > sensitivity * df[column].std())
    ].copy()
    
    return significant_changes


@st.cache_data(ttl=3600)
def get_time_series_summary(time_series_df, column='reading_count'):
    """
    Get comprehensive summary of time series
    
    Args:
        time_series_df: DataFrame with time series data
        column: Column to summarize
    
    Returns:
        dict with summary statistics
    """
    # Map column names for compatibility
    if column == 'reading_count' and 'total_readings' in time_series_df.columns:
        column = 'total_readings'
    elif column == 'reading_count' and 'unique_users' in time_series_df.columns:
        column = 'unique_users'
    
    if time_series_df.empty or column not in time_series_df.columns:
        return {}
    
    values = time_series_df[column]
    
    return {
        'total_observations': len(values),
        'mean': values.mean(),
        'median': values.median(),
        'std': values.std(),
        'min': values.min(),
        'max': values.max(),
        'range': values.max() - values.min(),
        'coefficient_of_variation': (values.std() / values.mean()) * 100 if values.mean() != 0 else 0
    }
