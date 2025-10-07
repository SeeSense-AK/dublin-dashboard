# src/perception_hotspot_analyzer.py
"""
Perception-driven hotspot detection
UPDATED: Uses full date range for sensor validation instead of just perception report dates
"""

import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
import streamlit as st
from typing import Dict, List, Tuple
from utils.geo_utils import haversine_distance, find_points_within_radius
from src.sentiment_analyzer import analyze_perception_sentiment
from src.athena_database import get_athena_database


def cluster_perception_reports(infra_df: pd.DataFrame, ride_df: pd.DataFrame, 
                               eps_meters: int = 50) -> pd.DataFrame:
    """
    Cluster perception reports by location using DBSCAN
    
    Args:
        infra_df: Infrastructure reports
        ride_df: Ride reports
        eps_meters: Clustering radius in meters (default: 50m)
    
    Returns:
        DataFrame with clustered perception reports
    """
    # Combine both report types
    combined_reports = []
    
    # Process infrastructure reports
    if not infra_df.empty:
        infra_subset = infra_df[['lat', 'lng', 'infrastructuretype', 'finalcomment', 'date']].copy()
        infra_subset['report_type'] = 'infrastructure'
        infra_subset['theme'] = infra_subset['infrastructuretype']
        infra_subset['comment'] = infra_subset['finalcomment']
        infra_subset['rating'] = None
        combined_reports.append(infra_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating', 'date']])
    
    # Process ride reports
    if not ride_df.empty:
        ride_subset = ride_df[['lat', 'lng', 'incidenttype', 'commentfinal', 'incidentrating', 'date']].copy()
        ride_subset['report_type'] = 'ride'
        ride_subset['theme'] = ride_subset['incidenttype']
        ride_subset['comment'] = ride_subset['commentfinal']
        ride_subset['rating'] = ride_subset['incidentrating']
        combined_reports.append(ride_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating', 'date']])
    
    if not combined_reports:
        return pd.DataFrame()
    
    # Combine all reports
    all_reports = pd.concat(combined_reports, ignore_index=True)
    
    # Convert eps from meters to degrees (approximate)
    eps_degrees = eps_meters / 111000  # 1 degree ≈ 111km
    
    # Perform DBSCAN clustering
    coords = all_reports[['lat', 'lng']].values
    clustering = DBSCAN(eps=eps_degrees, min_samples=2, metric='euclidean')
    all_reports['cluster_id'] = clustering.fit_predict(coords)
    
    # Filter out noise (cluster_id = -1)
    clustered_reports = all_reports[all_reports['cluster_id'] >= 0].copy()
    
    return clustered_reports


def analyze_perception_cluster(cluster_reports: pd.DataFrame, cluster_id: int) -> Dict:
    """
    Analyze a single perception cluster to extract themes and sentiment
    
    Args:
        cluster_reports: DataFrame with all clustered reports
        cluster_id: ID of cluster to analyze
    
    Returns:
        Dictionary with cluster analysis
    """
    cluster_data = cluster_reports[cluster_reports['cluster_id'] == cluster_id]
    
    if cluster_data.empty:
        return None
    
    # Calculate centroid
    center_lat = cluster_data['lat'].mean()
    center_lng = cluster_data['lng'].mean()
    
    # Count report types
    report_counts = cluster_data['report_type'].value_counts().to_dict()
    
    # Extract themes
    theme_counts = cluster_data['theme'].value_counts().to_dict()
    top_theme = cluster_data['theme'].mode()[0] if not cluster_data['theme'].mode().empty else 'Unknown'
    
    # Get comments for AI analysis
    comments = cluster_data['comment'].dropna().tolist()
    
    # Calculate severity from ratings (if available)
    ratings = cluster_data['rating'].dropna()
    avg_rating = ratings.mean() if not ratings.empty else None
    
    # Get date range
    dates = pd.to_datetime(cluster_data['date'], errors='coerce')
    date_range = {
        'first_report': dates.min() if not dates.isna().all() else None,
        'last_report': dates.max() if not dates.isna().all() else None,
        'days_span': (dates.max() - dates.min()).days if not dates.isna().all() else 0
    }
    
    return {
        'cluster_id': cluster_id,
        'center_lat': center_lat,
        'center_lng': center_lng,
        'total_reports': len(cluster_data),
        'report_types': report_counts,
        'theme_counts': theme_counts,
        'primary_theme': top_theme,
        'avg_rating': avg_rating,
        'comments': comments,
        'date_range': date_range,
        'raw_reports': cluster_data.to_dict('records')
    }


def enrich_with_ai_sentiment(cluster_analysis: Dict) -> Dict:
    """
    Add AI-powered sentiment and theme analysis
    
    Args:
        cluster_analysis: Basic cluster analysis dict
    
    Returns:
        Enhanced analysis with AI insights
    """
    comments = cluster_analysis['comments']
    
    if not comments:
        cluster_analysis['ai_analysis'] = {
            'sentiment': 'unknown',
            'severity': 'unknown',
            'summary': 'No comments available',
            'key_issues': [],
            'method': 'none'
        }
        return cluster_analysis
    
    # Run AI sentiment analysis
    ai_result = analyze_perception_sentiment(comments)
    
    cluster_analysis['ai_analysis'] = ai_result
    
    # Add urgency score based on sentiment + frequency
    urgency_score = calculate_urgency_score(
        sentiment=ai_result['severity'],
        num_reports=cluster_analysis['total_reports'],
        avg_rating=cluster_analysis['avg_rating'],
        days_span=cluster_analysis['date_range']['days_span']
    )
    
    cluster_analysis['urgency_score'] = urgency_score
    
    return cluster_analysis


def calculate_urgency_score(sentiment: str, num_reports: int, 
                            avg_rating: float = None, days_span: int = 0) -> int:
    """
    Calculate urgency score (0-100) based on multiple factors
    
    Args:
        sentiment: AI-detected severity (low/medium/high/critical)
        num_reports: Number of reports in cluster
        avg_rating: Average user rating (1-5, lower = worse)
        days_span: Days between first and last report
    
    Returns:
        Urgency score (0-100)
    """
    # Base score from sentiment
    sentiment_scores = {
        'critical': 40,
        'high': 30,
        'medium': 20,
        'low': 10,
        'unknown': 0
    }
    score = sentiment_scores.get(sentiment, 0)
    
    # Add points for frequency (more reports = more urgent)
    frequency_score = min(30, num_reports * 2)
    score += frequency_score
    
    # Add points for low ratings (if available)
    if avg_rating is not None:
        rating_score = (5 - avg_rating) * 5  # Lower rating = higher score
        score += rating_score
    
    # Add points if reports span many days (persistent problem)
    if days_span > 7:
        persistence_score = min(10, days_span / 7)
        score += persistence_score
    
    return min(100, int(score))


@st.cache_data(ttl=3600)
def find_sensor_data_for_perception_cluster(cluster_lat: float, cluster_lng: float, 
                                           radius_m: int = 50,
                                           start_date: str = None, 
                                           end_date: str = None) -> Dict:
    """
    Find sensor readings near a perception cluster
    UPDATED: Now uses the full date range selected by user, not just perception report dates
    
    Args:
        cluster_lat: Cluster center latitude
        cluster_lng: Cluster center longitude
        radius_m: Search radius in meters
        start_date: START of FULL date range selected by user
        end_date: END of FULL date range selected by user
    
    Returns:
        Dictionary with sensor data summary
    """
    try:
        db = get_athena_database()
        
        # Convert radius to degrees
        radius_deg = radius_m / 111000
        
        # IMPORTANT: We now use the FULL date range from user selection
        # This allows us to see ALL sensor data in that location, not just during report dates
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'"
        
        query = f"""
        SELECT 
            COUNT(*) as total_events,
            COUNT(CASE WHEN is_abnormal_event THEN 1 END) as abnormal_events,
            AVG(max_severity) as avg_severity,
            MAX(max_severity) as max_severity,
            COUNT(CASE WHEN primary_event_type LIKE '%brake%' THEN 1 END) as brake_events,
            COUNT(CASE WHEN primary_event_type LIKE '%swerve%' THEN 1 END) as swerve_events,
            COUNT(CASE WHEN primary_event_type LIKE '%pothole%' OR primary_event_type LIKE '%bump%' THEN 1 END) as pothole_events,
            COUNT(DISTINCT device_id) as unique_devices
        FROM spinovate_production.spinovate_production_optimised
        WHERE ABS(lat - {cluster_lat}) <= {radius_deg}
            AND ABS(lng - {cluster_lng}) <= {radius_deg}
            AND lat IS NOT NULL
            AND lng IS NOT NULL
            {date_filter}
        """
        
        result = pd.read_sql(query, db.conn)
        
        if result.empty:
            return {
                'has_sensor_data': False,
                'total_events': 0
            }
        
        row = result.iloc[0]
        
        return {
            'has_sensor_data': row['total_events'] > 0,
            'total_events': int(row['total_events']),
            'abnormal_events': int(row['abnormal_events']),
            'avg_severity': float(row['avg_severity']) if row['avg_severity'] else 0,
            'max_severity': int(row['max_severity']) if row['max_severity'] else 0,
            'brake_events': int(row['brake_events']),
            'swerve_events': int(row['swerve_events']),
            'pothole_events': int(row['pothole_events']),
            'unique_devices': int(row['unique_devices'])
        }
        
    except Exception as e:
        print(f"Error finding sensor data: {e}")
        return {
            'has_sensor_data': False,
            'total_events': 0,
            'error': str(e)
        }


def cross_validate_perception_with_sensor(perception_analysis: Dict, 
                                          sensor_data: Dict) -> Dict:
    """
    Cross-validate perception reports with sensor data
    Checks if sensor data supports user complaints
    
    Args:
        perception_analysis: Dict with perception cluster analysis
        sensor_data: Dict with sensor data summary
    
    Returns:
        Validation results
    """
    if not sensor_data['has_sensor_data']:
        return {
            'validation_status': 'NO_SENSOR_DATA',
            'confidence': 'low',
            'notes': 'No sensor data available to validate perception reports'
        }
    
    # Check if sensor data supports perception theme
    primary_theme = perception_analysis['primary_theme'].lower()
    
    matches = []
    conflicts = []
    
    # Theme-specific validation
    if 'close' in primary_theme or 'pass' in primary_theme or 'danger' in primary_theme:
        # Expect braking/swerving for close passes
        if sensor_data['brake_events'] > 5 or sensor_data['swerve_events'] > 5:
            matches.append(f"Sensor confirms: {sensor_data['brake_events']} brakes, {sensor_data['swerve_events']} swerves")
        else:
            conflicts.append("Expected more braking/swerving for reported close passes")
    
    elif 'pothole' in primary_theme or 'surface' in primary_theme or 'bump' in primary_theme:
        # Expect pothole/bump events
        if sensor_data['pothole_events'] > 3:
            matches.append(f"Sensor confirms: {sensor_data['pothole_events']} pothole/bump events")
        else:
            conflicts.append("Limited pothole events detected in sensor data")
    
    # Check overall activity
    if sensor_data['abnormal_events'] > 10:
        matches.append(f"{sensor_data['abnormal_events']} abnormal events detected")
    
    # Determine validation status
    if len(matches) >= 2 and len(conflicts) == 0:
        status = 'STRONGLY_CONFIRMED'
        confidence = 'very_high'
    elif len(matches) >= 1 and len(conflicts) == 0:
        status = 'CONFIRMED'
        confidence = 'high'
    elif len(matches) >= 1 and len(conflicts) >= 1:
        status = 'PARTIALLY_CONFIRMED'
        confidence = 'medium'
    elif len(conflicts) > len(matches):
        status = 'CONFLICTED'
        confidence = 'low'
    else:
        status = 'INCONCLUSIVE'
        confidence = 'medium'
    
    return {
        'validation_status': status,
        'confidence': confidence,
        'matches': matches,
        'conflicts': conflicts,
        'sensor_summary': f"{sensor_data['abnormal_events']} abnormal events, avg severity {sensor_data['avg_severity']:.1f}"
    }


def create_enriched_perception_hotspots(infra_df: pd.DataFrame, ride_df: pd.DataFrame,
                                       eps_meters: int = 50, min_reports: int = 2,
                                       start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    MAIN FUNCTION: Create perception-driven hotspots with sensor validation
    UPDATED: Uses full date range for sensor data validation
    
    Args:
        infra_df: Infrastructure reports
        ride_df: Ride reports
        eps_meters: Clustering radius
        min_reports: Minimum reports to form a hotspot
        start_date: START of FULL user-selected date range (for sensor queries)
        end_date: END of FULL user-selected date range (for sensor queries)
    
    Returns:
        DataFrame with enriched perception hotspots
    """
    # Step 1: Cluster perception reports
    clustered_reports = cluster_perception_reports(infra_df, ride_df, eps_meters)
    
    if clustered_reports.empty:
        return pd.DataFrame()
    
    # Step 2: Filter clusters by minimum reports
    cluster_sizes = clustered_reports['cluster_id'].value_counts()
    valid_clusters = cluster_sizes[cluster_sizes >= min_reports].index
    
    enriched_hotspots = []
    
    # Step 3: Analyze each cluster
    for cluster_id in valid_clusters:
        # Basic analysis
        analysis = analyze_perception_cluster(clustered_reports, cluster_id)
        
        if not analysis:
            continue
        
        # AI sentiment analysis
        analysis = enrich_with_ai_sentiment(analysis)
        
        # Find sensor data using FULL date range (not just perception report dates)
        # This is the key change - we now look at ALL sensor data in that location
        sensor_data = find_sensor_data_for_perception_cluster(
            analysis['center_lat'],
            analysis['center_lng'],
            radius_m=eps_meters,
            start_date=start_date,  # Full range start
            end_date=end_date        # Full range end
        )
        
        analysis['sensor_data'] = sensor_data
        
        # Cross-validate
        validation = cross_validate_perception_with_sensor(analysis, sensor_data)
        analysis['validation'] = validation
        
        enriched_hotspots.append(analysis)
    
    # Convert to DataFrame
    if not enriched_hotspots:
        return pd.DataFrame()
    
    hotspots_df = pd.DataFrame(enriched_hotspots)
    
    # Sort by urgency score
    hotspots_df = hotspots_df.sort_values('urgency_score', ascending=False)
    
    # Add hotspot IDs
    hotspots_df['hotspot_id'] = range(1, len(hotspots_df) + 1)
    
    return hotspots_df