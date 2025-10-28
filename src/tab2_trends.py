"""
Tab 2: Cycling Route Trends Analysis
Using Leaflet.TimeDimension with large file handling
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import streamlit.components.v1 as components
import json


def load_popularity_data():
    """Load route popularity data from Parquet file for summary stats"""
    data_dir = Path("data/processed/tab2_trend")
    popularity_file = data_dir / "route_popularity" / "dailytop50.parquet"
    
    try:
        if popularity_file.exists():
            df = pd.read_parquet(popularity_file)
            # Parse dates
            if 'ride_date' in df.columns:
                df['ride_date'] = pd.to_datetime(df['ride_date'])
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading popularity data: {e}")
        return pd.DataFrame()


def analyze_large_geojson():
    """Analyze GeoJSON structure without loading the entire file"""
    geojson_file = Path("route_popularity_timeseries_small.geojson")
    
    if not geojson_file.exists():
        return None
    
    file_size_mb = geojson_file.stat().st_size / (1024 * 1024)
    st.warning(f"📁 **Large File Detected:** {file_size_mb:.1f} MB")
    
    try:
        # Read just the first few lines to understand structure
        with open(geojson_file, 'r', encoding='utf-8') as f:
            # Read first 1000 characters to get structure
            sample = f.read(1000)
            
        st.markdown("### 🔍 GeoJSON Sample Analysis")
        st.write(f"**File Size:** {file_size_mb:.1f} MB")
        st.write(f"**Sample (first 1000 chars):**")
        st.code(sample, language='json')
        
        # Try to parse the beginning to understand structure
        if sample.strip().startswith('{'):
            # Find the first feature
            f.seek(0)
            line_count = 0
            for line in f:
                if '"features"' in line:
                    st.write("✅ Found features array")
                    break
                if '"properties"' in line:
                    st.write("✅ Found properties")
                    # Try to extract a sample property
                    if 'time' in line.lower() or 'date' in line.lower():
                        st.write(f"🕒 **Temporal data found:** {line.strip()[:100]}...")
                    break
                line_count += 1
                if line_count > 50:  # Don't read too much
                    break
                    
    except Exception as e:
        st.error(f"Error analyzing file: {e}")
        return None
    
    return {"size_mb": file_size_mb}


def create_file_server_html():
    """Create HTML that serves the GeoJSON via a local file server approach"""
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Temporal Heatmap</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        
        <!-- Leaflet CSS -->
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
        
        <!-- Leaflet TimeDimension CSS -->
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet-timedimension@1.1.1/dist/leaflet.timedimension.control.css" />
        
        <style>
            #map { 
                height: 650px; 
                width: 100%;
            }
            .error-message {
                background: #ffebee;
                border: 1px solid #f44336;
                padding: 10px;
                margin: 10px;
                border-radius: 4px;
                color: #c62828;
            }
            .info-message {
                background: #e3f2fd;
                border: 1px solid #2196f3;
                padding: 10px;
                margin: 10px;
                border-radius: 4px;
                color: #1565c0;
            }
        </style>
    </head>
    <body>
        <div id="status" class="info-message">
            📊 Loading temporal heatmap data...
        </div>
        
        <div id="map"></div>
        
        <!-- Leaflet JS -->
        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        
        <!-- Leaflet TimeDimension JS -->
        <script src="https://cdn.jsdelivr.net/npm/iso8601-js-period@0.2.1/iso8601.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/leaflet-timedimension@1.1.1/dist/leaflet.timedimension.min.js"></script>
        
        <!-- Leaflet Heat JS -->
        <script src="https://cdn.jsdelivr.net/npm/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
        
        <script>
            function updateStatus(message, isError = false) {
                const statusDiv = document.getElementById('status');
                statusDiv.textContent = message;
                statusDiv.className = isError ? 'error-message' : 'info-message';
            }
            
            // Initialize map
            var map = L.map('map', {
                zoom: 12,
                center: [53.3498, -6.2603], // Dublin center
                timeDimension: true,
                timeDimensionControl: true,
                timeDimensionOptions: {
                    timeInterval: "2024-01-01/2024-12-31",
                    period: "P1D",
                    currentTime: Date.parse("2024-01-01T00:00:00Z")
                },
                timeDimensionControlOptions: {
                    autoPlay: false,
                    loopButton: true,
                    playReverseButton: true,
                    timeSliderDragUpdate: true,
                    speedSlider: false
                }
            });
            
            // Add base layer
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            
            updateStatus("🗺️ Map initialized, attempting to load data...");
            
            // Try to load GeoJSON with better error handling
            function loadGeojsonData() {
                // Try different approaches to load the large file
                
                // Approach 1: Direct fetch (will likely fail due to CORS/404)
                fetch('route_popularity_timeseries_small.geojson')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        updateStatus("✅ Data loaded successfully! Processing temporal layers...");
                        processGeojsonData(data);
                    })
                    .catch(error => {
                        console.error('Fetch error:', error);
                        updateStatus("❌ Failed to load data via fetch: " + error.message, true);
                        
                        // Provide fallback instructions
                        const statusDiv = document.getElementById('status');
                        statusDiv.innerHTML = `
                            <strong>❌ Unable to load large GeoJSON file (678MB)</strong><br><br>
                            <strong>Solutions:</strong><br>
                            1. <strong>Use a local file server:</strong> Run <code>python -m http.server 8000</code> in your project directory<br>
                            2. <strong>Reduce file size:</strong> Sample or compress your data<br>
                            3. <strong>Use tiled approach:</strong> Split data into smaller temporal chunks<br><br>
                            <strong>Current issue:</strong> Streamlit cannot serve large static files directly.<br>
                            The file exists but cannot be accessed by the embedded HTML.
                        `;
                    });
            }
            
            function processGeojsonData(geojsonData) {
                try {
                    console.log('Processing GeoJSON data:', geojsonData);
                    
                    // Extract temporal information
                    if (!geojsonData.features || geojsonData.features.length === 0) {
                        throw new Error('No features found in GeoJSON');
                    }
                    
                    // Analyze temporal properties
                    const firstFeature = geojsonData.features[0];
                    const props = firstFeature.properties;
                    console.log('First feature properties:', props);
                    
                    // Look for temporal fields
                    const temporalFields = Object.keys(props).filter(key => 
                        key.toLowerCase().includes('time') || 
                        key.toLowerCase().includes('date') ||
                        key.toLowerCase().includes('timestamp')
                    );
                    
                    console.log('Temporal fields found:', temporalFields);
                    
                    if (temporalFields.length === 0) {
                        throw new Error('No temporal fields found in GeoJSON properties');
                    }
                    
                    // Create time dimension layer
                    var geojsonLayer = L.geoJSON(geojsonData, {
                        onEachFeature: function(feature, layer) {
                            // Add popup with properties
                            if (feature.properties) {
                                layer.bindPopup(Object.keys(feature.properties)
                                    .map(key => `<b>${key}:</b> ${feature.properties[key]}`)
                                    .join('<br>'));
                            }
                        }
                    });
                    
                    var timeDimensionLayer = L.timeDimension.layer.geoJson(geojsonLayer, {
                        updateTimeDimension: true,
                        addlastPoint: false,
                        waitForReady: true
                    });
                    
                    timeDimensionLayer.addTo(map);
                    updateStatus(`✅ Temporal layer created with ${geojsonData.features.length} features`);
                    
                } catch (error) {
                    console.error('Processing error:', error);
                    updateStatus("❌ Error processing GeoJSON: " + error.message, true);
                }
            }
            
            // Start loading
            loadGeojsonData();
            
        </script>
    </body>
    </html>
    """
    
    return html_content


