#!/usr/bin/env python3
"""
Hotspot to Corridor Geometry Matcher
======================================

This script matches hotspots from JSON output with corridor geometry from GeoJSON
and creates an enhanced output with actual road segments instead of points.

Author: Abhishek Kumbhar
Date: November 2025
Version: 1.0

Usage:
    python corridor_matcher.py

Inputs:
    - top_30_hotspots_v2.json (hotspot ranking output)
    - corridors.geojson (road corridor geometries)

Outputs:
    - hotspots_with_corridors.json (enhanced with corridor geometry)
    - corridor_matching_summary.txt (matching statistics)
"""

import json
import re
from pathlib import Path
from datetime import datetime  # ADD THIS IMPORT
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration settings for corridor matching"""
    
    # Input file paths
    HOTSPOTS_JSON_PATH = "//Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/tests/top_30_hotspots_v2.json"
    CORRIDORS_GEOJSON_PATH = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/tests/map-6.geojson"
    
    # Output directory
    OUTPUT_DIR = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/tests/"
    
    # Street name matching parameters
    FUZZY_MATCH_THRESHOLD = 0.95  # Minimum similarity score for fuzzy matching
    USE_FUZZY_MATCHING = False   # Set to False for exact matching only
    
    # Output options
    INCLUDE_POINT_COORDS_AS_FALLBACK = True  # Keep point coords if no corridor match
    INCLUDE_MATCH_CONFIDENCE = False           # Add confidence score to output


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def normalize_street_name(name: str) -> str:
    """
    Normalize street names for better matching.
    
    Args:
        name: Raw street name
    
    Returns:
        Normalized street name
    """
    if not name or not isinstance(name, str):
        return ""
    
    # Convert to lowercase
    normalized = name.lower().strip()
    
    # Remove common suffixes and prefixes
    suffixes_to_remove = [
        'street', 'st', 'road', 'rd', 'avenue', 'ave', 'boulevard', 'blvd',
        'drive', 'dr', 'lane', 'ln', 'court', 'ct', 'place', 'pl', 'way',
        'terrace', 'ter', 'crescent', 'cres', 'close', 'square', 'sq',
        'circle', 'cir', 'park', 'pk', 'row', 'alley', 'ally'
    ]
    
    # Remove suffixes
    for suffix in suffixes_to_remove:
        pattern = r'\s+' + re.escape(suffix) + r'\.?$'
        normalized = re.sub(pattern, '', normalized)
    
    # Remove "the" prefix
    normalized = re.sub(r'^the\s+', '', normalized)
    
    # Remove extra whitespace and punctuation
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Handle special cases
    if normalized == "st":  # Single "st" could be "saint" or "street"
        return "saint"
    
    return normalized


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two street names.
    
    Args:
        name1: First street name
        name2: Second street name
    
    Returns:
        Similarity score (0-1)
    """
    if not name1 or not name2:
        return 0.0
    
    # Normalize both names
    norm1 = normalize_street_name(name1)
    norm2 = normalize_street_name(name2)
    
    # Exact match after normalization
    if norm1 == norm2:
        return 1.0
    
    # Token-based similarity
    tokens1 = set(norm1.split())
    tokens2 = set(norm2.split())
    
    if not tokens1 or not tokens2:
        return 0.0
    
    # Jaccard similarity
    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))
    
    if union == 0:
        return 0.0
    
    return intersection / union


def find_best_corridor_match(hotspot_street: str, corridors: List[Dict]) -> Tuple[Optional[Dict], float]:
    """
    Find the best matching corridor for a hotspot street name.
    """
    if not hotspot_street or not corridors:
        return None, 0.0
    
    best_match = None
    best_score = 0.0
    
    for corridor in corridors:
        properties = corridor.get('properties', {})
        
        # Check ALL possible street name fields
        corridor_street = (
            properties.get('street_name') or  # Your data has this
            properties.get('road_name') or
            properties.get('name') or
            properties.get('street') or
            properties.get('addr:street') or
            properties.get('ref')  # Sometimes road reference numbers
        )
        
        if not corridor_street:
            continue
        
        # Calculate similarity
        similarity = calculate_name_similarity(hotspot_street, corridor_street)
        
        # Check if this is the best match so far
        if similarity > best_score:
            best_score = similarity
            best_match = corridor
    
    return best_match, best_score


