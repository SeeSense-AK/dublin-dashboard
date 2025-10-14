"""
Data Export with Minimal Anonymization
FIXED: Properly loads .env from project root
"""
import pandas as pd
from pyathena import connect
import os
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env from project root
from dotenv import load_dotenv
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

print("=" * 70)
print("📦 DATA EXPORT WITH MINIMAL ANONYMIZATION")
print("=" * 70)
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# ============================================================================
# CREDENTIALS
# ============================================================================

print(f"🔑 Loading credentials from: {env_path}")

aws_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
s3_staging = os.getenv('AWS_S3_STAGING_DIR', 's3://seesense-air/summit2/spinovate-replay/athena-results/')
region = os.getenv('AWS_REGION', 'eu-west-1')

if not aws_key or not aws_secret:
    print(f"\n❌ AWS credentials not found in {env_path}!")
    print("\nMake sure your .env file contains:")
    print("  AWS_ACCESS_KEY_ID=your_key")
    print("  AWS_SECRET_ACCESS_KEY=your_secret")
    raise SystemExit(1)

print(f"✅ Found AWS_ACCESS_KEY_ID: {aws_key[:10]}...{aws_key[-4:]}")
print(f"✅ Found AWS_SECRET_ACCESS_KEY: ***...{aws_secret[-4:]}")
print(f"✅ S3 Staging: {s3_staging}")
print(f"✅ Region: {region}\n")

# ============================================================================
# ATHENA CONNECTION
# ============================================================================

print("Connecting to Athena...")
try:
    conn = connect(
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        s3_staging_dir=s3_staging,
        region_name=region
    )
    print("✅ Connected to Athena\n")
except Exception as e:
    print(f"❌ Failed to connect to Athena: {e}")
    raise SystemExit(1)

# Create output directory
output_dir = project_root / 'data'
output_dir.mkdir(exist_ok=True)

# ============================================================================
# 1. EXPORT SENSOR DATA (ABNORMAL EVENTS ONLY)
# ============================================================================

print("=" * 70)
print("📍 STEP 1: SENSOR DATA (Abnormal Events Only)")
print("=" * 70)

query_sensor = """
SELECT 
    device_id,
    device_name,
    timestamp,
    position_latitude as lat,
    position_longitude as lng,
    primary_event_type,
    max_severity,
    severity_x,
    severity_y,
    severity_z,
    peak_x,
    peak_y,
    peak_z,
    avg_x,
    avg_y,
    avg_z,
    speed_kmh,
    event_details,
    source_region
FROM spinovate_production.spinovate_production_optimised_v2
WHERE is_abnormal_event = true
    AND position_latitude IS NOT NULL
    AND position_longitude IS NOT NULL
    AND position_latitude BETWEEN 53.2 AND 53.5
    AND position_longitude BETWEEN -6.5 AND -6.0
ORDER BY timestamp
"""

print("Querying Athena for abnormal events...")
print("⏳ This may take 30-60 seconds...\n")

try:
    df_sensor = pd.read_sql(query_sensor, conn)
    original_count = len(df_sensor)
    print(f"✅ Extracted {original_count:,} abnormal events\n")
except Exception as e:
    print(f"❌ Query failed: {e}")
    conn.close()
    raise SystemExit(1)

# MINIMAL ANONYMIZATION
print("🔐 Applying minimal anonymization...")

# 1. Truncate GPS to 4 decimals (~11m precision)
df_sensor['lat'] = df_sensor['lat'].round(4)
df_sensor['lng'] = df_sensor['lng'].round(4)
print("  ✓ GPS truncated to 4 decimals (~11m precision)")

# Note: IMEI (ident) was not selected in query, so it's already excluded
print("  ✓ IMEI (ident) excluded from export")

# Save to parquet
sensor_output = output_dir / 'sensor_hotspots.parquet'
df_sensor.to_parquet(
    sensor_output,
    compression='zstd',
    compression_level=9,
    engine='pyarrow',
    index=False
)

sensor_size_mb = sensor_output.stat().st_size / (1024 * 1024)
print(f"\n💾 Saved to: {sensor_output}")
print(f"   Size: {sensor_size_mb:.2f} MB")
print(f"   Rows: {len(df_sensor):,}")

# ============================================================================
# 2. PROCESS PERCEPTION REPORTS
# ============================================================================

print("\n" + "=" * 70)
print("📝 STEP 2: PERCEPTION REPORTS")
print("=" * 70)

print("Loading perception reports from local files...")

