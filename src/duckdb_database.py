"""
DuckDB Database - Minimal Version (Tab 1 Only)
Drop-in replacement for AthenaDatabase for hotspot detection
"""
import duckdb
import pandas as pd
from pathlib import Path
import re
import logging
from typing import Dict, Any, Optional, List, Tuple

class DuckDBCyclingSafetyDB:
    """DuckDB implementation for hotspot detection"""

    def __init__(self):
        """Initialize DuckDB connection with local CSV files"""
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Initialize connection
        self.conn = duckdb.connect(':memory:')

        # Input validation patterns
        self.lat_pattern = re.compile(r'^-?90?\.?\d*$')
        self.lng_pattern = re.compile(r'^-?180?\.?\d*$')
        self.date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        self.severity_pattern = re.compile(r'^\d+$')

        # Determine data directory
        data_dir = Path(__file__).parent.parent / 'data' / 'raw'
        """Initialize DuckDB connection with local CSV files"""
        self.conn = duckdb.connect(':memory:')
        
        # Determine data directory
        data_dir = Path(__file__).parent.parent / 'data' / 'raw'
        
        # File paths
        sensor_file = data_dir / 'spinovate-abnormal-events.csv'
        
        # Check if sensor file exists
        if not sensor_file.exists():
            raise FileNotFoundError(
                f"❌ Sensor data not found: {sensor_file}\n"
                f"Expected location: {data_dir}\n"
                f"Make sure 'spinovate-abnormal-events.csv' is in data/raw/"
            )
        
        print(f"📂 Loading sensor data from {sensor_file}...")
        
        # Load sensor data into DuckDB
        try:
            self.conn.execute(f"""
                CREATE TABLE sensor_events AS 
                SELECT * FROM read_csv_auto('{sensor_file}', 
                    header=true,
                    ignore_errors=true,
                    all_varchar=false
                )
            """)
            
            # Check what we loaded
            count_result = self.conn.execute("SELECT COUNT(*) FROM sensor_events").fetchone()
            print(f"✅ Loaded {count_result[0]:,} sensor events into DuckDB")
            
            # Auto-detect column names
            self._detect_column_names()
            
        except Exception as e:
            raise Exception(f"❌ Failed to load sensor data: {e}")
    
    def _detect_column_names(self):
        """Auto-detect column names (handle variations)"""
        columns_df = self.conn.execute("DESCRIBE sensor_events").df()
        column_names = columns_df['column_name'].tolist()
        column_names_lower = [col.lower() for col in column_names]
        
        # Detect latitude column
        self.lat_col = None
        for possible in ['lat', 'latitude', 'position_latitude']:
            if possible.lower() in column_names_lower:
                idx = column_names_lower.index(possible.lower())
                self.lat_col = column_names[idx]
                break
        
        # Detect longitude column
        self.lng_col = None
        for possible in ['lng', 'longitude', 'position_longitude']:
            if possible.lower() in column_names_lower:
                idx = column_names_lower.index(possible.lower())
                self.lng_col = column_names[idx]
                break
        
        # Detect severity column
        self.severity_col = None
        for possible in ['max_severity', 'severity', 'severity_max']:
            if possible.lower() in column_names_lower:
                idx = column_names_lower.index(possible.lower())
                self.severity_col = column_names[idx]
                break
        
        # Detect event type column
        self.event_type_col = None
        for possible in ['primary_event_type', 'event_type', 'eventtype']:
            if possible.lower() in column_names_lower:
                idx = column_names_lower.index(possible.lower())
                self.event_type_col = column_names[idx]
                break
        
        # Detect device ID column
        self.device_col = None
        for possible in ['device_id', 'deviceid', 'device_name']:
            if possible.lower() in column_names_lower:
                idx = column_names_lower.index(possible.lower())
                self.device_col = column_names[idx]
                break
        
        # Detect speed column
        self.speed_col = None
        for possible in ['speed_kmh', 'speed', 'speed_km_h']:
            if possible.lower() in column_names_lower:
                idx = column_names_lower.index(possible.lower())
                self.speed_col = column_names[idx]
                break
        
        # Detect event details column
        self.event_details_col = None
        for possible in ['event_details', 'eventdetails', 'details']:
            if possible.lower() in column_names_lower:
                idx = column_names_lower.index(possible.lower())
                self.event_details_col = column_names[idx]
                break
        
        # Detect timestamp column
        self.timestamp_col = 'timestamp'  # Assume this exists
        
        print(f"✅ Detected columns:")
        print(f"   Latitude: {self.lat_col}")
        print(f"   Longitude: {self.lng_col}")
        print(f"   Severity: {self.severity_col}")
        print(f"   Event Type: {self.event_type_col}")
        print(f"   Device ID: {self.device_col}")
        
        if not self.lat_col or not self.lng_col:
            raise Exception(
                f"❌ Could not find lat/lng columns!\n"
                f"Available columns: {column_names}"
            )
    
    def get_dashboard_metrics(self):
        """Get summary metrics for dashboard overview"""
        
        device_count = f'COUNT(DISTINCT "{self.device_col}")' if self.device_col else '0'
        speed_avg = f'AVG(TRY_CAST("{self.speed_col}" AS DOUBLE))' if self.speed_col else '0'
        
        query = f"""
        SELECT 
            COUNT(*) as total_readings,
            {device_count} as unique_devices,
            COUNT(*) as abnormal_events,
            {speed_avg} as avg_speed,
            MIN({self.timestamp_col}) as earliest,
            MAX({self.timestamp_col}) as latest
        FROM sensor_events
        WHERE TRY_CAST("{self.lat_col}" AS DOUBLE) IS NOT NULL 
            AND TRY_CAST("{self.lng_col}" AS DOUBLE) IS NOT NULL
        """
        
        try:
            result = self.conn.execute(query).fetchone()
            
            return {
                'total_readings': int(result[0]) if result[0] else 0,
                'unique_devices': int(result[1]) if result[1] else 0,
                'abnormal_events': int(result[2]) if result[2] else 0,
                'avg_speed': round(float(result[3]), 1) if result[3] else 0,
                'earliest_reading': result[4],
                'latest_reading': result[5]
            }
        except Exception as e:
            print(f"❌ Error getting metrics: {e}")
            return {
                'total_readings': 0,
                'unique_devices': 0,
                'abnormal_events': 0,
                'avg_speed': 0,
                'earliest_reading': None,
                'latest_reading': None
            }
    
    def get_sensor_data_for_clustering(self, start_date, end_date, min_severity=0):
        """Get raw sensor data for DBSCAN clustering (used by HybridHotspotDetector)"""
        
        severity_filter = ""
        if self.severity_col and min_severity > 0:
            severity_filter = f'AND TRY_CAST("{self.severity_col}" AS INTEGER) >= {min_severity}'
        
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND TRY_CAST({self.timestamp_col} AS DATE) BETWEEN '{start_date}' AND '{end_date}'"
        
        event_type_select = f'"{self.event_type_col}"' if self.event_type_col else "'unknown'"
        device_select = f'"{self.device_col}"' if self.device_col else "'unknown'"
        severity_select = f'TRY_CAST("{self.severity_col}" AS INTEGER)' if self.severity_col else '0'
        event_details_select = f'"{self.event_details_col}"' if self.event_details_col else "'no details'"
        
        query = f"""
        SELECT 
            TRY_CAST("{self.lat_col}" AS DOUBLE) as lat,
            TRY_CAST("{self.lng_col}" AS DOUBLE) as lng,
            {severity_select} as max_severity,
            {event_type_select} as primary_event_type,
            {device_select} as device_id,
            {self.timestamp_col} as timestamp,
            {event_details_select} as event_details
        FROM sensor_events
        WHERE TRY_CAST("{self.lat_col}" AS DOUBLE) IS NOT NULL
            AND TRY_CAST("{self.lng_col}" AS DOUBLE) IS NOT NULL
            {severity_filter}
            {date_filter}
        """
        
        try:
            df = self.conn.execute(query).df()
            print(f"✅ Retrieved {len(df):,} sensor events for clustering")
            return df
        except Exception as e:
            print(f"❌ Error getting sensor data: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def find_sensor_data_in_radius(self, center_lat, center_lng, radius_m=30, 
                                   min_severity=0, start_date=None, end_date=None):
        """Find sensor events within radius of a point (used by P1 precedence)"""
        
        radius_deg = radius_m / 111000.0
        
        severity_filter = ""
        if self.severity_col and min_severity > 0:
            severity_filter = f'AND TRY_CAST("{self.severity_col}" AS INTEGER) >= {min_severity}'
        
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND TRY_CAST({self.timestamp_col} AS DATE) BETWEEN '{start_date}' AND '{end_date}'"
        
        event_type_select = f'"{self.event_type_col}"' if self.event_type_col else "'unknown'"
        device_select = f'"{self.device_col}"' if self.device_col else "'unknown'"
        severity_select = f'TRY_CAST("{self.severity_col}" AS INTEGER)' if self.severity_col else '0'
        
        query = f"""
        WITH nearby AS (
            SELECT 
                TRY_CAST("{self.lat_col}" AS DOUBLE) as lat,
                TRY_CAST("{self.lng_col}" AS DOUBLE) as lng,
                {severity_select} as severity,
                {event_type_select} as event_type,
                {device_select} as device_id,
                6371000 * 2 * ASIN(SQRT(
                    POW(SIN(RADIANS((TRY_CAST("{self.lat_col}" AS DOUBLE) - {center_lat})) / 2), 2) +
                    COS(RADIANS({center_lat})) * COS(RADIANS(TRY_CAST("{self.lat_col}" AS DOUBLE))) *
                    POW(SIN(RADIANS((TRY_CAST("{self.lng_col}" AS DOUBLE) - {center_lng})) / 2), 2)
                )) as distance_m
            FROM sensor_events
            WHERE TRY_CAST("{self.lat_col}" AS DOUBLE) BETWEEN {center_lat - radius_deg} AND {center_lat + radius_deg}
                AND TRY_CAST("{self.lng_col}" AS DOUBLE) BETWEEN {center_lng - radius_deg} AND {center_lng + radius_deg}
                {severity_filter}
                {date_filter}
        )
        SELECT 
            COUNT(*) as event_count,
            AVG(severity) as avg_severity,
            MAX(severity) as max_severity,
            COUNT(DISTINCT device_id) as unique_devices,
            LIST(event_type) as event_types
        FROM nearby 
        WHERE distance_m <= {radius_m}
        """
        
        try:
            result = self.conn.execute(query).fetchone()
            
            if result[0] == 0:
                return {
                    'has_data': False,
                    'event_count': 0,
                    'avg_severity': 0,
                    'max_severity': 0,
                    'unique_devices': 0,
                    'event_types': []
                }
            
            return {
                'has_data': True,
                'event_count': int(result[0]),
                'avg_severity': float(result[1]) if result[1] else 0,
                'max_severity': int(result[2]) if result[2] else 0,
                'unique_devices': int(result[3]) if result[3] else 0,
                'event_types': result[4] if result[4] else []
            }
            
        except Exception as e:
            print(f"❌ Error finding sensor data in radius: {e}")
            return {
                'has_data': False,
                'event_count': 0,
                'avg_severity': 0,
                'max_severity': 0,
                'unique_devices': 0,
                'event_types': []
            }
    
    def find_sensor_data_in_polygon(self, polygon_coords, start_date=None, end_date=None, min_severity=0):
        """Find sensor events within a polygon (used by P2 corridor detection)"""
        
        lats = [coord[0] for coord in polygon_coords]
        lngs = [coord[1] for coord in polygon_coords]
        
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)
        
        severity_filter = ""
        if self.severity_col and min_severity > 0:
            severity_filter = f'AND TRY_CAST("{self.severity_col}" AS INTEGER) >= {min_severity}'
        
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND TRY_CAST({self.timestamp_col} AS DATE) BETWEEN '{start_date}' AND '{end_date}'"
        
        event_type_select = f'"{self.event_type_col}"' if self.event_type_col else "'unknown'"
        device_select = f'"{self.device_col}"' if self.device_col else "'unknown'"
        severity_select = f'TRY_CAST("{self.severity_col}" AS INTEGER)' if self.severity_col else '0'
        
        query = f"""
        SELECT 
            COUNT(*) as event_count,
            AVG({severity_select}) as avg_severity,
            MAX({severity_select}) as max_severity,
            COUNT(DISTINCT {device_select}) as unique_devices,
            LIST({event_type_select}) as event_types
        FROM sensor_events
        WHERE TRY_CAST("{self.lat_col}" AS DOUBLE) BETWEEN {min_lat} AND {max_lat}
            AND TRY_CAST("{self.lng_col}" AS DOUBLE) BETWEEN {min_lng} AND {max_lng}
            {severity_filter}
            {date_filter}
        """
        
        try:
            result = self.conn.execute(query).fetchone()
            
            if result[0] == 0:
                return {
                    'has_data': False,
                    'event_count': 0,
                    'avg_severity': 0,
                    'max_severity': 0,
                    'unique_devices': 0,
                    'event_types': []
                }
            
            return {
                'has_data': True,
                'event_count': int(result[0]),
                'avg_severity': float(result[1]) if result[1] else 0,
                'max_severity': int(result[2]) if result[2] else 0,
                'unique_devices': int(result[3]) if result[3] else 0,
                'event_types': result[4] if result[4] else []
            }
            
        except Exception as e:
            print(f"❌ Error finding sensor data in polygon: {e}")
            return {
                'has_data': False,
                'event_count': 0,
                'avg_severity': 0,
                'max_severity': 0,
                'unique_devices': 0,
                'event_types': []
            }
    
    def close(self):
        """Close database connection"""
        self.conn.close()


# Singleton instance
_db_instance = None

def get_duckdb_database():
    """Get or create DuckDB database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DuckDBCyclingSafetyDB()
    return _db_instance