def extract_corridor_geometry(corridor_feature: Dict) -> Optional[Dict]:
    """
    Extract and format corridor geometry from GeoJSON feature.
    
    Args:
        corridor_feature: GeoJSON feature
    
    Returns:
        Formatted geometry dict or None
    """
    if not corridor_feature:
        return None
    
    geometry = corridor_feature.get('geometry')
    if not geometry:
        return None
    
    geometry_type = geometry.get('type')
    coordinates = geometry.get('coordinates')
    
    if not geometry_type or not coordinates:
        return None
    
    # Handle different geometry types
    if geometry_type == 'Polygon':
        # Extract the outer ring of the polygon
        if coordinates and len(coordinates) > 0:
            # For polygon, we might want the first ring (exterior)
            polygon_coords = coordinates[0]
            
            # Calculate center point (for display purposes)
            if polygon_coords:
                lats = [coord[1] for coord in polygon_coords]
                lngs = [coord[0] for coord in polygon_coords]
                center_lat = sum(lats) / len(lats)
                center_lng = sum(lngs) / len(lngs)
            else:
                center_lat, center_lng = None, None
            
            return {
                'type': 'corridor_polygon',
                'geometry_type': 'Polygon',
                'coordinates': coordinates,
                'center_point': {
                    'latitude': center_lat,
                    'longitude': center_lng
                } if center_lat and center_lng else None
            }
    
    elif geometry_type == 'LineString':
        # For LineString, we can use it directly
        line_coords = coordinates
        
        # Calculate center point
        if line_coords:
            lats = [coord[1] for coord in line_coords]
            lngs = [coord[0] for coord in line_coords]
            center_lat = sum(lats) / len(lats)
            center_lng = sum(lngs) / len(lngs)
        else:
            center_lat, center_lng = None, None
        
        return {
            'type': 'corridor_linestring',
            'geometry_type': 'LineString',
            'coordinates': coordinates,
            'center_point': {
                'latitude': center_lat,
                'longitude': center_lng
            } if center_lat and center_lng else None
        }
    
    elif geometry_type == 'MultiLineString':
        # For MultiLineString, we can flatten or take the first one
        if coordinates and len(coordinates) > 0:
            # Take the first LineString for simplicity
            first_line = coordinates[0]
            
            if first_line:
                lats = [coord[1] for coord in first_line]
                lngs = [coord[0] for coord in first_line]
                center_lat = sum(lats) / len(lats)
                center_lng = sum(lngs) / len(lngs)
            else:
                center_lat, center_lng = None, None
            
            return {
                'type': 'corridor_multilinestring',
                'geometry_type': 'MultiLineString',
                'coordinates': coordinates,
                'center_point': {
                    'latitude': center_lat,
                    'longitude': center_lng
                } if center_lat and center_lng else None
            }
    
    return None


def extract_corridor_properties(corridor_feature: Dict) -> Dict:
    """
    Extract relevant properties from corridor feature.
    
    Args:
        corridor_feature: GeoJSON feature
    
    Returns:
        Dictionary of corridor properties
    """
    if not corridor_feature:
        return {}
    
    properties = corridor_feature.get('properties', {})
    
    # Extract relevant properties
    return {
        'road_name': properties.get('road_name'),
        'osmid': properties.get('osmid'),
        'highway': properties.get('highway'),
        'lanes': properties.get('lanes'),
        'maxspeed': properties.get('maxspeed'),
        'length': properties.get('length'),
        'report_count': properties.get('report_count'),
        'dominant_category': properties.get('dominant_category'),
        'avg_severity': properties.get('avg_severity'),
        'max_severity': properties.get('max_severity'),
        'weighted_score': properties.get('weighted_score'),
        'priority_rank': properties.get('priority_rank'),
        'priority_category': properties.get('priority_category')
    }


