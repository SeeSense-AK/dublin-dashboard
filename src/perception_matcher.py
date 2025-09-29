"""
Module for matching perception reports to sensor hotspots
"""
import pandas as pd
import streamlit as st
from utils.geo_utils import find_points_within_radius
from config import PERCEPTION_CONFIG


@st.cache_data(ttl=3600)
def match_perception_to_hotspots(hotspots_df, infra_reports_df, ride_reports_df, radius_m=None):
    """
    Match perception reports to each hotspot within a radius
    
    Args:
        hotspots_df: DataFrame with hotspot locations
        infra_reports_df: DataFrame with infrastructure reports
        ride_reports_df: DataFrame with ride reports
        radius_m: Matching radius in meters (default from config)
    
    Returns:
        DataFrame with hotspots and matched perception reports
    """
    radius_m = radius_m or PERCEPTION_CONFIG["matching_radius_m"]
    
    if hotspots_df.empty:
        return pd.DataFrame()
    
    results = []
    
    for idx, hotspot in hotspots_df.iterrows():
        hotspot_data = hotspot.to_dict()
        
        # Find nearby infrastructure reports
        infra_nearby = find_points_within_radius(
            hotspot['latitude'],
            hotspot['longitude'],
            infra_reports_df,
            radius_m,
            lat_col='lat',
            lon_col='lng'
        )
        
        # Find nearby ride reports
        ride_nearby = find_points_within_radius(
            hotspot['latitude'],
            hotspot['longitude'],
            ride_reports_df,
            radius_m,
            lat_col='lat',
            lon_col='lng'
        )
        
        # Add matched reports info
        hotspot_data['infra_reports_count'] = len(infra_nearby)
        hotspot_data['ride_reports_count'] = len(ride_nearby)
        hotspot_data['total_perception_reports'] = len(infra_nearby) + len(ride_nearby)
        
        # Store the actual reports for later analysis
        hotspot_data['infra_reports'] = infra_nearby.to_dict('records') if not infra_nearby.empty else []
        hotspot_data['ride_reports'] = ride_nearby.to_dict('records') if not ride_nearby.empty else []
        
        results.append(hotspot_data)
    
    return pd.DataFrame(results)


def get_perception_summary(matched_hotspots_df, hotspot_id):
    """
    Get a summary of perception reports for a specific hotspot
    
    Args:
        matched_hotspots_df: DataFrame with matched hotspots
        hotspot_id: ID of the hotspot
    
    Returns:
        dict with perception summary
    """
    hotspot = matched_hotspots_df[matched_hotspots_df['hotspot_id'] == hotspot_id]
    
    if hotspot.empty:
        return None
    
    hotspot_row = hotspot.iloc[0]
    
    summary = {
        'total_reports': hotspot_row['total_perception_reports'],
        'infrastructure_reports': hotspot_row['infra_reports_count'],
        'ride_reports': hotspot_row['ride_reports_count'],
        'infra_details': hotspot_row['infra_reports'],
        'ride_details': hotspot_row['ride_reports']
    }
    
    return summary


def extract_perception_themes(infra_reports, ride_reports):
    """
    Extract common themes from perception reports
    
    Args:
        infra_reports: List of infrastructure report dicts
        ride_reports: List of ride report dicts
    
    Returns:
        dict with theme counts
    """
    themes = {}
    
    # Infrastructure types
    for report in infra_reports:
        infra_type = report.get('infrastructuretype', 'Unknown')
        themes[infra_type] = themes.get(infra_type, 0) + 1
    
    # Incident types
    for report in ride_reports:
        incident_type = report.get('incidenttype', 'Unknown')
        themes[incident_type] = themes.get(incident_type, 0) + 1
    
    return themes


def get_perception_comments(infra_reports, ride_reports, max_comments=5):
    """
    Get sample comments from perception reports
    
    Args:
        infra_reports: List of infrastructure report dicts
        ride_reports: List of ride report dicts
        max_comments: Maximum number of comments to return
    
    Returns:
        list of comment strings
    """
    comments = []
    
    # Get infrastructure comments
    for report in infra_reports[:max_comments]:
        comment = report.get('finalcomment', '')
        if comment and isinstance(comment, str) and len(comment.strip()) > 0:
            comments.append({
                'type': 'Infrastructure',
                'comment': comment,
                'date': report.get('date', 'Unknown')
            })
    
    # Get ride comments
    for report in ride_reports[:max_comments]:
        comment = report.get('commentfinal', '')
        if comment and isinstance(comment, str) and len(comment.strip()) > 0:
            comments.append({
                'type': 'Ride',
                'comment': comment,
                'rating': report.get('incidentrating', 'N/A'),
                'date': report.get('date', 'Unknown')
            })
    
    return comments[:max_comments]


def calculate_perception_sentiment_score(ride_reports):
    """
    Calculate a simple sentiment score based on incident ratings
    
    Args:
        ride_reports: List of ride report dicts
    
    Returns:
        float: Average sentiment score (1-5 scale, lower is worse)
    """
    ratings = []
    
    for report in ride_reports:
        rating = report.get('incidentrating')
        if rating is not None and not pd.isna(rating):
            ratings.append(rating)
    
    if not ratings:
        return None
    
    return sum(ratings) / len(ratings)


def enrich_hotspot_with_perception(hotspot, infra_reports, ride_reports):
    """
    Enrich a hotspot with detailed perception analysis
    
    Args:
        hotspot: Hotspot dict
        infra_reports: List of infrastructure reports
        ride_reports: List of ride reports
    
    Returns:
        dict: Enriched hotspot data
    """
    enriched = hotspot.copy()
    
    # Add themes
    enriched['themes'] = extract_perception_themes(infra_reports, ride_reports)
    
    # Add sample comments
    enriched['comments'] = get_perception_comments(infra_reports, ride_reports)
    
    # Add sentiment score
    enriched['sentiment_score'] = calculate_perception_sentiment_score(ride_reports)
    
    # Add confirmation flag (if we have perception reports, it confirms the issue)
    enriched['confirmed_by_perception'] = len(infra_reports) + len(ride_reports) > 0
    
    return enriched