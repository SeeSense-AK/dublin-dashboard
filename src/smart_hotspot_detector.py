"""
Smart Hotspot Detector v2
Enhanced for Streamlit + Kepler dashboard integration
- Aggregates sensor & perception data into unified, context-rich hotspots
- Uses spatial clustering and NLP sentiment/theme extraction
- Generates AI-based summaries for each hotspot (Groq)
"""

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from sklearn.cluster import DBSCAN
from typing import Dict, List, Optional
from utils.geo_utils import haversine_distance
from src.athena_database import get_athena_database
from src.sentiment_analyzer import analyze_perception_sentiment
from src.theme_extractor import extract_perception_themes   # new optional module
from src.groq_ai import generate_hotspot_summary             # new Groq wrapper


class SmartHotspotDetectorV2:
    """
    Enhanced intelligent hotspot detector combining sensor + perception data
    Optimized for Kepler and Streamlit dashboard integration
    """

    def __init__(self, infra_df: pd.DataFrame, ride_df: pd.DataFrame):
        self.infra_df = infra_df
        self.ride_df = ride_df
        self.athena_db = get_athena_database()

    # -------------------------------------------------------------------------
    # 1. SENSOR HOTSPOT DETECTION
    # -------------------------------------------------------------------------
    def detect_sensor_hotspots(
        self,
        min_severity: float = 5.0,
        min_events: int = 2,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Detect hotspots from Athena sensor data
        Returns DataFrame with severity, event counts, and coordinates
        """
        df = self.athena_db.detect_sensor_hotspots(
            min_events=min_events,
            severity_threshold=min_severity,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            return df

        df.rename(
            columns={
                "lat": "center_lat",
                "lng": "center_lng",
                "event_count": "event_count",
                "severity_score": "avg_severity",
            },
            inplace=True,
        )

        df["source"] = "sensor"
        df["hotspot_id"] = ["sensor_" + str(i) for i in range(len(df))]
        df["risk_score"] = df["avg_severity"] * np.log1p(df["event_count"])
        df["geometry"] = [Point(xy) for xy in zip(df.center_lng, df.center_lat)]
        df["dominant_theme"] = None
        df["sentiment_label"] = None

        return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

    # -------------------------------------------------------------------------
    # 2. PERCEPTION HOTSPOT DETECTION
    # -------------------------------------------------------------------------
    def detect_perception_hotspots(
        self, cluster_radius_m: int = 50, min_reports: int = 3
    ) -> gpd.GeoDataFrame:
        """
        Cluster perception reports into hotspots using DBSCAN
        """
        combined = []

        if not self.infra_df.empty:
            infra = self.infra_df.rename(
                columns={
                    "lat": "lat",
                    "lng": "lng",
                    "infrastructuretype": "theme",
                    "finalcomment": "comment",
                }
            )
            infra["source"] = "infrastructure"
            combined.append(infra[["lat", "lng", "theme", "comment", "source"]])

        if not self.ride_df.empty:
            ride = self.ride_df.rename(
                columns={
                    "lat": "lat",
                    "lng": "lng",
                    "incidenttype": "theme",
                    "commentfinal": "comment",
                }
            )
            ride["source"] = "ride"
            combined.append(ride[["lat", "lng", "theme", "comment", "source"]])

        if not combined:
            return gpd.GeoDataFrame(columns=["lat", "lng", "theme", "comment", "source"])

        all_reports = pd.concat(combined, ignore_index=True)

        coords = all_reports[["lat", "lng"]].values
        eps_deg = cluster_radius_m / 111000
        clustering = DBSCAN(eps=eps_deg, min_samples=min_reports).fit(coords)
        all_reports["cluster_id"] = clustering.labels_

        clustered = all_reports[all_reports["cluster_id"] >= 0]
        if clustered.empty:
            return gpd.GeoDataFrame(columns=["lat", "lng", "theme", "comment"])

        clusters = []
        for cid, group in clustered.groupby("cluster_id"):
            comments = group["comment"].dropna().tolist()
            sentiment = analyze_perception_sentiment(comments)
            themes = extract_perception_themes(comments)

            clusters.append(
                {
                    "hotspot_id": f"perception_{cid}",
                    "center_lat": group["lat"].mean(),
                    "center_lng": group["lng"].mean(),
                    "report_count": len(group),
                    "primary_theme": group["theme"].mode()[0]
                    if not group["theme"].mode().empty
                    else None,
                    "sentiment_label": sentiment.get("label"),
                    "sentiment_score": sentiment.get("score"),
                    "dominant_theme": themes.get("dominant_theme"),
                    "keywords": ", ".join(themes.get("keywords", [])),
                    "source": "perception",
                }
            )

        df = pd.DataFrame(clusters)
        df["urgency_score"] = df["report_count"] * (1 + df["sentiment_score"].fillna(0))
        df["geometry"] = [Point(xy) for xy in zip(df.center_lng, df.center_lat)]
        return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

    # -------------------------------------------------------------------------
    # 3. SENSOR–PERCEPTION ENRICHMENT
    # -------------------------------------------------------------------------
    def enrich_hotspots(
        self,
        sensor_gdf: gpd.GeoDataFrame,
        perception_gdf: gpd.GeoDataFrame,
        radius_m: int = 50,
    ) -> gpd.GeoDataFrame:
        """
        Spatially join perception and sensor hotspots within given radius
        Produces unified, context-rich hotspots for visualization
        """
        if sensor_gdf.empty and perception_gdf.empty:
            return gpd.GeoDataFrame()

        # Convert to projected CRS for distance-based joins
        sensor_gdf = sensor_gdf.to_crs(epsg=3857)
        perception_gdf = perception_gdf.to_crs(epsg=3857)

        joined = gpd.sjoin_nearest(
            sensor_gdf,
            perception_gdf,
            how="outer",
            distance_col="distance_m",
            max_distance=radius_m,
        ).to_crs(epsg=4326)

        joined["perception_count"] = joined["report_count"].fillna(0).astype(int)
        joined["avg_severity"] = joined["avg_severity"].fillna(0)
        joined["risk_score"] = joined["risk_score"].fillna(0)
        joined["urgency_score"] = joined["urgency_score"].fillna(0)

        # Compute unified priority
        joined["priority_score"] = (
            0.6 * joined["risk_score"] + 0.4 * joined["urgency_score"]
        )
        joined["priority_score"] += joined["perception_count"] * 2

        # Create unified summary text for map tooltip
        def build_summary(row):
            return (
                f"{int(row.get('event_count',0))} sensor events, "
                f"{int(row.get('perception_count',0))} user reports "
                f"({row.get('dominant_theme','N/A')}), sentiment={row.get('sentiment_label','N/A')}"
            )

        joined["summary_text"] = joined.apply(build_summary, axis=1)

        # Generate Groq AI summary per hotspot
        joined["ai_summary"] = joined.apply(
            lambda r: generate_hotspot_summary(
                lat=r["center_lat"],
                lon=r["center_lng"],
                theme=r.get("dominant_theme"),
                sentiment=r.get("sentiment_label"),
                sensor_events=r.get("event_count", 0),
                perception_reports=r.get("perception_count", 0),
                avg_severity=r.get("avg_severity", 0),
            ),
            axis=1,
        )

        joined["final_hotspot_id"] = [
            f"hotspot_{i+1}" for i in range(len(joined))
        ]
        return joined

    # -------------------------------------------------------------------------
    # 4. MASTER PIPELINE
    # -------------------------------------------------------------------------
    def get_unified_hotspots(
        self,
        sensor_params: Dict = None,
        perception_params: Dict = None,
        radius_m: int = 50,
    ) -> gpd.GeoDataFrame:
        """
        Complete end-to-end hotspot detection + enrichment pipeline
        Returns unified GeoDataFrame for Kepler or Streamlit
        """
        sensor_params = sensor_params or {}
        perception_params = perception_params or {}

        # Detect independently
        sensor_hotspots = self.detect_sensor_hotspots(**sensor_params)
        perception_hotspots = self.detect_perception_hotspots(**perception_params)

        # Merge both
        enriched = self.enrich_hotspots(sensor_hotspots, perception_hotspots, radius_m)

        # Sort by priority for dashboard display
        return enriched.sort_values("priority_score", ascending=False).reset_index(drop=True)

