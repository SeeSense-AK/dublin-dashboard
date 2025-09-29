# Dublin Road Safety Dashboard

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
source venv/bin/activate  # On Windows: venv\Scripts\activate
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