# ============================================================================
# MAIN MATCHING CLASS
# ============================================================================

class CorridorMatcher:
    """Main class for matching hotspots with corridor geometry"""
    
    def __init__(self, config):
        self.config = config
        self.hotspots = []
        self.corridors = []
        self.matched_results = []
        self.matching_stats = {
            'total_hotspots': 0,
            'matched_with_corridors': 0,
            'partial_matches': 0,
            'no_matches': 0,
            'average_confidence': 0.0
        }
    
    def load_data(self):
        """Load hotspots and corridor data"""
        print("=" * 80)
        print("LOADING DATA")
        print("=" * 80)
        
        # Load hotspots data
        print(f"\nLoading hotspots from: {self.config.HOTSPOTS_JSON_PATH}")
        with open(self.config.HOTSPOTS_JSON_PATH, 'r') as f:
            self.hotspots = json.load(f)
        
        print(f"  Loaded {len(self.hotspots)} hotspots")
        self.matching_stats['total_hotspots'] = len(self.hotspots)
        
        # Load corridor data
        print(f"\nLoading corridors from: {self.config.CORRIDORS_GEOJSON_PATH}")
        with open(self.config.CORRIDORS_GEOJSON_PATH, 'r') as f:
            corridors_data = json.load(f)
        
        # Extract features from GeoJSON
        if corridors_data.get('type') == 'FeatureCollection':
            self.corridors = corridors_data.get('features', [])
        elif corridors_data.get('type') == 'Feature':
            self.corridors = [corridors_data]
        else:
            # Assume it's a list of features
            self.corridors = corridors_data
        
        print(f"  Loaded {len(self.corridors)} corridor features")
        
        # Print sample of corridor street names
        print(f"\n  Sample corridor street names:")
        unique_names = set()
        for corridor in self.corridors[:10]:
            props = corridor.get('properties', {})
            name = props.get('road_name') or props.get('name')
            if name:
                unique_names.add(name)
        
        for name in list(unique_names)[:5]:
            print(f"    - {name}")
        
        print("\n✓ Data loading complete")
    
    def match_hotspots_with_corridors(self):
        """Match each hotspot with corridor geometry"""
        print("\n" + "=" * 80)
        print("MATCHING HOTSPOTS WITH CORRIDORS")
        print("=" * 80)
        
        total_confidence = 0.0
        
        for hotspot in self.hotspots:
            identification = hotspot.get('identification', {})
            street_name = identification.get('street_name', '')
            
            print(f"\nProcessing: {street_name}")
            
            # Find best corridor match
            corridor_match, confidence = find_best_corridor_match(street_name, self.corridors)
            
            # Create enhanced hotspot
            enhanced_hotspot = hotspot.copy()
            
            # Add corridor information if match found
            if corridor_match and confidence >= self.config.FUZZY_MATCH_THRESHOLD:
                # Extract corridor geometry
                corridor_geometry = extract_corridor_geometry(corridor_match)
                corridor_properties = extract_corridor_properties(corridor_match)
                
                # Add corridor data to hotspot
                enhanced_hotspot['corridor_data'] = {
                    'match_confidence': confidence,
                    'geometry': corridor_geometry,
                    'properties': corridor_properties,
                    'match_status': 'full_match'
                }
                
                # Update original coordinates if geometry available
                if corridor_geometry and corridor_geometry.get('center_point'):
                    center = corridor_geometry['center_point']
                    enhanced_hotspot['identification']['latitude'] = center['latitude']
                    enhanced_hotspot['identification']['longitude'] = center['longitude']
                    enhanced_hotspot['identification']['geometry_type'] = 'corridor'
                
                self.matching_stats['matched_with_corridors'] += 1
                print(f"  ✓ Matched with corridor (confidence: {confidence:.2f})")
                
            elif corridor_match and confidence >= 0.5:  # Partial match
                corridor_geometry = extract_corridor_geometry(corridor_match)
                corridor_properties = extract_corridor_properties(corridor_match)
                
                enhanced_hotspot['corridor_data'] = {
                    'match_confidence': confidence,
                    'geometry': corridor_geometry,
                    'properties': corridor_properties,
                    'match_status': 'partial_match'
                }
                
                self.matching_stats['partial_matches'] += 1
                print(f"  ~ Partial match (confidence: {confidence:.2f})")
                
            else:
                # No corridor match found
                enhanced_hotspot['corridor_data'] = {
                    'match_confidence': 0.0,
                    'geometry': None,
                    'properties': {},
                    'match_status': 'no_match'
                }
                
                # Keep original point coordinates as fallback
                if self.config.INCLUDE_POINT_COORDS_AS_FALLBACK:
                    enhanced_hotspot['identification']['geometry_type'] = 'point'
                
                self.matching_stats['no_matches'] += 1
                print(f"  ✗ No corridor match found")
            
            # Add match confidence if configured
            if self.config.INCLUDE_MATCH_CONFIDENCE:
                enhanced_hotspot['identification']['match_confidence'] = confidence
            
            total_confidence += confidence
            self.matched_results.append(enhanced_hotspot)
        
        # Calculate average confidence
        if self.matching_stats['total_hotspots'] > 0:
            self.matching_stats['average_confidence'] = total_confidence / self.matching_stats['total_hotspots']
        
        print("\n✓ Matching complete")
    
    def generate_outputs(self):
        """Generate output files"""
        print("\n" + "=" * 80)
        print("GENERATING OUTPUT FILES")
        print("=" * 80)
        
        # Ensure output directory exists
        output_dir = Path(self.config.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # ========================================
        # Enhanced JSON Output
        # ========================================
        json_output_path = output_dir / "hotspots_with_corridors.json"
        
        # Create GeoJSON FeatureCollection for map display
        geojson_features = []
        
        for hotspot in self.matched_results:
            identification = hotspot.get('identification', {})
            corridor_data = hotspot.get('corridor_data', {})
            
            # Create GeoJSON feature
            feature = {
                'type': 'Feature',
                'properties': {
                    'rank': hotspot.get('rank'),
                    'street_name': identification.get('street_name'),
                    'cluster_id': identification.get('cluster_id'),
                    'composite_score': hotspot.get('scores', {}).get('composite_score'),
                    'collision_total_count': hotspot.get('collision_reports', {}).get('total_count'),
                    'has_fatality': hotspot.get('flags', {}).get('has_fatality'),
                    'has_serious_injury': hotspot.get('flags', {}).get('has_serious_injury'),
                    'match_confidence': identification.get('match_confidence', 0.0),
                    'match_status': corridor_data.get('match_status', 'no_match'),
                    'corridor_road_name': corridor_data.get('properties', {}).get('road_name'),
                    'corridor_length': corridor_data.get('properties', {}).get('length'),
                    'corridor_report_count': corridor_data.get('properties', {}).get('report_count'),
                    'corridor_priority': corridor_data.get('properties', {}).get('priority_category')
                }
            }
            
            # Add geometry based on match status
            corridor_geometry = corridor_data.get('geometry')
            
            if corridor_geometry and corridor_geometry.get('coordinates'):
                # Use corridor geometry
                feature['geometry'] = {
                    'type': corridor_geometry.get('geometry_type'),
                    'coordinates': corridor_geometry.get('coordinates')
                }
            else:
                # Fall back to point geometry
                feature['geometry'] = {
                    'type': 'Point',
                    'coordinates': [
                        identification.get('longitude'),
                        identification.get('latitude')
                    ]
                }
            
            geojson_features.append(feature)
        
        # Create complete GeoJSON
        geojson_output = {
            'type': 'FeatureCollection',
            'features': geojson_features
        }
        
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson_output, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ GeoJSON file created: {json_output_path}")
        print(f"  Contains {len(geojson_features)} features with corridor geometry")
        
        # ========================================
        # Enhanced detailed JSON (with all original data)
        # ========================================
        detailed_json_path = output_dir / "hotspots_with_corridors_detailed.json"
        
        with open(detailed_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.matched_results, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Detailed JSON file created: {detailed_json_path}")
        
        # ========================================
        # Summary Text File
        # ========================================
        summary_path = output_dir / "corridor_matching_summary.txt"
        
        with open(summary_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("CORRIDOR MATCHING SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Matching Threshold: {self.config.FUZZY_MATCH_THRESHOLD}\n")
            f.write(f"Fuzzy Matching: {'Enabled' if self.config.USE_FUZZY_MATCHING else 'Disabled'}\n")
            f.write(f"\n")
            
            f.write("MATCHING STATISTICS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total hotspots processed: {self.matching_stats['total_hotspots']}\n")
            f.write(f"Full corridor matches (≥{self.config.FUZZY_MATCH_THRESHOLD}): {self.matching_stats['matched_with_corridors']} ({self.matching_stats['matched_with_corridors']/self.matching_stats['total_hotspots']*100:.1f}%)\n")
            f.write(f"Partial matches (≥0.5): {self.matching_stats['partial_matches']} ({self.matching_stats['partial_matches']/self.matching_stats['total_hotspots']*100:.1f}%)\n")
            f.write(f"No matches: {self.matching_stats['no_matches']} ({self.matching_stats['no_matches']/self.matching_stats['total_hotspots']*100:.1f}%)\n")
            f.write(f"Average match confidence: {self.matching_stats['average_confidence']:.2f}\n")
            f.write(f"\n")
            
            # Top matches
            f.write("TOP 10 HIGHEST CONFIDENCE MATCHES\n")
            f.write("-" * 80 + "\n")
            
            # Sort by match confidence
            sorted_hotspots = sorted(
                self.matched_results,
                key=lambda x: x.get('identification', {}).get('match_confidence', 0),
                reverse=True
            )
            
            for i, hotspot in enumerate(sorted_hotspots[:10], 1):
                ident = hotspot.get('identification', {})
                corridor = hotspot.get('corridor_data', {})
                
                f.write(f"\n#{i}: {ident.get('street_name')}\n")
                f.write(f"    Match confidence: {ident.get('match_confidence', 0):.2f}\n")
                f.write(f"    Match status: {corridor.get('match_status', 'no_match')}\n")
                
                if corridor.get('properties', {}).get('road_name'):
                    f.write(f"    Matched corridor: {corridor['properties']['road_name']}\n")
                
                if corridor.get('properties', {}).get('length'):
                    f.write(f"    Corridor length: {corridor['properties']['length']:.0f}m\n")
            
            # No matches list
            no_matches = [h for h in self.matched_results 
                         if h.get('corridor_data', {}).get('match_status') == 'no_match']
            
            if no_matches:
                f.write(f"\nHOTSPOTS WITHOUT CORRIDOR MATCHES\n")
                f.write("-" * 80 + "\n")
                for hotspot in no_matches[:10]:
                    street_name = hotspot.get('identification', {}).get('street_name', 'Unknown')
                    f.write(f"  - {street_name}\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF SUMMARY\n")
            f.write("=" * 80 + "\n")
        
        print(f"✓ Summary file created: {summary_path}")
        
        print(f"\n✅ All output files created successfully!")
        print(f"\nOutput location: {output_dir}")
        print(f"  - hotspots_with_corridors.json (GeoJSON for map display)")
        print(f"  - hotspots_with_corridors_detailed.json (All data with corridor info)")
        print(f"  - corridor_matching_summary.txt (Matching statistics)")
        
    def run(self):
        """Run the complete corridor matching pipeline"""
        print("\n")
        print("█" * 80)
        print("█" + " " * 78 + "█")
        print("█" + "  CORRIDOR GEOMETRY MATCHER".center(78) + "█")
        print("█" + " " * 78 + "█")
        print("█" * 80)
        print("\n")
        
        self.load_data()
        self.match_hotspots_with_corridors()
        self.generate_outputs()
        
        print("\n" + "█" * 80)
        print("█" + " " * 78 + "█")
        print("█" + "  MATCHING COMPLETE ✓".center(78) + "█")
        print("█" + " " * 78 + "█")
        print("█" * 80)
        print("\n")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    config = Config()
    matcher = CorridorMatcher(config)
    matcher.run()