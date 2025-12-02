#!/usr/bin/env python3
"""
Hotspot Analysis Script - Sensor Data + Collision Tracker Integration (UPDATED WITH USER DATA)
======================================================================

This script combines sensor hotspot data with citizen collision reports to create
a validated priority ranking of cycling safety hotspots.

Updated to work with new sensor data format including actual user counts.

Author: Abhishek Kumbhar
Date: November 2025
Version: 2.1

Usage:
    python hotspot_analyzer_v2.py

Output:
    - top_30_hotspots.csv (CSV format for easy viewing)
    - top_30_hotspots.json (JSON format for dashboard integration)
    - hotspot_analysis_summary.txt (Human-readable summary)
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration settings for the analysis"""
    
    # Input file paths
    COLLISION_DATA_PATH = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/data/processed/tab1_hotspots/collision_data.csv"
    SENSOR_DATA_PATH = "/Users/abhishekkumbhar/Downloads/clusters_with_users.csv"  # UPDATED WITH USER DATA
    
    # Output directory
    OUTPUT_DIR = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/data/processed/tab1_hotspots"
    
    # Analysis parameters
    MATCHING_RADIUS_METERS = 100  # Radius for matching collision reports to hotspots
    TOP_N_HOTSPOTS = 50  # Number of top hotspots to output
    MAX_DESCRIPTIONS_PER_HOTSPOT = 8  # Number of collision descriptions to include
    
    # Dublin bounding box (to filter collision reports)
    DUBLIN_LAT_MIN = 53.2
    DUBLIN_LAT_MAX = 53.45
    DUBLIN_LNG_MIN = -6.4
    DUBLIN_LNG_MAX = -6.1
    
    # Scoring weights
    WEIGHT_SENSOR = 0.60  # Weight for sensor concern score
    WEIGHT_COLLISION = 0.30  # Weight for collision validation
    WEIGHT_VOLUME = 0.10  # Weight for volume factor
    
    # Severity multipliers
    MULTIPLIER_FATALITY = 2.0
    MULTIPLIER_SERIOUS_INJURY = 1.5
    MULTIPLIER_COLLISION_VS_NEAR_MISS = 1.3
    
    # User engagement parameters
    REPEAT_USER_BONUS = 0.2  # Bonus for high repeat user percentage
    MIN_EVENTS_PER_USER = 5  # Threshold for meaningful user engagement


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on Earth in meters.
    
    Args:
        lat1, lon1: Latitude and longitude of point 1 (degrees)
        lat2, lon2: Latitude and longitude of point 2 (degrees)
    
    Returns:
        Distance in meters
    """
    R = 6371000  # Earth radius in meters
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c


def extract_themes(descriptions):
    """
    Extract common themes from collision descriptions.
    
    Args:
        descriptions: List of description strings
    
    Returns:
        Dictionary with theme counts
    """
    if not descriptions or len(descriptions) == 0:
        return {}
    
    all_text = ' '.join([str(d).lower() for d in descriptions if pd.notna(d)])
    
    themes = {
        'left_hook': ['left hook', 'left turn', 'turning left', 'turned left'],
        'right_hook': ['right hook', 'right turn', 'turning right', 'turned right'],
        'dooring': ['door', 'car door', 'opened door'],
        'close_pass': ['close pass', 'overtake', 'overtaking', 'passed too close'],
        'red_light': ['red light', 'ran red', 'traffic light'],
        'pothole': ['pothole', 'hole in road', 'road surface'],
        'poor_visibility': ['dark', 'blind', 'couldn\'t see', 'visibility'],
        'pedestrian_conflict': ['pedestrian', 'walked out', 'crossing'],
        'cycle_lane_blocked': ['blocked', 'parked in', 'obstruct'],
        'junction_design': ['junction', 'roundabout', 'intersection'],
        'speed': ['speed', 'fast', 'racing'],
        'hgv': ['hgv', 'lorry', 'truck', 'heavy vehicle'],
        'taxi': ['taxi', 'cab'],
        'bus': ['bus'],
        'luas': ['luas', 'tram', 'track']
    }
    
    theme_counts = {}
    for theme_name, keywords in themes.items():
        count = sum(keyword in all_text for keyword in keywords)
        if count > 0:
            theme_counts[theme_name] = count
    
    return theme_counts


def generate_summary_text(theme_counts, total_reports):
    """
    Generate human-readable summary of common issues.
    
    Args:
        theme_counts: Dictionary of theme counts
        total_reports: Total number of reports
    
    Returns:
        Summary string
    """
    if not theme_counts:
        return "No common themes identified"
    
    sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
    top_themes = sorted_themes[:3]
    
    theme_labels = {
        'left_hook': 'left-hook turning conflicts',
        'right_hook': 'right-hook turning conflicts',
        'dooring': 'car door incidents',
        'close_pass': 'close passing/overtaking',
        'red_light': 'red light violations',
        'pothole': 'road surface issues',
        'poor_visibility': 'visibility problems',
        'pedestrian_conflict': 'pedestrian conflicts',
        'cycle_lane_blocked': 'blocked cycle lanes',
        'junction_design': 'junction design issues',
        'speed': 'speeding',
        'hgv': 'HGV conflicts',
        'taxi': 'taxi-related incidents',
        'bus': 'bus-related incidents',
        'luas': 'Luas/tram hazards'
    }
    
    summary_parts = []
    for theme, count in top_themes:
        label = theme_labels.get(theme, theme.replace('_', ' '))
        summary_parts.append(f"{label} ({count} mentions)")
    
    return "; ".join(summary_parts)


def calculate_sensor_score(row, config):
    """
    Calculate sensor concern score from the new data format including user data.
    
    Args:
        row: DataFrame row with sensor data
        config: Configuration object
    
    Returns:
        Sensor score (0-1)
    """
    # Extract event counts
    braking = row.get('braking_events', 0)
    swerve = row.get('swerve_events', 0)
    roughness = row.get('roughness_events', 0)
    total_events = braking + swerve + roughness
    
    if total_events == 0:
        return 0.0
    
    # 1. Size score (normalized by max cluster size ~800)
    size_score = min(row.get('size', 0) / 800, 1.0)
    
    # 2. User engagement score
    unique_users = row.get('unique_users', 0)
    events_per_user = row.get('events_per_user', 0)
    repeat_user_pct = row.get('repeat_user_pct', 0)
    
    # More unique users = more widespread issue
    user_diversity_score = min(unique_users / 100, 1.0)  # Normalize to 100 users
    
    # High events per user = problematic for individuals
    engagement_score = min(events_per_user / config.MIN_EVENTS_PER_USER, 1.0)
    
    # High repeat users = persistent problem location
    repeat_user_score = min(repeat_user_pct / 100, 1.0) if pd.notna(repeat_user_pct) else 0
    
    user_engagement_score = (user_diversity_score * 0.4 + 
                            engagement_score * 0.3 + 
                            repeat_user_score * 0.3)
    
    # 3. Hazard composition score
    hazard_type = str(row.get('hazard_type', ''))
    hazard_complexity = 0.5  # Default for single hazard types
    if 'mixed' in hazard_type.lower():
        if 'braking_swerve_roughness' in hazard_type.lower():
            hazard_complexity = 1.0  # All three hazard types
        elif 'braking_swerve' in hazard_type.lower() or 'braking_roughness' in hazard_type.lower():
            hazard_complexity = 0.8  # Two hazard types
        else:
            hazard_complexity = 0.7  # Mixed but unspecified
    
    # 4. Acceleration severity score
    avg_accel = (row.get('avg_x', 0) + row.get('avg_y', 0) + row.get('avg_z', 0)) / 3
    max_accel = max(row.get('max_x', 0), row.get('max_y', 0), row.get('max_z', 0))
    accel_score = min((avg_accel + max_accel) / 150, 1.0)
    
    # 5. Temporal concentration score
    peak_events = row.get('peak_events', 0)
    offpeak_events = row.get('offpeak_events', 0)
    total_temporal = peak_events + offpeak_events
    temporal_score = 0.0
    if total_temporal > 0:
        temporal_score = min(peak_events / (offpeak_events + 1), 2.0) / 2.0
    
    # FINAL SENSOR SCORE (weighted combination)
    sensor_score = (
        size_score * 0.20 +           # 20% weight: Total volume
        user_engagement_score * 0.25 + # 25% weight: User engagement
        hazard_complexity * 0.20 +    # 20% weight: Hazard complexity
        accel_score * 0.20 +          # 20% weight: Acceleration severity
        temporal_score * 0.15         # 15% weight: Peak hour concentration
    )
    
    return min(sensor_score, 1.0)


def calculate_max_severity(row):
    """
    Calculate maximum severity based on acceleration data.
    
    Args:
        row: DataFrame row with acceleration data
    
    Returns:
        Max severity score (1-10)
    """
    max_accel = max(row.get('max_x', 0), row.get('max_y', 0), row.get('max_z', 0))
    
    # Map acceleration to severity scale
    if max_accel >= 100:
        return 10
    elif max_accel >= 80:
        return 8
    elif max_accel >= 60:
        return 6
    elif max_accel >= 40:
        return 4
    elif max_accel >= 20:
        return 2
    else:
        return 1


def calculate_median_severity(row):
    """
    Calculate median severity based on acceleration data.
    
    Args:
        row: DataFrame row with acceleration data
    
    Returns:
        Median severity score (1-10)
    """
    avg_accel = (row.get('avg_x', 0) + row.get('avg_y', 0) + row.get('avg_z', 0)) / 3
    
    # Map average acceleration to severity scale
    if avg_accel >= 60:
        return 8
    elif avg_accel >= 40:
        return 6
    elif avg_accel >= 20:
        return 4
    elif avg_accel >= 10:
        return 2
    else:
        return 1


# ============================================================================
# MAIN ANALYSIS CLASS
# ============================================================================

class HotspotAnalyzerV2:
    """Main class for hotspot analysis - Updated for new data format with user data"""
    
    def __init__(self, config):
        self.config = config
        self.collision_data = None
        self.sensor_data = None
        self.results = None
        
    def load_data(self):
        """Load and preprocess input data"""
        print("=" * 80)
        print("LOADING DATA")
        print("=" * 80)
        
        # Load collision data
        print(f"\nLoading collision data from: {self.config.COLLISION_DATA_PATH}")
        self.collision_data = pd.read_csv(self.config.COLLISION_DATA_PATH)
        print(f"  Loaded {len(self.collision_data)} collision reports")
        
        # Clean collision data
        self.collision_data = self.collision_data.dropna(subset=['Lat', 'Long'])
        print(f"  After removing missing coordinates: {len(self.collision_data)} reports")
        
        # Filter to Dublin area
        self.collision_data = self.collision_data[
            (self.collision_data['Lat'] >= self.config.DUBLIN_LAT_MIN) &
            (self.collision_data['Lat'] <= self.config.DUBLIN_LAT_MAX) &
            (self.collision_data['Long'] >= self.config.DUBLIN_LNG_MIN) &
            (self.collision_data['Long'] <= self.config.DUBLIN_LNG_MAX)
        ]
        print(f"  After filtering to Dublin area: {len(self.collision_data)} reports")
        
        # Parse dates
        self.collision_data['OccurredAt'] = pd.to_datetime(
            self.collision_data['OccurredAt'], 
            errors='coerce'
        )
        
        # Create severity scores
        severity_mapping = {
            'No injuries': 1,
            'Minor injuries': 3,
            'Serious injuries': 5,
            'Fatality': 10
        }
        
        incident_type_weight = {
            'Hazard': 0.5,
            'Near Miss': 1.0,
            'Collision': 2.0
        }
        
        self.collision_data['severity_score'] = self.collision_data['Outcome'].map(severity_mapping)
        self.collision_data['incident_weight'] = self.collision_data['IncidentType'].map(incident_type_weight)
        self.collision_data['weighted_severity'] = (
            self.collision_data['severity_score'] * self.collision_data['incident_weight']
        )
        
        # Load sensor data with user metrics
        print(f"\nLoading sensor data from: {self.config.SENSOR_DATA_PATH}")
        self.sensor_data = pd.read_csv(self.config.SENSOR_DATA_PATH)
        print(f"  Loaded {len(self.sensor_data)} sensor clusters")
        
        # Calculate derived metrics
        print("\n  Calculating derived metrics from sensor data...")
        self.sensor_data['event_count'] = self.sensor_data['size']
        
        # Calculate sensor scores with actual user data
        self.sensor_data['sensor_concern_score'] = self.sensor_data.apply(
            lambda row: calculate_sensor_score(row, self.config), axis=1
        )
        
        # Calculate severity metrics
        self.sensor_data['median_severity'] = self.sensor_data.apply(
            calculate_median_severity, axis=1
        )
        
        self.sensor_data['max_severity'] = self.sensor_data.apply(
            calculate_max_severity, axis=1
        )
        
        # Add temporal metadata
        self.sensor_data['first_seen'] = pd.to_datetime('2024-01-01')
        self.sensor_data['last_seen'] = pd.to_datetime('2024-12-01')
        
        # Calculate event_type from hazard_type
        self.sensor_data['event_type'] = self.sensor_data['hazard_type'].apply(
            lambda x: 'mixed' if 'mixed' in str(x).lower() else str(x).lower()
        )
        
        # User statistics
        print(f"  Average unique users per cluster: {self.sensor_data['unique_users'].mean():.1f}")
        print(f"  Average repeat user percentage: {self.sensor_data['repeat_user_pct'].mean():.1f}%")
        print(f"  Total unique users across all clusters: {self.sensor_data['unique_users'].sum():.0f}")
        
        print("\n✓ Data loading complete")
        
    def spatial_matching(self):
        """Match collision reports to hotspots based on spatial proximity"""
        print("\n" + "=" * 80)
        print("SPATIAL MATCHING")
        print("=" * 80)
        print(f"\nMatching collision reports within {self.config.MATCHING_RADIUS_METERS}m of each hotspot...")
        
        results = []
        
        for idx, sensor_cluster in self.sensor_data.iterrows():
            if (idx + 1) % 20 == 0:
                print(f"  Processing cluster {idx + 1}/{len(self.sensor_data)}...")
            
            h_lat = sensor_cluster['medoid_lat']
            h_lng = sensor_cluster['medoid_lng']
            
            # Calculate distances to all collision reports
            distances = self.collision_data.apply(
                lambda row: haversine_distance(h_lat, h_lng, row['Lat'], row['Long']),
                axis=1
            )
            
            # Find reports within radius
            nearby_collisions = self.collision_data[distances <= self.config.MATCHING_RADIUS_METERS].copy()
            
            # Calculate statistics
            collision_count = len(nearby_collisions)
            
            if collision_count > 0:
                # Incident type breakdown
                near_miss_count = (nearby_collisions['IncidentType'] == 'Near Miss').sum()
                collision_incident_count = (nearby_collisions['IncidentType'] == 'Collision').sum()
                hazard_count = (nearby_collisions['IncidentType'] == 'Hazard').sum()
                
                # Cause breakdown
                infrastructure_cause = (nearby_collisions['CauseCategory'] == 'Infrastructure').sum()
                driver_car_cause = (nearby_collisions['CauseCategory'] == 'Driver Behaviour (Car)').sum()
                driver_hgv_cause = (nearby_collisions['CauseCategory'] == 'Driver Behaviour (Other Heavy Vehicle)').sum()
                driver_bus_cause = (nearby_collisions['CauseCategory'] == 'Driver Behaviour (Bus)').sum()
                
                # Outcome breakdown
                no_injuries = (nearby_collisions['Outcome'] == 'No injuries').sum()
                minor_injuries = (nearby_collisions['Outcome'] == 'Minor injuries').sum()
                serious_injuries = (nearby_collisions['Outcome'] == 'Serious injuries').sum()
                fatalities = (nearby_collisions['Outcome'] == 'Fatality').sum()
                
                # Severity metrics
                avg_severity = nearby_collisions['weighted_severity'].mean()
                max_severity = nearby_collisions['weighted_severity'].max()
                
                # Get top descriptions
                top_collisions = nearby_collisions.nlargest(
                    self.config.MAX_DESCRIPTIONS_PER_HOTSPOT, 
                    'weighted_severity'
                )
                descriptions = top_collisions['Description'].tolist()
                
                # Extract themes
                themes = extract_themes(nearby_collisions['Description'].tolist())
                theme_summary = generate_summary_text(themes, collision_count)
                
                # Date range
                date_range_start = nearby_collisions['OccurredAt'].min()
                date_range_end = nearby_collisions['OccurredAt'].max()
                
            else:
                near_miss_count = 0
                collision_incident_count = 0
                hazard_count = 0
                infrastructure_cause = 0
                driver_car_cause = 0
                driver_hgv_cause = 0
                driver_bus_cause = 0
                no_injuries = 0
                minor_injuries = 0
                serious_injuries = 0
                fatalities = 0
                avg_severity = 0
                max_severity = 0
                descriptions = []
                themes = {}
                theme_summary = ""
                date_range_start = None
                date_range_end = None
            
            # Compile results
            results.append({
                # Identification
                'cluster_id': sensor_cluster['cluster_id'],
                'street_name': sensor_cluster['street_name'],
                'latitude': h_lat,
                'longitude': h_lng,
                
                # Sensor data - WITH USER METRICS
                'sensor_size': int(sensor_cluster['size']),
                'sensor_unique_users': int(sensor_cluster.get('unique_users', 0)),
                'sensor_events_per_user': float(sensor_cluster.get('events_per_user', 0)),
                'sensor_repeat_users': int(sensor_cluster.get('repeat_users', 0)),
                'sensor_repeat_user_pct': float(sensor_cluster.get('repeat_user_pct', 0)),
                'sensor_braking_events': int(sensor_cluster.get('braking_events', 0)),
                'sensor_swerve_events': int(sensor_cluster.get('swerve_events', 0)),
                'sensor_roughness_events': int(sensor_cluster.get('roughness_events', 0)),
                'sensor_hazard_type': sensor_cluster['hazard_type'],
                'sensor_event_type': sensor_cluster.get('event_type', 'unknown'),
                'sensor_event_count': int(sensor_cluster.get('event_count', 0)),
                'sensor_concern_score': float(sensor_cluster.get('sensor_concern_score', 0)),
                'sensor_median_severity': float(sensor_cluster.get('median_severity', 0)),
                'sensor_max_severity': int(sensor_cluster.get('max_severity', 0)),
                'sensor_avg_acceleration': float((sensor_cluster.get('avg_x', 0) + sensor_cluster.get('avg_y', 0) + sensor_cluster.get('avg_z', 0)) / 3),
                'sensor_max_acceleration': float(max(sensor_cluster.get('max_x', 0), sensor_cluster.get('max_y', 0), sensor_cluster.get('max_z', 0))),
                'sensor_peak_events': int(sensor_cluster.get('peak_events', 0)),
                'sensor_offpeak_events': int(sensor_cluster.get('offpeak_events', 0)),
                'sensor_morning_peak': int(sensor_cluster.get('morning_peak', 0)),
                'sensor_evening_peak': int(sensor_cluster.get('evening_peak', 0)),
                
                # Collision data
                'collision_total_count': int(collision_count),
                'collision_near_miss_count': int(near_miss_count),
                'collision_incident_count': int(collision_incident_count),
                'collision_hazard_count': int(hazard_count),
                
                # Collision data - causes
                'cause_infrastructure': int(infrastructure_cause),
                'cause_driver_car': int(driver_car_cause),
                'cause_driver_hgv': int(driver_hgv_cause),
                'cause_driver_bus': int(driver_bus_cause),
                
                # Collision data - outcomes
                'outcome_no_injuries': int(no_injuries),
                'outcome_minor_injuries': int(minor_injuries),
                'outcome_serious_injuries': int(serious_injuries),
                'outcome_fatalities': int(fatalities),
                
                # Severity metrics
                'collision_avg_severity': float(avg_severity) if collision_count > 0 else 0,
                'collision_max_severity': float(max_severity) if collision_count > 0 else 0,
                
                # Flags
                'has_fatality': bool(fatalities > 0),
                'has_serious_injury': bool(serious_injuries > 0),
                'has_collision_reports': bool(collision_count > 0),
                
                # Descriptions and themes
                'top_descriptions': descriptions,
                'common_themes': themes,
                'theme_summary': theme_summary,
                
                # Temporal
                'collision_date_range_start': date_range_start.strftime('%Y-%m-%d') if pd.notna(date_range_start) else None,
                'collision_date_range_end': date_range_end.strftime('%Y-%m-%d') if pd.notna(date_range_end) else None,
            })
        
        self.results = pd.DataFrame(results)
        
        validated_count = len(self.results[self.results['collision_total_count'] > 0])
        print(f"\n✓ Spatial matching complete")
        print(f"  Hotspots with collision validation: {validated_count}/{len(self.results)} ({validated_count/len(self.results)*100:.1f}%)")
        
    def calculate_composite_scores(self):
        """Calculate composite priority scores with user engagement factors"""
        print("\n" + "=" * 80)
        print("CALCULATING PRIORITY SCORES")
        print("=" * 80)
        
        def calc_score(row):
            # Base sensor score (0-1) - already includes user engagement
            sensor_score = row['sensor_concern_score']
            
            # User engagement bonus (high repeat users = persistent problem)
            repeat_user_bonus = 0
            if row['sensor_repeat_user_pct'] > 50:  # More than 50% repeat users
                repeat_user_bonus = min((row['sensor_repeat_user_pct'] - 50) / 50, 0.2)
            
            enhanced_sensor_score = sensor_score + repeat_user_bonus
            enhanced_sensor_score = min(enhanced_sensor_score, 1.0)
            
            # Collision validation score
            if row['collision_total_count'] > 0:
                # Scale collision count with diminishing returns
                collision_factor = min(row['collision_total_count'] / 10, 1.0)
                
                # Severity multiplier
                severity_multiplier = 1.0
                if row['has_fatality']:
                    severity_multiplier = self.config.MULTIPLIER_FATALITY
                elif row['has_serious_injury']:
                    severity_multiplier = self.config.MULTIPLIER_SERIOUS_INJURY
                elif row['collision_incident_count'] > 0:
                    severity_multiplier = self.config.MULTIPLIER_COLLISION_VS_NEAR_MISS
                
                collision_score = collision_factor * severity_multiplier
            else:
                collision_score = 0
            
            # Volume factor (using size and unique users)
            size_factor = min(row['sensor_size'] / 800, 1.0) * 0.3
            user_factor = min(row['sensor_unique_users'] / 100, 1.0) * 0.2
            volume_factor = size_factor + user_factor
            
            # Composite score
            composite = (
                enhanced_sensor_score * self.config.WEIGHT_SENSOR +
                collision_score * self.config.WEIGHT_COLLISION +
                volume_factor * self.config.WEIGHT_VOLUME
            )
            
            return min(composite, 1.0)
        
        self.results['composite_score'] = self.results.apply(calc_score, axis=1)
        
        # Also calculate sensor-only rank for comparison
        self.results['sensor_only_rank'] = self.results['sensor_concern_score'].rank(
            ascending=False, method='min'
        ).astype(int)
        
        # Calculate composite rank
        self.results['composite_rank'] = self.results['composite_score'].rank(
            ascending=False, method='min'
        ).astype(int)
        
        # Sort by composite score
        self.results = self.results.sort_values('composite_score', ascending=False)
        
        print("\n✓ Scoring complete")
        print(f"\nScore Distribution:")
        print(f"  Critical (≥0.8): {len(self.results[self.results['composite_score'] >= 0.8])}")
        print(f"  High (0.6-0.8): {len(self.results[(self.results['composite_score'] >= 0.6) & (self.results['composite_score'] < 0.8)])}")
        print(f"  Medium (0.4-0.6): {len(self.results[(self.results['composite_score'] >= 0.4) & (self.results['composite_score'] < 0.6)])}")
        print(f"  Low (<0.4): {len(self.results[self.results['composite_score'] < 0.4])}")
        
    def generate_outputs(self):
        """Generate output files"""
        print("\n" + "=" * 80)
        print("GENERATING OUTPUT FILES")
        print("=" * 80)
        
        # Ensure output directory exists
        output_dir = Path(self.config.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get top N hotspots
        top_n = self.results.head(self.config.TOP_N_HOTSPOTS).copy()
        
        # ========================================
        # CSV Output
        # ========================================
        csv_path = output_dir / "top_30_hotspots_v2.csv"
        
        # For CSV, we need to flatten some fields
        csv_data = top_n.copy()
        
        # Convert theme dictionary to string
        csv_data['common_themes'] = csv_data['common_themes'].apply(
            lambda x: json.dumps(x) if x else ""
        )
        
        # Convert descriptions list to string (truncated)
        csv_data['sample_descriptions'] = csv_data['top_descriptions'].apply(
            lambda x: " | ".join([str(d)[:100] + "..." if len(str(d)) > 100 else str(d) for d in x[:3]]) if x else ""
        )
        
        # Select columns for CSV
        csv_columns = [
            'composite_rank', 'street_name', 'composite_score',
            'latitude', 'longitude',
            'sensor_size', 'sensor_unique_users', 'sensor_events_per_user', 
            'sensor_repeat_user_pct', 'sensor_braking_events', 
            'sensor_swerve_events', 'sensor_roughness_events',
            'sensor_hazard_type', 'sensor_concern_score',
            'collision_total_count', 'has_fatality', 'has_serious_injury',
            'theme_summary', 'sample_descriptions'
        ]
        
        csv_data = csv_data[csv_columns]
        csv_data.to_csv(csv_path, index=False)
        print(f"\n✓ CSV file created: {csv_path}")
        
        # ========================================
        # JSON Output
        # ========================================
        json_path = output_dir / "top_30_hotspots_v2.json"
        
        # Convert to JSON-friendly format
        json_data = []
        for idx, row in top_n.iterrows():
            hotspot_dict = {
                'rank': int(row['composite_rank']),
                'identification': {
                    'cluster_id': row['cluster_id'],
                    'street_name': row['street_name'],
                    'latitude': float(row['latitude']),
                    'longitude': float(row['longitude'])
                },
                'scores': {
                    'composite_score': float(row['composite_score']),
                    'sensor_concern_score': float(row['sensor_concern_score']),
                    'composite_rank': int(row['composite_rank']),
                    'sensor_only_rank': int(row['sensor_only_rank'])
                },
                'sensor_data': {
                    'size': int(row['sensor_size']),
                    'unique_users': int(row['sensor_unique_users']),
                    'events_per_user': float(row['sensor_events_per_user']),
                    'repeat_users': int(row['sensor_repeat_users']),
                    'repeat_user_percentage': float(row['sensor_repeat_user_pct']),
                    'hazard_type': row['sensor_hazard_type'],
                    'event_type': row['sensor_event_type'],
                    'braking_events': int(row['sensor_braking_events']),
                    'swerve_events': int(row['sensor_swerve_events']),
                    'roughness_events': int(row['sensor_roughness_events']),
                    'median_severity': float(row['sensor_median_severity']),
                    'max_severity': int(row['sensor_max_severity']),
                    'avg_acceleration': float(row['sensor_avg_acceleration']),
                    'max_acceleration': float(row['sensor_max_acceleration']),
                    'peak_events': int(row['sensor_peak_events']),
                    'offpeak_events': int(row['sensor_offpeak_events']),
                    'device_count': int(row['sensor_unique_users'])  # Use unique_users as device count
                },
                'collision_reports': {
                    'total_count': int(row['collision_total_count']),
                    'breakdown': {
                        'near_miss': int(row['collision_near_miss_count']),
                        'collision': int(row['collision_incident_count']),
                        'hazard': int(row['collision_hazard_count'])
                    },
                    'causes': {
                        'infrastructure': int(row['cause_infrastructure']),
                        'driver_car': int(row['cause_driver_car']),
                        'driver_hgv': int(row['cause_driver_hgv']),
                        'driver_bus': int(row['cause_driver_bus'])
                    },
                    'outcomes': {
                        'no_injuries': int(row['outcome_no_injuries']),
                        'minor_injuries': int(row['outcome_minor_injuries']),
                        'serious_injuries': int(row['outcome_serious_injuries']),
                        'fatalities': int(row['outcome_fatalities'])
                    },
                    'severity': {
                        'average': float(row['collision_avg_severity']),
                        'maximum': float(row['collision_max_severity'])
                    },
                    'date_range': {
                        'start': row['collision_date_range_start'],
                        'end': row['collision_date_range_end']
                    }
                },
                'flags': {
                    'has_fatality': bool(row['has_fatality']),
                    'has_serious_injury': bool(row['has_serious_injury']),
                    'has_collision_reports': bool(row['has_collision_reports']),
                    'is_validated': bool(row['collision_total_count'] > 0)
                },
                'narrative': {
                    'theme_summary': row['theme_summary'],
                    'common_themes': row['common_themes'],
                    'sample_descriptions': row['top_descriptions'][:self.config.MAX_DESCRIPTIONS_PER_HOTSPOT]
                }
            }
            json_data.append(hotspot_dict)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ JSON file created: {json_path}")
        
        # ========================================
        # Summary Text File
        # ========================================
        summary_path = output_dir / "hotspot_analysis_summary_v2.txt"
        
        with open(summary_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("HOTSPOT ANALYSIS SUMMARY (WITH USER METRICS)\n")
            f.write("=" * 80 + "\n")
            f.write(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Matching Radius: {self.config.MATCHING_RADIUS_METERS}m\n")
            f.write(f"Data Source: {self.config.SENSOR_DATA_PATH}\n")
            f.write(f"\n")
            
            f.write("DATASET OVERVIEW\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total sensor clusters: {len(self.results)}\n")
            f.write(f"Clusters with collision validation: {len(self.results[self.results['collision_total_count'] > 0])}\n")
            f.write(f"Validation rate: {len(self.results[self.results['collision_total_count'] > 0]) / len(self.results) * 100:.1f}%\n")
            f.write(f"Total collision reports matched: {self.results['collision_total_count'].sum():.0f}\n")
            f.write(f"Total sensor events: {self.results['sensor_size'].sum():.0f}\n")
            f.write(f"Total unique users: {self.results['sensor_unique_users'].sum():.0f}\n")
            f.write(f"\n")
            
            f.write("USER ENGAGEMENT METRICS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Average users per cluster: {self.results['sensor_unique_users'].mean():.1f}\n")
            f.write(f"Average events per user: {self.results['sensor_events_per_user'].mean():.1f}\n")
            f.write(f"Average repeat user percentage: {self.results['sensor_repeat_user_pct'].mean():.1f}%\n")
            f.write(f"Clusters with >50% repeat users: {(self.results['sensor_repeat_user_pct'] > 50).sum()}\n")
            f.write(f"\n")
            
            f.write(f"TOP {self.config.TOP_N_HOTSPOTS} HOTSPOTS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Hotspots with fatalities: {top_n['has_fatality'].sum()}\n")
            f.write(f"Hotspots with serious injuries: {top_n['has_serious_injury'].sum()}\n")
            f.write(f"Hotspots with any collision reports: {top_n['has_collision_reports'].sum()}\n")
            f.write(f"Total collision reports in top hotspots: {top_n['collision_total_count'].sum():.0f}\n")
            f.write(f"Total unique users in top hotspots: {top_n['sensor_unique_users'].sum():.0f}\n")
            f.write(f"\n")
            
            f.write("TOP 10 HOTSPOTS\n")
            f.write("-" * 80 + "\n")
            for i, (idx, row) in enumerate(top_n.head(10).iterrows(), 1):
                f.write(f"\n#{i}: {row['street_name']}\n")
                f.write(f"    Composite Score: {row['composite_score']:.3f}\n")
                f.write(f"    Sensor: {int(row['sensor_size'])} events from {int(row['sensor_unique_users'])} users")
                if row['sensor_repeat_user_pct'] > 50:
                    f.write(f" ({row['sensor_repeat_user_pct']:.0f}% repeat users ⚠)")
                f.write("\n")
                f.write(f"    Citizen: {int(row['collision_total_count'])} reports")
                if row['has_fatality']:
                    f.write(" ⚠️ FATALITY")
                elif row['has_serious_injury']:
                    f.write(" ⚠️ SERIOUS INJURY")
                f.write("\n")
                if row['theme_summary']:
                    f.write(f"    Themes: {row['theme_summary']}\n")
            
            # User engagement in top hotspots
            f.write("\nUSER ENGAGEMENT IN TOP 10\n")
            f.write("-" * 80 + "\n")
            top_10 = top_n.head(10)
            f.write(f"  Average users: {top_10['sensor_unique_users'].mean():.1f}\n")
            f.write(f"  Average repeat user %: {top_10['sensor_repeat_user_pct'].mean():.1f}%\n")
            f.write(f"  Average events per user: {top_10['sensor_events_per_user'].mean():.1f}\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF SUMMARY\n")
            f.write("=" * 80 + "\n")
        
        print(f"✓ Summary file created: {summary_path}")
        
        print(f"\n✅ All output files created successfully!")
        print(f"\nOutput location: {output_dir}")
        print(f"  - top_30_hotspots_v2.csv (with user metrics)")
        print(f"  - top_30_hotspots_v2.json (dashboard integration with user data)")
        print(f"  - hotspot_analysis_summary_v2.txt (enhanced user-focused summary)")
        
    def run(self):
        """Run the complete analysis pipeline"""
        print("\n")
        print("█" * 80)
        print("█" + " " * 78 + "█")
        print("█" + "  HOTSPOT ANALYSIS V2.1 - WITH USER METRICS".center(78) + "█")
        print("█" + " " * 78 + "█")
        print("█" * 80)
        print("\n")
        
        self.load_data()
        self.spatial_matching()
        self.calculate_composite_scores()
        self.generate_outputs()
        
        print("\n" + "█" * 80)
        print("█" + " " * 78 + "█")
        print("█" + "  ANALYSIS COMPLETE ✓".center(78) + "█")
        print("█" + " " * 78 + "█")
        print("█" * 80)
        print("\n")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    config = Config()
    analyzer = HotspotAnalyzerV2(config)
    analyzer.run()