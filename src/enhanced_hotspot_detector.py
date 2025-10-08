# src/enhanced_hotspot_detector.py
"""
Enhanced hotspot detection using accelerometer data and DBSCAN clustering
"""
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import streamlit as st
from typing import Dict, List
from src.athena_database import get_athena_database

class EnhancedHotspotDetector:
    """
    Enhanced hotspot detector using accelerometer data for better clustering
    """
    
    def __init__(self):
        self.db = get_athena_database()
    
    def detect_hotspots_with_accelerometer(self, 
                                          start_date: str,
                                          end_date: str,
                                          min_events: int = 3,
                                          severity_threshold: int = 2,
                                          top_n: int = 20) -> pd.DataFrame:
        """
        Detect hotspots using DBSCAN with accelerometer data
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            min_events: Minimum events to form a hotspot
            severity_threshold: Minimum severity threshold
            top_n: Number of top hotspots to return
        
        Returns:
            DataFrame with top N hotspots
        """
        
        # Query sensor data for the date range
        query = f"""
        SELECT 
            lat,
            lng,
            max_severity,
            primary_event_type,
            timestamp,
            device_id,
            speed_kmh,
            peak_x,
            peak_y,
            peak_z,
            severity_x,
            severity_y,
            severity_z
        FROM spinovate_production.spinovate_production_optimised_v2
        WHERE is_abnormal_event = true 
            AND max_severity >= {severity_threshold}
            AND lat IS NOT NULL 
            AND lng IS NOT NULL
            AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'
        """
        
        try:
            events_df = pd.read_sql(query, self.db.conn)
            
            if events_df.empty:
                return pd.DataFrame()
            
            # Prepare features for DBSCAN: lat, lng, and accelerometer data
            features = events_df[['lat', 'lng', 'peak_x', 'peak_y', 'peak_z']].copy()
            
            # Handle any null values
            features = features.fillna(0)
            
            # Normalize features (important for DBSCAN with mixed units)
            scaler = StandardScaler()
            
            # Scale lat/lng separately (geographic data)
            geo_scaled = scaler.fit_transform(features[['lat', 'lng']])
            
            # Scale accelerometer data separately
            accel_scaled = scaler.fit_transform(features[['peak_x', 'peak_y', 'peak_z']])
            
            # Combine with weights (prioritize geographic clustering but consider accelerometer)
            # 70% weight to geography, 30% to accelerometer pattern
            combined_features = np.hstack([
                geo_scaled * 0.7,
                accel_scaled * 0.3
            ])
            
            # Apply DBSCAN
            # eps tuned for combined feature space
            clustering = DBSCAN(eps=0.3, min_samples=min_events, metric='euclidean')
            events_df['cluster_id'] = clustering.fit_predict(combined_features)
            
            # Filter out noise (cluster_id = -1)
            clustered_events = events_df[events_df['cluster_id'] >= 0].copy()
            
            if clustered_events.empty:
                return pd.DataFrame()
            
            # Aggregate clusters into hotspots
            hotspots = self._aggregate_clusters(clustered_events, start_date, end_date)
            
            # Calculate risk scores and get top N
            hotspots['risk_score'] = hotspots.apply(self._calculate_risk_score, axis=1)
            hotspots = hotspots.nlargest(top_n, 'risk_score').reset_index(drop=True)
            
            # Assign hotspot IDs
            hotspots['hotspot_id'] = range(1, len(hotspots) + 1)
            
            return hotspots
            
        except Exception as e:
            st.error(f"Error detecting hotspots: {e}")
            return pd.DataFrame()
    
    def _aggregate_clusters(self, clustered_events: pd.DataFrame, 
                           start_date: str, end_date: str) -> pd.DataFrame:
        """
        Aggregate events by cluster to create hotspot summaries
        Uses MEDOID (most central actual event) instead of centroid to ensure point is on road
        """
        hotspots = []
        
        for cluster_id in clustered_events['cluster_id'].unique():
            cluster_data = clustered_events[clustered_events['cluster_id'] == cluster_id]
            
            # Calculate MEDOID instead of centroid
            # Find the event that's closest to the center of all events
            center_lat = cluster_data['lat'].mean()
            center_lng = cluster_data['lng'].mean()
            
            # Calculate distance of each event to the center
            from utils.geo_utils import haversine_distance
            
            cluster_data_copy = cluster_data.copy()
            cluster_data_copy['dist_to_center'] = cluster_data_copy.apply(
                lambda row: haversine_distance(center_lat, center_lng, row['lat'], row['lng']),
                axis=1
            )
            
            # Get the event closest to center (medoid)
            medoid_event = cluster_data_copy.loc[cluster_data_copy['dist_to_center'].idxmin()]
            
            # Use medoid's actual coordinates (guaranteed to be on road!)
            hotspot_lat = medoid_event['lat']
            hotspot_lng = medoid_event['lng']
            
            # Calculate event type distribution
            event_types = cluster_data['primary_event_type'].value_counts()
            event_distribution = (event_types / len(cluster_data) * 100).to_dict()
            
            hotspot = {
                'cluster_id': cluster_id,
                'center_lat': hotspot_lat,  # Using medoid coordinates
                'center_lng': hotspot_lng,  # Using medoid coordinates
                'event_count': len(cluster_data),
                'unique_devices': cluster_data['device_id'].nunique(),
                'avg_severity': cluster_data['max_severity'].mean(),
                'max_severity': cluster_data['max_severity'].max(),
                'avg_speed': cluster_data['speed_kmh'].mean(),
                'event_distribution': event_distribution,
                'event_types_raw': event_types.to_dict(),
                'avg_peak_x': cluster_data['peak_x'].mean(),
                'avg_peak_y': cluster_data['peak_y'].mean(),
                'avg_peak_z': cluster_data['peak_z'].mean(),
                'first_event': cluster_data['timestamp'].min(),
                'last_event': cluster_data['timestamp'].max(),
                'date_range': f"{start_date} to {end_date}",
                'medoid_event_id': medoid_event.name,  # Store which event was chosen as center
                'radius_m': cluster_data_copy['dist_to_center'].max()  # Cluster radius
            }
            
            hotspots.append(hotspot)
        
        return pd.DataFrame(hotspots)
    
    def _calculate_risk_score(self, row: pd.Series) -> float:
        """
        Calculate combined risk score: events × severity
        """
        return row['event_count'] * row['avg_severity']
    
    def find_perception_reports_all_time(self, 
                                        hotspot_lat: float, 
                                        hotspot_lng: float,
                                        infra_df: pd.DataFrame,
                                        ride_df: pd.DataFrame,
                                        radius_m: int = 100) -> Dict:
        """
        Find ALL perception reports near a hotspot (not limited by date)
        
        Args:
            hotspot_lat: Hotspot latitude
            hotspot_lng: Hotspot longitude
            infra_df: Infrastructure reports dataframe
            ride_df: Ride reports dataframe
            radius_m: Search radius in meters
        
        Returns:
            Dict with perception reports and summary
        """
        from utils.geo_utils import haversine_distance
        
        # Find nearby infrastructure reports
        infra_nearby = []
        if not infra_df.empty:
            for idx, report in infra_df.iterrows():
                dist = haversine_distance(
                    hotspot_lat, hotspot_lng,
                    report['lat'], report['lng']
                )
                if dist <= radius_m:
                    infra_nearby.append({
                        'type': 'infrastructure',
                        'theme': report.get('infrastructuretype', 'Unknown'),
                        'comment': report.get('finalcomment', ''),
                        'date': report.get('date', ''),
                        'distance_m': dist
                    })
        
        # Find nearby ride reports
        ride_nearby = []
        if not ride_df.empty:
            for idx, report in ride_df.iterrows():
                dist = haversine_distance(
                    hotspot_lat, hotspot_lng,
                    report['lat'], report['lng']
                )
                if dist <= radius_m:
                    ride_nearby.append({
                        'type': 'ride',
                        'theme': report.get('incidenttype', 'Unknown'),
                        'comment': report.get('commentfinal', ''),
                        'rating': report.get('incidentrating', None),
                        'date': report.get('date', ''),
                        'distance_m': dist
                    })
        
        # Combine
        all_reports = infra_nearby + ride_nearby
        
        # Extract themes
        themes = {}
        for report in all_reports:
            theme = report['theme']
            themes[theme] = themes.get(theme, 0) + 1
        
        # Extract comments
        comments = [r['comment'] for r in all_reports if r['comment'] and len(str(r['comment']).strip()) > 0]
        
        return {
            'total_reports': len(all_reports),
            'infra_reports': len(infra_nearby),
            'ride_reports': len(ride_nearby),
            'themes': themes,
            'comments': comments,
            'all_reports': all_reports
        }
    
    def analyze_hotspot_with_groq(self, 
                                  hotspot: Dict, 
                                  perception_data: Dict) -> Dict:
        """
        Use Groq to analyze and paint a picture of what's happening at the hotspot
        
        Args:
            hotspot: Hotspot data including sensor info
            perception_data: Perception reports near hotspot
        
        Returns:
            Dict with Groq analysis
        """
        from src.sentiment_analyzer import get_groq_client
        
        client = get_groq_client()
        
        if not client:
            # Fallback analysis
            return self._fallback_analysis(hotspot, perception_data)
        
        # Build context for Groq
        event_distribution_text = "\n".join([
            f"- {event_type}: {hotspot['event_types_raw'][event_type]} events ({pct:.1f}%)"
            for event_type, pct in hotspot['event_distribution'].items()
        ])
        
        sensor_summary = f"""
Sensor Data Summary:
- Total Events: {hotspot['event_count']}
- Average Severity: {hotspot['avg_severity']:.1f}/10
- Max Severity: {hotspot['max_severity']}/10
- Unique Cyclists: {hotspot['unique_devices']}
- Average Speed: {hotspot['avg_speed']:.1f} km/h

Event Distribution:
{event_distribution_text}

Accelerometer Readings:
- Peak X (lateral): {hotspot['avg_peak_x']:.2f}
- Peak Y (forward/back): {hotspot['avg_peak_y']:.2f}
- Peak Z (vertical): {hotspot['avg_peak_z']:.2f}
"""
        
        perception_summary = f"""
User Perception Reports ({perception_data['total_reports']} total):
- Infrastructure Reports: {perception_data['infra_reports']}
- Ride Reports: {perception_data['ride_reports']}

Reported Issues:
"""
        for theme, count in perception_data['themes'].items():
            perception_summary += f"- {theme}: {count} reports\n"
        
        perception_summary += "\nUser Comments:\n"
        for idx, comment in enumerate(perception_data['comments'][:10], 1):
            perception_summary += f"{idx}. \"{comment}\"\n"
        
        prompt = f"""You are a road safety analyst. Analyze this cycling safety hotspot and paint a clear picture of what's happening there. Use BOTH sensor data and user reports to tell the story.

{sensor_summary}

{perception_summary}

Your analysis should:
1. Describe what's actually happening at this location (combine sensor patterns with user experiences)
2. Explain how sensor data and perception reports relate to each other
3. Paint a vivid picture that helps understand the safety issues
4. Be objective and factual - NO recommendations or solutions

Provide a 2-3 paragraph analysis that gives decision-makers a complete understanding of the situation.
"""
        
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
            
            analysis_text = response.choices[0].message.content
            
            return {
                'analysis': analysis_text,
                'method': 'groq_ai',
                'model': 'llama-3.3-70b-versatile'
            }
            
        except Exception as e:
            st.warning(f"Groq analysis failed: {e}, using fallback")
            return self._fallback_analysis(hotspot, perception_data)
    
    def _fallback_analysis(self, hotspot: Dict, perception_data: Dict) -> Dict:
        """
        Fallback analysis when Groq is unavailable
        """
        # Get dominant event type
        top_event = max(hotspot['event_distribution'].items(), key=lambda x: x[1])
        event_type, pct = top_event
        
        # Get dominant perception theme
        if perception_data['themes']:
            top_theme = max(perception_data['themes'].items(), key=lambda x: x[1])
            theme, theme_count = top_theme
        else:
            theme = "No perception reports"
            theme_count = 0
        
        analysis = f"""This location shows {hotspot['event_count']} abnormal cycling events with an average severity of {hotspot['avg_severity']:.1f}/10. The dominant event type is {event_type} ({pct:.1f}% of events), suggesting specific road conditions or traffic patterns requiring attention.

The accelerometer data reveals peak vertical forces of {hotspot['avg_peak_z']:.2f}g, indicating the physical impact cyclists experience at this location. """
        
        if perception_data['total_reports'] > 0:
            analysis += f"""{perception_data['total_reports']} user reports corroborate these findings, with {theme_count} reports specifically mentioning {theme}. The convergence of sensor data and user experiences confirms this as a genuine safety concern."""
        else:
            analysis += """No user perception reports are available for this location, making the sensor data the primary evidence of safety issues."""
        
        return {
            'analysis': analysis,
            'method': 'fallback',
            'model': 'rule_based'
        }


