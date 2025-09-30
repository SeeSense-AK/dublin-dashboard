# src/athena_database.py
import pandas as pd
from pyathena import connect
import streamlit as st
from typing import List, Dict, Tuple, Optional
import os
import warnings

# Suppress pandas warnings about PyAthena connections
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

class AthenaCyclingSafetyDB:
    """
    AWS Athena backend for cycling safety dashboard
    Connects to your optimized Parquet tables in Athena
    """
    
    def __init__(self):
        """Initialize Athena connection using multiple fallback methods"""
        connection_established = False
        
        # Method 1: Try Streamlit secrets (for deployment)
        try:
            self.conn = connect(
                aws_access_key_id=st.secrets["aws"]["access_key_id"],
                aws_secret_access_key=st.secrets["aws"]["secret_access_key"],
                s3_staging_dir=st.secrets["aws"]["s3_staging_dir"],
                region_name=st.secrets["aws"]["region"]
            )
            print("✅ Connected to Athena using Streamlit secrets")
            connection_established = True
        except Exception as e:
            print(f"⚠️  Streamlit secrets not available: {e}")
        
        # Method 2: Try environment variables from .env file
        if not connection_established:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                
                aws_key = os.getenv('AWS_ACCESS_KEY_ID')
                aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
                s3_staging = os.getenv('AWS_S3_STAGING_DIR', 's3://seesense-air/summit2/spinovate-replay/athena-results/')
                region = os.getenv('AWS_REGION', 'eu-west-1')
                
                if aws_key and aws_secret:
                    self.conn = connect(
                        aws_access_key_id=aws_key,
                        aws_secret_access_key=aws_secret,
                        s3_staging_dir=s3_staging,
                        region_name=region
                    )
                    print("✅ Connected to Athena using .env file")
                    connection_established = True
            except Exception as e:
                print(f"⚠️  .env file credentials not available: {e}")
        
        # Method 3: Try default AWS credentials (from ~/.aws/credentials)
        if not connection_established:
            try:
                s3_staging = 's3://seesense-air/summit2/spinovate-replay/athena-results/'
                region = 'eu-west-1'
                
                self.conn = connect(
                    s3_staging_dir=s3_staging,
                    region_name=region
                )
                print("✅ Connected to Athena using default AWS credentials")
                connection_established = True
            except Exception as e:
                print(f"❌ Failed to connect to Athena: {e}")
                raise Exception(
                    "Could not connect to Athena. Please ensure one of the following:\n"
                    "1. Create .streamlit/secrets.toml with AWS credentials\n"
                    "2. Add AWS credentials to .env file\n"
                    "3. Configure AWS CLI with 'aws configure'"
                )
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_dashboard_metrics(_self) -> Dict:
        """Get key metrics for dashboard overview"""
        
        query = """
        SELECT 
            COUNT(*) as total_readings,
            COUNT(DISTINCT device_id) as unique_devices,
            COUNT(CASE WHEN is_abnormal_event THEN 1 END) as abnormal_events,
            AVG(speed_kmh) as avg_speed,
            MAX(timestamp) as latest_reading,
            MIN(timestamp) as earliest_reading
        FROM spinovate_production.spinovate_production_optimised
        """
        
        try:
            df = pd.read_sql(query, _self.conn)
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
            st.error(f"Error getting metrics: {e}")
            return {
                'total_readings': 0,
                'unique_devices': 0,
                'abnormal_events': 0,
                'avg_speed': 0,
                'latest_reading': None,
                'earliest_reading': None
            }
    
    @st.cache_data(ttl=1800)  # Cache for 30 minutes
    def detect_sensor_hotspots(_self, min_events: int = 3, severity_threshold: int = 2, 
                              start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Detect hotspots from sensor data using spatial clustering"""
        
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'"
        
        query = f"""
        WITH abnormal_events AS (
            SELECT 
                lat,
                lng,
                max_severity,
                primary_event_type,
                timestamp
            FROM spinovate_production.spinovate_production_optimised
            WHERE is_abnormal_event = true 
                AND max_severity >= {severity_threshold}
                AND lat IS NOT NULL 
                AND lng IS NOT NULL
                {date_filter}
        ),
        -- Grid-based clustering (simplified alternative to DBSCAN)
        grid_clusters AS (
            SELECT 
                ROUND(lat, 3) as lat_cluster,
                ROUND(lng, 3) as lng_cluster,
                COUNT(*) as event_count,
                AVG(max_severity) as avg_severity,
                AVG(lat) as center_lat,
                AVG(lng) as center_lng,
                MIN(timestamp) as first_event,
                MAX(timestamp) as last_event,
                ARRAY_AGG(DISTINCT primary_event_type) as event_types
            FROM abnormal_events
            GROUP BY lat_cluster, lng_cluster
            HAVING COUNT(*) >= {min_events}
        )
        SELECT 
            center_lat as lat,
            center_lng as lng,
            event_count,
            ROUND(avg_severity, 2) as severity_score,
            first_event,
            last_event,
            event_types,
            'sensor_based' as hotspot_type
        FROM grid_clusters
        ORDER BY event_count DESC, avg_severity DESC
        LIMIT 100
        """
        
        try:
            return pd.read_sql(query, _self.conn)
        except Exception as e:
            st.error(f"Error detecting hotspots: {e}")
            return pd.DataFrame()
    
    @st.cache_data(ttl=1800)
    def get_usage_trends(_self, days: int = 30) -> pd.DataFrame:
        """Get daily usage trends for time series analysis"""
        
        query = f"""
        SELECT 
            DATE_TRUNC('day', timestamp) as date,
            COUNT(DISTINCT device_id) as unique_users,
            COUNT(*) as total_readings,
            COUNT(CASE WHEN is_abnormal_event THEN 1 END) as abnormal_events,
            AVG(speed_kmh) as avg_speed
        FROM spinovate_production.spinovate_production_optimised
        WHERE timestamp >= CURRENT_DATE - INTERVAL '{days}' DAY
        GROUP BY DATE_TRUNC('day', timestamp)
        ORDER BY date
        """
        
        try:
            df = pd.read_sql(query, _self.conn)
            
            # Calculate day-over-day changes
            if not df.empty:
                df['prev_day_users'] = df['unique_users'].shift(1)
                df['usage_change_pct'] = ((df['unique_users'] - df['prev_day_users']) / df['prev_day_users'] * 100).fillna(0)
            
            return df
        except Exception as e:
            st.error(f"Error getting usage trends: {e}")
            return pd.DataFrame()
    
    def detect_usage_anomalies(self) -> pd.DataFrame:
        """Detect significant drops in usage that warrant investigation"""
        
        query = """
        WITH daily_usage AS (
            SELECT 
                DATE_TRUNC('day', timestamp) as date,
                COUNT(DISTINCT device_id) as daily_users,
                COUNT(*) as daily_readings
            FROM spinovate_production.spinovate_production_optimised
            WHERE timestamp >= CURRENT_DATE - INTERVAL '90' DAY
            GROUP BY DATE_TRUNC('day', timestamp)
            ORDER BY date
        ),
        usage_with_lag AS (
            SELECT *,
                LAG(daily_users, 1) OVER (ORDER BY date) as prev_day_users,
                LAG(daily_users, 7) OVER (ORDER BY date) as week_ago_users
            FROM daily_usage
        )
        SELECT *,
            CASE 
                WHEN prev_day_users > 0 THEN (daily_users - prev_day_users) * 100.0 / prev_day_users
                ELSE NULL 
            END as day_over_day_change,
            CASE 
                WHEN week_ago_users > 0 THEN (daily_users - week_ago_users) * 100.0 / week_ago_users
                ELSE NULL 
            END as week_over_week_change
        FROM usage_with_lag
        WHERE (prev_day_users > 0 AND (daily_users - prev_day_users) * 100.0 / prev_day_users < -30)  -- 30% daily drop
           OR (week_ago_users > 0 AND (daily_users - week_ago_users) * 100.0 / week_ago_users < -20)  -- 20% weekly drop
        ORDER BY date DESC
        """
        
        try:
            return pd.read_sql(query, self.conn)
        except Exception as e:
            st.error(f"Error detecting anomalies: {e}")
            return pd.DataFrame()
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

# Streamlit integration
@st.cache_resource
def get_athena_database():
    """Initialize Athena database connection (cached)"""
    return AthenaCyclingSafetyDB()

def generate_street_view_url(lat: float, lng: float) -> str:
    """Generate Google Street View URL"""
    return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}"
