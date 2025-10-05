"""
Smart Hotspot Detection Module
Handles both sensor-driven and perception-driven hotspot detection
Works with AWS Athena for sensor data and local CSV for perception data
"""

import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from scipy.spatial import distance_matrix
import streamlit as st
from typing import Dict, List, Tuple
from utils.geo_utils import haversine_distance
from src.sentiment_analyzer import analyze_perception_sentiment
from src.athena_database import get_athena_database


class SmartHotspotDetector:
    """
    Intelligent hotspot detector that combines sensor and perception data
    Uses Athena for sensor data queries
    """
    
    def __init__(self, infra_df: pd.DataFrame, ride_df: pd.DataFrame):
        """
        Initialize detector with perception data only
        Sensor data is queried from Athena on-demand
        """
        self.infra_df = infra_df
        self.ride_df = ride_df
        self.athena_db = get_athena_database()
        
    def detect_sensor_hotspots(self, 
                              min_severity: int = 5,
                              min_events: int = 2,
                              start_date: str = None,
                              end_date: str = None) -> pd.DataFrame:
        """
        Detect hotspots from Athena sensor data using spatial clustering
        
        Args:
            min_severity: Minimum severity level to consider
            min_events: Minimum events required to form a hotspot
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)
            
        Returns:
            DataFrame with sensor hotspots
        """
        try:
            # Query Athena for sensor hotspots
            hotspots_df = self.athena_db.detect_sensor_hotspots(
                min_events=min_events,
                severity_threshold=min_severity,
                start_date=start_date,
                end_date=end_date
            )
            
            if hotspots_df.empty:
                return pd.DataFrame()
            
            # Standardize column names
            hotspots_df = hotspots_df.rename(columns={
                'lat': 'center_lat',
                'lng': 'center_lng',
                'event_count': 'event_count',
                'severity_score': 'avg_severity'
            })
            
            # Add source identifier
            hotspots_df['source'] = 'sensor'
            hotspots_df['hotspot_id'] = ['sensor_' + str(i) for i in range(len(hotspots_df))]
            
            # Calculate risk score
            hotspots_df['risk_score'] = hotspots_df['avg_severity'] * np.log1p(hotspots_df['event_count'])
            
            # Add device count if not present
            if 'device_count' not in hotspots_df.columns:
                hotspots_df['device_count'] = 1
            
            # Add max severity if not present
            if 'max_severity' not in hotspots_df.columns:
                hotspots_df['max_severity'] = hotspots_df['avg_severity']
            
            return hotspots_df.sort_values('risk_score', ascending=False).reset_index(drop=True)
            
        except Exception as e:
            st.error(f"Error detecting sensor hotspots from Athena: {e}")
            return pd.DataFrame()
    
    def detect_perception_hotspots(self,
                                   cluster_radius_m: int = 50,
                                   min_reports: int = 3) -> pd.DataFrame:
        """
        Detect hotspots from perception reports using spatial clustering
        
        Args:
            cluster_radius_m: Radius for spatial clustering (meters)
            min_reports: Minimum reports required to form a hotspot
            
        Returns:
            DataFrame with perception hotspots
        """
        # Combine infrastructure and ride reports
        combined = []
        
        if not self.infra_df.empty:
            infra_subset = self.infra_df[['lat', 'lng', 'infrastructuretype', 'finalcomment']].copy()
            infra_subset['report_type'] = 'infrastructure'
            infra_subset['theme'] = infra_subset['infrastructuretype']
            infra_subset['comment'] = infra_subset['finalcomment']
            infra_subset['rating'] = None
            combined.append(infra_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating']])
        
        if not self.ride_df.empty:
            ride_subset = self.ride_df[['lat', 'lng', 'incidenttype', 'commentfinal', 'incidentrating']].copy()
            ride_subset['report_type'] = 'ride'
            ride_subset['theme'] = ride_subset['incidenttype']
            ride_subset['comment'] = ride_subset['commentfinal']
            ride_subset['rating'] = ride_subset['incidentrating']
            combined.append(ride_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating']])
        
        if not combined:
            return pd.DataFrame()
        
        all_reports = pd.concat(combined, ignore_index=True)
        
        # Spatial clustering
        coords = all_reports[['lat', 'lng']].values
        eps_degrees = cluster_radius_m / 111000
        
        clustering = DBSCAN(eps=eps_degrees, min_samples=min_reports, metric='euclidean')
        all_reports['cluster_id'] = clustering.fit_predict(coords)
        
        clustered = all_reports[all_reports['cluster_id'] >= 0].copy()
        
        if clustered.empty:
            return pd.DataFrame()
        
        # Aggregate into hotspots
        hotspots = []
        for cluster_id in clustered['cluster_id'].unique():
            cluster_points = clustered[clustered['cluster_id'] == cluster_id]
            
            # Get comments for sentiment analysis
            comments = cluster_points['comment'].dropna().tolist()
            
            hotspot = {
                'hotspot_id': f'perception_{cluster_id}',
                'source': 'perception',
                'center_lat': cluster_points['lat'].mean(),
                'center_lng': cluster_points['lng'].mean(),
                'report_count': len(cluster_points),
                'report_types': cluster_points['report_type'].value_counts().to_dict(),
                'themes': cluster_points['theme'].value_counts().to_dict(),
                'primary_theme': cluster_points['theme'].mode()[0] if not cluster_points['theme'].mode().empty else 'Unknown',
                'avg_rating': cluster_points['rating'].mean() if cluster_points['rating'].notna().any() else None,
                'comments': comments,
                'raw_reports': cluster_points.to_dict('records')
            }
            
            hotspots.append(hotspot)
        
        hotspots_df = pd.DataFrame(hotspots)
        
        # Calculate urgency score
        hotspots_df['urgency_score'] = hotspots_df.apply(
            lambda row: self._calculate_urgency(row['report_count'], row['avg_rating']),
            axis=1
        )
        hotspots_df = hotspots_df.sort_values('urgency_score', ascending=False).reset_index(drop=True)
        
        return hotspots_df
    
    def enrich_with_perception(self, sensor_hotspots: pd.DataFrame, radius_m: int = 25) -> pd.DataFrame:
        """
        Enrich sensor hotspots with nearby perception reports
        
        Args:
            sensor_hotspots: DataFrame with sensor hotspots
            radius_m: Matching radius in meters
            
        Returns:
            Enriched hotspots DataFrame
        """
        if sensor_hotspots.empty:
            return sensor_hotspots
        
        # Combine perception reports
        perception_combined = []
        
        if not self.infra_df.empty:
            infra_subset = self.infra_df[['lat', 'lng', 'infrastructuretype', 'finalcomment']].copy()
            infra_subset['type'] = 'infrastructure'
            infra_subset['theme'] = infra_subset['infrastructuretype']
            infra_subset['comment'] = infra_subset['finalcomment']
            perception_combined.append(infra_subset[['lat', 'lng', 'type', 'theme', 'comment']])
        
        if not self.ride_df.empty:
            ride_subset = self.ride_df[['lat', 'lng', 'incidenttype', 'commentfinal']].copy()
            ride_subset['type'] = 'ride'
            ride_subset['theme'] = ride_subset['incidenttype']
            ride_subset['comment'] = ride_subset['commentfinal']
            perception_combined.append(ride_subset[['lat', 'lng', 'type', 'theme', 'comment']])
        
        if not perception_combined:
            sensor_hotspots['perception_reports'] = [[] for _ in range(len(sensor_hotspots))]
            sensor_hotspots['perception_count'] = 0
            sensor_hotspots['perception_sentiment'] = None
            return sensor_hotspots
        
        all_perception = pd.concat(perception_combined, ignore_index=True)
        
        # Match perception to each hotspot
        enriched_hotspots = []
        
        for idx, hotspot in sensor_hotspots.iterrows():
            # Find nearby perception reports
            nearby = []
            for _, report in all_perception.iterrows():
                dist = haversine_distance(
                    hotspot['center_lat'], hotspot['center_lng'],
                    report['lat'], report['lng']
                )
                if dist <= radius_m:
                    nearby.append(report.to_dict())
            
            # Add perception data to hotspot
            hotspot_dict = hotspot.to_dict()
            hotspot_dict['perception_reports'] = nearby
            hotspot_dict['perception_count'] = len(nearby)
            
            # Run sentiment analysis if we have comments
            if nearby:
                comments = [r['comment'] for r in nearby if pd.notna(r.get('comment'))]
                if comments:
                    sentiment = analyze_perception_sentiment(comments)
                    hotspot_dict['perception_sentiment'] = sentiment
                else:
                    hotspot_dict['perception_sentiment'] = None
            else:
                hotspot_dict['perception_sentiment'] = None
            
            enriched_hotspots.append(hotspot_dict)
        
        return pd.DataFrame(enriched_hotspots)
    
    def enrich_with_sensor(self, perception_hotspots: pd.DataFrame, 
                          radius_m: int = 50,
                          start_date: str = None,
                          end_date: str = None) -> pd.DataFrame:
        """
        Enrich perception hotspots with nearby sensor events from Athena
        
        Args:
            perception_hotspots: DataFrame with perception hotspots
            radius_m: Matching radius in meters
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Enriched hotspots DataFrame
        """
        if perception_hotspots.empty:
            return perception_hotspots
        
        # Import the function from perception_hotspot_analyzer
        from src.perception_hotspot_analyzer import find_sensor_data_for_perception_cluster
        
        # Match sensor events to each hotspot
        enriched_hotspots = []
        
        for idx, hotspot in perception_hotspots.iterrows():
            # Query Athena for nearby sensor data
            sensor_data = find_sensor_data_for_perception_cluster(
                hotspot['center_lat'],
                hotspot['center_lng'],
                radius_m=radius_m,
                start_date=start_date,
                end_date=end_date
            )
            
            # Add sensor data to hotspot
            hotspot_dict = hotspot.to_dict()
            hotspot_dict['sensor_data'] = sensor_data
            hotspot_dict['sensor_count'] = sensor_data.get('total_events', 0)
            
            # Validate with sensor data
            if sensor_data.get('has_sensor_data'):
                validation = self._cross_validate_with_sensor(hotspot_dict, sensor_data)
                hotspot_dict['sensor_validation'] = validation
            else:
                hotspot_dict['sensor_validation'] = 'no_sensor_data'
            
            enriched_hotspots.append(hotspot_dict)
        
        return pd.DataFrame(enriched_hotspots)
    
    def _calculate_urgency(self, report_count: int, avg_rating: float = None) -> int:
        """Calculate urgency score (0-100)"""
        score = min(40, report_count * 5)  # Frequency component
        
        if avg_rating is not None:
            # Lower rating = higher urgency (ratings are 1-5, lower is worse)
            rating_score = (5 - avg_rating) * 10
            score += rating_score
        
        return min(100, int(score))
    
    def _cross_validate_with_sensor(self, perception_hotspot: Dict, sensor_data: Dict) -> str:
        """
        Cross-validate perception reports with sensor data
        
        Returns: 'confirmed', 'partial', 'conflicted', or 'no_sensor_data'
        """
        if not sensor_data.get('has_sensor_data'):
            return 'no_sensor_data'
        
        primary_theme = perception_hotspot.get('primary_theme', '').lower()
        
        matches = 0
        
        # Check for relevant sensor events
        if 'close' in primary_theme or 'pass' in primary_theme:
            if sensor_data.get('brake_events', 0) > 0 or sensor_data.get('swerve_events', 0) > 0:
                matches += 1
        
        if 'pothole' in primary_theme or 'surface' in primary_theme:
            if sensor_data.get('pothole_events', 0) > 0:
                matches += 1
        
        # General validation
        if sensor_data.get('abnormal_events', 0) >= 2:
            matches += 1
        
        if matches >= 2:
            return 'confirmed'
        elif matches == 1:
            return 'partial'
        else:
            return 'conflicted'
    
    def get_combined_hotspots(self,
                             sensor_params: Dict = None,
                             perception_params: Dict = None,
                             max_total_hotspots: int = 20) -> pd.DataFrame:
        """
        Get combined sensor and perception hotspots with smart filtering
        
        Args:
            sensor_params: Dict with sensor detection parameters
            perception_params: Dict with perception detection parameters
            max_total_hotspots: Maximum number of hotspots to return
            
        Returns:
            Combined and ranked DataFrame of hotspots
        """
        sensor_params = sensor_params or {}
        perception_params = perception_params or {}
        
        # Detect sensor hotspots from Athena
        sensor_hotspots = self.detect_sensor_hotspots(**sensor_params)
        
        # Enrich with perception
        if not sensor_hotspots.empty:
            sensor_hotspots = self.enrich_with_perception(
                sensor_hotspots, 
                radius_m=sensor_params.get('perception_radius_m', 25)
            )
        
        # Detect perception hotspots
        perception_hotspots = self.detect_perception_hotspots(**perception_params)
        
        # Enrich with sensor data from Athena
        if not perception_hotspots.empty:
            perception_hotspots = self.enrich_with_sensor(
                perception_hotspots,
                radius_m=perception_params.get('sensor_radius_m', 50),
                start_date=sensor_params.get('start_date'),
                end_date=sensor_params.get('end_date')
            )
        
        # Combine both sources
        combined = []
        
        if not sensor_hotspots.empty:
            combined.append(sensor_hotspots)
        
        if not perception_hotspots.empty:
            combined.append(perception_hotspots)
        
        if not combined:
            return pd.DataFrame()
        
        all_hotspots = pd.concat(combined, ignore_index=True)
        
        # Calculate final priority score
        all_hotspots['priority_score'] = all_hotspots.apply(self._calculate_priority, axis=1)
        
        # Sort by priority and limit to max
        all_hotspots = all_hotspots.sort_values('priority_score', ascending=False)
        all_hotspots = all_hotspots.head(max_total_hotspots)
        
        # Assign final hotspot IDs
        all_hotspots['final_hotspot_id'] = range(1, len(all_hotspots) + 1)
        
        return all_hotspots.reset_index(drop=True)
    
    def _calculate_priority(self, row: pd.Series) -> float:
        """
        Calculate priority score for ranking hotspots
        Combines sensor severity, perception urgency, and cross-validation
        """
        score = 0
        
        # Sensor component
        if row.get('source') == 'sensor':
            score += row.get('risk_score', 0) * 10
            # Bonus for perception confirmation
            if row.get('perception_count', 0) > 0:
                score += 20
                if row.get('perception_sentiment'):
                    severity = row['perception_sentiment'].get('severity', 'low')
                    severity_bonus = {'low': 5, 'medium': 10, 'high': 15, 'critical': 20}
                    score += severity_bonus.get(severity, 0)
        
        # Perception component
        elif row.get('source') == 'perception':
            score += row.get('urgency_score', 0)
            # Bonus for sensor validation
            validation = row.get('sensor_validation', 'no_sensor_data')
            validation_bonus = {'confirmed': 30, 'partial': 15, 'conflicted': 0, 'no_sensor_data': 5}
            score += validation_bonus.get(validation, 0)
            if row.get('sensor_count', 0) > 0:
                score += min(20, row['sensor_count'] * 2)
        
        return score

        """
        Detect hotspots from sensor data using spatial clustering
        
        Args:
            min_severity: Minimum severity level to consider
            cluster_radius_m: Radius for spatial clustering (meters)
            min_events: Minimum events required to form a hotspot
            
        Returns:
            DataFrame with sensor hotspots
        """
        # Filter for abnormal events with sufficient severity
        abnormal = self.sensor_df[
            (self.sensor_df['is_abnormal_event'] == True) | 
            (self.sensor_df['is_abnormal_event'] == 'True')
        ].copy()
        
        abnormal['max_severity'] = pd.to_numeric(abnormal['max_severity'], errors='coerce')
        high_severity = abnormal[abnormal['max_severity'] >= min_severity].copy()
        
        if len(high_severity) < min_events:
            st.warning(f"Only {len(high_severity)} events with severity >= {min_severity}. Consider lowering threshold.")
            return pd.DataFrame()
        
        # Spatial clustering using DBSCAN
        coords = high_severity[['position_latitude', 'position_longitude']].values
        
        # Convert radius from meters to degrees (approximate)
        eps_degrees = cluster_radius_m / 111000  # 1 degree ≈ 111km
        
        clustering = DBSCAN(eps=eps_degrees, min_samples=min_events, metric='euclidean')
        high_severity['cluster_id'] = clustering.fit_predict(coords)
        
        # Filter out noise points (cluster_id == -1)
        clustered = high_severity[high_severity['cluster_id'] >= 0].copy()
        
        if clustered.empty:
            st.warning(f"No clusters formed with current parameters. Try increasing cluster radius or lowering min_events.")
            return pd.DataFrame()
        
        # Aggregate clusters into hotspots
        hotspots = []
        for cluster_id in clustered['cluster_id'].unique():
            cluster_points = clustered[clustered['cluster_id'] == cluster_id]
            
            hotspot = {
                'hotspot_id': f'sensor_{cluster_id}',
                'source': 'sensor',
                'center_lat': cluster_points['position_latitude'].mean(),
                'center_lng': cluster_points['position_longitude'].mean(),
                'event_count': len(cluster_points),
                'avg_severity': cluster_points['max_severity'].mean(),
                'max_severity': cluster_points['max_severity'].max(),
                'event_types': cluster_points['primary_event_type'].value_counts().to_dict(),
                'device_count': cluster_points['device_id'].nunique(),
                'raw_events': cluster_points.to_dict('records')
            }
            
            hotspots.append(hotspot)
        
        hotspots_df = pd.DataFrame(hotspots)
        
        # Sort by combined score (severity * frequency)
        hotspots_df['risk_score'] = hotspots_df['avg_severity'] * np.log1p(hotspots_df['event_count'])
        hotspots_df = hotspots_df.sort_values('risk_score', ascending=False).reset_index(drop=True)
        
        return hotspots_df
    
    def detect_perception_hotspots(self,
                                   cluster_radius_m: int = 50,
                                   min_reports: int = 3) -> pd.DataFrame:
        """
        Detect hotspots from perception reports using spatial clustering
        
        Args:
            cluster_radius_m: Radius for spatial clustering (meters)
            min_reports: Minimum reports required to form a hotspot
            
        Returns:
            DataFrame with perception hotspots
        """
        # Combine infrastructure and ride reports
        combined = []
        
        if not self.infra_df.empty:
            infra_subset = self.infra_df[['lat', 'lng', 'infrastructuretype', 'finalcomment']].copy()
            infra_subset['report_type'] = 'infrastructure'
            infra_subset['theme'] = infra_subset['infrastructuretype']
            infra_subset['comment'] = infra_subset['finalcomment']
            infra_subset['rating'] = None
            combined.append(infra_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating']])
        
        if not self.ride_df.empty:
            ride_subset = self.ride_df[['lat', 'lng', 'incidenttype', 'commentfinal', 'incidentrating']].copy()
            ride_subset['report_type'] = 'ride'
            ride_subset['theme'] = ride_subset['incidenttype']
            ride_subset['comment'] = ride_subset['commentfinal']
            ride_subset['rating'] = ride_subset['incidentrating']
            combined.append(ride_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating']])
        
        if not combined:
            return pd.DataFrame()
        
        all_reports = pd.concat(combined, ignore_index=True)
        
        # Spatial clustering
        coords = all_reports[['lat', 'lng']].values
        eps_degrees = cluster_radius_m / 111000
        
        clustering = DBSCAN(eps=eps_degrees, min_samples=min_reports, metric='euclidean')
        all_reports['cluster_id'] = clustering.fit_predict(coords)
        
        clustered = all_reports[all_reports['cluster_id'] >= 0].copy()
        
        if clustered.empty:
            return pd.DataFrame()
        
        # Aggregate into hotspots
        hotspots = []
        for cluster_id in clustered['cluster_id'].unique():
            cluster_points = clustered[clustered['cluster_id'] == cluster_id]
            
            # Get comments for sentiment analysis
            comments = cluster_points['comment'].dropna().tolist()
            
            hotspot = {
                'hotspot_id': f'perception_{cluster_id}',
                'source': 'perception',
                'center_lat': cluster_points['lat'].mean(),
                'center_lng': cluster_points['lng'].mean(),
                'report_count': len(cluster_points),
                'report_types': cluster_points['report_type'].value_counts().to_dict(),
                'themes': cluster_points['theme'].value_counts().to_dict(),
                'primary_theme': cluster_points['theme'].mode()[0] if not cluster_points['theme'].mode().empty else 'Unknown',
                'avg_rating': cluster_points['rating'].mean() if cluster_points['rating'].notna().any() else None,
                'comments': comments,
                'raw_reports': cluster_points.to_dict('records')
            }
            
            hotspots.append(hotspot)
        
        hotspots_df = pd.DataFrame(hotspots)
        
        # Calculate urgency score
        hotspots_df['urgency_score'] = hotspots_df.apply(
            lambda row: self._calculate_urgency(row['report_count'], row['avg_rating']),
            axis=1
        )
        hotspots_df = hotspots_df.sort_values('urgency_score', ascending=False).reset_index(drop=True)
        
        return hotspots_df
    
    def enrich_with_perception(self, sensor_hotspots: pd.DataFrame, radius_m: int = 25) -> pd.DataFrame:
        """
        Enrich sensor hotspots with nearby perception reports
        
        Args:
            sensor_hotspots: DataFrame with sensor hotspots
            radius_m: Matching radius in meters
            
        Returns:
            Enriched hotspots DataFrame
        """
        if sensor_hotspots.empty:
            return sensor_hotspots
        
        # Combine perception reports
        perception_combined = []
        
        if not self.infra_df.empty:
            infra_subset = self.infra_df[['lat', 'lng', 'infrastructuretype', 'finalcomment']].copy()
            infra_subset['type'] = 'infrastructure'
            infra_subset['theme'] = infra_subset['infrastructuretype']
            infra_subset['comment'] = infra_subset['finalcomment']
            perception_combined.append(infra_subset[['lat', 'lng', 'type', 'theme', 'comment']])
        
        if not self.ride_df.empty:
            ride_subset = self.ride_df[['lat', 'lng', 'incidenttype', 'commentfinal']].copy()
            ride_subset['type'] = 'ride'
            ride_subset['theme'] = ride_subset['incidenttype']
            ride_subset['comment'] = ride_subset['commentfinal']
            perception_combined.append(ride_subset[['lat', 'lng', 'type', 'theme', 'comment']])
        
        if not perception_combined:
            sensor_hotspots['perception_reports'] = [[] for _ in range(len(sensor_hotspots))]
            sensor_hotspots['perception_count'] = 0
            sensor_hotspots['perception_sentiment'] = None
            return sensor_hotspots
        
        all_perception = pd.concat(perception_combined, ignore_index=True)
        
        # Match perception to each hotspot
        enriched_hotspots = []
        
        for idx, hotspot in sensor_hotspots.iterrows():
            # Find nearby perception reports
            nearby = []
            for _, report in all_perception.iterrows():
                dist = haversine_distance(
                    hotspot['center_lat'], hotspot['center_lng'],
                    report['lat'], report['lng']
                )
                if dist <= radius_m:
                    nearby.append(report.to_dict())
            
            # Add perception data to hotspot
            hotspot_dict = hotspot.to_dict()
            hotspot_dict['perception_reports'] = nearby
            hotspot_dict['perception_count'] = len(nearby)
            
            # Run sentiment analysis if we have comments
            if nearby:
                comments = [r['comment'] for r in nearby if pd.notna(r.get('comment'))]
                if comments:
                    sentiment = analyze_perception_sentiment(comments)
                    hotspot_dict['perception_sentiment'] = sentiment
                else:
                    hotspot_dict['perception_sentiment'] = None
            else:
                hotspot_dict['perception_sentiment'] = None
            
            enriched_hotspots.append(hotspot_dict)
        
        return pd.DataFrame(enriched_hotspots)
    
    def enrich_with_sensor(self, perception_hotspots: pd.DataFrame, radius_m: int = 50) -> pd.DataFrame:
        """
        Enrich perception hotspots with nearby sensor events
        
        Args:
            perception_hotspots: DataFrame with perception hotspots
            radius_m: Matching radius in meters
            
        Returns:
            Enriched hotspots DataFrame
        """
        if perception_hotspots.empty:
            return perception_hotspots
        
        # Get abnormal sensor events
        abnormal = self.sensor_df[
            (self.sensor_df['is_abnormal_event'] == True) | 
            (self.sensor_df['is_abnormal_event'] == 'True')
        ].copy()
        
        if abnormal.empty:
            perception_hotspots['sensor_events'] = [[] for _ in range(len(perception_hotspots))]
            perception_hotspots['sensor_count'] = 0
            perception_hotspots['sensor_validation'] = 'no_data'
            return perception_hotspots
        
        # Match sensor events to each hotspot
        enriched_hotspots = []
        
        for idx, hotspot in perception_hotspots.iterrows():
            # Find nearby sensor events
            nearby = []
            for _, event in abnormal.iterrows():
                dist = haversine_distance(
                    hotspot['center_lat'], hotspot['center_lng'],
                    event['position_latitude'], event['position_longitude']
                )
                if dist <= radius_m:
                    nearby.append(event.to_dict())
            
            # Add sensor data to hotspot
            hotspot_dict = hotspot.to_dict()
            hotspot_dict['sensor_events'] = nearby
            hotspot_dict['sensor_count'] = len(nearby)
            
            # Validate with sensor data
            if nearby:
                validation = self._cross_validate(hotspot_dict, nearby)
                hotspot_dict['sensor_validation'] = validation
            else:
                hotspot_dict['sensor_validation'] = 'no_sensor_data'
            
            enriched_hotspots.append(hotspot_dict)
        
        return pd.DataFrame(enriched_hotspots)
    
    def _calculate_urgency(self, report_count: int, avg_rating: float = None) -> int:
        """Calculate urgency score (0-100)"""
        score = min(40, report_count * 5)  # Frequency component
        
        if avg_rating is not None:
            # Lower rating = higher urgency (ratings are 1-5, lower is worse)
            rating_score = (5 - avg_rating) * 10
            score += rating_score
        
        return min(100, int(score))
    
    def _cross_validate(self, perception_hotspot: Dict, sensor_events: List[Dict]) -> str:
        """
        Cross-validate perception reports with sensor data
        
        Returns: 'confirmed', 'partial', 'conflicted', or 'no_sensor_data'
        """
        if not sensor_events:
            return 'no_sensor_data'
        
        primary_theme = perception_hotspot.get('primary_theme', '').lower()
        
        # Count event types in sensor data
        event_types = {}
        for event in sensor_events:
            etype = event.get('primary_event_type', 'unknown')
            event_types[etype] = event_types.get(etype, 0) + 1
        
        # Check for matches
        matches = 0
        
        if 'close' in primary_theme or 'pass' in primary_theme:
            # Expect braking/swerving
            if event_types.get('hard_brake', 0) > 0 or event_types.get('swerve', 0) > 0:
                matches += 1
        
        if 'pothole' in primary_theme or 'surface' in primary_theme:
            # Expect pothole events
            if event_types.get('pothole', 0) > 0:
                matches += 1
        
        # General validation - any abnormal activity is somewhat confirmatory
        if len(sensor_events) >= 2:
            matches += 1
        
        if matches >= 2:
            return 'confirmed'
        elif matches == 1:
            return 'partial'
        else:
            return 'conflicted'
    
    def get_combined_hotspots(self,
                             sensor_params: Dict = None,
                             perception_params: Dict = None,
                             max_total_hotspots: int = 20) -> pd.DataFrame:
        """
        Get combined sensor and perception hotspots with smart filtering
        
        Args:
            sensor_params: Dict with sensor detection parameters
            perception_params: Dict with perception detection parameters
            max_total_hotspots: Maximum number of hotspots to return
            
        Returns:
            Combined and ranked DataFrame of hotspots
        """
        sensor_params = sensor_params or {}
        perception_params = perception_params or {}
        
        # Detect sensor hotspots
        sensor_hotspots = self.detect_sensor_hotspots(**sensor_params)
        
        # Enrich with perception
        if not sensor_hotspots.empty:
            sensor_hotspots = self.enrich_with_perception(
                sensor_hotspots, 
                radius_m=sensor_params.get('perception_radius_m', 25)
            )
        
        # Detect perception hotspots
        perception_hotspots = self.detect_perception_hotspots(**perception_params)
        
        # Enrich with sensor
        if not perception_hotspots.empty:
            perception_hotspots = self.enrich_with_sensor(
                perception_hotspots,
                radius_m=perception_params.get('sensor_radius_m', 50)
            )
        
        # Combine both sources
        combined = []
        
        if not sensor_hotspots.empty:
            combined.append(sensor_hotspots)
        
        if not perception_hotspots.empty:
            combined.append(perception_hotspots)
        
        if not combined:
            return pd.DataFrame()
        
        all_hotspots = pd.concat(combined, ignore_index=True)
        
        # Calculate final priority score
        all_hotspots['priority_score'] = all_hotspots.apply(self._calculate_priority, axis=1)
        
        # Sort by priority and limit to max
        all_hotspots = all_hotspots.sort_values('priority_score', ascending=False)
        all_hotspots = all_hotspots.head(max_total_hotspots)
        
        # Assign final hotspot IDs
        all_hotspots['final_hotspot_id'] = range(1, len(all_hotspots) + 1)
        
        return all_hotspots.reset_index(drop=True)
    
    def _calculate_priority(self, row: pd.Series) -> float:
        """
        Calculate priority score for ranking hotspots
        Combines sensor severity, perception urgency, and cross-validation
        """
        score = 0
        
        # Sensor component
        if row.get('source') == 'sensor':
            score += row.get('risk_score', 0) * 10
            # Bonus for perception confirmation
            if row.get('perception_count', 0) > 0:
                score += 20
                if row.get('perception_sentiment'):
                    severity = row['perception_sentiment'].get('severity', 'low')
                    severity_bonus = {'low': 5, 'medium': 10, 'high': 15, 'critical': 20}
                    score += severity_bonus.get(severity, 0)
        
        # Perception component
        elif row.get('source') == 'perception':
            score += row.get('urgency_score', 0)
            # Bonus for sensor validation
            validation = row.get('sensor_validation', 'no_sensor_data')
            validation_bonus = {'confirmed': 30, 'partial': 15, 'conflicted': 0, 'no_sensor_data': 5}
            score += validation_bonus.get(validation, 0)
            if row.get('sensor_count', 0) > 0:
                score += min(20, row['sensor_count'] * 2)
        
        return score
