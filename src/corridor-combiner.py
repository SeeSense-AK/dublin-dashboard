import json
from collections import defaultdict

def combine_road_features(geojson_data):
    road_groups = defaultdict(list)
    
    for feature in geojson_data['features']:
        road_name = feature['properties'].get('road_name')
        
        if isinstance(road_name, list):
            road_name = road_name[0] if road_name else "Unknown"
        elif road_name is None:
            road_name = "Unknown"
            
        road_groups[road_name].append(feature)
    
    combined_features = []
    
    for road_name, features in road_groups.items():
        if len(features) == 1:
            combined_features.append(features[0])
        else:
            combined_feature = combine_single_road_features(road_name, features)
            combined_features.append(combined_feature)
    
    return {
        'type': 'FeatureCollection',
        'features': combined_features
    }

def combine_single_road_features(road_name, features):
    base_feature = features[0].copy()
    combined_properties = combine_properties(features)
    
    all_coordinates = []
    for feature in features:
        if feature['geometry']['type'] == 'Polygon':
            coords = feature['geometry']['coordinates'][0]
            all_coordinates.extend(coords)
    
    combined_geometry = {
        'type': 'Polygon',
        'coordinates': [all_coordinates]
    }
    
    base_feature['properties'] = combined_properties
    base_feature['geometry'] = combined_geometry
    
    return base_feature

def combine_properties(features):
    if not features:
        return {}
    
    combined = features[0]['properties'].copy()
    
    report_counts = []
    max_severities = []
    avg_severities = []
    weighted_scores = []
    all_comments = []
    sources_set = set()
    
    for feature in features:
        props = feature['properties']
        
        if 'report_count' in props and props['report_count'] is not None:
            report_counts.append(props['report_count'])
        if 'max_severity' in props and props['max_severity'] is not None:
            max_severities.append(props['max_severity'])
        if 'avg_severity' in props and props['avg_severity'] is not None:
            avg_severities.append(props['avg_severity'])
        if 'weighted_score' in props and props['weighted_score'] is not None:
            weighted_scores.append(props['weighted_score'])
        
        if 'all_comments' in props and props['all_comments']:
            all_comments.append(props['all_comments'])
        if 'sources' in props and props['sources']:
            if isinstance(props['sources'], str):
                sources_set.add(props['sources'])
            elif isinstance(props['sources'], list):
                sources_set.update(props['sources'])
    
    if report_counts:
        combined['report_count'] = sum(report_counts)
    if max_severities:
        combined['max_severity'] = max(max_severities)
    if avg_severities:
        combined['avg_severity'] = sum(avg_severities) / len(avg_severities)
    if weighted_scores:
        combined['weighted_score'] = sum(weighted_scores)
    if all_comments:
        combined['all_comments'] = ' | '.join(all_comments)
    if sources_set:
        combined['sources'] = list(sources_set)
    
    combined['combined_features'] = len(features)
    
    return combined

# Main execution
if __name__ == "__main__":
    # Load your GeoJSON file
    with open('perception_corridors_polys.geojson', 'r') as f:
        original_data = json.load(f)
    
    # Process the data
    combined_data = combine_road_features(original_data)
    
    # Save the result
    with open('combined_roads.geojson', 'w') as f:
        json.dump(combined_data, f, indent=2)
    
    # Print summary
    print("=== Road Consolidation Complete ===")
    print(f"Original features: {len(original_data['features'])}")
    print(f"Combined features: {len(combined_data['features'])}")
    print(f"Reduction: {len(original_data['features']) - len(combined_data['features'])} features removed")
    
    # Show which roads were combined
    road_counts = {}
    for feature in original_data['features']:
        road_name = feature['properties'].get('road_name')
        if isinstance(road_name, list):
            road_name = road_name[0] if road_name else "Unknown"
        road_counts[road_name] = road_counts.get(road_name, 0) + 1
    
    print("\nRoads that were combined:")
    for road, count in sorted(road_counts.items(), key=lambda x: x[1], reverse=True):
        if count > 1:
            print(f"  {road}: {count} features → 1 combined feature")