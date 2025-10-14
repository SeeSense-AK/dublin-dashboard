"""
Hybrid Hotspot Detection System - REWRITTEN FOR DUCKDB
Implements 55-45 split strategy:
- 55% Sensor-Primary hotspots
- 45% Perception-Primary hotspots (P1, P2, P3)
"""
import pandas as pd
import numpy as np
import math
import re
from sklearn.cluster import DBSCAN
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import nearest_points
import streamlit as st
from typing import Dict, List, Tuple

from src.duckdb_database import get_duckdb_database
from utils.geo_utils import haversine_distance
from src.sentiment_analyzer import get_groq_client


class HybridHotspotDetector:
    """
    Hybrid hotspot detector - DuckDB version
    """
    
    def __init__(self):
        self.db = get_duckdb_database()
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def parse_event_severity(self, event_details: str) -> int:
        """Parse event_details field to extract severity"""
        if not event_details or event_details == "" or event_details == "0":
            return None
        
        match = re.search(r'\((\d+)\)', str(event_details))
        if match:
            return int(match.group(1))
        
        return None
    
    def calculate_rank_score(self, avg_severity: float, event_count: int) -> float:
        """Calculate rank score: avg_severity + log10(event_count)"""
        if event_count == 0:
            return avg_severity
        
        log_bonus = math.log10(event_count)
        rank_score = avg_severity + log_bonus
        
        return round(rank_score, 2)
    
    def get_color_from_score(self, rank_score: float, is_perception_only: bool = False) -> str:
        """Get color based on rank score"""
        if is_perception_only:
            return 'blue'
        
        if rank_score >= 7:
            return 'red'
        elif rank_score >= 4:
            return 'orange'
        else:
            return 'green'
    
    # ========================================================================
    # PART 1: SENSOR-PRIMARY (55%)
    # ========================================================================
    
    def detect_sensor_primary_hotspots(self, 
                                       start_date: str,
                                       end_date: str,
                                       top_n: int) -> pd.DataFrame:
        """Detect sensor-primary hotspots using DBSCAN clustering"""
        
        try:
            # Get raw sensor data from DuckDB
            print(f"📊 Fetching sensor data from {start_date} to {end_date}...")
            events_df = self.db.get_sensor_data_for_clustering(
                start_date=start_date,
                end_date=end_date,
                min_severity=0  # Get all events
            )
            
            if events_df.empty:
                print("⚠️ No sensor events found")
                return pd.DataFrame()
            
            print(f"✅ Retrieved {len(events_df):,} sensor events")
            
            # Parse severity from event_details if needed
            if 'event_details' in events_df.columns:
                events_df['parsed_severity'] = events_df['event_details'].apply(
                    self.parse_event_severity
                )
                
                # Use parsed severity if max_severity is missing or 0
                if 'max_severity' not in events_df.columns or events_df['max_severity'].isna().all():
                    events_df['max_severity'] = events_df['parsed_severity']
                else:
                    # Fill nulls with parsed severity
                    mask = (events_df['max_severity'].isna()) | (events_df['max_severity'] == 0)
                    events_df.loc[mask, 'max_severity'] = events_df.loc[mask, 'parsed_severity']
            
            # Filter out events without valid severity
            events_df = events_df[events_df['max_severity'].notna()].copy()
            events_df = events_df[events_df['max_severity'] > 0].copy()
            
            if events_df.empty:
                print("⚠️ No events with valid severity found")
                return pd.DataFrame()
            
            print(f"✅ {len(events_df):,} events with valid severity")
            
            # CLUSTERING: Geographic clustering with DBSCAN
            coords = events_df[['lat', 'lng']].values
            eps_degrees = 0.0005  # ~50m radius
            
            print(f"🔍 Running DBSCAN clustering (eps={eps_degrees}, min_samples=3)...")
            clustering = DBSCAN(eps=eps_degrees, min_samples=3, metric='euclidean')
            events_df['cluster_id'] = clustering.fit_predict(coords)
            
            # Filter out noise (cluster_id = -1)
            clustered = events_df[events_df['cluster_id'] >= 0].copy()
            
            if clustered.empty:
                print("⚠️ No clusters formed")
                return pd.DataFrame()
            
            n_clusters = clustered['cluster_id'].nunique()
            print(f"✅ Found {n_clusters} clusters")
            
            # Aggregate clusters into hotspots
            hotspots = self._aggregate_sensor_clusters(clustered, start_date, end_date)
            
            if hotspots.empty:
                return pd.DataFrame()
            
            # Calculate rank scores
            hotspots['rank_score'] = hotspots.apply(
                lambda row: self.calculate_rank_score(row['avg_severity'], row['event_count']),
                axis=1
            )
            
            # Take top N
            hotspots = hotspots.nlargest(min(top_n, len(hotspots)), 'rank_score').reset_index(drop=True)
            
            # Add metadata
            hotspots['source'] = 'sensor_primary'
            hotspots['precedence'] = 'sensor'
            hotspots['perception_count'] = 0
            hotspots['hotspot_id'] = ['S' + str(i+1) for i in range(len(hotspots))]
            hotspots['color'] = hotspots['rank_score'].apply(
                lambda x: self.get_color_from_score(x, False)
            )
            
            print(f"✅ Created {len(hotspots)} sensor-primary hotspots")
            
            return hotspots
            
        except Exception as e:
            print(f"❌ Error detecting sensor hotspots: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def _aggregate_sensor_clusters(self, clustered_events: pd.DataFrame,
                                   start_date: str, end_date: str) -> pd.DataFrame:
        """Aggregate sensor events by cluster using medoid approach"""
        
        hotspots = []
        
        for cluster_id in clustered_events['cluster_id'].unique():
            cluster_data = clustered_events[clustered_events['cluster_id'] == cluster_id].copy()
            
            # Find medoid (most central point)
            center_lat = cluster_data['lat'].mean()
            center_lng = cluster_data['lng'].mean()
            
            cluster_data['dist_to_center'] = cluster_data.apply(
                lambda row: haversine_distance(center_lat, center_lng, row['lat'], row['lng']),
                axis=1
            )
            
            medoid_event = cluster_data.loc[cluster_data['dist_to_center'].idxmin()]
            
            hotspot_lat = medoid_event['lat']
            hotspot_lng = medoid_event['lng']
            
            # Event type distribution
            event_distribution = {}
            if 'primary_event_type' in cluster_data.columns:
                event_types = cluster_data['primary_event_type'].value_counts()
                if not event_types.empty:
                    event_distribution = (event_types / len(cluster_data) * 100).to_dict()
            
            # Severity metrics
            avg_severity = cluster_data['max_severity'].mean()
            max_severity = cluster_data['max_severity'].max()
            
            hotspot = {
                'cluster_id': int(cluster_id),
                'center_lat': hotspot_lat,
                'center_lng': hotspot_lng,
                'event_count': len(cluster_data),
                'unique_devices': cluster_data['device_id'].nunique() if 'device_id' in cluster_data.columns else 0,
                'avg_severity': avg_severity,
                'max_severity': max_severity,
                'event_distribution': event_distribution,
                'first_event': cluster_data['timestamp'].min() if 'timestamp' in cluster_data.columns else None,
                'last_event': cluster_data['timestamp'].max() if 'timestamp' in cluster_data.columns else None,
                'date_range': f"{start_date} to {end_date}",
                'radius_m': cluster_data['dist_to_center'].max(),
                # Corridor fields (None for sensor hotspots)
                'start_lat': None,
                'start_lng': None,
                'end_lat': None,
                'end_lng': None,
                'corridor_length_m': None,
                'corridor_points': None,
                'is_corridor': False
            }
            
            hotspots.append(hotspot)
        
        return pd.DataFrame(hotspots)
    
    # ========================================================================
    # PART 2: PERCEPTION-PRIMARY (45%)
    # ========================================================================
    
    def detect_perception_primary_hotspots(self,
                                          infra_df: pd.DataFrame,
                                          ride_df: pd.DataFrame,
                                          start_date: str,
                                          end_date: str,
                                          quota: int) -> pd.DataFrame:
        """Detect perception-primary hotspots with 3 precedence levels"""
        
        all_hotspots = []
        remaining_quota = quota
        
        # Precedence 1: Perception + Strong Sensor
        if remaining_quota > 0:
            print(f"🔍 P1: Detecting perception + sensor hotspots...")
            p1_hotspots = self.detect_p1_perception_sensor(
                infra_df, ride_df, start_date, end_date
            )
            
            if not p1_hotspots.empty:
                take_count = min(len(p1_hotspots), remaining_quota)
                all_hotspots.append(p1_hotspots.head(take_count))
                remaining_quota -= take_count
                print(f"✅ P1: Found {take_count} hotspots")
        
        # Precedence 2: Corridors with Sensor
        if remaining_quota > 0:
            print(f"🔍 P2: Detecting corridor + sensor hotspots...")
            p2_corridors = self.detect_p2_corridors_sensor(
                infra_df, ride_df, start_date, end_date
            )
            
            if not p2_corridors.empty:
                take_count = min(len(p2_corridors), remaining_quota)
                all_hotspots.append(p2_corridors.head(take_count))
                remaining_quota -= take_count
                print(f"✅ P2: Found {take_count} corridor hotspots")
        
        # Precedence 3: Standalone Perception
        if remaining_quota > 0:
            print(f"🔍 P3: Detecting standalone perception hotspots...")
            p3_standalone = self.detect_p3_standalone_perception(infra_df, ride_df)
            
            if not p3_standalone.empty:
                take_count = min(len(p3_standalone), remaining_quota)
                all_hotspots.append(p3_standalone.head(take_count))
                print(f"✅ P3: Found {take_count} standalone hotspots")
        
        if not all_hotspots:
            return pd.DataFrame()
        
        result = pd.concat(all_hotspots, ignore_index=True)
        return result
    
    # ========================================================================
    # PRECEDENCE 1: Perception + Strong Sensor
    # ========================================================================
    
    def detect_p1_perception_sensor(self,
                                    infra_df: pd.DataFrame,
                                    ride_df: pd.DataFrame,
                                    start_date: str,
                                    end_date: str) -> pd.DataFrame:
        """P1: Perception reports with strong sensor validation"""
        
        combined_reports = self._combine_perception_reports(infra_df, ride_df)
        
        if combined_reports.empty:
            return pd.DataFrame()
        
        # Cluster perception reports (30m radius)
        eps_degrees = 0.00027  # ~30m
        coords = combined_reports[['lat', 'lng']].values
        
        clustering = DBSCAN(eps=eps_degrees, min_samples=1, metric='euclidean')
        combined_reports['cluster_id'] = clustering.fit_predict(coords)
        
        hotspots = []
        
        for cluster_id in combined_reports['cluster_id'].unique():
            if cluster_id == -1:
                continue
            
            cluster_points = combined_reports[combined_reports['cluster_id'] == cluster_id]
            
            center_lat = cluster_points['lat'].mean()
            center_lng = cluster_points['lng'].mean()
            
            # Find sensor data within 30m using DuckDB
            sensor_data = self.db.find_sensor_data_in_radius(
                center_lat=center_lat,
                center_lng=center_lng,
                radius_m=30,
                min_severity=2,
                start_date=start_date,
                end_date=end_date
            )
            
            if not sensor_data['has_data']:
                continue  # Skip if no sensor validation
            
            hotspot = {
                'cluster_id': f'P1_{cluster_id}',
                'center_lat': center_lat,
                'center_lng': center_lng,
                'perception_count': len(cluster_points),
                'event_count': sensor_data['event_count'],
                'avg_severity': sensor_data['avg_severity'],
                'max_severity': sensor_data['max_severity'],
                'unique_devices': sensor_data.get('unique_devices', 0),
                'perception_reports': cluster_points.to_dict('records'),
                'source': 'perception_sensor',
                'precedence': 'P1',
                'is_corridor': False,
                'start_lat': None,
                'start_lng': None,
                'end_lat': None,
                'end_lng': None,
                'corridor_length_m': None,
                'corridor_points': None,
                'event_distribution': {},
                'date_range': f"{start_date} to {end_date}"
            }
            
            hotspot['rank_score'] = self.calculate_rank_score(
                sensor_data['avg_severity'],
                sensor_data['event_count']
            )
            
            hotspot['color'] = self.get_color_from_score(hotspot['rank_score'], False)
            
            hotspots.append(hotspot)
        
        if not hotspots:
            return pd.DataFrame()
        
        result = pd.DataFrame(hotspots)
        result = result.sort_values('rank_score', ascending=False).reset_index(drop=True)
        result['hotspot_id'] = ['P1_' + str(i+1) for i in range(len(result))]
        
        return result
    
    # ========================================================================
    # PRECEDENCE 2: Corridors + Sensor
    # ========================================================================
    
    def detect_p2_corridors_sensor(self,
                                   infra_df: pd.DataFrame,
                                   ride_df: pd.DataFrame,
                                   start_date: str,
                                   end_date: str) -> pd.DataFrame:
        """P2: Corridors with sensor validation"""
        
        combined_reports = self._combine_perception_reports(infra_df, ride_df)
        
        if combined_reports.empty:
            return pd.DataFrame()
        
        hotspots = []
        
        # Find corridors for each user
        for userid in combined_reports['userid'].unique():
            user_reports = combined_reports[combined_reports['userid'] == userid].copy()
            
            if len(user_reports) < 3:
                continue
            
            # Sort by time
            if 'datetime' in user_reports.columns:
                user_reports = user_reports.sort_values('datetime')
            
            # Check consecutive distance
            coords_list = user_reports[['lat', 'lng']].values.tolist()
            
            is_corridor = True
            for i in range(len(coords_list) - 1):
                dist = haversine_distance(
                    coords_list[i][0], coords_list[i][1],
                    coords_list[i+1][0], coords_list[i+1][1]
                )
                if dist > 150:  # More than 150m apart
                    is_corridor = False
                    break
            
            if not is_corridor:
                continue
            
            # Calculate corridor length and create polygon
            total_length = 0
            for i in range(len(coords_list) - 1):
                total_length += haversine_distance(
                    coords_list[i][0], coords_list[i][1],
                    coords_list[i+1][0], coords_list[i+1][1]
                )
            
            # Create bounding box around corridor (20m buffer)
            corridor_line = LineString([(c[1], c[0]) for c in coords_list])  # lng, lat for shapely
            corridor_polygon = corridor_line.buffer(0.00018)  # ~20m buffer
            
            # Get bounding box coordinates for polygon query
            bounds = corridor_polygon.bounds  # (minx, miny, maxx, maxy)
            polygon_coords = [
                (bounds[1], bounds[0]),  # SW
                (bounds[3], bounds[0]),  # NW
                (bounds[3], bounds[2]),  # NE
                (bounds[1], bounds[2])   # SE
            ]
            
            # Find sensor data in polygon using DuckDB
            sensor_data = self.db.find_sensor_data_in_polygon(
                polygon_coords=polygon_coords,
                start_date=start_date,
                end_date=end_date,
                min_severity=0
            )
            
            if not sensor_data['has_data']:
                continue  # Must have sensor validation for P2
            
            # Get start and end points
            start_point = coords_list[0]
            end_point = coords_list[-1]
            center_lat = (start_point[0] + end_point[0]) / 2
            center_lng = (start_point[1] + end_point[1]) / 2
            
            hotspot = {
                'cluster_id': f'P2_corridor_{userid}',
                'center_lat': center_lat,
                'center_lng': center_lng,
                'start_lat': start_point[0],
                'start_lng': start_point[1],
                'end_lat': end_point[0],
                'end_lng': end_point[1],
                'corridor_length_m': total_length,
                'corridor_points': coords_list,  # List of [lat, lng]
                'perception_count': len(user_reports),
                'primary_user': userid,
                'event_count': sensor_data['event_count'],
                'avg_severity': sensor_data['avg_severity'],
                'max_severity': sensor_data['max_severity'],
                'unique_devices': sensor_data.get('unique_devices', 0),
                'perception_reports': user_reports.to_dict('records'),
                'source': 'corridor_sensor',
                'precedence': 'P2',
                'is_corridor': True,
                'event_distribution': {},
                'date_range': f"{start_date} to {end_date}"
            }
            
            hotspot['rank_score'] = self.calculate_rank_score(
                sensor_data['avg_severity'],
                sensor_data['event_count']
            )
            
            hotspot['color'] = self.get_color_from_score(hotspot['rank_score'], False)
            
            hotspots.append(hotspot)
        
        if not hotspots:
            return pd.DataFrame()
        
        result = pd.DataFrame(hotspots)
        result = result.sort_values('rank_score', ascending=False).reset_index(drop=True)
        result['hotspot_id'] = ['P2_' + str(i+1) for i in range(len(result))]
        
        return result
    
    # ========================================================================
    # PRECEDENCE 3: Standalone Perception (No Sensor)
    # ========================================================================
    
    def detect_p3_standalone_perception(self,
                                       infra_df: pd.DataFrame,
                                       ride_df: pd.DataFrame) -> pd.DataFrame:
        """P3: Standalone perception reports without sensor validation"""
        
        combined_reports = self._combine_perception_reports(infra_df, ride_df)
        
        if combined_reports.empty:
            return pd.DataFrame()
        
        # Cluster: 3+ reports from different users
        eps_degrees = 0.00027  # ~30m
        coords = combined_reports[['lat', 'lng']].values
        
        clustering = DBSCAN(eps=eps_degrees, min_samples=3, metric='euclidean')
        combined_reports['cluster_id'] = clustering.fit_predict(coords)
        
        hotspots = []
        
        for cluster_id in combined_reports['cluster_id'].unique():
            if cluster_id == -1:
                continue
            
            cluster_points = combined_reports[combined_reports['cluster_id'] == cluster_id]
            
            # Must have 3+ different users
            unique_users = cluster_points['userid'].nunique()
            if unique_users < 3:
                continue
            
            center_lat = cluster_points['lat'].mean()
            center_lng = cluster_points['lng'].mean()
            
            hotspot = {
                'cluster_id': f'P3_{cluster_id}',
                'center_lat': center_lat,
                'center_lng': center_lng,
                'perception_count': len(cluster_points),
                'unique_users': unique_users,
                'event_count': 0,
                'avg_severity': None,
                'max_severity': None,
                'unique_devices': 0,
                'perception_reports': cluster_points.to_dict('records'),
                'source': 'perception_only',
                'precedence': 'P3',
                'is_corridor': False,
                'start_lat': None,
                'start_lng': None,
                'end_lat': None,
                'end_lng': None,
                'corridor_length_m': None,
                'corridor_points': None,
                'event_distribution': {},
                'rank_score': None,
                'color': 'blue',
                'date_range': None
            }
            
            hotspots.append(hotspot)
        
        if not hotspots:
            return pd.DataFrame()
        
        result = pd.DataFrame(hotspots)
        result = result.sort_values('perception_count', ascending=False).reset_index(drop=True)
        result['hotspot_id'] = ['P3_' + str(i+1) for i in range(len(result))]
        
        return result
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _combine_perception_reports(self, infra_df: pd.DataFrame, 
                                    ride_df: pd.DataFrame) -> pd.DataFrame:
        """Combine infrastructure and ride reports into single dataframe"""
        
        combined = []
        
        # Process infrastructure reports
        if not infra_df.empty and 'lat' in infra_df.columns and 'lng' in infra_df.columns:
            infra_subset = infra_df[['lat', 'lng', 'userid']].copy()
            if 'datetime' in infra_df.columns:
                infra_subset['datetime'] = infra_df['datetime']
            if 'infrastructuretype' in infra_df.columns:
                infra_subset['report_type'] = infra_df['infrastructuretype']
            else:
                infra_subset['report_type'] = 'infrastructure'
            combined.append(infra_subset)
        
        # Process ride reports
        if not ride_df.empty and 'lat' in ride_df.columns and 'lng' in ride_df.columns:
            ride_subset = ride_df[['lat', 'lng', 'userid']].copy()
            if 'datetime' in ride_df.columns:
                ride_subset['datetime'] = ride_df['datetime']
            if 'incidenttype' in ride_df.columns:
                ride_subset['report_type'] = ride_df['incidenttype']
            else:
                ride_subset['report_type'] = 'incident'
            combined.append(ride_subset)
        
        if not combined:
            return pd.DataFrame()
        
        result = pd.concat(combined, ignore_index=True)
        result = result.dropna(subset=['lat', 'lng', 'userid'])
        
        return result


