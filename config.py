"""
Configuration file for Dublin Road Safety Dashboard
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Create directories if they don't exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Data file paths
SENSOR_DATA_FILE = RAW_DATA_DIR / "20250831_complete_dataset.csv"
INFRA_REPORTS_FILE = RAW_DATA_DIR / "dublin_infra_reports_dublin2025_upto20250924.csv"
RIDE_REPORTS_FILE = RAW_DATA_DIR / "dublin_ride_reports_dublin2025_upto20250924.csv"

# API Configuration - Grok (xAI)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.1-70b-versatile"

# Hotspot Detection Parameters
HOTSPOT_CONFIG = {
    "eps": 0.0003,  # DBSCAN epsilon (approx 30m in degrees)
    "min_samples": 3,  # Minimum points to form a cluster
    "severity_threshold": 2,  # Minimum severity to consider
    "features": ["position_latitude", "position_longitude", "max_severity"],
    "severity_weight": 0.3  # Weight for severity in clustering
}

# Perception Report Matching
PERCEPTION_CONFIG = {
    "matching_radius_m": 25,  # Radius in meters to match reports
    "min_reports_for_analysis": 1,  # Minimum reports needed for sentiment analysis
}

# Time Series Analysis
TIMESERIES_CONFIG = {
    "rolling_window": 7,  # Days for rolling average
    "anomaly_threshold": 2.0,  # Z-score threshold for anomalies
    "min_data_points": 30,  # Minimum points for trend analysis
}

# Visualization Settings
VIZ_CONFIG = {
    "map_zoom_start": 12,
    "map_center": [53.3498, -6.2603],  # Dublin center
    "hotspot_color": "red",
    "perception_color": "blue",
    "cluster_colors": ["red", "orange", "yellow", "green", "blue", "purple"],
}

# Dashboard Settings
DASHBOARD_CONFIG = {
    "title": "Dublin Road Safety Dashboard",
    "page_icon": "🚗",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

# Caching
CACHE_CONFIG = {
    "ttl": 3600,  # Cache time-to-live in seconds (1 hour)
    "use_cache": True,
}

# Severity Labels
SEVERITY_LABELS = {
    0: "None",
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Very High"
}

# Event Type Labels
EVENT_TYPE_LABELS = {
    "acceleration": "Hard Acceleration",
    "braking": "Hard Braking",
    "cornering": "Sharp Turn",
    "pothole": "Pothole/Bump",
}
# Severity Colors (for visualizations)
SEVERITY_COLORS = {
    0: "#90EE90",  # Light Green
    1: "#FFD700",  # Gold
    2: "#FFA500",  # Orange
    3: "#FF4500",  # Orange Red
    4: "#DC143C",  # Crimson
}