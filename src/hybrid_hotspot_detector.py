# src/hybrid_hotspot_detector.py - FIXED VERSION
"""
Hybrid Hotspot Detection System - FIXED
✅ Removed unnecessary fields (avg_speed, peak_x/y/z)
✅ Fixed corridor detection and polyline creation
✅ Fixed Groq context to prevent leakage
✅ Better corridor visualization
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
        """Detect sensor-primary hotspots (55% of total)"""
        
        query = f"""
        SELECT 
            lat,
            lng,
            max_severity,
            primary_event_type,
            event_details,
            timestamp,
            device_id
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
            
            events_df['parsed_severity'] = events_df['event_details'].apply(
                self.parse_event_severity
            )
            
            events_df = events_df[events_df['parsed_severity'].notna()].copy()
            
            if events_df.empty:
                return pd.DataFrame()
            
            # CLUSTERING: Geographic only (lat/lng)
            coords = events_df[['lat', 'lng']].values
            eps_degrees = 0.0003  # ~30-40m
            
            clustering = DBSCAN(eps=eps_degrees, min_samples=3, metric='euclidean')
            events_df['cluster_id'] = clustering.fit_predict(coords)
            
            clustered = events_df[events_df['cluster_id'] >= 0].copy()
            
            if clustered.empty:
                return pd.DataFrame()
            
            hotspots = self._aggregate_sensor_clusters(clustered, start_date, end_date)
            
            hotspots['rank_score'] = hotspots.apply(
                lambda row: self.calculate_rank_score(row['avg_severity'], row['event_count']),
                axis=1
            )
            
            hotspots = hotspots.nlargest(top_n, 'rank_score').reset_index(drop=True)
            
            hotspots['source'] = 'sensor_primary'
            hotspots['precedence'] = 'sensor'
            hotspots['hotspot_id'] = ['S' + str(i+1) for i in range(len(hotspots))]
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
        Aggregate sensor events by cluster using MEDOID
        CLEANED: Removed avg_speed, peak_x/y/z
        """
        hotspots = []
        
        for cluster_id in clustered_events['cluster_id'].unique():
            cluster_data = clustered_events[clustered_events['cluster_id'] == cluster_id]
            
            # Find medoid (most central point)
            center_lat = cluster_data['lat'].mean()
            center_lng = cluster_data['lng'].mean()
            
            cluster_data_copy = cluster_data.copy()
            cluster_data_copy['dist_to_center'] = cluster_data_copy.apply(
                lambda row: haversine_distance(center_lat, center_lng, row['lat'], row['lng']),
                axis=1
            )
            
            medoid_event = cluster_data_copy.loc[cluster_data_copy['dist_to_center'].idxmin()]
            
            hotspot_lat = medoid_event['lat']
            hotspot_lng = medoid_event['lng']
            
            # Event type distribution
            event_types = cluster_data['primary_event_type'].value_counts()
            event_distribution = {}
            if not event_types.empty:
                event_distribution = (event_types / len(cluster_data) * 100).to_dict()
            
            # Severity metrics
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
                'event_distribution': event_distribution,
                'event_types_raw': event_types.to_dict() if not event_types.empty else {},
                'first_event': cluster_data['timestamp'].min(),
                'last_event': cluster_data['timestamp'].max(),
                'date_range': f"{start_date} to {end_date}",
                'radius_m': cluster_data_copy['dist_to_center'].max(),
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
        """Precedence 1: Perception reports with strong sensor validation"""
        
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
                'sensor_data': sensor_data,
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
                'event_types_raw': {}
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
    # PRECEDENCE 2: Corridors with Sensor Validation
    # ========================================================================
    
    def detect_p2_corridors_sensor(self,
                                   infra_df: pd.DataFrame,
                                   ride_df: pd.DataFrame,
                                   start_date: str,
                                   end_date: str) -> pd.DataFrame:
        """
        Precedence 2: Corridors with sensor validation
        FIXED: Proper corridor detection and polyline creation
        """
        combined_reports = self._combine_perception_reports(infra_df, ride_df)
        
        if combined_reports.empty:
            return pd.DataFrame()
        
        hotspots = []
        
        # Group by user
        for userid, user_reports in combined_reports.groupby('userid'):
            if len(user_reports) < 3:
                continue
            
            # Sort by timestamp/date to get sequential order
            if 'datetime' in user_reports.columns:
                user_reports = user_reports.sort_values('datetime')
            elif 'date' in user_reports.columns:
                user_reports = user_reports.sort_values('date')
            else:
                user_reports = user_reports.sort_index()
            
            # Check if consecutive points are < 150m apart
            points = user_reports[['lat', 'lng']].values
            
            is_corridor = True
            distances = []
            for i in range(len(points) - 1):
                dist = haversine_distance(
                    points[i][0], points[i][1],
                    points[i+1][0], points[i+1][1]
                )
                distances.append(dist)
                if dist > 150:
                    is_corridor = False
                    break
            
            if not is_corridor:
                continue
            
            corridor_length = sum(distances)
            
            # Only consider as corridor if length > 100m
            if corridor_length < 100:
                continue
            
            # FIXED: Create corridor polyline as list of [lat, lng] tuples
            corridor_points_list = [
                [float(row['lat']), float(row['lng'])] 
                for _, row in user_reports.iterrows()
            ]
            
            # Create LineString for buffer (lng, lat order for Shapely)
            corridor_line = LineString([
                (lng, lat) for lat, lng in corridor_points_list
            ])
            
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
            
            # Get start and end points
            start_point = corridor_points_list[0]
            end_point = corridor_points_list[-1]
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
                'corridor_points': corridor_points_list,  # CRITICAL: List format
                'perception_count': len(all_corridor_reports),
                'primary_user': userid,
                'event_count': sensor_data['event_count'],
                'avg_severity': sensor_data['avg_severity'],
                'max_severity': sensor_data['max_severity'],
                'unique_devices': sensor_data.get('unique_devices', 0),
                'perception_reports': all_corridor_reports.to_dict('records'),
                'sensor_data': sensor_data,
                'source': 'corridor_sensor',
                'precedence': 'P2',
                'is_corridor': True,
                'event_distribution': {},
                'event_types_raw': {}
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
        """Precedence 3: Standalone perception reports without sensor validation"""
        
        combined_reports = self._combine_perception_reports(infra_df, ride_df)
        
        if combined_reports.empty:
            return pd.DataFrame()
        
        hotspots = []
        
        # First, try to find point clusters
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
        result['rank_score'] = None
        
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
                'unique_devices': 0,
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
                'event_types_raw': {}
            }
            
            hotspots.append(hotspot)
        
        return hotspots
    
    def _detect_p3_corridors(self, combined_reports: pd.DataFrame) -> List[Dict]:
        """
        Detect P3 corridors: 3+ reports from different users forming a corridor
        FIXED: Better corridor formation logic
        """
        hotspots = []
        
        # Group reports geographically first (loose clustering)
        eps_degrees = 0.0014  # ~150m
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
            
            # Sort by position (create linear order)
            cluster_points = cluster_points.sort_values('lat').reset_index(drop=True)
            
            # Check if consecutive points < 150m
            points = cluster_points[['lat', 'lng']].values
            
            is_corridor = True
            distances = []
            for i in range(len(points) - 1):
                dist = haversine_distance(
                    points[i][0], points[i][1],
                    points[i+1][0], points[i+1][1]
                )
                distances.append(dist)
                if dist > 150:
                    is_corridor = False
                    break
            
            if not is_corridor or len(cluster_points) < 3:
                continue
            
            corridor_length = sum(distances)
            
            # Only consider as corridor if length > 100m
            if corridor_length < 100:
                continue
            
            # FIXED: Create corridor points list
            corridor_points_list = [
                [float(row['lat']), float(row['lng'])] 
                for _, row in cluster_points.iterrows()
            ]
            
            start_point = corridor_points_list[0]
            end_point = corridor_points_list[-1]
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
                'corridor_points': corridor_points_list,  # CRITICAL: List format
                'perception_count': len(cluster_points),
                'unique_users': unique_users,
                'perception_reports': cluster_points.to_dict('records'),
                'event_count': 0,
                'avg_severity': None,
                'max_severity': None,
                'unique_devices': 0,
                'source': 'corridor_perception_only',
                'precedence': 'P3',
                'is_corridor': True,
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
            COUNT(DISTINCT device_id) as unique_devices
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
        bounds = corridor_polygon.bounds  # (minx, miny, maxx, maxy)
        
        abnormal_filter = "AND is_abnormal_event = true" if require_abnormal else ""
        
        query = f"""
        SELECT 
            lat, lng,
            COUNT(*) as event_count,
            AVG(max_severity) as avg_severity,
            MAX(max_severity) as max_severity,
            COUNT(DISTINCT device_id) as unique_devices
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
                'max_severity': int(corridor_events['max_severity'].max()),
                'unique_devices': int(corridor_events['unique_devices'].sum())
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
    # GROQ ANALYSIS - FIXED TO PREVENT LEAKAGE
    # ========================================================================
    
    def analyze_hotspot_with_groq(self, hotspot: Dict) -> Dict:
        """
        Analyze hotspot with Groq AI
        FIXED: Proper context building to prevent leakage
        """
        client = get_groq_client()
        
        if not client:
            return self._fallback_analysis(hotspot)
        
        # Build CLEAN context for Groq
        context = self._build_clean_groq_context(hotspot)
        
        prompt = f"""You are a road safety analyst. Analyze this cycling safety hotspot and paint a clear picture of what's happening there.

{context}

Your analysis should:
1. Describe what's actually happening at this location
2. Connect sensor patterns with user experiences (if both available)
3. Be objective and factual - NO recommendations or solutions

Provide a 1-2 paragraph analysis."""

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
    
    def _build_clean_groq_context(self, hotspot: Dict) -> str:
        """
        Build CLEAN context for Groq - FIXED to prevent leakage
        Only includes human-readable information
        """
        context_lines = []
        
        # Location type
        if hotspot.get('is_corridor'):
            context_lines.append(f"LOCATION TYPE: Corridor ({hotspot.get('corridor_length_m', 0):.0f} meters long)")
            context_lines.append(f"This is a stretch of road where issues persist along the entire length.")
        else:
            context_lines.append("LOCATION TYPE: Point location")
            context_lines.append("This is a specific spot on the road.")
        
        context_lines.append("")
        
        # Sensor data (if available)
        if hotspot.get('event_count', 0) > 0:
            context_lines.append("SENSOR DATA:")
            context_lines.append(f"- {hotspot['event_count']} abnormal cycling events recorded")
            context_lines.append(f"- Average severity: {hotspot.get('avg_severity', 0):.1f}/10")
            context_lines.append(f"- Maximum severity: {hotspot.get('max_severity', 0)}/10")
            context_lines.append(f"- {hotspot.get('unique_devices', 0)} different cyclists affected")
            
            # Event type breakdown
            event_dist = hotspot.get('event_distribution', {})
            if event_dist:
                context_lines.append("")
                context_lines.append("Event types detected:")
                for event_type, pct in sorted(event_dist.items(), key=lambda x: x[1], reverse=True):
                    context_lines.append(f"  • {event_type}: {pct:.1f}% of events")
            
            context_lines.append("")
        
        # User perception reports (if available)
        if hotspot.get('perception_count', 0) > 0:
            context_lines.append("USER REPORTS:")
            context_lines.append(f"- {hotspot['perception_count']} cyclists reported issues here")
            
            # Extract themes from reports
            reports = hotspot.get('perception_reports', [])
            if reports:
                themes = {}
                for report in reports:
                    theme = report.get('theme', 'Unknown')
                    themes[theme] = themes.get(theme, 0) + 1
                
                if themes:
                    context_lines.append("")
                    context_lines.append("Issues reported:")
                    for theme, count in sorted(themes.items(), key=lambda x: x[1], reverse=True):
                        context_lines.append(f"  • {theme}: {count} reports")
                
                # Sample comments
                comments = [r.get('comment', '') for r in reports if r.get('comment') and len(str(r.get('comment'))) > 10]
                if comments:
                    context_lines.append("")
                    context_lines.append("Sample user comments:")
                    for i, comment in enumerate(comments[:5], 1):
                        context_lines.append(f'  {i}. "{comment}"')
            
            context_lines.append("")
        
        # No sensor data case
        if hotspot.get('event_count', 0) == 0:
            context_lines.append("NOTE: No sensor validation data available for this location.")
            context_lines.append("Analysis based solely on user reports.")
        
        return "\n".join(context_lines)
    
    def _fallback_analysis(self, hotspot: Dict) -> Dict:
        """Fallback analysis when Groq unavailable"""
        if hotspot.get('event_count', 0) > 0:
            analysis = f"""This location shows {hotspot['event_count']} abnormal cycling events with an average severity of {hotspot.get('avg_severity', 0):.1f}/10. """
            
            if hotspot.get('is_corridor'):
                analysis += f"""The issues span a {hotspot.get('corridor_length_m', 0):.0f}m stretch of road, indicating persistent problems along the entire corridor. """
            
            if hotspot.get('perception_count', 0) > 0:
                analysis += f"""{hotspot['perception_count']} user reports corroborate these sensor findings, indicating genuine safety concerns at this location."""
            else:
                analysis += """Sensor data indicates potential safety issues requiring attention."""
        else:
            analysis = f"""{hotspot.get('perception_count', 0)} users have reported safety concerns at this location. """
            
            if hotspot.get('is_corridor'):
                analysis += f"""Reports span a {hotspot.get('corridor_length_m', 0):.0f}m corridor. """
            
            analysis += """No sensor validation data is available."""
        
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
        """
        sensor_quota = int(total_hotspots * 0.55)
        perception_quota = total_hotspots - sensor_quota
        
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