# ========================================================================
# MAIN DETECTION FUNCTION
# ========================================================================

def detect_hybrid_hotspots(start_date: str,
                          end_date: str,
                          infra_df: pd.DataFrame,
                          ride_df: pd.DataFrame,
                          total_hotspots: int = 10,
                          enable_groq: bool = True) -> pd.DataFrame:
    """
    Main function to detect hybrid hotspots (55-45 split)
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        infra_df: Infrastructure perception reports
        ride_df: Ride perception reports
        total_hotspots: Total number of hotspots to return
        enable_groq: Enable Groq AI analysis (optional)
    
    Returns:
        DataFrame with all hotspots (sensor + perception)
    """
    
    print("=" * 70)
    print("🚀 HYBRID HOTSPOT DETECTION (55-45 Split)")
    print("=" * 70)
    
    detector = HybridHotspotDetector()
    
    # Calculate quotas
    sensor_quota = round(total_hotspots * 0.55)
    perception_quota = total_hotspots - sensor_quota
    
    print(f"\n📊 Quotas: {sensor_quota} sensor + {perception_quota} perception = {total_hotspots} total")
    
    all_hotspots = []
    
    # Part 1: Sensor-Primary (55%)
    print(f"\n{'='*70}")
    print(f"PART 1: SENSOR-PRIMARY HOTSPOTS (55%)")
    print(f"{'='*70}")
    
    sensor_hotspots = detector.detect_sensor_primary_hotspots(
        start_date=start_date,
        end_date=end_date,
        top_n=sensor_quota
    )
    
    if not sensor_hotspots.empty:
        all_hotspots.append(sensor_hotspots)
        print(f"✅ Added {len(sensor_hotspots)} sensor-primary hotspots")
    else:
        print("⚠️ No sensor-primary hotspots found")
    
    # Part 2: Perception-Primary (45%)
    print(f"\n{'='*70}")
    print(f"PART 2: PERCEPTION-PRIMARY HOTSPOTS (45%)")
    print(f"{'='*70}")
    
    perception_hotspots = detector.detect_perception_primary_hotspots(
        infra_df=infra_df,
        ride_df=ride_df,
        start_date=start_date,
        end_date=end_date,
        quota=perception_quota
    )
    
    if not perception_hotspots.empty:
        all_hotspots.append(perception_hotspots)
        print(f"✅ Added {len(perception_hotspots)} perception-primary hotspots")
    else:
        print("⚠️ No perception-primary hotspots found")
    
    # Combine all hotspots
    if not all_hotspots:
        print("\n❌ No hotspots detected!")
        return pd.DataFrame()
    
    result = pd.concat(all_hotspots, ignore_index=True)
    
    # Add final hotspot IDs
    result['final_hotspot_id'] = range(1, len(result) + 1)
    
    # Optional: Run Groq AI analysis
    if enable_groq:
        print(f"\n🤖 Running Groq AI analysis on {len(result)} hotspots...")
        try:
            result = _run_groq_analysis(result)
            print("✅ Groq analysis complete")
        except Exception as e:
            print(f"⚠️ Groq analysis failed: {e}")
            print("   Continuing without AI analysis")
    
    print(f"\n{'='*70}")
    print(f"✅ DETECTION COMPLETE: {len(result)} total hotspots")
    print(f"{'='*70}")
    print(f"\nBreakdown:")
    if 'precedence' in result.columns:
        print(result['precedence'].value_counts())
    
    return result


