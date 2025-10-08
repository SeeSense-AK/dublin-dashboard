# src/hybrid_hotspot_detector.py
"""
Hybrid Hotspot Detection System
55% Sensor-Primary, 45% Perception-Primary with 3 precedence levels
"""
import pandas as pd
import numpy as np
import math
import re
from sklearn.cluster import DBSCAN
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
import streamlit as st
from typing import Dict, List, Tuple

from src.athena_database import get_athena_database
from utils.geo_utils import haversine_distance
from src.sentiment_analyzer import get_groq_client


class HybridHotspotDetector:
    """
    Hybrid hotspot detector implementing 55-45 split strategy
    """
    
    def __init__(self):
        self.db = get_athena_database()
    
    # ========================================================================
    # UTILITY: Parse event_details to extract severity
    # ========================================================================
    
    def parse_event_severity(self, event_details: str) -> int:
        """
        Parse event_details field to extract severity
        
        Format examples:
        - "hard_brake(6)" → 6
        - "pothole(3)" → 3
        - "swerve(2)" → 2
        
        Returns:
            Severity integer, or None if can't parse
        """
        if not event_details or event_details == "" or event_details == "0":
            return None
        
        # Extract number in parentheses
        match = re.search(r'\((\d+)\)', str(event_details))
        if match:
            return int(match.group(1))
        
        return None
    
    # ========================================================================
    # UTILITY: Calculate rank score
    # ========================================================================
    
    def calculate_rank_score(self, avg_severity: float, event_count: int) -> float:
        """
        Calculate rank score: avg_severity + log10(event_count)
        
        Returns:
            Rank score (typically 0-13 range)
        """
        if event_count == 0:
            return avg_severity
        
        log_bonus = math.log10(event_count)
        rank_score = avg_severity + log_bonus
        
        return round(rank_score, 2)
    
    def get_color_from_score(self, rank_score: float, is_perception_only: bool = False) -> str:
        """
        Get color based on rank score
        
        Args:
            rank_score: The calculated rank score
            is_perception_only: True for Precedence 3 (no sensor data)
        
        Returns:
            Color string: 'red', 'orange', 'green', or 'blue'
        """
        if is_perception_only:
            return 'blue'  # Precedence 3 - no sensor data
        
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
        """
        Detect sensor-primary hotspots (55% of total)
        
        Only considers events where:
        - is_abnormal_event = true
        - event_details contains valid severity
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            top_n: Number of hotspots to return
        
        Returns:
            DataFrame with sensor hotspots
        """
        
        query = f"""
        SELECT 
            lat,
            lng,
            max_severity,
            primary_event_type,
            event_details,
            timestamp,
            device_id,
            speed_kmh,
            peak_x,
            peak_y,
            peak_z
        FROM spinovate_production.spinovate_production_optimised_v2
        WHERE is_abnormal_event = true 
            AND lat IS NOT NULL 
            AND lng IS NOT NULL
            AND event_details IS NOT NULL
            AND event_details != ''
            AND event_details != '0'
            AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'
        """
        
        try:
            events_df = pd.read_sql(query, self.db.conn)
            
            if events_df.empty:
                return pd.DataFrame()
            
            # Parse severities from event_details
            events_df['parsed_severity'] = events_df['event_details'].apply(
                self.parse_event_severity
            )
            
            # Remove events where severity couldn't be parsed
            events_df = events_df[events_df['parsed_severity'].notna()].copy()
            
            if events_df.empty:
                return pd.DataFrame()
            
            # Cluster using DBSCAN on lat/lng only (simple geographic clustering)
            coords = events_df[['lat', 'lng']].values
            eps_degrees = 0.0003  # ~30-40m
            
            clustering = DBSCAN(eps=eps_degrees, min_samples=3, metric='euclidean')
            events_df['cluster_id'] = clustering.fit_predict(coords)
            
            # Filter out noise
            clustered = events_df[events_df['cluster_id'] >= 0].copy()
            
            if clustered.empty:
                return pd.DataFrame()
            
            # Aggregate clusters
            hotspots = self._aggregate_sensor_clusters(clustered, start_date, end_date)
            
            # Calculate rank scores
            hotspots['rank_score'] = hotspots.apply(
                lambda row: self.calculate_rank_score(row['avg_severity'], row['event_count']),
                axis=1
            )
            
            # Sort and take top N
            hotspots = hotspots.nlargest(top_n, 'rank_score').reset_index(drop=True)
            
            # Add metadata
            hotspots['source'] = 'sensor_primary'
            hotspots['precedence'] = 'sensor'
            hotspots['hotspot_id'] = ['S' + str(i+1) for i in range(len(hotspots))]
            
            # Add color
            hotspots['color'] = hotspots['rank_score'].apply(
                lambda x: self.get_color_from_score(x, False)
            )
            
            return hotspots
        except Exception as e:
            st.error(f"Error detecting sensor hotspots: {e}")
            return pd.DataFrame()

    def _aggregate_sensor_clusters(self, clustered_events: pd.DataFrame,
                                   start_date: str, end_date: str) -> pd.DataFrame:
        """
        Aggregate sensor events by cluster using MEDOID (most central actual event)
        """
        hotspots = []
        
        for cluster_id in clustered_events['cluster_id'].unique():
            cluster_data = clustered_events[clustered_events['cluster_id'] == cluster_id]
            
            # Calculate centroid first
            center_lat = cluster_data['lat'].mean()
            center_lng = cluster_data['lng'].mean()
            
            # Find medoid (closest event to centroid)
            cluster_data_copy = cluster_data.copy()
            cluster_data_copy['dist_to_center'] = cluster_data_copy.apply(
                lambda row: haversine_distance(center_lat, center_lng, row['lat'], row['lng']),
                axis=1
            )
            
            medoid_event = cluster_data_copy.loc[cluster_data_copy['dist_to_center'].idxmin()]
            
            # Use medoid coordinates (guaranteed on road)
            hotspot_lat = medoid_event['lat']
            hotspot_lng = medoid_event['lng']
            
            # Calculate statistics
            event_types = cluster_data['primary_event_type'].value_counts()
            event_distribution = {}
            if not event_types.empty:
                event_distribution = (event_types / len(cluster_data) * 100).to_dict()
            
            # Average severity from parsed values
            avg_severity = cluster_data['parsed_severity'].mean()
            max_severity = cluster_data['parsed_severity'].max()
            
            hotspot = {
                'cluster_id': cluster_id,
                'center_lat': hotspot_lat,
                'center_lng': hotspot_lng,
                'event_count': len(cluster_data),
                'unique_devices': cluster_data['device_id'].nunique(),
                'avg_severity': avg_severity,
                'max_severity': max_severity,
                'avg_speed': cluster_data['speed_kmh'].mean(),
                'event_distribution': event_distribution,  # Now guaranteed to be dict
                'event_types_raw': event_types.to_dict() if not event_types.empty else {},
                'avg_peak_x': cluster_data['peak_x'].mean(),
                'avg_peak_y': cluster_data['peak_y'].mean(),
                'avg_peak_z': cluster_data['peak_z'].mean(),
                'first_event': cluster_data['timestamp'].min(),
                'last_event': cluster_data['timestamp'].max(),
                'date_range': f"{start_date} to {end_date}",
                'medoid_event_id': medoid_event.name,
                'radius_m': cluster_data_copy['dist_to_center'].max(),
                # Add default corridor fields to avoid KeyErrors
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
        """
        Detect perception-primary hotspots with 3 precedence levels
        
        Waterfall approach:
        1. P1: Perception + Strong Sensor
        2. P2: Corridors with Sensor
        3. P3: Standalone Perception
        
        Args:
            infra_df: Infrastructure reports
            ride_df: Ride reports
            start_date: For sensor queries
            end_date: For sensor queries
            quota: Number of hotspots to return (13 for 45%)
        
        Returns:
            DataFrame with perception hotspots
        """
        all_hotspots = []
        remaining_quota = quota
        
        # Precedence 1: Perception + Strong Sensor
        if remaining_quota > 0:
            p1_hotspots = self.detect_p1_perception_sensor(
                infra_df, ride_df, start_date, end_date
            )
            
            if not p1_hotspots.empty:
                take_count = min(len(p1_hotspots), remaining_quota)
                all_hotspots.append(p1_hotspots.head(take_count))
                remaining_quota -= take_count
        
        # Precedence 2: Corridors with Sensor
        if remaining_quota > 0:
            p2_corridors = self.detect_p2_corridors_sensor(
                infra_df, ride_df, start_date, end_date
            )
            
            if not p2_corridors.empty:
                take_count = min(len(p2_corridors), remaining_quota)
                all_hotspots.append(p2_corridors.head(take_count))
                remaining_quota -= take_count
        
        # Precedence 3: Standalone Perception
        if remaining_quota > 0:
            p3_standalone = self.detect_p3_standalone_perception(infra_df, ride_df)
            
            if not p3_standalone.empty:
                take_count = min(len(p3_standalone), remaining_quota)
                all_hotspots.append(p3_standalone.head(take_count))
        
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
        """
        Precedence 1: Perception reports with strong sensor validation
        
        Criteria:
        - Perception report(s)
        - Sensor readings with max_severity >= 2 within 30m radius
        
        Returns:
            DataFrame with P1 hotspots ranked by score
        """
        # Combine perception reports
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
            
            # Calculate cluster center (centroid for perception, then we'll find sensor data)
            center_lat = cluster_points['lat'].mean()
            center_lng = cluster_points['lng'].mean()
            
            # Find sensor data within 30m
            sensor_data = self._find_sensor_data_radius(
                center_lat, center_lng, 
                radius_m=30,
                min_severity=2,
                start_date=start_date,
                end_date=end_date
            )
            
            if not sensor_data['has_data']:
                continue  # Skip if no sensor validation
            
            # Create hotspot
            hotspot = {
                'cluster_id': f'P1_{cluster_id}',
                'center_lat': center_lat,
                'center_lng': center_lng,
                'perception_count': len(cluster_points),
                'event_count': sensor_data['event_count'],
                'avg_severity': sensor_data['avg_severity'],
                'max_severity': sensor_data['max_severity'],
                'perception_reports': cluster_points.to_dict('records'),
                'sensor_data': sensor_data,
                'source': 'perception_sensor',
                'precedence': 'P1',
                'is_corridor': False
            }
            
            # Calculate rank score
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
    # PRECEDENCE 2: Corridors with Sensor Validation
    # ========================================================================
    
    def detect_p2_corridors_sensor(self,
                                   infra_df: pd.DataFrame,
                                   ride_df: pd.DataFrame,
                                   start_date: str,
                                   end_date: str) -> pd.DataFrame:
        """
        Precedence 2: Corridors with sensor validation
        
        Criteria:
        - 3+ reports from SAME user
        - Consecutive points < 150m apart
        - Must have 1+ sensor reading with is_abnormal_event=true along corridor
        - Include other users' reports and sensor data along corridor path
        
        Returns:
            DataFrame with P2 corridor hotspots
        """
        combined_reports = self._combine_perception_reports(infra_df, ride_df)
        
        if combined_reports.empty:
            return pd.DataFrame()
        
        hotspots = []
        
        # Group by user
        for userid, user_reports in combined_reports.groupby('userid'):
            if len(user_reports) < 3:
                continue
            
            # Sort by timestamp or index to get sequential order
            user_reports = user_reports.sort_index()
            
            # Check if consecutive points are < 150m apart
            points = user_reports[['lat', 'lng']].values
            
            is_corridor = True
            for i in range(len(points) - 1):
                dist = haversine_distance(
                    points[i][0], points[i][1],
                    points[i+1][0], points[i+1][1]
                )
                if dist > 150:
                    is_corridor = False
                    break
            
            if not is_corridor:
                continue
            
            # Create corridor polyline
            corridor_line = LineString([(row['lng'], row['lat']) for _, row in user_reports.iterrows()])
            
            # Create 20m buffer polygon
            corridor_polygon = corridor_line.buffer(0.00018)  # ~20m in degrees
            
            # Find sensor data along corridor
            sensor_data = self._find_sensor_data_along_corridor(
                corridor_polygon,
                start_date,
                end_date,
                require_abnormal=True
            )
            
            if not sensor_data['has_data']:
                continue  # Must have sensor validation for P2
            
            # Find other users' reports along corridor
            other_reports = combined_reports[combined_reports['userid'] != userid]
            corridor_reports = self._find_reports_in_polygon(other_reports, corridor_polygon)
            
            # Combine all reports
            all_corridor_reports = pd.concat([user_reports, corridor_reports], ignore_index=True)
            
            # Calculate corridor length
            corridor_length = sum([
                haversine_distance(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
                for i in range(len(points) - 1)
            ])
            
            # Use medoid or middle point
            start_point = (user_reports.iloc[0]['lat'], user_reports.iloc[0]['lng'])
            end_point = (user_reports.iloc[-1]['lat'], user_reports.iloc[-1]['lng'])
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
                'corridor_length_m': corridor_length,
                'corridor_points': [(row['lat'], row['lng']) for _, row in user_reports.iterrows()],
                'perception_count': len(all_corridor_reports),
                'primary_user': userid,
                'event_count': sensor_data['event_count'],
                'avg_severity': sensor_data['avg_severity'],
                'max_severity': sensor_data['max_severity'],
                'perception_reports': all_corridor_reports.to_dict('records'),
                'sensor_data': sensor_data,
                'source': 'corridor_sensor',
                'precedence': 'P2',
                'is_corridor': True,
                # Ensure event_distribution exists for all hotspots
                'event_distribution': {},
                'event_types_raw': {}
            }
            
            # Calculate rank score
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
        """
        Precedence 3: Standalone perception reports without sensor validation
        
        Criteria:
        - 3+ reports from DIFFERENT users
        - Can be point cluster OR corridor
        - NO sensor validation required
        
        Returns:
            DataFrame with P3 hotspots (color = blue)
        """
        combined_reports = self._combine_perception_reports(infra_df, ride_df)
        
        if combined_reports.empty:
            return pd.DataFrame()
        
        hotspots = []
        
        # First, try to find point clusters (30m radius, 3+ different users)
        point_clusters = self._detect_p3_point_clusters(combined_reports)
        hotspots.extend(point_clusters)
        
        # Second, try to find multi-user corridors
        corridor_clusters = self._detect_p3_corridors(combined_reports)
        hotspots.extend(corridor_clusters)
        
        if not hotspots:
            return pd.DataFrame()
        
        result = pd.DataFrame(hotspots)
        
        # Rank by report count (no sensor data)
        result = result.sort_values('perception_count', ascending=False).reset_index(drop=True)
        result['hotspot_id'] = ['P3_' + str(i+1) for i in range(len(result))]
        
        # All P3 are blue (no sensor data)
        result['color'] = 'blue'
        result['rank_score'] = None  # No severity available
        
        return result
    
    def _detect_p3_point_clusters(self, combined_reports: pd.DataFrame) -> List[Dict]:
        """Detect P3 point clusters: 3+ reports from different users"""
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
                'cluster_id': f'P3_point_{cluster_id}',
                'center_lat': center_lat,
                'center_lng': center_lng,
                'perception_count': len(cluster_points),
                'unique_users': unique_users,
                'perception_reports': cluster_points.to_dict('records'),
                'event_count': 0,
                'avg_severity': None,
                'max_severity': None,
                'source': 'perception_only',
                'precedence': 'P3',
                'is_corridor': False
            }
            
            hotspots.append(hotspot)
        
        return hotspots
    
    def _detect_p3_corridors(self, combined_reports: pd.DataFrame) -> List[Dict]:
        """
        Detect P3 corridors: 3+ reports from different users forming a corridor
        
        Logic:
        - Need 3+ users total
        - All points consecutive < 150m apart
        - Forms a linear pattern
        """
        hotspots = []
        
        # Group reports geographically first (loose clustering)
        eps_degrees = 0.0014  # ~150m - loose grouping
        coords = combined_reports[['lat', 'lng']].values
        
        clustering = DBSCAN(eps=eps_degrees, min_samples=3, metric='euclidean')
        combined_reports['temp_cluster'] = clustering.fit_predict(coords)
        
        for cluster_id in combined_reports['temp_cluster'].unique():
            if cluster_id == -1:
                continue
            
            cluster_points = combined_reports[combined_reports['temp_cluster'] == cluster_id]
            
            # Must have 3+ different users
            unique_users = cluster_points['userid'].nunique()
            if unique_users < 3:
                continue
            
            # Sort by position (try to form a line)
            cluster_points = cluster_points.sort_values('lat')
            
            # Check if consecutive points < 150m
            points = cluster_points[['lat', 'lng']].values
            
            is_corridor = True
            for i in range(len(points) - 1):
                dist = haversine_distance(
                    points[i][0], points[i][1],
                    points[i+1][0], points[i+1][1]
                )
                if dist > 150:
                    is_corridor = False
                    break
            
            if not is_corridor or len(cluster_points) < 3:
                continue
            
            # Calculate corridor metrics
            corridor_length = sum([
                haversine_distance(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
                for i in range(len(points) - 1)
            ])
            
            # Only consider as corridor if length > 100m
            if corridor_length < 100:
                continue
            
            start_point = (cluster_points.iloc[0]['lat'], cluster_points.iloc[0]['lng'])
            end_point = (cluster_points.iloc[-1]['lat'], cluster_points.iloc[-1]['lng'])
            center_lat = (start_point[0] + end_point[0]) / 2
            center_lng = (start_point[1] + end_point[1]) / 2
            
            hotspot = {
                'cluster_id': f'P3_corridor_{cluster_id}',
                'center_lat': center_lat,
                'center_lng': center_lng,
                'start_lat': start_point[0],
                'start_lng': start_point[1],
                'end_lat': end_point[0],
                'end_lng': end_point[1],
                'corridor_length_m': corridor_length,
                'corridor_points': [(row['lat'], row['lng']) for _, row in cluster_points.iterrows()],
                'perception_count': len(cluster_points),
                'unique_users': unique_users,
                'perception_reports': cluster_points.to_dict('records'),
                'event_count': 0,
                'avg_severity': None,
                'max_severity': None,
                'source': 'corridor_perception_only',
                'precedence': 'P3',
                'is_corridor': True,
                # Ensure event_distribution exists for all hotspots
                'event_distribution': {},
                'event_types_raw': {}
            }
            
            hotspots.append(hotspot)
        
        return hotspots
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _combine_perception_reports(self, infra_df: pd.DataFrame, 
                                    ride_df: pd.DataFrame) -> pd.DataFrame:
        """Combine infrastructure and ride reports into single DataFrame"""
        combined = []
        
        if not infra_df.empty:
            infra_subset = infra_df[['lat', 'lng', 'infrastructuretype', 'finalcomment', 'userid', 'date']].copy()
            infra_subset['report_type'] = 'infrastructure'
            infra_subset['theme'] = infra_subset['infrastructuretype']
            infra_subset['comment'] = infra_subset['finalcomment']
            infra_subset['rating'] = None
            combined.append(infra_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating', 'userid', 'date']])
        
        if not ride_df.empty:
            ride_subset = ride_df[['lat', 'lng', 'incidenttype', 'commentfinal', 'incidentrating', 'userid', 'date']].copy()
            ride_subset['report_type'] = 'ride'
            ride_subset['theme'] = ride_subset['incidenttype']
            ride_subset['comment'] = ride_subset['commentfinal']
            ride_subset['rating'] = ride_subset['incidentrating']
            combined.append(ride_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating', 'userid', 'date']])
        
        if not combined:
            return pd.DataFrame()
        
        return pd.concat(combined, ignore_index=True)
    
    def _find_sensor_data_radius(self, lat: float, lng: float, radius_m: int,
                                 min_severity: int, start_date: str, 
                                 end_date: str) -> Dict:
        """Find sensor data within radius of a point"""
        radius_deg = radius_m / 111000
        
        query = f"""
        SELECT 
            COUNT(*) as event_count,
            AVG(max_severity) as avg_severity,
            MAX(max_severity) as max_severity,
            COUNT(DISTINCT device_id) as unique_devices,
            COUNT(DISTINCT primary_event_type) as event_type_count
        FROM spinovate_production.spinovate_production_optimised_v2
        WHERE ABS(lat - {lat}) <= {radius_deg}
            AND ABS(lng - {lng}) <= {radius_deg}
            AND max_severity >= {min_severity}
            AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'
        """
        
        try:
            result = pd.read_sql(query, self.db.conn)
            row = result.iloc[0]
            
            return {
                'has_data': row['event_count'] > 0,
                'event_count': int(row['event_count']),
                'avg_severity': float(row['avg_severity']) if row['avg_severity'] else 0,
                'max_severity': int(row['max_severity']) if row['max_severity'] else 0,
                'unique_devices': int(row['unique_devices'])
            }
        except:
            return {'has_data': False, 'event_count': 0}
    
    def _find_sensor_data_along_corridor(self, corridor_polygon, 
                                         start_date: str, end_date: str,
                                         require_abnormal: bool = True) -> Dict:
        """Find sensor data along a corridor polygon"""
        # Get bounding box of polygon
        bounds = corridor_polygon.bounds  # (minx, miny, maxx, maxy)
        
        abnormal_filter = "AND is_abnormal_event = true" if require_abnormal else ""
        
        query = f"""
        SELECT 
            lat, lng,
            COUNT(*) as event_count,
            AVG(max_severity) as avg_severity,
            MAX(max_severity) as max_severity
        FROM spinovate_production.spinovate_production_optimised_v2
        WHERE lat BETWEEN {bounds[1]} AND {bounds[3]}
            AND lng BETWEEN {bounds[0]} AND {bounds[2]}
            {abnormal_filter}
            AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'
        GROUP BY lat, lng
        """
        
        try:
            events = pd.read_sql(query, self.db.conn)
            
            if events.empty:
                return {'has_data': False, 'event_count': 0}
            
            # Filter points that are actually inside polygon
            events['point'] = events.apply(lambda row: Point(row['lng'], row['lat']), axis=1)
            events['in_corridor'] = events['point'].apply(lambda p: corridor_polygon.contains(p))
            
            corridor_events = events[events['in_corridor']]
            
            if corridor_events.empty:
                return {'has_data': False, 'event_count': 0}
            
            return {
                'has_data': True,
                'event_count': int(corridor_events['event_count'].sum()),
                'avg_severity': float(corridor_events['avg_severity'].mean()),
                'max_severity': int(corridor_events['max_severity'].max())
            }
        except:
            return {'has_data': False, 'event_count': 0}
    
    def _find_reports_in_polygon(self, reports_df: pd.DataFrame, 
                                 polygon) -> pd.DataFrame:
        """Find perception reports inside a polygon"""
        if reports_df.empty:
            return pd.DataFrame()
        
        reports_copy = reports_df.copy()
        reports_copy['point'] = reports_copy.apply(
            lambda row: Point(row['lng'], row['lat']), axis=1
        )
        reports_copy['in_polygon'] = reports_copy['point'].apply(
            lambda p: polygon.contains(p)
        )
        
        return reports_copy[reports_copy['in_polygon']].drop(columns=['point', 'in_polygon'])
    
    # ========================================================================
    # GROQ ANALYSIS
    # ========================================================================
    
    def analyze_hotspot_with_groq(self, hotspot: Dict) -> Dict:
        """
        Analyze hotspot with Groq AI to paint a picture
        
        Args:
            hotspot: Hotspot dictionary with all data
        
        Returns:
            Dict with analysis text and metadata
        """
        client = get_groq_client()
        
        if not client:
            return self._fallback_analysis(hotspot)
        
        # Build context for Groq
        context = self._build_groq_context(hotspot)
        
        prompt = f"""You are a road safety analyst. Analyze this cycling safety hotspot and paint a clear picture of what's happening there.

{context}

Your analysis should:
1. Describe what's actually happening at this location
2. Connect sensor patterns with user experiences (if both available)
3. Paint a vivid picture that helps understand the safety issues
4. Be objective and factual - NO recommendations or solutions

Provide a 2-3 paragraph analysis."""

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert road safety analyst. Provide clear, objective analysis without recommendations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=500
            )
            
            return {
                'analysis': response.choices[0].message.content,
                'method': 'groq_ai',
                'model': 'llama-3.3-70b-versatile'
            }
        except Exception as e:
            st.warning(f"Groq analysis failed: {e}")
            return self._fallback_analysis(hotspot)
    
    def _build_groq_context(self, hotspot: dict) -> str:
        """
        Builds a detailed context string for Groq analysis based on the hotspot data.
        Handles missing or malformed fields safely to avoid runtime errors.
        """

        context_lines = []

        # --- Basic metadata ---
        lat = hotspot.get("lat")
        lng = hotspot.get("lng")
        context_lines.append(f"Hotspot location: ({lat}, {lng})")

        primary_event = hotspot.get("primary_event_type", "Unknown")
        context_lines.append(f"Primary event type: {primary_event}")

        max_severity = hotspot.get("max_severity", "N/A")
        context_lines.append(f"Maximum severity recorded: {max_severity}")

        # --- Event distribution ---
        event_dist = hotspot.get("event_distribution")
        if isinstance(event_dist, str):
            try:
                import json
                event_dist = json.loads(event_dist)
            except Exception:
                event_dist = None

        if isinstance(event_dist, dict):
            context_lines.append("Event distribution breakdown:")
            for event_type, pct in event_dist.items():
                context_lines.append(f"- {event_type}: {pct}%")
        else:
            context_lines.append("Event distribution data unavailable.")

        # --- Sensor summary ---
        sensor_summary = hotspot.get("sensor_summary")
        if isinstance(sensor_summary, str):
            try:
                import json
                sensor_summary = json.loads(sensor_summary)
            except Exception:
                sensor_summary = None

        if isinstance(sensor_summary, dict):
            context_lines.append("Sensor summary:")
            for sensor_type, count in sensor_summary.items():
                context_lines.append(f"- {sensor_type}: {count}")
        else:
            context_lines.append("Sensor summary unavailable.")

        # --- Abnormal event info ---
        is_abnormal = hotspot.get("is_abnormal_event", False)
        context_lines.append(f"Abnormal event detected: {is_abnormal}")

        details = hotspot.get("event_details", "No further details available.")
        context_lines.append(f"Additional details: {details}")

        # --- Optional user context ---
        user_comments = hotspot.get("user_comments")
        if user_comments:
            context_lines.append(f"User comments summary: {user_comments}")

        # Join all parts
        context = "\n".join(context_lines)
        return context
    
    def _fallback_analysis(self, hotspot: Dict) -> Dict:
        """Fallback analysis when Groq unavailable"""
        if hotspot.get('event_count', 0) > 0:
            analysis = f"""This location shows {hotspot['event_count']} abnormal cycling events with an average severity of {hotspot.get('avg_severity', 0):.1f}/10. """
            
            if hotspot.get('perception_count', 0) > 0:
                analysis += f"""{hotspot['perception_count']} user reports corroborate these sensor findings, indicating genuine safety concerns at this location."""
            else:
                analysis += """Sensor data indicates potential safety issues requiring attention."""
        else:
            analysis = f"""{hotspot.get('perception_count', 0)} users have reported safety concerns at this location. No sensor validation data is available."""
        
        return {
            'analysis': analysis,
            'method': 'fallback',
            'model': 'rule_based'
        }
    
    # ========================================================================
    # MAIN ORCHESTRATION
    # ========================================================================
    
    def detect_all_hotspots(self,
                           start_date: str,
                           end_date: str,
                           infra_df: pd.DataFrame,
                           ride_df: pd.DataFrame,
                           total_hotspots: int = 30) -> pd.DataFrame:
        """
        Main function: Detect all hotspots using 55-45 split
        
        Args:
            start_date: Start date for sensor queries (YYYY-MM-DD)
            end_date: End date for sensor queries (YYYY-MM-DD)
            infra_df: Infrastructure perception reports (all time)
            ride_df: Ride perception reports (all time)
            total_hotspots: Total number of hotspots to detect (default 30)
        
        Returns:
            DataFrame with all hotspots, analyzed and ready for visualization
        """
        # Calculate split
        sensor_quota = int(total_hotspots * 0.55)  # 55%
        perception_quota = total_hotspots - sensor_quota  # 45%
        
        st.info(f"🔬 Detecting {sensor_quota} sensor-primary and {perception_quota} perception-primary hotspots...")
        
        all_hotspots = []
        
        # PART 1: Sensor-Primary (55%)
        with st.spinner("Detecting sensor-primary hotspots..."):
            sensor_hotspots = self.detect_sensor_primary_hotspots(
                start_date, end_date, sensor_quota
            )
            
            if not sensor_hotspots.empty:
                st.success(f"✅ Found {len(sensor_hotspots)} sensor-primary hotspots")
                all_hotspots.append(sensor_hotspots)
            else:
                st.warning("⚠️ No sensor-primary hotspots found")
        
        # PART 2: Perception-Primary (45%)
        with st.spinner("Detecting perception-primary hotspots..."):
            perception_hotspots = self.detect_perception_primary_hotspots(
                infra_df, ride_df, start_date, end_date, perception_quota
            )
            
            if not perception_hotspots.empty:
                st.success(f"✅ Found {len(perception_hotspots)} perception-primary hotspots")
                all_hotspots.append(perception_hotspots)
            else:
                st.warning("⚠️ No perception-primary hotspots found")
        
        if not all_hotspots:
            return pd.DataFrame()
        
        # Combine all hotspots
        combined = pd.concat(all_hotspots, ignore_index=True)
        
        # Assign final hotspot IDs
        combined['final_hotspot_id'] = range(1, len(combined) + 1)
        
        # Run Groq analysis on all hotspots
        st.info("🤖 Running AI analysis on all hotspots...")
        combined = self._analyze_all_hotspots(combined)
        
        return combined
    
    def _analyze_all_hotspots(self, hotspots_df: pd.DataFrame) -> pd.DataFrame:
        """Run Groq analysis on all hotspots with progress bar"""
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        analyses = []
        
        for idx, hotspot in hotspots_df.iterrows():
            status_text.text(f"Analyzing hotspot {idx + 1}/{len(hotspots_df)}...")
            
            analysis = self.analyze_hotspot_with_groq(hotspot.to_dict())
            analyses.append(analysis)
            
            progress_bar.progress((idx + 1) / len(hotspots_df))
        
        progress_bar.empty()
        status_text.empty()
        
        hotspots_df['groq_analysis'] = analyses
        
        st.success(f"✅ AI analysis complete for all {len(hotspots_df)} hotspots")
        
        return hotspots_df


# ========================================================================
# MAIN FUNCTION FOR EXTERNAL USE
# ========================================================================

def detect_hybrid_hotspots(start_date: str,
                          end_date: str,
                          infra_df: pd.DataFrame,
                          ride_df: pd.DataFrame,
                          total_hotspots: int = 30) -> pd.DataFrame:
    """
    Main entry point for hybrid hotspot detection
    
    Usage:
        hotspots = detect_hybrid_hotspots(
            start_date='2025-07-01',
            end_date='2025-09-01',
            infra_df=infra_df,
            ride_df=ride_df,
            total_hotspots=30
        )
    
    Returns:
        DataFrame with all hotspots including Groq analysis
    """
    detector = HybridHotspotDetector()
    return detector.detect_all_hotspots(
        start_date, end_date, infra_df, ride_df, total_hotspots
    )