def create_complete_hotspots(start_date: str, end_date: str,
                             infra_df: pd.DataFrame, ride_df: pd.DataFrame,
                             min_events: int = 3, top_n: int = 20) -> pd.DataFrame:
    """
    Main function: Create complete hotspots with sensor + perception + Groq analysis
    
    Args:
        start_date: Start date for sensor data
        end_date: End date for sensor data
        infra_df: Infrastructure reports (all time)
        ride_df: Ride reports (all time)
        min_events: Minimum events per hotspot
        top_n: Number of hotspots to return
    
    Returns:
        DataFrame with complete hotspot analysis
    """
    detector = EnhancedHotspotDetector()
    
    # Step 1: Detect hotspots from sensor data (date filtered)
    hotspots = detector.detect_hotspots_with_accelerometer(
        start_date=start_date,
        end_date=end_date,
        min_events=min_events,
        top_n=top_n
    )
    
    if hotspots.empty:
        return pd.DataFrame()
    
    # Step 2: For each hotspot, find perception reports (all time) and analyze
    enriched_hotspots = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, hotspot in hotspots.iterrows():
        status_text.text(f"Analyzing hotspot {idx + 1}/{len(hotspots)}...")
        
        # Find perception reports (100m radius, all time)
        perception_data = detector.find_perception_reports_all_time(
            hotspot['center_lat'],
            hotspot['center_lng'],
            infra_df,
            ride_df,
            radius_m=100
        )
        
        # Get Groq analysis
        groq_analysis = detector.analyze_hotspot_with_groq(
            hotspot.to_dict(),
            perception_data
        )
        
        # Combine everything
        enriched_hotspot = hotspot.to_dict()
        enriched_hotspot['perception_data'] = perception_data
        enriched_hotspot['groq_analysis'] = groq_analysis
        enriched_hotspot['urgency_score'] = calculate_urgency_score(
            enriched_hotspot['risk_score'],
            perception_data['total_reports'],
            hotspot['avg_severity']
        )
        
        enriched_hotspots.append(enriched_hotspot)
        
        progress_bar.progress((idx + 1) / len(hotspots))
    
    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame(enriched_hotspots)


def calculate_urgency_score(risk_score: float, perception_count: int, avg_severity: float) -> int:
    """
    Calculate urgency score (0-100) based on risk score, perception reports, and severity
    """
    # Base score from risk
    base_score = min(50, risk_score / 10)
    
    # Perception boost
    perception_boost = min(30, perception_count * 3)
    
    # Severity boost
    severity_boost = min(20, avg_severity * 2)
    
    return int(base_score + perception_boost + severity_boost)