"""
Time series and trend analysis module
Detects anomalies, usage patterns, and temporal trends
"""
import pandas as pd
import numpy as np
import streamlit as st
from scipy import stats
from config import TIMESERIES_CONFIG


@st.cache_data(ttl=3600)
def prepare_time_series(sensor_df, freq='D'):
    """
    Prepare time series data from sensor readings
    
    Args:
        sensor_df: DataFrame with sensor data
        freq: Frequency for aggregation ('D'=daily, 'W'=weekly, 'M'=monthly)
    
    Returns:
        DataFrame with time series aggregated by frequency
    """
    if sensor_df.empty or 'datetime' not in sensor_df.columns:
        return pd.DataFrame()
    
    # Set datetime as index
    ts_df = sensor_df.set_index('datetime').copy()
    
    # Aggregate by frequency
    aggregated = ts_df.resample(freq).agg({
        'device_id': 'count',  # Number of readings
        'max_severity': ['mean', 'max'],
        'speed_kmh': 'mean'
    })
    
    # Flatten columns
    aggregated.columns = ['reading_count', 'avg_severity', 'max_severity', 'avg_speed']
    aggregated = aggregated.reset_index()
    
    return aggregated


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
    if time_series_df.empty or column not in time_series_df.columns:
        return {}
    
    df = time_series_df.copy()
    
    # Extract time features if datetime column exists
    if 'datetime' in df.columns:
        df['day_of_week'] = df['datetime'].dt.dayofweek
        df['month'] = df['datetime'].dt.month
        df['hour'] = df['datetime'].dt.hour if df['datetime'].dt.hour.nunique() > 1 else None
        
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
    
    Args:
        sensor_df: DataFrame with sensor data
        period1_start: Start date of first period
        period1_end: End date of first period
        period2_start: Start date of second period
        period2_end: End date of second period
    
    Returns:
        dict with comparison metrics
    """
    if sensor_df.empty or 'datetime' not in sensor_df.columns:
        return {}
    
    # Filter data for each period
    period1 = sensor_df[
        (sensor_df['datetime'] >= period1_start) & 
        (sensor_df['datetime'] <= period1_end)
    ]
    
    period2 = sensor_df[
        (sensor_df['datetime'] >= period2_start) & 
        (sensor_df['datetime'] <= period2_end)
    ]
    
    if period1.empty or period2.empty:
        return {}
    
    # Calculate metrics for each period
    comparison = {
        'period1_count': len(period1),
        'period2_count': len(period2),
        'count_change_pct': ((len(period2) - len(period1)) / len(period1)) * 100,
        'period1_avg_severity': period1['max_severity'].mean(),
        'period2_avg_severity': period2['max_severity'].mean(),
        'severity_change': period2['max_severity'].mean() - period1['max_severity'].mean()
    }
    
    return comparison


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