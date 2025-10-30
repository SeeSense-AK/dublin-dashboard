import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from shapely.geometry import MultiLineString
from pathlib import Path

# ==============================
# PAGE SETUP
# ==============================
st.markdown("## 🚲 Route Popularity & Performance Trends")
st.markdown(
    "This section visualizes popular cycling routes and their performance trends across time. "
    "Use the interactive map to explore route-level popularity, safety, and perception metrics."
)

# ==============================
# FILE LOADING (UPDATED)
# ==============================
# Automatically locate files whether running locally or on Streamlit Cloud
BASE_DIR = Path(__file__).resolve().parents[2]  # go up to project root
DATA_DIR = BASE_DIR / "data" / "processed" / "tab2_trend" / "route_popularity"

csv_path = DATA_DIR / "Spinovate Tab 2 - Popularity.csv"
geojson_path = DATA_DIR / "active_segments.geojson"

@st.cache_data
def load_route_data():
    try:
        df_routes = pd.read_csv(csv_path)
    except Exception as e:
        st.error(f"Error loading CSV data: {e}")
        return None, None

    try:
        gdf_routes = gpd.read_file(geojson_path)
    except Exception as e:
        st.warning(f"GeoPandas failed: {e}")
        gdf_routes = None

    return df_routes, gdf_routes

# Load the data
df_routes, gdf_routes = load_route_data()

if df_routes is None or gdf_routes is None:
    st.stop()

# ==============================
# DATA PROCESSING
# ==============================
try:
    df_routes["route_name"] = df_routes["route_name"].fillna("Unnamed Route")
    df_routes["popularity_score"] = df_routes["popularity_score"].fillna(0)
except Exception as e:
    st.error(f"Error processing route data: {e}")
    st.stop()

# Merge geometry with CSV data
try:
    gdf_routes = gdf_routes.merge(df_routes, on="route_name", how="left")
except Exception as e:
    st.error(f"Error merging GeoJSON with CSV: {e}")
    st.stop()

# ==============================
# INTERACTIVE MAP
# ==============================
try:
    m = folium.Map(location=[53.35, -6.26], zoom_start=12, tiles="cartodb positron")

    # Add colored routes based on popularity
    for _, row in gdf_routes.iterrows():
        color = (
            "red"
            if row["popularity_score"] < 4
            else "orange"
            if row["popularity_score"] < 7
            else "green"
        )
        geom = row["geometry"]
        if geom.geom_type == "MultiLineString":
            for line in geom.geoms:
                coords = [(pt[1], pt[0]) for pt in line.coords]
                folium.PolyLine(
                    coords,
                    color=color,
                    weight=4,
                    opacity=0.8,
                    tooltip=f"{row['route_name']} (Score: {row['popularity_score']})",
                ).add_to(m)
        elif geom.geom_type == "LineString":
            coords = [(pt[1], pt[0]) for pt in geom.coords]
            folium.PolyLine(
                coords,
                color=color,
                weight=4,
                opacity=0.8,
                tooltip=f"{row['route_name']} (Score: {row['popularity_score']})",
            ).add_to(m)

    st_data = st_folium(m, width=900, height=600)
except Exception as e:
    st.error(f"Error generating map: {e}")

# ==============================
# ROUTE POPULARITY CHART
# ==============================
try:
    fig = px.bar(
        df_routes.sort_values("popularity_score", ascending=False).head(20),
        x="route_name",
        y="popularity_score",
        color="popularity_score",
        color_continuous_scale="Viridis",
        title="Top 20 Routes by Popularity Score",
    )
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"Error creating popularity chart: {e}")

# ==============================
# SUMMARY STATISTICS
# ==============================
try:
    avg_popularity = df_routes["popularity_score"].mean()
    top_route = df_routes.loc[df_routes["popularity_score"].idxmax(), "route_name"]
    st.markdown(f"**Average Popularity Score:** {avg_popularity:.2f}")
    st.markdown(f"**Most Popular Route:** {top_route}")
except Exception as e:
    st.error(f"Error computing summary statistics: {e}")
