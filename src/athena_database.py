# src/athena_database.py - UPDATED FOR NEW SCHEMA
import pandas as pd
from pyathena import connect
import warnings
import os
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

class AthenaCyclingSafetyDB:
    """AWS Athena backend - UPDATED for spinovate_production_optimised_v2"""
    
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
        """Get key metrics for dashboard overview"""
        
        query = """
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
            df = pd.read_sql(query, self.conn)
            result = df.iloc[0]
            
            return {
                'total_readings': int(result['total_readings']),
                'unique_devices': int(result['unique_devices']),
                'abnormal_events': int(result['abnormal_events']),
                'avg_speed': round(float(result['avg_speed']), 1) if result['avg_speed'] else 0,
                'latest_reading': result['latest_reading'],
                'earliest_reading': result['earliest_reading']
            }
        except Exception as e:
            print(f"Error getting metrics: {e}")
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
        Detect hotspots using spatial clustering
        
        Args:
            min_events: Minimum events to form a hotspot
            severity_threshold: Minimum severity level
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            radius_m: Radius for clustering (meters)
        """
        
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'"
        
        # Calculate clustering precision (degrees per radius)
        # ~111km per degree at equator, so 50m = 0.00045 degrees
        cluster_precision = 3  # Round to 3 decimal places (~111m precision)
        
        query = f"""
        WITH abnormal_events AS (
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
                {date_filter}
        ),
        grid_clusters AS (
            SELECT 
                ROUND(lat, {cluster_precision}) as lat_cluster,
                ROUND(lng, {cluster_precision}) as lng_cluster,
                COUNT(*) as event_count,
                AVG(max_severity) as avg_severity,
                MAX(max_severity) as max_severity,
                AVG(lat) as center_lat,
                AVG(lng) as center_lng,
                MIN(timestamp) as first_event,
                MAX(timestamp) as last_event,
                COUNT(DISTINCT device_id) as unique_devices,
                AVG(speed_kmh) as avg_speed,
                ARRAY_AGG(DISTINCT primary_event_type) as event_types,
                APPROX_PERCENTILE(peak_x, 0.95) as peak_accel_x,
                APPROX_PERCENTILE(peak_y, 0.95) as peak_accel_y,
                APPROX_PERCENTILE(peak_z, 0.95) as peak_accel_z
            FROM abnormal_events
            GROUP BY ROUND(lat, {cluster_precision}), ROUND(lng, {cluster_precision})
            HAVING COUNT(*) >= {min_events}
        )
        SELECT 
            center_lat as lat,
            center_lng as lng,
            event_count,
            avg_severity as severity_score,
            max_severity,
            first_event,
            last_event,
            unique_devices,
            avg_speed,
            event_types,
            peak_accel_x,
            peak_accel_y,
            peak_accel_z,
            'sensor_based' as hotspot_type
        FROM grid_clusters
        ORDER BY event_count DESC, avg_severity DESC
        LIMIT 100
        """
        
        try:
            df = pd.read_sql(query, self.conn)
            
            if df.empty:
                return pd.DataFrame()
            
            # Calculate risk score
            df['risk_score'] = df['severity_score'] * (1 + 0.1 * df['event_count'])
            
            return df
        except Exception as e:
            print(f"Error detecting hotspots: {e}")
            return pd.DataFrame()
    
    def get_usage_trends(self, days: int = 90) -> pd.DataFrame:
        """Get daily usage trends"""
        
        query = f"""
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
            df = pd.read_sql(query, self.conn)
            
            if not df.empty:
                df['prev_day_users'] = df['unique_users'].shift(1)
                df['usage_change_pct'] = ((df['unique_users'] - df['prev_day_users']) / df['prev_day_users'] * 100).fillna(0)
            
            return df
        except Exception as e:
            print(f"Error getting usage trends: {e}")
            return pd.DataFrame()
    
    def detect_usage_anomalies(self, threshold_pct: float = 30) -> pd.DataFrame:
        """Detect significant drops in usage"""
        
        query = f"""
        WITH daily_usage AS (
            SELECT 
                DATE_TRUNC('day', timestamp) as date,
                COUNT(DISTINCT device_id) as daily_users,
                COUNT(*) as daily_readings
            FROM spinovate_production.spinovate_production_optimised_v2
            WHERE timestamp >= CURRENT_DATE - INTERVAL '90' DAY
            GROUP BY DATE_TRUNC('day', timestamp)
            ORDER BY date
        ),
        usage_with_lag AS (
            SELECT *,
                LAG(daily_users, 1) OVER (ORDER BY date) as prev_day_users,
                LAG(daily_users, 7) OVER (ORDER BY date) as week_ago_users,
                AVG(daily_users) OVER (ORDER BY date ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) as rolling_avg
            FROM daily_usage
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
    
    def find_sensor_data_near_location(self, lat: float, lng: float, 
                                       radius_m: int = 50,
                                       start_date: str = None, 
                                       end_date: str = None) -> dict:
        """
        Find sensor readings near a specific location
        Used for validating perception reports with sensor data
        """
        
        radius_deg = radius_m / 111000
        
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'"
        
        query = f"""
        SELECT 
            COUNT(*) as total_events,
            COUNT(CASE WHEN is_abnormal_event THEN 1 END) as abnormal_events,
            AVG(max_severity) as avg_severity,
            MAX(max_severity) as max_severity,
            COUNT(CASE WHEN primary_event_type LIKE '%brake%' THEN 1 END) as brake_events,
            COUNT(CASE WHEN primary_event_type LIKE '%swerve%' THEN 1 END) as swerve_events,
            COUNT(CASE WHEN primary_event_type LIKE '%pothole%' OR primary_event_type LIKE '%bump%' THEN 1 END) as pothole_events,
            COUNT(DISTINCT device_id) as unique_devices,
            AVG(speed_kmh) as avg_speed,
            APPROX_PERCENTILE(peak_x, 0.95) as peak_x_95,
            APPROX_PERCENTILE(peak_y, 0.95) as peak_y_95,
            APPROX_PERCENTILE(peak_z, 0.95) as peak_z_95
        FROM spinovate_production.spinovate_production_optimised_v2
        WHERE ABS(lat - {lat}) <= {radius_deg}
            AND ABS(lng - {lng}) <= {radius_deg}
            AND lat IS NOT NULL
            AND lng IS NOT NULL
            {date_filter}
        """
        
        try:
            result = pd.read_sql(query, self.conn)
            
            if result.empty:
                return {'has_sensor_data': False, 'total_events': 0}
            
            row = result.iloc[0]
            
            return {
                'has_sensor_data': row['total_events'] > 0,
                'total_events': int(row['total_events']),
                'abnormal_events': int(row['abnormal_events']),
                'avg_severity': float(row['avg_severity']) if row['avg_severity'] else 0,
                'max_severity': int(row['max_severity']) if row['max_severity'] else 0,
                'brake_events': int(row['brake_events']),
                'swerve_events': int(row['swerve_events']),
                'pothole_events': int(row['pothole_events']),
                'unique_devices': int(row['unique_devices']),
                'avg_speed': float(row['avg_speed']) if row['avg_speed'] else 0,
                'peak_accelerations': {
                    'x': float(row['peak_x_95']) if row['peak_x_95'] else 0,
                    'y': float(row['peak_y_95']) if row['peak_y_95'] else 0,
                    'z': float(row['peak_z_95']) if row['peak_z_95'] else 0
                }
            }
            
        except Exception as e:
            print(f"Error finding sensor data: {e}")
            return {'has_sensor_data': False, 'total_events': 0, 'error': str(e)}
    
    def get_event_type_distribution(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Get distribution of event types"""
        
        date_filter = ""
        if start_date and end_date:
            date_filter = f"WHERE timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'"
        
        query = f"""
        SELECT 
            primary_event_type,
            COUNT(*) as event_count,
            AVG(max_severity) as avg_severity,
            COUNT(DISTINCT device_id) as unique_devices
        FROM spinovate_production.spinovate_production_optimised_v2
        {date_filter}
        GROUP BY primary_event_type
        ORDER BY event_count DESC
        """
        
        try:
            return pd.read_sql(query, self.conn)
        except Exception as e:
            print(f"Error getting event distribution: {e}")
            return pd.DataFrame()
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

# Singleton instance
_db_instance = None

def get_athena_database():
    """Get or create Athena database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = AthenaCyclingSafetyDB()
    return _db_instance