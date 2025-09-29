"""
Geospatial utility functions
"""
import numpy as np
from math import radians, cos, sin, asin, sqrt
from utils.constants import EARTH_RADIUS_M


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    
    Returns distance in meters
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    return c * EARTH_RADIUS_M


def find_points_within_radius(center_lat, center_lon, points_df, radius_m, lat_col='lat', lon_col='lng'):
    """
    Find all points in a dataframe within a given radius of a center point
    
    Args:
        center_lat: Latitude of center point
        center_lon: Longitude of center point
        points_df: DataFrame containing points to search
        radius_m: Radius in meters
        lat_col: Name of latitude column in points_df
        lon_col: Name of longitude column in points_df
    
    Returns:
        DataFrame of points within radius
    """
    if points_df.empty:
        return points_df
    
    # Calculate distances
    distances = points_df.apply(
        lambda row: haversine_distance(center_lat, center_lon, row[lat_col], row[lon_col]),
        axis=1
    )
    
    # Filter by radius
    return points_df[distances <= radius_m].copy()


def generate_street_view_url(lat, lon, heading=0):
    """
    Generate a Google Street View URL for given coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
        heading: Direction to face (0-360 degrees, 0=North)
    
    Returns:
        Google Street View URL
    """
    from utils.constants import STREET_VIEW_URL_TEMPLATE
    return STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lon, heading=heading)


def calculate_centroid(points_df, lat_col='lat', lon_col='lng'):
    """
    Calculate the centroid of a set of points
    
    Args:
        points_df: DataFrame containing points
        lat_col: Name of latitude column
        lon_col: Name of longitude column
    
    Returns:
        Tuple of (centroid_lat, centroid_lon)
    """
    if points_df.empty:
        return None, None
    
    return points_df[lat_col].mean(), points_df[lon_col].mean()


def calculate_bounding_box(points_df, lat_col='lat', lon_col='lng', buffer_pct=0.1):
    """
    Calculate bounding box for a set of points with optional buffer
    
    Args:
        points_df: DataFrame containing points
        lat_col: Name of latitude column
        lon_col: Name of longitude column
        buffer_pct: Percentage to expand the bounding box (0.1 = 10%)
    
    Returns:
        List [[south, west], [north, east]]
    """
    if points_df.empty:
        return None
    
    min_lat, max_lat = points_df[lat_col].min(), points_df[lat_col].max()
    min_lon, max_lon = points_df[lon_col].min(), points_df[lon_col].max()
    
    # Add buffer
    lat_buffer = (max_lat - min_lat) * buffer_pct
    lon_buffer = (max_lon - min_lon) * buffer_pct
    
    return [
        [min_lat - lat_buffer, min_lon - lon_buffer],
        [max_lat + lat_buffer, max_lon + lon_buffer]
    ]
