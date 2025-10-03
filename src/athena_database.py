# src/athena_database.py - UPDATED with strict filtering

import pandas as pd
from pyathena import connect
import warnings
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Suppress pandas warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

class AthenaCyclingSafetyDB:
    """AWS Athena backend for cycling safety dashboard"""
    
    def __init__(self):
        """Initialize Athena connection using .env file"""
        try:
            # Get credentials from environment variables
            aws_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
            s3_staging = os.getenv('AWS_S3_STAGING_DIR', 's3://seesense-air/summit2/spinovate-replay/athena-results/')
            region = os.getenv('AWS_REGION', 'eu-west-1')
            
            if not aws_key or not aws_secret:
                raise Exception(
                    "AWS credentials not found in .env file!\n"
                    "Please add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to your .env file"
                )
            
            self.conn = connect(
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                s3_staging_dir=s3_staging,
                region_name=region
            )
            print("✅ Connected to Athena using .env credentials")
            
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
        FROM spinovate_production.spinovate_production_optimised
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
    
    def detect_sensor_hotspots(self, min_events: int = 15, severity_threshold: int = 3, 
                              start_date: str = None, end_date: str = None,
                              top_n: int = 20) -> pd.DataFrame:
        """
        Detect ONLY the most dangerous hotspots using strict filtering
        
        UPDATED VERSION - Returns 10-20 hotspots maximum
        
        Args:
            min_events: Minimum events (default: 15, much stricter than before)
            severity_threshold: Minimum severity (default: 3, high severity only)
            start_date: Start date for analysis (YYYY-MM-DD)
            end_date: End date for analysis (YYYY-MM-DD)
            top_n: Maximum hotspots to return (default: 20)
        
        Returns:
            DataFrame with only the most critical hotspots
        """
        
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'"
        
        query = f"""
        WITH abnormal_events AS (
            -- Step 1: Get only HIGH severity abnormal events
            SELECT 
                lat,
                lng,
                max_severity,
                primary_event_type,
                timestamp,
                device_id
            FROM spinovate_production.spinovate_production_optimised
            WHERE is_abnormal_event = true 
                AND max_severity >= {severity_threshold}
                AND lat IS NOT NULL 
                AND lng IS NOT NULL
                {date_filter}
        ),
        grid_clusters AS (
            -- Step 2: Group into ~111m grid cells
            SELECT 
                ROUND(lat, 3) as lat_cluster,
                ROUND(lng, 3) as lng_cluster,
                COUNT(*) as event_count,
                AVG(max_severity) as avg_severity,
                MAX(max_severity) as max_severity,
                AVG(lat) as center_lat,
                AVG(lng) as center_lng,
                MIN(timestamp) as first_event,
                MAX(timestamp) as last_event,
                ARRAY_AGG(DISTINCT primary_event_type) as event_types,
                COUNT(DISTINCT DATE_TRUNC('day', timestamp)) as days_with_events,
                COUNT(DISTINCT device_id) as unique_devices
            FROM abnormal_events
            GROUP BY ROUND(lat, 3), ROUND(lng, 3)
            HAVING COUNT(*) >= {min_events}  -- Strict minimum
                AND COUNT(DISTINCT DATE_TRUNC('day', timestamp)) >= 2  -- Must occur on 2+ days
        ),
        cluster_stats AS (
            -- Step 3: Calculate statistics for filtering
            SELECT 
                AVG(event_count) as mean_events,
                STDDEV(event_count) as stddev_events,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY event_count) as p75_events,
                AVG(avg_severity) as mean_severity
            FROM grid_clusters
        ),
        scored_hotspots AS (
            -- Step 4: Calculate risk scores and z-scores
            SELECT 
                gc.*,
                -- Composite Risk Score: combines frequency + severity + impact
                -- Formula: (count × 0.4) + (avg_sev × 10 × 0.4) + (max_sev × 5 × 0.2)
                (
                    CAST(gc.event_count AS DOUBLE) * 0.4 + 
                    gc.avg_severity * 10 * 0.4 + 
                    CAST(gc.max_severity AS DOUBLE) * 5 * 0.2
                ) as risk_score,
                
                -- Z-score: how many standard deviations above mean
                CASE 
                    WHEN s.stddev_events > 0 THEN 
                        (CAST(gc.event_count AS DOUBLE) - s.mean_events) / s.stddev_events
                    ELSE 0
                END as event_zscore,
                
                -- Events per active day (frequency metric)
                CAST(gc.event_count AS DOUBLE) / NULLIF(gc.days_with_events, 0) as events_per_day,
                
                -- Reference statistics
                s.mean_events,
                s.p75_events
            FROM grid_clusters gc
            CROSS JOIN cluster_stats s
        )
        SELECT 
            center_lat as lat,
            center_lng as lng,
            event_count,
            avg_severity as severity_score,
            max_severity,
            first_event,
            last_event,
            event_types,
            days_with_events,
            unique_devices,
            events_per_day,
            risk_score,
            event_zscore,
            mean_events,
            'sensor_based' as hotspot_type
        FROM scored_hotspots
        WHERE 
            -- Multi-tier filtering: must meet at least ONE of these criteria
            (event_zscore >= 1.5)  -- 1.5 std devs above mean (top ~7%)
            OR (risk_score >= 35)   -- High composite risk score
            OR (event_count >= 30 AND avg_severity >= 3.5)  -- Extreme frequency + severity
        ORDER BY risk_score DESC, event_count DESC, avg_severity DESC
        LIMIT {top_n}
        """
        
        try:
            df = pd.read_sql(query, self.conn)
            
            if not df.empty:
                # Add human-readable risk categories
                df['risk_category'] = pd.cut(
                    df['risk_score'],
                    bins=[0, 25, 35, 45, 100],
                    labels=['Medium', 'High', 'Critical', 'Extreme']
                )
                
                # Add percentile ranking
                df['percentile_rank'] = df['event_count'].rank(pct=True) * 100
                
                # Flag if significantly above average
                df['significantly_above_avg'] = df['event_zscore'] >= 1.5
                
                print(f"✅ Found {len(df)} critical hotspots (filtered from all clusters)")
                
            return df
            
        except Exception as e:
            print(f"Error detecting hotspots: {e}")
            return pd.DataFrame()
    
    def get_usage_trends(self, days: int = 30) -> pd.DataFrame:
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
            df = pd.read_sql(query, self.conn)
            
            if not df.empty:
                df['prev_day_users'] = df['unique_users'].shift(1)
                df['usage_change_pct'] = ((df['unique_users'] - df['prev_day_users']) / df['prev_day_users'] * 100).fillna(0)
            
            return df
        except Exception as e:
            print(f"Error getting usage trends: {e}")
            return pd.DataFrame()
    
    def detect_usage_anomalies(self) -> pd.DataFrame:
        """Detect significant drops in usage"""
        
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
        WHERE (prev_day_users > 0 AND (daily_users - prev_day_users) * 100.0 / prev_day_users < -30)
           OR (week_ago_users > 0 AND (daily_users - week_ago_users) * 100.0 / week_ago_users < -20)
        ORDER BY date DESC
        """
        
        try:
            return pd.read_sql(query, self.conn)
        except Exception as e:
            print(f"Error detecting anomalies: {e}")
            return pd.DataFrame()
    
    def get_hotspot_event_details(self, lat: float, lng: float, radius_m: int = 50) -> pd.DataFrame:
        """
        Get detailed event information for a specific hotspot
        
        Args:
            lat: Hotspot latitude
            lng: Hotspot longitude  
            radius_m: Radius in meters (default: 50m)
        
        Returns:
            DataFrame with individual events near this hotspot
        """
        # Convert radius to degrees (approximate)
        radius_deg = radius_m / 111000  # 1 degree ≈ 111km
        
        query = f"""
        SELECT 
            lat,
            lng,
            max_severity,
            primary_event_type,
            timestamp,
            speed_kmh,
            device_id,
            peak_x,
            peak_y,
            peak_z
        FROM spinovate_production.spinovate_production_optimised
        WHERE is_abnormal_event = true
            AND ABS(lat - {lat}) <= {radius_deg}
            AND ABS(lng - {lng}) <= {radius_deg}
            AND lat IS NOT NULL
            AND lng IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 100
        """
        
        try:
            return pd.read_sql(query, self.conn)
        except Exception as e:
            print(f"Error getting hotspot details: {e}")
            return pd.DataFrame()
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

# Cache the database connection
_db_instance = None

def get_athena_database():
    """Get or create Athena database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = AthenaCyclingSafetyDB()
    return _db_instance