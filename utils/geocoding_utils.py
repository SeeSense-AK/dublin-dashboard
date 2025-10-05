"""
Geocoding utilities for reverse geocoding and location names
Uses OpenStreetMap Nominatim service (free, no API key required)
"""

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
import streamlit as st
from functools import lru_cache


# Initialize geocoder with a user agent
geolocator = Nominatim(user_agent="spinovate_safety_dashboard")


@lru_cache(maxsize=200)
def reverse_geocode(lat: float, lng: float, timeout: int = 5) -> dict:
    """
    Reverse geocode coordinates to get location name
    
    Args:
        lat: Latitude
        lng: Longitude
        timeout: Timeout in seconds
    
    Returns:
        Dict with location information
    """
    try:
        # Add small delay to respect OSM rate limits (1 request per second)
        time.sleep(1)
        
        location = geolocator.reverse(f"{lat}, {lng}", timeout=timeout, language='en')
        
        if location:
            address = location.raw.get('address', {})
            
            # Extract useful parts
            location_name = _build_location_name(address)
            
            return {
                'success': True,
                'display_name': location.address,
                'short_name': location_name,
                'road': address.get('road', ''),
                'suburb': address.get('suburb', ''),
                'city': address.get('city', address.get('town', address.get('village', ''))),
                'county': address.get('county', ''),
                'postcode': address.get('postcode', ''),
                'raw': address
            }
        else:
            return _get_fallback_location(lat, lng)
            
    except GeocoderTimedOut:
        st.warning(f"Geocoding timeout for ({lat}, {lng})")
        return _get_fallback_location(lat, lng)
    
    except GeocoderServiceError as e:
        st.warning(f"Geocoding service error: {e}")
        return _get_fallback_location(lat, lng)
    
    except Exception as e:
        st.warning(f"Geocoding error: {e}")
        return _get_fallback_location(lat, lng)


def _build_location_name(address: dict) -> str:
    """Build a concise location name from address components"""
    parts = []
    
    # Priority order for location naming
    if address.get('road'):
        parts.append(address['road'])
    
    if address.get('suburb'):
        parts.append(address['suburb'])
    elif address.get('neighbourhood'):
        parts.append(address['neighbourhood'])
    
    if address.get('city'):
        parts.append(address['city'])
    elif address.get('town'):
        parts.append(address['town'])
    
    if not parts:
        # Fallback to any available location
        for key in ['hamlet', 'village', 'county', 'state']:
            if address.get(key):
                parts.append(address[key])
                break
    
    return ', '.join(parts) if parts else 'Unknown Location'


def _get_fallback_location(lat: float, lng: float) -> dict:
    """Return fallback location when geocoding fails"""
    return {
        'success': False,
        'display_name': f"Location at {lat:.4f}, {lng:.4f}",
        'short_name': f"Lat: {lat:.4f}, Lng: {lng:.4f}",
        'road': '',
        'suburb': '',
        'city': '',
        'county': '',
        'postcode': '',
        'raw': {}
    }


def batch_reverse_geocode(coordinates: list, max_requests: int = 20) -> dict:
    """
    Reverse geocode multiple coordinates with rate limiting
    
    Args:
        coordinates: List of (lat, lng) tuples
        max_requests: Maximum number of geocoding requests to make
    
    Returns:
        Dict mapping (lat, lng) to location info
    """
    results = {}
    
    # Limit to avoid excessive API calls
    coords_to_process = coordinates[:max_requests]
    
    with st.spinner(f"Geocoding {len(coords_to_process)} locations..."):
        for i, (lat, lng) in enumerate(coords_to_process):
            # Round coordinates to reduce cache misses
            lat_rounded = round(lat, 4)
            lng_rounded = round(lng, 4)
            
            location_info = reverse_geocode(lat_rounded, lng_rounded)
            results[(lat_rounded, lng_rounded)] = location_info
            
            # Progress indication
            if (i + 1) % 5 == 0:
                st.info(f"Geocoded {i + 1}/{len(coords_to_process)} locations...")
    
    return results


def get_location_name_safe(lat: float, lng: float, use_geocoding: bool = True) -> str:
    """
    Safely get location name with fallback to coordinates
    
    Args:
        lat: Latitude
        lng: Longitude
        use_geocoding: Whether to attempt geocoding
    
    Returns:
        Location name string
    """
    if not use_geocoding:
        return f"Lat: {lat:.4f}, Lng: {lng:.4f}"
    
    try:
        location = reverse_geocode(round(lat, 4), round(lng, 4))
        return location.get('short_name', f"Lat: {lat:.4f}, Lng: {lng:.4f}")
    except:
        return f"Lat: {lat:.4f}, Lng: {lng:.4f}"


def enrich_hotspots_with_locations(hotspots_df, use_geocoding: bool = True):
    """
    Add location names to hotspots DataFrame
    
    Args:
        hotspots_df: DataFrame with hotspots (must have center_lat, center_lng)
        use_geocoding: Whether to use reverse geocoding
    
    Returns:
        Enriched DataFrame with location_name column
    """
    if hotspots_df.empty:
        return hotspots_df
    
    hotspots_enriched = hotspots_df.copy()
    
    if use_geocoding:
        # Batch geocode
        coordinates = list(zip(hotspots_enriched['center_lat'], hotspots_enriched['center_lng']))
        location_results = batch_reverse_geocode(coordinates)
        
        # Add location names
        hotspots_enriched['location_name'] = hotspots_enriched.apply(
            lambda row: location_results.get(
                (round(row['center_lat'], 4), round(row['center_lng'], 4)),
                {'short_name': f"Lat: {row['center_lat']:.4f}, Lng: {row['center_lng']:.4f}"}
            )['short_name'],
            axis=1
        )
    else:
        # Fallback to coordinates
        hotspots_enriched['location_name'] = hotspots_enriched.apply(
            lambda row: f"Lat: {row['center_lat']:.4f}, Lng: {row['center_lng']:.4f}",
            axis=1
        )
    
    return hotspots_enriched
