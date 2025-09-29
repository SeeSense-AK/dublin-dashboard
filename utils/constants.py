"""
Constants used throughout the application
"""

# Earth radius in meters (for distance calculations)
EARTH_RADIUS_M = 6371000

# Coordinate precision
COORDINATE_PRECISION = 6

# Google Street View URL template
STREET_VIEW_URL_TEMPLATE = "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}&heading={heading}&pitch=0&fov=90"

# Map tiles
MAP_TILES = {
    "OpenStreetMap": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "CartoDB Positron": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    "CartoDB Dark Matter": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
}

# Color schemes
SEVERITY_COLORS = {
    0: "#90EE90",  # Light Green
    1: "#FFD700",  # Gold
    2: "#FFA500",  # Orange
    3: "#FF4500",  # Orange Red
    4: "#DC143C",  # Crimson
}

# Data columns that must exist
REQUIRED_SENSOR_COLUMNS = [
    "position_latitude",
    "position_longitude",
    "max_severity",
    "timestamp",
]

REQUIRED_PERCEPTION_COLUMNS = {
    "infra": ["lat", "lng", "infrastructuretype", "finalcomment"],
    "ride": ["lat", "lng", "incidenttype", "commentfinal", "incidentrating"],
}
