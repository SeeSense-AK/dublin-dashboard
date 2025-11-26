#!/usr/bin/env python3
"""
Hotspot Analysis Script - Sensor Data + Collision Tracker Integration
======================================================================

This script combines sensor hotspot data with citizen collision reports to create
a validated priority ranking of cycling safety hotspots.

Author: Spinovate Analysis Team
Date: November 2025
Version: 1.0

Usage:
    python hotspot_analyzer.py

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
    HOTSPOTS_MASTER_PATH = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/data/processed/tab1_hotspots/hotspots_master_with_streets.csv"
    
    # Output directory
    OUTPUT_DIR = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/data/processed/tab1_hotspots"
    
    # Analysis parameters
    MATCHING_RADIUS_METERS = 100  # Radius for matching collision reports to hotspots
    TOP_N_HOTSPOTS = 30  # Number of top hotspots to output
    MAX_DESCRIPTIONS_PER_HOTSPOT = 5  # Number of collision descriptions to include
    
    # Dublin bounding box (to filter collision reports)
    DUBLIN_LAT_MIN = 53.2
    DUBLIN_LAT_MAX = 53.45
    DUBLIN_LNG_MIN = -6.4
    DUBLIN_LNG_MAX = -6.1
    
    # Scoring weights
    WEIGHT_SENSOR = 0.50  # Weight for sensor concern score
    WEIGHT_COLLISION = 0.35  # Weight for collision validation
    WEIGHT_VOLUME = 0.15  # Weight for volume factor
    
    # Severity multipliers
    MULTIPLIER_FATALITY = 2.0
    MULTIPLIER_SERIOUS_INJURY = 1.5
    MULTIPLIER_COLLISION_VS_NEAR_MISS = 1.3


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


# ============================================================================
# MAIN ANALYSIS CLASS
# ============================================================================

class HotspotAnalyzer:
    """Main class for hotspot analysis"""
    
    def __init__(self, config):
        self.config = config
        self.collision_data = None
        self.hotspots_data = None
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
        
        # Load hotspots data
        print(f"\nLoading hotspots data from: {self.config.HOTSPOTS_MASTER_PATH}")
        self.hotspots_data = pd.read_csv(self.config.HOTSPOTS_MASTER_PATH)
        print(f"  Loaded {len(self.hotspots_data)} sensor hotspots")
        
        # Parse dates
        self.hotspots_data['first_seen'] = pd.to_datetime(
            self.hotspots_data['first_seen']
        )
        self.hotspots_data['last_seen'] = pd.to_datetime(
            self.hotspots_data['last_seen']
        )
        
        print("\n✓ Data loading complete")
        
    def spatial_matching(self):
        """Match collision reports to hotspots based on spatial proximity"""
        print("\n" + "=" * 80)
        print("SPATIAL MATCHING")
        print("=" * 80)
        print(f"\nMatching collision reports within {self.config.MATCHING_RADIUS_METERS}m of each hotspot...")
        
        results = []
        
        for idx, hotspot in self.hotspots_data.iterrows():
            if (idx + 1) % 50 == 0:
                print(f"  Processing hotspot {idx + 1}/{len(self.hotspots_data)}...")
            
            h_lat = hotspot['medoid_lat']
            h_lng = hotspot['medoid_lng']
            
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
                'cluster_id': hotspot['cluster_id'],
                'street_name': hotspot['street_name'],
                'latitude': h_lat,
                'longitude': h_lng,
                
                # Sensor data
                'sensor_event_type': hotspot['event_type'],
                'sensor_event_count': int(hotspot['event_count']),
                'sensor_concern_score': float(hotspot['concern_score']),
                'sensor_median_severity': float(hotspot['median_severity']),
                'sensor_max_severity': int(hotspot['max_severity']),
                'sensor_device_count': int(hotspot['device_count']),
                'sensor_first_seen': hotspot['first_seen'].strftime('%Y-%m-%d') if pd.notna(hotspot['first_seen']) else None,
                'sensor_last_seen': hotspot['last_seen'].strftime('%Y-%m-%d') if pd.notna(hotspot['last_seen']) else None,
                
                # Collision data - counts
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
        """Calculate composite priority scores"""
        print("\n" + "=" * 80)
        print("CALCULATING PRIORITY SCORES")
        print("=" * 80)
        
        def calc_score(row):
            # Base sensor score (0-1)
            sensor_score = row['sensor_concern_score']
            
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
            
            # Volume factor
            volume_factor = min(row['sensor_event_count'] / 400, 1.0) * 0.5
            
            # Composite score
            composite = (
                sensor_score * self.config.WEIGHT_SENSOR +
                collision_score * self.config.WEIGHT_COLLISION +
                volume_factor * self.config.WEIGHT_VOLUME
            )
            
            return composite
        
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
        csv_path = output_dir / "top_30_hotspots.csv"
        
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
        csv_data = csv_data.drop(columns=['top_descriptions'])
        
        csv_data.to_csv(csv_path, index=False)
        print(f"\n✓ CSV file created: {csv_path}")
        
        # ========================================
        # JSON Output
        # ========================================
        json_path = output_dir / "top_30_hotspots.json"
        
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
                    'event_type': row['sensor_event_type'],
                    'event_count': int(row['sensor_event_count']),
                    'median_severity': float(row['sensor_median_severity']),
                    'max_severity': int(row['sensor_max_severity']),
                    'device_count': int(row['sensor_device_count']),
                    'first_seen': row['sensor_first_seen'],
                    'last_seen': row['sensor_last_seen']
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
        summary_path = output_dir / "hotspot_analysis_summary.txt"
        
        with open(summary_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("HOTSPOT ANALYSIS SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Matching Radius: {self.config.MATCHING_RADIUS_METERS}m\n")
            f.write(f"\n")
            
            f.write("DATASET OVERVIEW\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total sensor hotspots: {len(self.results)}\n")
            f.write(f"Hotspots with collision validation: {len(self.results[self.results['collision_total_count'] > 0])}\n")
            f.write(f"Validation rate: {len(self.results[self.results['collision_total_count'] > 0]) / len(self.results) * 100:.1f}%\n")
            f.write(f"Total collision reports matched: {self.results['collision_total_count'].sum():.0f}\n")
            f.write(f"\n")
            
            f.write(f"TOP {self.config.TOP_N_HOTSPOTS} HOTSPOTS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Hotspots with fatalities: {top_n['has_fatality'].sum()}\n")
            f.write(f"Hotspots with serious injuries: {top_n['has_serious_injury'].sum()}\n")
            f.write(f"Total collision reports: {top_n['collision_total_count'].sum():.0f}\n")
            f.write(f"Total sensor events: {top_n['sensor_event_count'].sum():.0f}\n")
            f.write(f"\n")
            
            f.write("TOP 10 HOTSPOTS\n")
            f.write("-" * 80 + "\n")
            for i, (idx, row) in enumerate(top_n.head(10).iterrows(), 1):
                f.write(f"\n#{i}: {row['street_name']}\n")
                f.write(f"    Composite Score: {row['composite_score']:.3f}\n")
                f.write(f"    Sensor: {int(row['sensor_event_count'])} {row['sensor_event_type']} events\n")
                f.write(f"    Citizen: {int(row['collision_total_count'])} reports")
                if row['has_fatality']:
                    f.write(" ⚠️ FATALITY")
                elif row['has_serious_injury']:
                    f.write(" ⚠️ SERIOUS INJURY")
                f.write("\n")
                if row['theme_summary']:
                    f.write(f"    Themes: {row['theme_summary']}\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF SUMMARY\n")
            f.write("=" * 80 + "\n")
        
        print(f"✓ Summary file created: {summary_path}")
        
        print(f"\n✅ All output files created successfully!")
        print(f"\nOutput location: {output_dir}")
        print(f"  - top_30_hotspots.csv (spreadsheet format)")
        print(f"  - top_30_hotspots.json (dashboard integration)")
        print(f"  - hotspot_analysis_summary.txt (human-readable summary)")
        
    def run(self):
        """Run the complete analysis pipeline"""
        print("\n")
        print("█" * 80)
        print("█" + " " * 78 + "█")
        print("█" + "  HOTSPOT ANALYSIS - SENSOR + COLLISION TRACKER INTEGRATION".center(78) + "█")
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
    analyzer = HotspotAnalyzer(config)
    analyzer.run()