# Look in project root
infra_file = project_root / 'dublin_infra_reports_dublin2025_upto20250924.csv'
ride_file = project_root / 'dublin_ride_reports_dublin2025_upto20250924.csv'

if not infra_file.exists() or not ride_file.exists():
    print(f"❌ Perception report files not found in {project_root}!")
    print("Looking for:")
    print(f"  - {infra_file}")
    print(f"  - {ride_file}")
    conn.close()
    raise SystemExit(1)

infra_df = pd.read_csv(infra_file)
ride_df = pd.read_csv(ride_file)

print(f"✅ Loaded {len(infra_df)} infrastructure + {len(ride_df)} ride reports\n")

# MINIMAL ANONYMIZATION
print("🔐 Applying minimal anonymization...")

for df, name in [(infra_df, 'Infrastructure'), (ride_df, 'Ride')]:
    # Truncate GPS to 4 decimals
    df['lat'] = df['lat'].round(4)
    df['lng'] = df['lng'].round(4)
    print(f"  ✓ {name}: GPS truncated to 4 decimals")

# Save
infra_output = output_dir / 'infra_reports.csv'
ride_output = output_dir / 'ride_reports.csv'

infra_df.to_csv(infra_output, index=False)
ride_df.to_csv(ride_output, index=False)

infra_size_kb = infra_output.stat().st_size / 1024
ride_size_kb = ride_output.stat().st_size / 1024

print(f"\n💾 Saved to:")
print(f"   {infra_output} ({infra_size_kb:.1f} KB, {len(infra_df)} rows)")
print(f"   {ride_output} ({ride_size_kb:.1f} KB, {len(ride_df)} rows)")

# ============================================================================
# 3. EXPORT USAGE TRENDS
# ============================================================================

print("\n" + "=" * 70)
print("📊 STEP 3: USAGE TRENDS (Pre-aggregated)")
print("=" * 70)

query_trends = """
SELECT 
    date,
    unique_users,
    total_readings,
    abnormal_events,
    avg_severity,
    avg_speed
FROM spinovate_production.usage_trends_daily
ORDER BY date
"""

print("Querying Athena for usage trends...")
try:
    df_trends = pd.read_sql(query_trends, conn)
    print(f"✅ Extracted {len(df_trends):,} daily records\n")
except Exception as e:
    print(f"❌ Query failed: {e}")
    conn.close()
    raise SystemExit(1)

print("🔐 No anonymization needed (already aggregated)")

trends_output = output_dir / 'usage_trends_daily.parquet'
df_trends.to_parquet(
    trends_output,
    compression='zstd',
    engine='pyarrow',
    index=False
)

trends_size_kb = trends_output.stat().st_size / 1024
print(f"\n💾 Saved to: {trends_output}")
print(f"   Size: {trends_size_kb:.1f} KB")
print(f"   Rows: {len(df_trends):,}")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 70)
print("✅ EXPORT COMPLETE!")
print("=" * 70)

total_size_mb = sensor_size_mb + (infra_size_kb + ride_size_kb + trends_size_kb) / 1024

print(f"\n📦 SUMMARY:")
print(f"   Sensor events:    {len(df_sensor):,} rows ({sensor_size_mb:.2f} MB)")
print(f"   Infra reports:    {len(infra_df)} rows ({infra_size_kb:.1f} KB)")
print(f"   Ride reports:     {len(ride_df)} rows ({ride_size_kb:.1f} KB)")
print(f"   Usage trends:     {len(df_trends)} rows ({trends_size_kb:.1f} KB)")
print(f"   TOTAL SIZE:       {total_size_mb:.2f} MB")

print(f"\n🔐 MINIMAL ANONYMIZATION APPLIED:")
print(f"   ✓ IMEI numbers:   Excluded from export")
print(f"   ✓ GPS precision:  Truncated to ~11m grid")
print(f"   ✓ User IDs:       Kept as-is (supervisor confirmed GDPR compliance)")
print(f"   ✓ Comments:       Kept as-is")

print(f"\n📅 Data Coverage:")
print(f"   Sensor data:      {df_sensor['timestamp'].min()} to {df_sensor['timestamp'].max()}")
print(f"   Usage trends:     {df_trends['date'].min()} to {df_trends['date'].max()}")

print(f"\n🎯 NEXT STEPS:")
print(f"   1. Review files in data/ directory")
print(f"   2. Test locally: streamlit run app.py")
print(f"   3. Commit to private GitHub repo")
print(f"   4. Deploy to Streamlit Cloud")

print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

conn.close()