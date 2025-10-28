"""
Generate Cycling Route Popularity Heatmap Video
Author: Spinovate Production
Purpose: Create a temporal heatmap animation (MP4) from daily cycling route data
Environment: Run from VS Code or terminal (NOT Jupyter)
"""

# ===============================================================
# Imports
# ===============================================================
import os
import pandas as pd
import plotly.express as px
import plotly.io as pio
import imageio.v2 as imageio
from tqdm import tqdm

# ===============================================================
# Configuration
# ===============================================================
# Path to your parquet file
DATA_PATH = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/data/processed/tab2_trend/route_popularity/dailytop50.parquet"

# Output paths
FRAMES_DIR = "frames"
OUTPUT_VIDEO = "data/processed/heatmap_animation.mp4"

# Frame and video parameters
FPS = 8                     # frames per second (192 days ≈ 24 seconds)
ZOOM_LEVEL = 12             # map zoom
RADIUS = 10                 # heatmap radius (affects smoothness)
CLEANUP_FRAMES = True       # delete PNGs after video creation

# ===============================================================
# 1. Setup environment for Kaleido (ensures proper engine)
# ===============================================================
pio.renderers.default = "png"   # ensures Kaleido backend is active

try:
    import kaleido  # noqa: F401
    print("✅ Kaleido found and ready.")
except ImportError:
    raise SystemExit("❌ Kaleido not installed. Run: pip install -U kaleido")

# ===============================================================
# 2. Load and prepare dataset
# ===============================================================
print("📂 Loading dataset...")
df = pd.read_parquet(DATA_PATH)
df["ride_date"] = pd.to_datetime(df["ride_date"])
print(f"✅ Loaded {len(df):,} rows covering {df['ride_date'].nunique()} days.")

# Round coordinates slightly to reduce duplicates
df["lat_r"] = df["latitude"].round(4)
df["lon_r"] = df["longitude"].round(4)

# Aggregate points by date and grid
agg = (
    df.groupby(["ride_date", "lat_r", "lon_r"])
      .agg({"popularity_score": "mean"})
      .reset_index()
)

print(f"✅ Aggregated shape: {agg.shape}")

# ===============================================================
# 3. Prepare directories
# ===============================================================
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_VIDEO), exist_ok=True)

dates = sorted(agg["ride_date"].unique())
print(f"📅 Total frames to render: {len(dates)}")

# ===============================================================
# 4. Generate heatmap frames
# ===============================================================
for d in tqdm(dates, desc="Rendering daily heatmaps"):
    subset = agg[agg["ride_date"] == d]

    fig = px.density_mapbox(
        subset,
        lat="lat_r",
        lon="lon_r",
        z="popularity_score",
        radius=RADIUS,
        center=dict(lat=53.34, lon=-6.26),
        zoom=ZOOM_LEVEL,
        mapbox_style="carto-positron",
        title=f"📅 Cycling Route Popularity — {d.strftime('%Y-%m-%d')}",
    )

    out_path = os.path.join(FRAMES_DIR, f"frame_{d.strftime('%Y-%m-%d')}.png")
    try:
        fig.write_image(out_path, scale=2)
    except Exception as e:
        print(f"⚠️ Failed to export frame for {d.date()}: {e}")

print("✅ Frame generation complete.")

# ===============================================================
# 5. Combine frames into MP4 video
# ===============================================================
print("🎬 Building video...")
frames = []
for d in tqdm(dates, desc="Combining frames"):
    frame_path = os.path.join(FRAMES_DIR, f"frame_{d.strftime('%Y-%m-%d')}.png")
    if os.path.exists(frame_path):
        frames.append(imageio.imread(frame_path))
    else:
        print(f"⚠️ Missing frame: {frame_path}")

if not frames:
    raise SystemExit("❌ No frames generated. Video cannot be created.")

imageio.mimsave(OUTPUT_VIDEO, frames, fps=FPS)
print(f"✅ Video saved → {OUTPUT_VIDEO}")

# ===============================================================
# 6. Optional cleanup
# ===============================================================
if CLEANUP_FRAMES:
    for f in os.listdir(FRAMES_DIR):
        os.remove(os.path.join(FRAMES_DIR, f))
    os.rmdir(FRAMES_DIR)
    print("🧹 Cleaned up temporary frame images.")

print("🎉 Done! Heatmap animation is ready.")
