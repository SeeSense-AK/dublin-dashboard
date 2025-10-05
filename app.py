"""
Streamlit Smart Hotspot Dashboard
Integrates Kepler.gl, AWS Athena, and Groq AI
Author: SeeSense
"""

import streamlit as st
import pandas as pd
from keplergl import KeplerGl
from streamlit_keplergl import keplergl_static
from modules.smart_hotspot_detector_v2 import SmartHotspotDetectorV2

# -------------------------------------------------------------------
# 🧠 APP CONFIGURATION
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Cycling Safety Hotspot Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🚲 Cycling Safety Hotspot Intelligence Dashboard")

st.markdown(
    """
    This dashboard combines **sensor-based abnormal events** with 
    **user perception reports** to detect and explain urban safety hotspots.  
    Explore where cyclists experience issues and how sensor data supports those perceptions.
    """
)

# -------------------------------------------------------------------
# ⚙️ SIDEBAR FILTERS
# -------------------------------------------------------------------
st.sidebar.header("🔧 Data Filters")

date_range = st.sidebar.date_input("Select Date Range", [])
min_severity = st.sidebar.slider("Minimum Severity Threshold", 0.0, 10.0, 5.0)
min_events = st.sidebar.slider("Minimum Sensor Events per Cluster", 1, 10, 2)
cluster_radius = st.sidebar.slider("Perception Cluster Radius (m)", 10, 100, 50)
min_reports = st.sidebar.slider("Minimum Perception Reports per Cluster", 1, 10, 3)
join_radius = st.sidebar.slider("Sensor–Perception Join Radius (m)", 10, 100, 50)

run_btn = st.sidebar.button("🚀 Run Hotspot Detection")

# -------------------------------------------------------------------
# 📦 LOAD DATA
# -------------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_perception_data():
    infra_df = pd.read_csv("data/infrastructure_reports.csv")
    ride_df = pd.read_csv("data/ride_reports.csv")
    return infra_df, ride_df


infra_df, ride_df = load_perception_data()

# -------------------------------------------------------------------
# 🧮 RUN DETECTION PIPELINE
# -------------------------------------------------------------------
if run_btn:
    st.info("Detecting and enriching hotspots... please wait ⏳")

    sensor_params = {
        "min_severity": min_severity,
        "min_events": min_events,
        "start_date": str(date_range[0]) if date_range else None,
        "end_date": str(date_range[-1]) if date_range else None,
    }

    perception_params = {
        "cluster_radius_m": cluster_radius,
        "min_reports": min_reports,
    }

    detector = SmartHotspotDetectorV2(infra_df, ride_df)
    unified_hotspots = detector.get_unified_hotspots(
        sensor_params=sensor_params,
        perception_params=perception_params,
        radius_m=join_radius,
    )

    if unified_hotspots.empty:
        st.warning("No hotspots detected for the selected filters.")
        st.stop()

    # -------------------------------------------------------------------
    # 🗺️ RENDER KEPPLER MAP
    # -------------------------------------------------------------------
    st.subheader("📍 Hotspot Map")

    # Prepare Kepler map
    kepler_map = KeplerGl(height=650)

    # Simplify GeoDataFrame for Kepler
    map_df = unified_hotspots.copy()
    map_df["lat"] = map_df["geometry"].y
    map_df["lng"] = map_df["geometry"].x

    kepler_map.add_data(
        data=map_df.drop(columns=["geometry"]),
        name="Unified Hotspots"
    )

    keplergl_static(kepler_map)

    # -------------------------------------------------------------------
    # 📊 HOTSPOT DETAILS PANEL
    # -------------------------------------------------------------------
    st.subheader("🧠 Hotspot Insights")

    st.markdown(
        "Each hotspot combines **sensor event intensity**, "
        "**user perception sentiment**, and **AI-generated narrative summaries**."
    )

    # Interactive table
    st.dataframe(
        unified_hotspots[
            [
                "final_hotspot_id",
                "center_lat",
                "center_lng",
                "event_count",
                "perception_count",
                "dominant_theme",
                "sentiment_label",
                "priority_score",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    # -------------------------------------------------------------------
    # 🧾 DETAILED HOTSPOT SELECTION
    # -------------------------------------------------------------------
    selected_id = st.selectbox(
        "Select a Hotspot for Details",
        unified_hotspots["final_hotspot_id"].tolist(),
    )

    if selected_id:
        hotspot = unified_hotspots.query("final_hotspot_id == @selected_id").iloc[0]

        st.markdown(f"### 📍 Hotspot {selected_id}")
        st.markdown(
            f"**Location:** ({hotspot.center_lat:.5f}, {hotspot.center_lng:.5f})  \n"
            f"**Dominant Theme:** {hotspot.dominant_theme or 'N/A'}  \n"
            f"**Sentiment:** {hotspot.sentiment_label or 'N/A'}  \n"
            f"**Sensor Events:** {int(hotspot.get('event_count', 0))}  \n"
            f"**User Reports:** {int(hotspot.get('perception_count', 0))}  \n"
            f"**Priority Score:** {hotspot.priority_score:.2f}"
        )

        # Street View link
        lat, lon = hotspot.center_lat, hotspot.center_lng
        street_view_url = f"https://www.google.com/maps?q=&layer=c&cbll={lat},{lon}"
        st.markdown(f"[🌐 Open in Google Street View]({street_view_url})")

        # AI Summary
        st.markdown("#### 🤖 AI-Generated Summary")
        st.info(hotspot.ai_summary or "No summary available.")

        # Tooltip summary text
        st.markdown("#### 🧾 Context Summary")
        st.write(hotspot.summary_text)

    # -------------------------------------------------------------------
    # 📈 ANALYTICS PANEL
    # -------------------------------------------------------------------
    st.subheader("📊 Hotspot Analytics Summary")

    st.bar_chart(
        unified_hotspots[["final_hotspot_id", "priority_score"]].set_index(
            "final_hotspot_id"
        )
    )

else:
    st.warning("👈 Configure filters and click **Run Hotspot Detection** to begin.")