def _run_groq_analysis(hotspots_df: pd.DataFrame) -> pd.DataFrame:
    """
    Run Groq AI analysis on hotspots (optional enhancement)
    Adds AI-generated summaries to perception reports
    """
    from src.sentiment_analyzer import analyze_perception_sentiment
    
    for idx, hotspot in hotspots_df.iterrows():
        # Only analyze if there are perception reports
        if hotspot.get('perception_count', 0) > 0 and 'perception_reports' in hotspot:
            try:
                reports = hotspot['perception_reports']
                
                # Extract comments from reports
                comments = []
                for report in reports:
                    if isinstance(report, dict):
                        comment = report.get('comment') or report.get('commentfinal') or report.get('finalcomment')
                        if comment and str(comment).strip():
                            comments.append(str(comment))
                
                if comments:
                    # Run sentiment analysis
                    analysis = analyze_perception_sentiment(comments, debug=False)
                    
                    # Add analysis to hotspot
                    hotspots_df.at[idx, 'ai_summary'] = analysis.get('summary', '')
                    hotspots_df.at[idx, 'ai_sentiment'] = analysis.get('sentiment', 'neutral')
                    hotspots_df.at[idx, 'ai_severity'] = analysis.get('severity', 'medium')
                    hotspots_df.at[idx, 'ai_key_issues'] = ', '.join(analysis.get('key_issues', []))
            except Exception as e:
                print(f"   Warning: Failed to analyze hotspot {idx}: {e}")
                continue
    
    return hotspots_df