def render_tab2():
    """Main function to render Tab 2 content"""
    
    st.header("Cycling Route Trends Analysis")
    st.markdown("**Temporal heatmap with large file handling**")
    
    # Check for the large GeoJSON file
    geojson_file = Path("route_popularity_timeseries_small.geojson")
    
    if not geojson_file.exists():
        st.error("❌ **GeoJSON file not found:** `route_popularity_timeseries_small.geojson`")
        st.info("Please place the file in the same directory as `app.py`")
        return
    
    # Analyze the file without loading it entirely
    file_info = analyze_large_geojson()
    
    # Load summary data for statistics (optional)
    popularity_df = load_popularity_data()
    
    # Show summary statistics if data is available
    if not popularity_df.empty:
        # Display summary metrics in sidebar
        st.sidebar.header("Dataset Overview")
        
        # Create summary statistics
        stats = {
            'total_records': len(popularity_df),
            'unique_dates': popularity_df['ride_date'].nunique() if 'ride_date' in popularity_df.columns else 0,
            'avg_popularity': popularity_df['popularity_score'].mean() if 'popularity_score' in popularity_df.columns else 0,
            'max_popularity': popularity_df['popularity_score'].max() if 'popularity_score' in popularity_df.columns else 0,
        }
        
        st.sidebar.metric("Total Records", f"{stats['total_records']:,}")
        st.sidebar.metric("Time Period", f"{stats['unique_dates']} days")
        st.sidebar.metric("Avg Popularity", f"{stats['avg_popularity']:.2f}")
        st.sidebar.metric("Max Popularity", f"{stats['max_popularity']:.2f}")
    
    # Large file handling options
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔧 Large File Solutions:**")
    
    solution_choice = st.sidebar.radio(
        "Choose approach:",
        [
            "Embedded HTML (Current)",
            "Local File Server",
            "Data Sampling"
        ]
    )
    
    if solution_choice == "Local File Server":
        st.sidebar.markdown("""
        **Steps:**
        1. Open terminal in project directory
        2. Run: `python -m http.server 8000`
        3. Update HTML to use: `http://localhost:8000/route_popularity_timeseries_small.geojson`
        """)
    
    elif solution_choice == "Data Sampling":
        st.sidebar.markdown("""
        **Reduce file size:**
        1. Sample every Nth feature
        2. Reduce temporal resolution
        3. Geographic bounding box
        4. Compress coordinates
        """)
    
    # Instructions for using the temporal map
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🎮 Temporal Map Controls:**")
    st.sidebar.markdown("⏯️ **Play/Pause:** Animate through time")
    st.sidebar.markdown("⏭️ **Step:** Move forward/backward in time")
    st.sidebar.markdown("🔄 **Loop:** Repeat animation")
    st.sidebar.markdown("📅 **Slider:** Jump to specific time")
    
    # Display the temporal heatmap
    st.subheader("Interactive Temporal Heatmap")
    
    # Show file status
    file_size_mb = geojson_file.stat().st_size / (1024 * 1024)
    st.warning(f"⚠️ **Large File Warning:** {file_size_mb:.1f} MB file detected")
    
    if file_size_mb > 100:
        st.error("""
        **File too large for direct embedding!**
        
        **Current limitations:**
        - Streamlit cannot serve large static files directly
        - Browser memory limits for large datasets
        - Network transfer time for 678MB file
        
        **Recommended solutions:**
        1. **Use local file server** (see sidebar)
        2. **Reduce data size** by sampling or temporal aggregation
        3. **Split into smaller temporal chunks**
        """)
    
    # Create and embed the HTML with error handling
    html_content = create_file_server_html()
    
    # Embed the HTML
    components.html(
        html_content,
        width=1200,
        height=700,
        scrolling=False
    )
    
    # Troubleshooting section
    with st.expander("🔧 Troubleshooting Large Files"):
        st.markdown("""
        **Why 678MB is too large:**
        - Streamlit message size limit: 200MB
        - Browser memory consumption
        - Network transfer time
        - JSON parsing overhead
        
        **Solutions in order of preference:**
        
        **1. Local File Server (Recommended)**
        ```bash
        # In your project directory:
        python -m http.server 8000
        
        # Then update your HTML to use:
        # http://localhost:8000/route_popularity_timeseries_small.geojson
        ```
        
        **2. Data Reduction**
        - Sample every 10th feature: reduces to ~68MB
        - Daily aggregation instead of hourly
        - Geographic bounding box for area of interest
        
        **3. Tiled Approach**
        - Split by month: 12 smaller files
        - Load tiles on demand
        - Progressive loading
        
        **4. Alternative Formats**
        - Parquet with spatial extension
        - Vector tiles (MVT)
        - Compressed GeoJSON
        """)