"""
Constants used throughout the application
"""

# Earth radius in meters (for distance calculations)
EARTH_RADIUS_M = 6371000

# Coordinate precision
COORDINATE_PRECISION = 6

# Google Street View URL template
STREET_VIEW_URL_TEMPLATE = "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}&heading={heading}&pitch=0&fov=80"

# Map tiles
MAP_TILES = {
    "OpenStreetMap": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "CartoDB Positron": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    "CartoDB Dark Matter": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
}

# Color schemes for severity/priority
SEVERITY_COLORS = {
    'CRITICAL': '#DC2626',  # Red
    'HIGH': '#F59E0B',      # Orange
    'MEDIUM': '#10B981',    # Green
    'LOW': '#6B7280'        # Gray
}

# Hotspot distribution weights
HOTSPOT_WEIGHTS = {
    'sensor': 0.5,      # 50% from sensor data
    'perception': 0.3,  # 30% from perception + sensor
    'corridor': 0.2     # 20% from corridor reports
}
