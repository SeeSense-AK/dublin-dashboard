import plotly.express as px
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import json
from pathlib import Path

def render_tab3():
    st.header("🔥 Route Popularity Time Heatmap")
    
    # --- Load GeoJSON ---
    geojson_path = Path("/Users/abhishekkumbhar/Downloads/route_popularity_W_timeseries.geojson")
    if not geojson_path.exists():
        st.error(f"File not found: {geojson_path}")
        return

    with open(geojson_path, "r") as f:
        data = json.load(f)

    # --- Extract data ---
    all_data = []
    for feat in data["features"]:
        props = feat["properties"]
        coords = feat["geometry"]["coordinates"]
        all_data.append({
            "lon": coords[0],
            "lat": coords[1],
            "time": props["time"],
            "weight": props.get("weight", 1)
        })
    
    df = pd.DataFrame(all_data)
    
    # Debug info
    st.write(f"Total data points: {len(df)}")
    st.write(f"Weight range: {df['weight'].min()} to {df['weight'].max()}")
    
    # Create density heatmap with better parameters
    fig = px.density_mapbox(
        df,
        lat='lat',
        lon='lon',
        z='weight',
        radius=20,  # Increased radius
        zoom=10,
        center=dict(lat=53.35, lon=-6.26),
        mapbox_style="carto-positron",
        title="Route Popularity Heatmap",
        opacity=0.7,  # Added opacity
        hover_data=['time', 'weight']
    )
    
    # Update layout for better visibility
    fig.update_layout(
        height=700,
        margin=dict(l=0, r=0, t=30, b=0)
    )
    
    # Update color scale
    fig.update_traces(
        colorscale='Hot',  # More visible colorscale
        showscale=True,
        zmid=df['weight'].median() if len(df) > 0 else 1
    )
    
    st.plotly_chart(fig, use_container_width=True)