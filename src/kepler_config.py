"""
Kepler.gl Configuration Module
Provides map configurations for different visualization needs
"""

import pandas as pd
from typing import Dict, List


def get_base_config() -> Dict:
    """Get base Kepler.gl map configuration"""
    return {
        'version': 'v1',
        'config': {
            'visState': {
                'filters': [],
                'layers': [],
                'interactionConfig': {
                    'tooltip': {
                        'fieldsToShow': {},
                        'enabled': True
                    },
                    'brush': {
                        'size': 0.5,
                        'enabled': False
                    }
                },
                'layerBlending': 'normal',
                'splitMaps': [],
                'animationConfig': {
                    'currentTime': None,
                    'speed': 1
                }
            },
            'mapState': {
                'bearing': 0,
                'dragRotate': False,
                'latitude': 53.3498,
                'longitude': -6.2603,
                'pitch': 0,
                'zoom': 11,
                'isSplit': False
            },
            'mapStyle': {
                'styleType': 'dark',
                'topLayerGroups': {},
                'visibleLayerGroups': {
                    'label': True,
                    'road': True,
                    'border': False,
                    'building': True,
                    'water': True,
                    'land': True,
                    '3d building': False
                },
                'threeDBuildingColor': [9.665468314072013, 17.18305478057247, 31.1442867897876],
                'mapStyles': {}
            }
        }
    }


def get_hotspot_layer_config(layer_name: str = 'Hotspots', color: List[int] = None) -> Dict:
    """
    Get layer configuration for hotspots
    
    Args:
        layer_name: Name of the layer
        color: RGB color array [R, G, B]
    
    Returns:
        Layer configuration dict
    """
    color = color or [220, 20, 60]  # Crimson red
    
    return {
        'id': layer_name.lower().replace(' ', '_'),
        'type': 'point',
        'config': {
            'dataId': layer_name,
            'label': layer_name,
            'color': color,
            'columns': {
                'lat': 'center_lat',
                'lng': 'center_lng',
                'altitude': None
            },
            'isVisible': True,
            'visConfig': {
                'radius': 10,
                'fixedRadius': False,
                'opacity': 0.8,
                'outline': True,
                'thickness': 2,
                'strokeColor': [255, 255, 255],
                'colorRange': {
                    'name': 'Global Warming',
                    'type': 'sequential',
                    'category': 'Uber',
                    'colors': ['#5A1846', '#900C3F', '#C70039', '#E3611C', '#F1920E', '#FFC300']
                },
                'strokeColorRange': {
                    'name': 'Global Warming',
                    'type': 'sequential',
                    'category': 'Uber',
                    'colors': ['#5A1846', '#900C3F', '#C70039', '#E3611C', '#F1920E', '#FFC300']
                },
                'radiusRange': [5, 50],
                'filled': True
            },
            'hidden': False,
            'textLabel': [
                {
                    'field': None,
                    'color': [255, 255, 255],
                    'size': 18,
                    'offset': [0, 0],
                    'anchor': 'start',
                    'alignment': 'center'
                }
            ]
        },
        'visualChannels': {
            'colorField': {
                'name': 'priority_score',
                'type': 'real'
            },
            'colorScale': 'quantile',
            'strokeColorField': None,
            'strokeColorScale': 'quantile',
            'sizeField': {
                'name': 'event_count',
                'type': 'integer'
            },
            'sizeScale': 'sqrt'
        }
    }


def get_perception_layer_config(layer_name: str = 'Perception Reports') -> Dict:
    """Get layer configuration for perception reports"""
    return {
        'id': 'perception_reports',
        'type': 'point',
        'config': {
            'dataId': layer_name,
            'label': layer_name,
            'color': [30, 150, 255],  # Blue
            'columns': {
                'lat': 'lat',
                'lng': 'lng',
                'altitude': None
            },
            'isVisible': True,
            'visConfig': {
                'radius': 5,
                'fixedRadius': False,
                'opacity': 0.6,
                'outline': True,
                'thickness': 1,
                'strokeColor': [255, 255, 255],
                'colorRange': {
                    'name': 'Ice And Fire',
                    'type': 'diverging',
                    'category': 'Uber',
                    'colors': ['#0198BD', '#49E3CE', '#E8FEB5', '#FEEDB1', '#FEAD54', '#D50255']
                },
                'radiusRange': [3, 15],
                'filled': True
            },
            'hidden': False,
            'textLabel': [
                {
                    'field': None,
                    'color': [255, 255, 255],
                    'size': 18,
                    'offset': [0, 0],
                    'anchor': 'start',
                    'alignment': 'center'
                }
            ]
        },
        'visualChannels': {
            'colorField': {
                'name': 'report_type',
                'type': 'string'
            },
            'colorScale': 'ordinal',
            'strokeColorField': None,
            'strokeColorScale': 'quantile',
            'sizeField': None,
            'sizeScale': 'linear'
        }
    }


