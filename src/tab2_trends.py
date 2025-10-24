"""
Tab 2: Cycling Route Trends Analysis
Using Leaflet.TimeDimension for smooth temporal heatmap animation
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import streamlit.components.v1 as components


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


def load_timed_heatmap_html():
    """Load the Leaflet.TimeDimension HTML file"""
    html_file = Path("timed_heatmap.html")
    
    try:
        if html_file.exists():
            with open(html_file, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            st.error(f"HTML file not found: {html_file}")
            st.info("Please ensure 'timed_heatmap.html' is in the same directory as app.py")
            return None
    except Exception as e:
        st.error(f"Error loading HTML file: {e}")
        return None


def create_summary_statistics(df):
    """Create summary statistics for the dataset"""
    if df.empty:
        return {}
    
    stats = {
        'total_records': len(df),
        'date_range': (df['ride_date'].min().date(), df['ride_date'].max().date()) if 'ride_date' in df.columns else None,
        'unique_dates': df['ride_date'].nunique() if 'ride_date' in df.columns else 0,
        'avg_popularity': df['popularity_score'].mean() if 'popularity_score' in df.columns else 0,
        'max_popularity': df['popularity_score'].max() if 'popularity_score' in df.columns else 0,
        'unique_locations': len(df[['latitude', 'longitude']].drop_duplicates()) if all(col in df.columns for col in ['latitude', 'longitude']) else 0
    }
    
    return stats


def render_tab2():
    """Main function to render Tab 2 content"""
    
    st.header("Cycling Route Trends Analysis")
    st.markdown("**Temporal heatmap with Leaflet.TimeDimension animation**")
    
    # Load the HTML file
    html_content = load_timed_heatmap_html()
    
    if html_content is None:
        st.error("Cannot load the temporal heatmap visualization.")
        st.markdown("""
        **Setup Instructions:**
        1. Ensure `timed_heatmap.html` is in the same directory as `app.py`
        2. Ensure your GeoJSON data files are properly referenced in the HTML
        3. Refresh the page after placing the files
        """)
        return
    
    # Load summary data for statistics (optional)
    popularity_df = load_popularity_data()
    
    # Show summary statistics if data is available
    if not popularity_df.empty:
        stats = create_summary_statistics(popularity_df)
        
        # Display summary metrics in sidebar
        st.sidebar.header("Dataset Overview")
        st.sidebar.metric("Total Records", f"{stats['total_records']:,}")
        st.sidebar.metric("Time Period", f"{stats['unique_dates']} days")
        
        if stats['date_range']:
            st.sidebar.write(f"**From:** {stats['date_range'][0]}")
            st.sidebar.write(f"**To:** {stats['date_range'][1]}")
        
        st.sidebar.metric("Unique Locations", f"{stats['unique_locations']:,}")
        st.sidebar.metric("Avg Popularity", f"{stats['avg_popularity']:.2f}")
        st.sidebar.metric("Max Popularity", f"{stats['max_popularity']:.2f}")
    
    # Instructions for using the temporal map
    st.sidebar.markdown("---")
    st.sidebar.markdown("**How to Use the Temporal Map:**")
    st.sidebar.markdown("🎮 **Play Controls:** Use the timeline controls at the bottom of the map")
    st.sidebar.markdown("⏯️ **Play/Pause:** Click the play button to animate through time")
    st.sidebar.markdown("⏭️ **Skip:** Drag the timeline slider to jump to specific dates")
    st.sidebar.markdown("🔍 **Zoom:** Use mouse wheel or zoom controls to explore areas")
    st.sidebar.markdown("📅 **Time Display:** Current date/time shown in the control panel")
    
    # Display the temporal heatmap
    st.subheader("Interactive Temporal Heatmap")
    st.markdown("Use the timeline controls below the map to play through different time periods and see how cycling route popularity changes over time.")
    
    # Embed the HTML file using Streamlit components
    components.html(
        html_content,
        width=1200,
        height=700,
        scrolling=False
    )
    
    # Additional information
    with st.expander("About This Visualization"):
        st.markdown("""
        **Technology Stack:**
        - **Leaflet.js**: Interactive mapping library
        - **Leaflet.TimeDimension**: Temporal animation plugin
        - **Leaflet.heat**: Heatmap visualization
        - **GeoJSON**: Temporal geospatial data format
        
        **Features:**
        - **Smooth Animation**: Native JavaScript temporal controls
        - **Interactive Timeline**: Scrub through time or play automatically
        - **Responsive Design**: Zoom and pan while animation plays
        - **Performance Optimized**: Efficient rendering for large datasets
        
        **Data Processing:**
        - Route popularity aggregated on 6m grid
        - Daily temporal resolution
        - Normalized popularity scores for consistent visualization
        
        **Color Scheme:**
        - **Blue**: Low cycling activity
        - **Green/Yellow**: Medium activity  
        - **Red**: High cycling activity
        """)
    
    # Troubleshooting section
    with st.expander("Troubleshooting"):
        st.markdown("""
        **If the map doesn't load:**
        1. **Check file location**: Ensure `timed_heatmap.html` is in the root directory
        2. **Check GeoJSON paths**: Verify data file paths in the HTML are correct
        3. **Browser console**: Open developer tools to check for JavaScript errors
        4. **File permissions**: Ensure files are readable
        
        **If animation doesn't work:**
        1. **Data format**: Ensure GeoJSON has proper temporal properties
        2. **Time field**: Check that time/date fields are properly formatted
        3. **Plugin loading**: Verify Leaflet.TimeDimension plugin loads correctly
        
        **Performance tips:**
        - Large datasets may load slowly
        - Consider data aggregation for better performance
        - Close other browser tabs to free memory
        """)
    
    # File status indicator
    st.markdown("---")
    html_status = "✅ Found" if Path("timed_heatmap.html").exists() else "❌ Missing"
    st.markdown(f"**File Status:** `timed_heatmap.html` - {html_status}")
    
    if not Path("timed_heatmap.html").exists():
        st.warning("Please place your `timed_heatmap.html` file in the same directory as `app.py`")