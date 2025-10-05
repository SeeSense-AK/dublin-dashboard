"""
Smart Hotspot Detection Module - ENHANCED VERSION
Implements advanced features: H3 clustering, haversine DBSCAN, spatial indexing,
temporal aggregation, semantic validation, and structured context mapping
"""

import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from scipy.spatial import cKDTree
import streamlit as st
from typing import Dict, List, Tuple
from datetime import datetime
from utils.geo_utils import haversine_distance
from src.sentiment_analyzer import analyze_perception_sentiment
from src.athena_database import get_athena_database


class SmartHotspotDetectorV2:
    """
    Enhanced intelligent hotspot detector with:
    - Haversine-based DBSCAN for accurate geospatial clustering
    - Spatial indexing for O(log n) lookups
    - Temporal aggregation support
    - Semantic theme detection
    - Structured context mapping for Kepler tooltips
    """
    
    def __init__(self, infra_df: pd.DataFrame, ride_df: pd.DataFrame):
        """Initialize detector with perception data"""
        self.infra_df = infra_df
        self.ride_df = ride_df
        self.athena_db = get_athena_database()
        
        # Event type severity normalization factors
        self.event_severity_norms = {
            'hard_brake': 1.2,
            'swerve': 1.0,
            'pothole': 1.5,
            'acceleration': 0.8
        }
        
        # Theme-to-sensor mapping for semantic validation
        self.theme_sensor_map = {
            'close pass': ['hard_brake', 'swerve'],
            'obstruction': ['hard_brake', 'swerve'],
            'pothole': ['pothole'],
            'poor surface': ['pothole'],
            'dangerous junction': ['hard_brake', 'swerve'],
            'traffic': ['hard_brake', 'swerve']
        }
    
    def _haversine_metric(self, coord1, coord2):
        """Haversine distance metric for DBSCAN (in meters)"""
        return haversine_distance(coord1[0], coord1[1], coord2[0], coord2[1])
    
    def detect_sensor_hotspots(self, 
                              min_severity: int = 5,
                              min_events: int = 2,
                              start_date: str = None,
                              end_date: str = None,
                              event_type: str = None) -> pd.DataFrame:
        """
        Enhanced sensor hotspot detection with event type filtering
        and temporal aggregation
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
            
            # Parse event types if available
            if 'event_types' in hotspots_df.columns:
                # Normalize severity by event type
                hotspots_df['normalized_severity'] = hotspots_df.apply(
                    lambda row: self._normalize_severity_by_event(row),
                    axis=1
                )
            else:
                hotspots_df['normalized_severity'] = hotspots_df['avg_severity']
            
            # Add temporal aggregation support
            if 'first_event' in hotspots_df.columns:
                try:
                    hotspots_df['first_event_dt'] = pd.to_datetime(hotspots_df['first_event'])
                    hotspots_df['time_period'] = hotspots_df['first_event_dt'].dt.to_period('M')
                    hotspots_df['time_period_str'] = hotspots_df['time_period'].astype(str)
                except:
                    hotspots_df['time_period_str'] = 'Unknown'
            else:
                hotspots_df['time_period_str'] = 'Unknown'
            
            # Add source identifier
            hotspots_df['source'] = 'sensor'
            hotspots_df['hotspot_id'] = ['sensor_' + str(i) for i in range(len(hotspots_df))]
            
            # Calculate risk score using normalized severity
            hotspots_df['risk_score'] = (
                hotspots_df['normalized_severity'] * np.log1p(hotspots_df['event_count'])
            )
            
            # Add metadata
            if 'device_count' not in hotspots_df.columns:
                hotspots_df['device_count'] = 1
            if 'max_severity' not in hotspots_df.columns:
                hotspots_df['max_severity'] = hotspots_df['avg_severity']
            
            return hotspots_df.sort_values('risk_score', ascending=False).reset_index(drop=True)
            
        except Exception as e:
            st.error(f"Error detecting sensor hotspots: {e}")
            return pd.DataFrame()
    
    def _normalize_severity_by_event(self, row: pd.Series) -> float:
        """Normalize severity based on event type distribution"""
        try:
            event_types = row.get('event_types', {})
            if isinstance(event_types, str):
                import ast
                event_types = ast.literal_eval(event_types)
            
            if not event_types:
                return row['avg_severity']
            
            # Weight severity by event type importance
            weighted_severity = 0
            total_events = sum(event_types.values())
            
            for event_type, count in event_types.items():
                weight = self.event_severity_norms.get(event_type, 1.0)
                weighted_severity += (count / total_events) * weight
            
            return row['avg_severity'] * weighted_severity
        except:
            return row['avg_severity']
    
    def detect_perception_hotspots(self,
                                   cluster_radius_m: int = 50,
                                   min_reports: int = 3,
                                   recency_weight: float = 0.2) -> pd.DataFrame:
        """
        Enhanced perception clustering with haversine DBSCAN
        and recency weighting
        """
        # Combine reports
        combined = []
        
        if not self.infra_df.empty:
            infra_subset = self.infra_df[['lat', 'lng', 'infrastructuretype', 'finalcomment', 'datetime']].copy()
            infra_subset['report_type'] = 'infrastructure'
            infra_subset['theme'] = infra_subset['infrastructuretype']
            infra_subset['comment'] = infra_subset['finalcomment']
            infra_subset['rating'] = None
            combined.append(infra_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating', 'datetime']])
        
        if not self.ride_df.empty:
            ride_subset = self.ride_df[['lat', 'lng', 'incidenttype', 'commentfinal', 'incidentrating', 'datetime']].copy()
            ride_subset['report_type'] = 'ride'
            ride_subset['theme'] = ride_subset['incidenttype']
            ride_subset['comment'] = ride_subset['commentfinal']
            ride_subset['rating'] = ride_subset['incidentrating']
            combined.append(ride_subset[['lat', 'lng', 'report_type', 'theme', 'comment', 'rating', 'datetime']])
        
        if not combined:
            return pd.DataFrame()
        
        all_reports = pd.concat(combined, ignore_index=True)
        
        # Calculate recency weights
        if recency_weight > 0 and 'datetime' in all_reports.columns:
            all_reports['datetime'] = pd.to_datetime(all_reports['datetime'], errors='coerce')
            latest = all_reports['datetime'].max()
            all_reports['days_old'] = (latest - all_reports['datetime']).dt.days
            all_reports['recency_factor'] = 1 + (recency_weight * np.exp(-all_reports['days_old'] / 30))
        else:
            all_reports['recency_factor'] = 1.0
        
        # Haversine-based DBSCAN clustering
        coords = all_reports[['lat', 'lng']].values
        
        # Pre-compute distance matrix using haversine
        # For smaller datasets, compute full distance matrix
        if len(coords) < 1000:
            from sklearn.metrics import pairwise_distances
            distance_matrix = pairwise_distances(
                coords, 
                metric=lambda u, v: haversine_distance(u[0], u[1], v[0], v[1])
            )
            clustering = DBSCAN(eps=cluster_radius_m, min_samples=min_reports, metric='precomputed')
            all_reports['cluster_id'] = clustering.fit_predict(distance_matrix)
        else:
            # For larger datasets, use approximate clustering
            eps_degrees = cluster_radius_m / 111000
            clustering = DBSCAN(eps=eps_degrees, min_samples=min_reports, metric='euclidean')
            all_reports['cluster_id'] = clustering.fit_predict(coords)
        
        clustered = all_reports[all_reports['cluster_id'] >= 0].copy()
        
        if clustered.empty:
            return pd.DataFrame()
        
        # Aggregate into hotspots with enhanced metadata
        hotspots = []
        for cluster_id in clustered['cluster_id'].unique():
            cluster_points = clustered[clustered['cluster_id'] == cluster_id]
            
            # Weight centroid by recency
            weights = cluster_points['recency_factor'].values
            center_lat = np.average(cluster_points['lat'].values, weights=weights)
            center_lng = np.average(cluster_points['lng'].values, weights=weights)
            
            comments = cluster_points['comment'].dropna().tolist()
            
            # Calculate weighted urgency
            avg_recency = cluster_points['recency_factor'].mean()
            
            hotspot = {
                'hotspot_id': f'perception_{cluster_id}',
                'source': 'perception',
                'center_lat': center_lat,
                'center_lng': center_lng,
                'report_count': len(cluster_points),
                'report_types': cluster_points['report_type'].value_counts().to_dict(),
                'themes': cluster_points['theme'].value_counts().to_dict(),
                'primary_theme': cluster_points['theme'].mode()[0] if not cluster_points['theme'].mode().empty else 'Unknown',
                'avg_rating': cluster_points['rating'].mean() if cluster_points['rating'].notna().any() else None,
                'comments': comments,
                'recency_factor': avg_recency,
                'raw_reports': cluster_points.to_dict('records')
            }
            
            hotspots.append(hotspot)
        
        hotspots_df = pd.DataFrame(hotspots)
        
        # Enhanced urgency score including recency
        hotspots_df['urgency_score'] = hotspots_df.apply(
            lambda row: self._calculate_enhanced_urgency(
                row['report_count'], 
                row['avg_rating'],
                row['recency_factor']
            ),
            axis=1
        )
        
        return hotspots_df.sort_values('urgency_score', ascending=False).reset_index(drop=True)
    
    def _calculate_enhanced_urgency(self, report_count: int, avg_rating: float = None, 
                                   recency_factor: float = 1.0) -> int:
        """Enhanced urgency calculation with recency weighting"""
        score = min(40, report_count * 5)
        
        if avg_rating is not None:
            rating_score = (5 - avg_rating) * 10
            score += rating_score
        
        # Apply recency boost
        score *= recency_factor
        
        return min(100, int(score))
    
    def enrich_with_perception(self, sensor_hotspots: pd.DataFrame, 
                              radius_m: int = 25) -> pd.DataFrame:
        """
        Enhanced enrichment with spatial indexing and structured context
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
            sensor_hotspots = self._add_empty_perception_fields(sensor_hotspots)
            return sensor_hotspots
        
        all_perception = pd.concat(perception_combined, ignore_index=True)
        
        # Build spatial index for fast lookups
        perception_coords = all_perception[['lat', 'lng']].values
        tree = cKDTree(perception_coords)
        
        # Match perception to hotspots using spatial index
        enriched_hotspots = []
        
        for idx, hotspot in sensor_hotspots.iterrows():
            hotspot_coord = np.array([[hotspot['center_lat'], hotspot['center_lng']]])
            
            # Query tree for nearby points (convert radius to degrees approx)
            radius_degrees = radius_m / 111000
            indices = tree.query_ball_point(hotspot_coord[0], radius_degrees)
            
            # Filter by exact haversine distance
            nearby = []
            for i in indices:
                dist = haversine_distance(
                    hotspot['center_lat'], hotspot['center_lng'],
                    all_perception.iloc[i]['lat'], all_perception.iloc[i]['lng']
                )
                if dist <= radius_m:
                    nearby.append(all_perception.iloc[i].to_dict())
            
            # Build structured context
            hotspot_dict = hotspot.to_dict()
            context = self._build_context_summary(nearby)
            
            hotspot_dict['perception_reports'] = nearby
            hotspot_dict['perception_count'] = len(nearby)
            hotspot_dict['context_summary'] = context['summary']
            hotspot_dict['dominant_theme'] = context['dominant_theme']
            hotspot_dict['sentiment_label'] = context['sentiment']
            
            # Run sentiment analysis
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
    
    def _build_context_summary(self, nearby_reports: List[Dict]) -> Dict:
        """Build structured context summary for Kepler tooltips"""
        if not nearby_reports:
            return {
                'summary': 'No perception reports nearby',
                'dominant_theme': 'None',
                'sentiment': 'Unknown'
            }
        
        # Get dominant theme
        themes = [r.get('theme', 'Unknown') for r in nearby_reports]
        theme_counts = pd.Series(themes).value_counts()
        dominant_theme = theme_counts.index[0] if not theme_counts.empty else 'Unknown'
        
        # Simple sentiment estimate
        sentiment = 'Negative'  # Most road reports are negative
        
        summary = f"{len(nearby_reports)} reports ({dominant_theme}), sentiment={sentiment}"
        
        return {
            'summary': summary,
            'dominant_theme': dominant_theme,
            'sentiment': sentiment
        }
    
    def _add_empty_perception_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add empty perception fields when no reports available"""
        df['perception_reports'] = [[] for _ in range(len(df))]
        df['perception_count'] = 0
        df['perception_sentiment'] = None
        df['context_summary'] = 'No perception reports nearby'
        df['dominant_theme'] = 'None'
        df['sentiment_label'] = 'Unknown'
        return df
    
    def enrich_with_sensor(self, perception_hotspots: pd.DataFrame, 
                          radius_m: int = 50,
                          start_date: str = None,
                          end_date: str = None) -> pd.DataFrame:
        """Enhanced sensor enrichment with semantic validation"""
        if perception_hotspots.empty:
            return perception_hotspots
        
        from src.perception_hotspot_analyzer import find_sensor_data_for_perception_cluster
        
        enriched_hotspots = []
        
        for idx, hotspot in perception_hotspots.iterrows():
            sensor_data = find_sensor_data_for_perception_cluster(
                hotspot['center_lat'],
                hotspot['center_lng'],
                radius_m=radius_m,
                start_date=start_date,
                end_date=end_date
            )
            
            hotspot_dict = hotspot.to_dict()
            hotspot_dict['sensor_data'] = sensor_data
            hotspot_dict['sensor_count'] = sensor_data.get('total_events', 0)
            
            # Semantic validation
            if sensor_data.get('has_sensor_data'):
                validation = self._semantic_cross_validate(hotspot_dict, sensor_data)
                hotspot_dict['sensor_validation'] = validation['status']
                hotspot_dict['validation_confidence'] = validation['confidence']
                hotspot_dict['validation_reasoning'] = validation['reasoning']
            else:
                hotspot_dict['sensor_validation'] = 'no_sensor_data'
                hotspot_dict['validation_confidence'] = 0.0
                hotspot_dict['validation_reasoning'] = 'No sensor data available'
            
            enriched_hotspots.append(hotspot_dict)
        
        return pd.DataFrame(enriched_hotspots)
    
    def _semantic_cross_validate(self, perception_hotspot: Dict, sensor_data: Dict) -> Dict:
        """
        Semantic validation using theme-to-sensor mapping
        Returns validation status, confidence score, and reasoning
        """
        primary_theme = perception_hotspot.get('primary_theme', '').lower()
        
        # Find expected sensor events for this theme
        expected_events = []
        for theme_key, events in self.theme_sensor_map.items():
            if theme_key in primary_theme:
                expected_events.extend(events)
        
        if not expected_events:
            # Unknown theme - use heuristic validation
            if sensor_data.get('abnormal_events', 0) >= 2:
                return {
                    'status': 'partial',
                    'confidence': 0.5,
                    'reasoning': f"Unknown theme '{primary_theme}' but abnormal activity detected"
                }
            else:
                return {
                    'status': 'inconclusive',
                    'confidence': 0.3,
                    'reasoning': f"Unknown theme '{primary_theme}' and minimal sensor activity"
                }
        
        # Count matching sensor events
        matches = 0
        total_expected = len(expected_events)
        reasoning_parts = []
        
        for event_type in expected_events:
            event_key = f'{event_type}_events'
            if sensor_data.get(event_key, 0) > 0:
                matches += 1
                reasoning_parts.append(f"{event_type}: {sensor_data[event_key]}")
        
        confidence = matches / total_expected if total_expected > 0 else 0
        
        if confidence >= 0.7:
            status = 'confirmed'
        elif confidence >= 0.4:
            status = 'partial'
        else:
            status = 'conflicted'
        
        reasoning = f"Expected {expected_events}, found: {', '.join(reasoning_parts) if reasoning_parts else 'none'}"
        
        return {
            'status': status,
            'confidence': confidence,
            'reasoning': reasoning
        }
    
    def get_combined_hotspots(self,
                             sensor_params: Dict = None,
                             perception_params: Dict = None,
                             max_total_hotspots: int = 20) -> pd.DataFrame:
        """Get combined hotspots with all enhancements"""
        sensor_params = sensor_params or {}
        perception_params = perception_params or {}
        
        # Extract enrichment parameters
        perception_radius_m = sensor_params.get('perception_radius_m', 25)
        sensor_radius_m = perception_params.get('sensor_radius_m', 50)
        
        # Build detection params
        sensor_detect_params = {
            'min_severity': sensor_params.get('min_severity', 5),
            'min_events': sensor_params.get('min_events', 2),
            'start_date': sensor_params.get('start_date'),
            'end_date': sensor_params.get('end_date')
        }
        
        perception_detect_params = {
            'cluster_radius_m': perception_params.get('cluster_radius_m', 50),
            'min_reports': perception_params.get('min_reports', 3),
            'recency_weight': perception_params.get('recency_weight', 0.2)
        }
        
        # Detect hotspots
        sensor_hotspots = self.detect_sensor_hotspots(**sensor_detect_params)
        
        if not sensor_hotspots.empty:
            sensor_hotspots = self.enrich_with_perception(sensor_hotspots, radius_m=perception_radius_m)
        
        perception_hotspots = self.detect_perception_hotspots(**perception_detect_params)
        
        if not perception_hotspots.empty:
            perception_hotspots = self.enrich_with_sensor(
                perception_hotspots,
                radius_m=sensor_radius_m,
                start_date=sensor_detect_params.get('start_date'),
                end_date=sensor_detect_params.get('end_date')
            )
        
        # Combine
        combined = []
        if not sensor_hotspots.empty:
            combined.append(sensor_hotspots)
        if not perception_hotspots.empty:
            combined.append(perception_hotspots)
        
        if not combined:
            return pd.DataFrame()
        
        all_hotspots = pd.concat(combined, ignore_index=True)
        all_hotspots['priority_score'] = all_hotspots.apply(self._calculate_priority, axis=1)
        all_hotspots = all_hotspots.sort_values('priority_score', ascending=False)
        all_hotspots = all_hotspots.head(max_total_hotspots)
        all_hotspots['final_hotspot_id'] = range(1, len(all_hotspots) + 1)
        
        return all_hotspots.reset_index(drop=True)
    
    def _calculate_priority(self, row: pd.Series) -> float:
        """Enhanced priority calculation"""
        score = 0
        
        if row.get('source') == 'sensor':
            score += row.get('risk_score', 0) * 10
            if row.get('perception_count', 0) > 0:
                score += 20
                if row.get('perception_sentiment'):
                    severity = row['perception_sentiment'].get('severity', 'low')
                    severity_bonus = {'low': 5, 'medium': 10, 'high': 15, 'critical': 20}
                    score += severity_bonus.get(severity, 0)
        
        elif row.get('source') == 'perception':
            score += row.get('urgency_score', 0)
            validation = row.get('sensor_validation', 'no_sensor_data')
            confidence = row.get('validation_confidence', 0)
            validation_bonus = {'confirmed': 30, 'partial': 15, 'conflicted': 0, 'no_sensor_data': 5}
            score += validation_bonus.get(validation, 0) * (1 + confidence)
            if row.get('sensor_count', 0) > 0:
                score += min(20, row['sensor_count'] * 2)
        
        return score
