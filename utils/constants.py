"""
Constants and configuration for the Dublin Road Safety Dashboard
"""

# Google Street View URL template
STREET_VIEW_URL_TEMPLATE = "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}&heading={heading}"

# Map configuration
DUBLIN_CENTER = [53.3498, -6.2603]
DEFAULT_ZOOM = 12

# Color schemes
SEVERITY_COLORS = {
    'critical': '#DC2626',  # Red
    'high': '#F59E0B',      # Orange  
    'medium': '#10B981',    # Green
    'low': '#6B7280'        # Gray
}

LAYER_COLORS = {
    'popularity': ['#0000FF', '#00FFFF', '#00FF00', '#FFFF00', '#FF0000'],
    'safety': ['#FFFF00', '#FF8C00', '#FF0000', '#8B0000']
}

# Data processing parameters
HOTSPOT_DISTRIBUTION = {
    'sensor': 0.5,      # 50% sensor data
    'perception': 0.3,  # 30% perception data  
    'corridor': 0.2     # 20% corridor data
}

# Grid resolution for trend analysis
GRID_RESOLUTION_M = 6

# File paths
DATA_DIR = "data/processed/tab1_hotspots"
TREND_DATA_DIR = "data/processed/tab2_trend"

# API configurations (if needed)
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30