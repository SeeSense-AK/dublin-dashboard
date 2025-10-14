"""
Optimized AWS Athena Database Connection
Now using pre-aggregated tables: hotspots_daily_v2 and usage_trends_daily
"""
import pandas as pd
import streamlit as st
from pyathena import connect
import warnings
import os
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')


class AthenaCyclingSafetyDB:
    def __init__(self):
        """Initialize Athena connection"""
        try:
            aws_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
            s3_staging = os.getenv('AWS_S3_STAGING_DIR', 's3://seesense-air/summit2/spinovate-replay/athena-results/')
            region = os.getenv('AWS_REGION', 'eu-west-1')
            
            if not aws_key or not aws_secret:
                raise Exception("AWS credentials not found in .env file!")
            
            self.conn = connect(
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                s3_staging_dir=s3_staging,
                region_name=region
            )
            print("✅ Connected to Athena")
            
        except Exception as e:
            raise Exception(f"❌ Failed to connect to Athena: {e}")
    
    def get_dashboard_metrics(self) -> dict:
        """Get key metrics for dashboard overview - OPTIMIZED with fallback"""
        
        # Try optimized table first
        query_optimized = """
        SELECT 
            SUM(total_readings) as total_readings,
            MAX(unique_users) as unique_devices,
            SUM(abnormal_events) as abnormal_events,
            AVG(avg_speed) as avg_speed,
            MAX(date) as latest_reading,
            MIN(date) as earliest_reading
        FROM spinovate_production.usage_trends_daily
        """
        
        # Fallback to raw table
        query_fallback = """
        SELECT 
            COUNT(*) as total_readings,
            COUNT(DISTINCT device_id) as unique_devices,
            COUNT(CASE WHEN is_abnormal_event THEN 1 END) as abnormal_events,
            AVG(speed_kmh) as avg_speed,
            MAX(timestamp) as latest_reading,
            MIN(timestamp) as earliest_reading
        FROM spinovate_production.spinovate_production_optimised_v2
        """
        
        try:
            df = pd.read_sql(query_optimized, self.conn)
            result = df.iloc[0]
            
            # Check if optimized table has data
            if pd.isna(result['total_readings']) or result['total_readings'] == 0:
                print("⚠️ Optimized table empty, using fallback...")
                df = pd.read_sql(query_fallback, self.conn)
                result = df.iloc[0]
            
            return {
                'total_readings': int(result['total_readings']) if result['total_readings'] else 0,
                'unique_devices': int(result['unique_devices']) if result['unique_devices'] else 0,
                'abnormal_events': int(result['abnormal_events']) if result['abnormal_events'] else 0,
                'avg_speed': round(float(result['avg_speed']), 1) if result['avg_speed'] else 0,
                'latest_reading': result['latest_reading'],
                'earliest_reading': result['earliest_reading']
            }
        except Exception as e:
            print(f"⚠️ Error with optimized query, trying fallback: {e}")
            # Try fallback
            try:
                df = pd.read_sql(query_fallback, self.conn)
                result = df.iloc[0]
                return {
                    'total_readings': int(result['total_readings']),
                    'unique_devices': int(result['unique_devices']),
                    'abnormal_events': int(result['abnormal_events']),
                    'avg_speed': round(float(result['avg_speed']), 1) if result['avg_speed'] else 0,
                    'latest_reading': result['latest_reading'],
                    'earliest_reading': result['earliest_reading']
                }
            except Exception as e2:
                print(f"❌ Both queries failed: {e2}")
                return {
                    'total_readings': 0,
                    'unique_devices': 0,
                    'abnormal_events': 0,
                    'avg_speed': 0,
                    'latest_reading': None,
                    'earliest_reading': None
                }
    
    def detect_sensor_hotspots(self, min_events: int = 3, severity_threshold: int = 2, 
                              start_date: str = None, end_date: str = None,
                              radius_m: int = 50) -> pd.DataFrame:
        """
        Detect hotspots - OPTIMIZED with fallback to raw table
        Filters by actual event dates (first_event/last_event), not analysis_date
        """
        
        # Build date filter for ACTUAL EVENT DATES
        date_filter_opt = ""
        date_filter_raw = ""
        if start_date and end_date:
            # Filter hotspots where events happened in this date range
            date_filter_opt = f"""AND (
                (first_event >= TIMESTAMP '{start_date}' AND first_event <= TIMESTAMP '{end_date}')
                OR (last_event >= TIMESTAMP '{start_date}' AND last_event <= TIMESTAMP '{end_date}')
                OR (first_event <= TIMESTAMP '{start_date}' AND last_event >= TIMESTAMP '{end_date}')
            )"""
            date_filter_raw = f"AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'"
        elif start_date:
            date_filter_opt = f"AND last_event >= TIMESTAMP '{start_date}'"
            date_filter_raw = f"AND timestamp >= TIMESTAMP '{start_date}'"
        elif end_date:
            date_filter_opt = f"AND first_event <= TIMESTAMP '{end_date}'"
            date_filter_raw = f"AND timestamp <= TIMESTAMP '{end_date}'"
        
        # Try optimized table first
        query_optimized = f"""
        SELECT 
            lat,
            lng,
            event_count,
            avg_severity as severity_score,
            max_severity,
            first_event,
            last_event,
            unique_devices,
            avg_speed,
            event_distribution as event_types,
            peak_accel_x,
            peak_accel_y,
            peak_accel_z,
            risk_score,
            'sensor_based' as hotspot_type
        FROM spinovate_production.hotspots_daily_v2
        WHERE event_count >= {min_events}
            AND avg_severity >= {severity_threshold}
            {date_filter_opt}
        ORDER BY risk_score DESC
        LIMIT 100
        """
        
        # Fallback to raw table with clustering
        query_fallback = f"""
        WITH abnormal_events AS (
            SELECT 
                lat,
                lng,
                max_severity,
                primary_event_type,
                timestamp,
                device_id,
                speed_kmh
            FROM spinovate_production.spinovate_production_optimised_v2
            WHERE is_abnormal_event = true 
                AND max_severity >= {severity_threshold}
                AND lat IS NOT NULL 
                AND lng IS NOT NULL
                {date_filter_raw}
        ),
        grid_clusters AS (
            SELECT 
                ROUND(lat, 3) as center_lat,
                ROUND(lng, 3) as center_lng,
                COUNT(*) as event_count,
                AVG(max_severity) as severity_score,
                MAX(max_severity) as max_severity,
                MIN(timestamp) as first_event,
                MAX(timestamp) as last_event,
                COUNT(DISTINCT device_id) as unique_devices,
                AVG(speed_kmh) as avg_speed,
                'mixed' as event_types
            FROM abnormal_events
            GROUP BY ROUND(lat, 3), ROUND(lng, 3)
            HAVING COUNT(*) >= {min_events}
        )
        SELECT 
            center_lat as lat,
            center_lng as lng,
            event_count,
            severity_score,
            max_severity,
            first_event,
            last_event,
            unique_devices,
            avg_speed,
            event_types,
            0 as peak_accel_x,
            0 as peak_accel_y,
            0 as peak_accel_z,
            'sensor_based' as hotspot_type
        FROM grid_clusters
        ORDER BY event_count DESC, severity_score DESC
        LIMIT 100
        """
        
        try:
            df = pd.read_sql(query_optimized, self.conn)
            
            if df.empty:
                print("⚠️ Optimized hotspots table empty, using raw table...")
                df = pd.read_sql(query_fallback, self.conn)
            
            if not df.empty and 'risk_score' not in df.columns:
                df['risk_score'] = df['severity_score'] * (1 + 0.1 * df['event_count'])
            
            return df
        except Exception as e:
            print(f"⚠️ Error with optimized query, trying fallback: {e}")
            try:
                df = pd.read_sql(query_fallback, self.conn)
                if not df.empty:
                    df['risk_score'] = df['severity_score'] * (1 + 0.1 * df['event_count'])
                return df
            except Exception as e2:
                print(f"❌ Both queries failed: {e2}")
                return pd.DataFrame()
    
    def get_usage_trends(self, days: int = 90) -> pd.DataFrame:
        """Get daily usage trends - OPTIMIZED with fallback"""
        
        query_optimized = f"""
        SELECT 
            date,
            unique_users,
            total_readings,
            abnormal_events,
            avg_speed,
            avg_severity
        FROM spinovate_production.usage_trends_daily
        WHERE date >= CURRENT_DATE - INTERVAL '{days}' DAY
        ORDER BY date
        """
        
        query_fallback = f"""
        SELECT 
            DATE_TRUNC('day', timestamp) as date,
            COUNT(DISTINCT device_id) as unique_users,
            COUNT(*) as total_readings,
            COUNT(CASE WHEN is_abnormal_event THEN 1 END) as abnormal_events,
            AVG(speed_kmh) as avg_speed,
            AVG(max_severity) as avg_severity
        FROM spinovate_production.spinovate_production_optimised_v2
        WHERE timestamp >= CURRENT_DATE - INTERVAL '{days}' DAY
        GROUP BY DATE_TRUNC('day', timestamp)
        ORDER BY date
        """
        
        try:
            df = pd.read_sql(query_optimized, self.conn)
            
            # If empty, try fallback
            if df.empty:
                print("⚠️ Optimized table empty, using fallback...")
                df = pd.read_sql(query_fallback, self.conn)
            
            if not df.empty:
                df['prev_day_users'] = df['unique_users'].shift(1)
                df['usage_change_pct'] = ((df['unique_users'] - df['prev_day_users']) / df['prev_day_users'] * 100).fillna(0)
            
            return df
        except Exception as e:
            print(f"⚠️ Error with optimized query, trying fallback: {e}")
            try:
                df = pd.read_sql(query_fallback, self.conn)
                if not df.empty:
                    df['prev_day_users'] = df['unique_users'].shift(1)
                    df['usage_change_pct'] = ((df['unique_users'] - df['prev_day_users']) / df['prev_day_users'] * 100).fillna(0)
                return df
            except Exception as e2:
                print(f"❌ Both queries failed: {e2}")
                return pd.DataFrame()
    
    def detect_usage_anomalies(self, threshold_pct: float = 30) -> pd.DataFrame:
        """Detect significant drops in usage - OPTIMIZED using usage_trends_daily!"""
        
        query = f"""
        WITH usage_with_lag AS (
            SELECT 
                date,
                unique_users as daily_users,
                total_readings as daily_readings,
                LAG(unique_users, 1) OVER (ORDER BY date) as prev_day_users,
                LAG(unique_users, 7) OVER (ORDER BY date) as week_ago_users,
                AVG(unique_users) OVER (ORDER BY date ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) as rolling_avg
            FROM spinovate_production.usage_trends_daily
            WHERE date >= CURRENT_DATE - INTERVAL '90' DAY
        )
        SELECT 
            date,
            daily_users,
            prev_day_users,
            week_ago_users,
            rolling_avg,
            CASE 
                WHEN prev_day_users > 0 THEN (daily_users - prev_day_users) * 100.0 / prev_day_users
                ELSE NULL 
            END as day_over_day_change,
            CASE 
                WHEN week_ago_users > 0 THEN (daily_users - week_ago_users) * 100.0 / week_ago_users
                ELSE NULL 
            END as week_over_week_change,
            CASE
                WHEN rolling_avg > 0 THEN (daily_users - rolling_avg) * 100.0 / rolling_avg
                ELSE NULL
            END as rolling_avg_deviation
        FROM usage_with_lag
        WHERE (prev_day_users > 0 AND (daily_users - prev_day_users) * 100.0 / prev_day_users < -{threshold_pct})
           OR (week_ago_users > 0 AND (daily_users - week_ago_users) * 100.0 / week_ago_users < -{threshold_pct})
           OR (rolling_avg > 0 AND (daily_users - rolling_avg) * 100.0 / rolling_avg < -{threshold_pct})
        ORDER BY date DESC
        """
        
        try:
            return pd.read_sql(query, self.conn)
        except Exception as e:
            print(f"Error detecting anomalies: {e}")
            return pd.DataFrame()
    
    def find_sensor_data_near_location(self, lat: float, lng: float, radius_m: int = 30) -> pd.DataFrame:
        """
        Find sensor readings near a specific location
        Uses main table since we need fine-grained location data
        
        Args:
            lat: Latitude of center point
            lng: Longitude of center point
            radius_m: Search radius in meters
        
        Returns:
            DataFrame with nearby sensor readings
        """
        
        # Convert radius to approximate degrees (rough approximation)
        # 1 degree ≈ 111km at equator
        radius_deg = radius_m / 111000.0
        
        query = f"""
        SELECT 
            lat,
            lng,
            timestamp,
            device_id,
            max_severity,
            primary_event_type,
            speed_kmh,
            event_details
        FROM spinovate_production.spinovate_production_optimised_v2
        WHERE lat BETWEEN {lat - radius_deg} AND {lat + radius_deg}
            AND lng BETWEEN {lng - radius_deg} AND {lng + radius_deg}
            AND is_abnormal_event = true
        ORDER BY timestamp DESC
        LIMIT 100
        """
        
        try:
            df = pd.read_sql(query, self.conn)
            
            if df.empty:
                return pd.DataFrame()
            
            # Calculate actual distance using Haversine formula
            from math import radians, cos, sin, asin, sqrt
            
            def haversine(lat1, lon1, lat2, lon2):
                """Calculate distance in meters between two points"""
                R = 6371000  # Earth radius in meters
                lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                return R * c
            
            df['distance_m'] = df.apply(lambda row: haversine(lat, lng, row['lat'], row['lng']), axis=1)
            df = df[df['distance_m'] <= radius_m].copy()
            df = df.sort_values('distance_m')
            
            return df
            
        except Exception as e:
            print(f"Error finding sensor data near location: {e}")
            return pd.DataFrame()
    
    def get_hotspot_time_series(self, lat: float, lng: float, grid_precision: int = 3) -> pd.DataFrame:
        """
        Get daily time series for a specific hotspot - OPTIMIZED using hotspots_daily_v2!
        
        Args:
            lat: Hotspot latitude
            lng: Hotspot longitude
            grid_precision: Decimal places for rounding (3 = ~111m)
        
        Returns:
            DataFrame with daily metrics for the hotspot
        """
        
        # Round to grid
        grid_lat = round(lat, grid_precision)
        grid_lng = round(lng, grid_precision)
        
        query = f"""
        SELECT 
            date,
            event_count,
            avg_severity,
            max_severity,
            COUNT(DISTINCT device_id) as unique_devices,
            avg_speed,
            primary_event_type
        FROM spinovate_production.hotspots_daily_v2
        WHERE grid_lat_3 = {grid_lat}
            AND grid_lng_3 = {grid_lng}
        GROUP BY date, event_count, avg_severity, max_severity, avg_speed, primary_event_type
        ORDER BY date
        """
        
        try:
            return pd.read_sql(query, self.conn)
        except Exception as e:
            print(f"Error getting hotspot time series: {e}")
            return pd.DataFrame()
    
    def close(self):
        """Close Athena connection"""
        if hasattr(self, 'conn'):
            self.conn.close()


# Singleton pattern for database connection
@st.cache_resource
def get_athena_database():
    """Get or create Athena database connection"""
    return AthenaCyclingSafetyDB()