def get_sensor_events_layer_config(layer_name: str = 'Sensor Events') -> Dict:
    """Get layer configuration for raw sensor events"""
    return {
        'id': 'sensor_events',
        'type': 'point',
        'config': {
            'dataId': layer_name,
            'label': layer_name,
            'color': [255, 165, 0],  # Orange
            'columns': {
                'lat': 'position_latitude',
                'lng': 'position_longitude',
                'altitude': None
            },
            'isVisible': False,  # Hidden by default
            'visConfig': {
                'radius': 3,
                'fixedRadius': False,
                'opacity': 0.5,
                'outline': False,
                'thickness': 1,
                'strokeColor': None,
                'colorRange': {
                    'name': 'Global Warming',
                    'type': 'sequential',
                    'category': 'Uber',
                    'colors': ['#5A1846', '#900C3F', '#C70039', '#E3611C', '#F1920E', '#FFC300']
                },
                'radiusRange': [1, 10],
                'filled': True
            },
            'hidden': False,
            'textLabel': [
                {
                    'field': None,
                    'color': [255, 255, 255],
                    'size': 18,
                    'offset': [0, 0],
                    'anchor': 'start',
                    'alignment': 'center'
                }
            ]
        },
        'visualChannels': {
            'colorField': {
                'name': 'max_severity',
                'type': 'integer'
            },
            'colorScale': 'quantile',
            'strokeColorField': None,
            'strokeColorScale': 'quantile',
            'sizeField': {
                'name': 'max_severity',
                'type': 'integer'
            },
            'sizeScale': 'linear'
        }
    }


def get_heatmap_layer_config(layer_name: str = 'Event Density') -> Dict:
    """Get heatmap layer configuration"""
    return {
        'id': 'heatmap',
        'type': 'heatmap',
        'config': {
            'dataId': layer_name,
            'label': layer_name,
            'color': [255, 0, 0],
            'columns': {
                'lat': 'position_latitude',
                'lng': 'position_longitude'
            },
            'isVisible': False,  # Hidden by default
            'visConfig': {
                'opacity': 0.8,
                'colorRange': {
                    'name': 'Global Warming',
                    'type': 'sequential',
                    'category': 'Uber',
                    'colors': ['#5A1846', '#900C3F', '#C70039', '#E3611C', '#F1920E', '#FFC300']
                },
                'radius': 20
            },
            'hidden': False,
            'textLabel': [
                {
                    'field': None,
                    'color': [255, 255, 255],
                    'size': 18,
                    'offset': [0, 0],
                    'anchor': 'start',
                    'alignment': 'center'
                }
            ]
        },
        'visualChannels': {
            'weightField': {
                'name': 'max_severity',
                'type': 'integer'
            },
            'weightScale': 'linear'
        }
    }


def prepare_data_for_kepler(hotspots_df: pd.DataFrame,
                            perception_df: pd.DataFrame = None,
                            sensor_df: pd.DataFrame = None) -> Dict:
    """
    Prepare data in Kepler.gl format
    
    Args:
        hotspots_df: Combined hotspots DataFrame
        perception_df: Raw perception reports (optional)
        sensor_df: Raw sensor events (optional)
    
    Returns:
        Dict with datasets for Kepler
    """
    datasets = {}
    
    # Add hotspots
    if not hotspots_df.empty:
        # Flatten nested columns for Kepler
        hotspots_clean = hotspots_df.copy()
        
        # Convert any dict columns to strings
        for col in hotspots_clean.columns:
            if hotspots_clean[col].dtype == 'object':
                try:
                    hotspots_clean[col] = hotspots_clean[col].apply(
                        lambda x: str(x) if isinstance(x, (dict, list)) else x
                    )
                except:
                    pass
        
        datasets['Hotspots'] = hotspots_clean
    
    # Add perception reports
    if perception_df is not None and not perception_df.empty:
        perception_clean = perception_df.copy()
        
        # Add report_type column if not present
        if 'report_type' not in perception_clean.columns:
            perception_clean['report_type'] = 'perception'
        
        datasets['Perception Reports'] = perception_clean
    
    # Add sensor events
    if sensor_df is not None and not sensor_df.empty:
        sensor_clean = sensor_df.copy()
        
        # Convert boolean to string
        if 'is_abnormal_event' in sensor_clean.columns:
            sensor_clean['is_abnormal_event'] = sensor_clean['is_abnormal_event'].astype(str)
        
        datasets['Sensor Events'] = sensor_clean
    
    return datasets


def build_kepler_config(include_perception: bool = True,
                       include_sensor: bool = False,
                       include_heatmap: bool = False) -> Dict:
    """
    Build complete Kepler configuration with selected layers
    
    Args:
        include_perception: Include perception reports layer
        include_sensor: Include raw sensor events layer
        include_heatmap: Include heatmap layer
    
    Returns:
        Complete Kepler config dict
    """
    config = get_base_config()
    layers = []
    
    # Always include hotspots layer
    layers.append(get_hotspot_layer_config())
    
    if include_perception:
        layers.append(get_perception_layer_config())
    
    if include_sensor:
        layers.append(get_sensor_events_layer_config())
    
    if include_heatmap:
        layers.append(get_heatmap_layer_config('Sensor Events'))
    
    config['config']['visState']['layers'] = layers
    
    return config
