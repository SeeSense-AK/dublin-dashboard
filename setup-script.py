"""
Project Setup Script for Dublin Road Safety Dashboard
Run this script to create the entire project structure and all necessary files.

Usage:
    python setup_project.py
"""

import os
from pathlib import Path


def create_directory_structure():
    """Create all necessary directories"""
    directories = [
        "data/raw",
        "data/processed",
        "src",
        "utils",
        "tests",
        ".streamlit"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {directory}")


def create_file(filepath, content):
    """Create a file with given content"""
    Path(filepath).write_text(content, encoding='utf-8')
    print(f"✓ Created file: {filepath}")


def setup_project():
    """Main setup function"""
    print("🚀 Setting up Dublin Road Safety Dashboard project...\n")
    
    # Create directory structure
    create_directory_structure()
    print()
    
    # .gitignore
    create_file(".gitignore", """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Streamlit
.streamlit/secrets.toml
.streamlit/config.toml

# Data files
data/raw/*.csv
data/processed/*.pkl
data/processed/*.parquet
*.csv
*.xlsx
*.parquet

# Jupyter Notebooks
.ipynb_checkpoints
*.ipynb

# Environment variables
.env
.env.local
config_local.py

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Cache
.cache/
*.cache

# Testing
.pytest_cache/
.coverage
htmlcov/

# API Keys (safety)
*_api_key.txt
secrets.json
""")

    # requirements.txt
    create_file("requirements.txt", """# Core
streamlit==1.31.0
pandas==2.1.4
numpy==1.26.3

# Geospatial
geopandas==0.14.2
folium==0.15.1
streamlit-folium==0.16.0
shapely==2.0.2

# Visualization
plotly==5.18.0
matplotlib==3.8.2
seaborn==0.13.1

# Machine Learning & Clustering
scikit-learn==1.4.0
scipy==1.11.4

# NLP & Sentiment Analysis (using OpenAI-compatible API for Grok)
openai==1.12.0

# Data Processing
pyarrow==14.0.2
openpyxl==3.1.2

# Utilities
python-dotenv==1.0.0
tqdm==4.66.1
requests==2.31.0
""")

    # .env.example
    create_file(".env.example", """# Grok (xAI) API Key for sentiment analysis
# Get your API key from: https://console.x.ai/
XAI_API_KEY=your_grok_api_key_here

# Optional: Custom configuration overrides
# HOTSPOT_RADIUS=25
# ANOMALY_THRESHOLD=2.0
""")

    # config.py
    create_file("config.py", '''"""
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
XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_BASE_URL = "https://api.x.ai/v1"
XAI_MODEL = "grok-beta"  # or "grok-vision-beta" if needed

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
''')

    # README.md
    create_file("README.md", """# Dublin Road Safety Dashboard

A comprehensive dashboard for analyzing road safety data combining sensor readings and perception reports.

## Features

### Tab 1: Hotspot Analysis
- **Sensor-based Hotspot Detection**: Identifies dangerous road segments using accelerometer data and severity metrics
- **Perception Report Matching**: Links user-reported issues within 20-30m radius of detected hotspots
- **Sentiment Analysis**: Analyzes perception reports using Grok AI to understand context and severity
- **Google Street View Integration**: Direct links to visualize actual road conditions
- **Interactive Map**: Explore hotspots with detailed information

### Tab 2: Trend Analysis
- **Time Series Visualization**: Track road usage patterns over time
- **Anomaly Detection**: Identify sudden drops or changes in usage
- **Pattern Recognition**: Discover seasonal or periodic trends
- **Investigative Insights**: Highlight periods requiring further investigation

## Setup

### Prerequisites
- Python 3.9 or higher
- Git
- Grok API key from xAI

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd dublin-road-safety-dashboard
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your data:
   - Place your CSV files in the `data/raw/` directory:
     - `20250831_complete_dataset.csv` (sensor data)
     - `dublin_infra_reports_dublin2025_upto20250924.csv` (infrastructure reports)
     - `dublin_ride_reports_dublin2025_upto20250924.csv` (ride reports)

5. Configure API keys (for sentiment analysis):
   - Create a `.env` file in the root directory
   - Add your Grok API key:
   ```
   XAI_API_KEY=your_grok_api_key_here
   ```

### Running the Dashboard

```bash
streamlit run app.py
```

The dashboard will open in your browser at `http://localhost:8501`

## Project Structure

```
dublin-road-safety-dashboard/
├── app.py                      # Main Streamlit application
├── config.py                   # Configuration settings
├── requirements.txt            # Python dependencies
├── data/
│   ├── raw/                    # Raw CSV files (gitignored)
│   └── processed/              # Processed data cache
├── src/
│   ├── data_loader.py         # Data loading & preprocessing
│   ├── hotspot_analysis.py    # Clustering algorithms
│   ├── perception_matcher.py  # Match reports to hotspots
│   ├── sentiment_analyzer.py  # Sentiment analysis via Grok
│   ├── trend_analysis.py      # Time series analysis
│   └── visualizations.py      # Visualization components
└── utils/
    ├── geo_utils.py           # Geospatial utilities
    └── constants.py           # Project constants
```

## Deployment

### Streamlit Cloud (Recommended for Quick Deployment)

1. Push your code to GitHub (without data files)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Add secrets in Streamlit Cloud settings:
   - `XAI_API_KEY`
5. Deploy!

### Docker Deployment

```bash
docker build -t dublin-dashboard .
docker run -p 8501:8501 dublin-dashboard
```

## Configuration

Edit `config.py` to customize:
- Hotspot detection parameters (clustering threshold, minimum points)
- Perception report matching radius (default: 25m)
- Time series analysis window sizes
- Severity thresholds

## Data Privacy

⚠️ **Important**: CSV data files are gitignored for privacy. When deploying:
- Upload data files separately to your deployment environment
- Never commit sensitive data to version control
- Use environment variables for API keys

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License

[Your License Here]

## Contact

[Your Contact Information]
""")

    # __init__.py files
    create_file("src/__init__.py", "")
    create_file("utils/__init__.py", "")
    create_file("tests/__init__.py", "")
    
    # utils/constants.py
    create_file("utils/constants.py", '''"""
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
''')

    # utils/geo_utils.py
    create_file("utils/geo_utils.py", '''"""
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
''')

    # Placeholder files for src/
    create_file("src/data_loader.py", '''"""
Data loading and preprocessing module
TODO: Implement data loading functions
"""
''')

    create_file("src/hotspot_analysis.py", '''"""
Hotspot detection and clustering module
TODO: Implement hotspot detection
"""
''')

    create_file("src/perception_matcher.py", '''"""
Module for matching perception reports to sensor hotspots
TODO: Implement perception matching
"""
''')

    create_file("src/sentiment_analyzer.py", '''"""
Sentiment analysis module using Grok API
TODO: Implement sentiment analysis
"""
''')

    create_file("src/trend_analysis.py", '''"""
Time series and trend analysis module
TODO: Implement trend analysis
"""
''')

    create_file("src/visualizations.py", '''"""
Visualization components for the dashboard
TODO: Implement visualization functions
"""
''')

    # Placeholder app.py
    create_file("app.py", '''"""
Dublin Road Safety Dashboard
Main Streamlit application
"""
import streamlit as st
from config import DASHBOARD_CONFIG

# Configure page
st.set_page_config(
    page_title=DASHBOARD_CONFIG["title"],
    page_icon=DASHBOARD_CONFIG["page_icon"],
    layout=DASHBOARD_CONFIG["layout"],
    initial_sidebar_state=DASHBOARD_CONFIG["initial_sidebar_state"]
)

st.title("🚗 Dublin Road Safety Dashboard")
st.markdown("### Comprehensive Road Safety Analysis")

st.info("Dashboard under construction. Core modules coming soon!")

# TODO: Implement tabs and functionality
''')

    print("\n" + "="*50)
    print("✅ Project setup complete!")
    print("="*50)
    print("\n📋 Next steps:")
    print("1. Copy your CSV files to data/raw/")
    print("2. Create a .env file (copy from .env.example)")
    print("3. Add your Grok API key to .env")
    print("4. Install dependencies: pip install -r requirements.txt")
    print("5. Run: streamlit run app.py")
    print("\n🚀 Ready to build the core modules!")


if __name__ == "__main__":
    setup_project()
