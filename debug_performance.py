"""
Performance Debug Script
Run this to identify where the slowdown is happening
"""

import time
import pandas as pd
from datetime import datetime, timedelta

def time_it(func_name):
    """Decorator to time functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"\n⏱️  Starting: {func_name}")
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            print(f"✅ Completed: {func_name} in {elapsed:.2f} seconds")
            return result
        return wrapper
    return decorator

# Test 1: Load perception data
@time_it("Load Perception Data")
def test_load_perception():
    infra_df = pd.read_csv('dublin_infra_reports_SYNTHETIC.csv')
    ride_df = pd.read_csv('dublin_ride_reports_SYNTHETIC.csv')
    return infra_df, ride_df

# Test 2: Initialize Athena
@time_it("Initialize Athena Connection")
def test_athena_init():
    from src.athena_database import get_athena_database
    db = get_athena_database()
    return db

# Test 3: Get sensor metrics
@time_it("Get Dashboard Metrics")
def test_metrics(db):
    return db.get_dashboard_metrics()

# Test 4: Detect sensor hotspots (THIS IS LIKELY THE CULPRIT)
@time_it("Detect Sensor Hotspots")
def test_sensor_hotspots(db, start_date, end_date):
    query = f"""
    SELECT COUNT(*) as total
    FROM spinovate_production.spinovate_production_optimised_v2
    WHERE is_abnormal_event = true 
        AND max_severity >= 4
        AND lat IS NOT NULL 
        AND lng IS NOT NULL
        AND timestamp BETWEEN TIMESTAMP '{start_date}' AND TIMESTAMP '{end_date}'
    """
    return pd.read_sql(query, db.conn)

# Test 5: Full hotspot detection
@time_it("Full Hybrid Hotspot Detection")
def test_full_detection(start_date, end_date, infra_df, ride_df):
    from src.hybrid_hotspot_detector import detect_hybrid_hotspots
    return detect_hybrid_hotspots(
        start_date=start_date,
        end_date=end_date,
        infra_df=infra_df,
        ride_df=ride_df,
        total_hotspots=10
    )

if __name__ == "__main__":
    print("="*60)
    print("🐛 PERFORMANCE DEBUG - Finding the Bottleneck")
    print("="*60)
    
    # Setup dates
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)
    
    print(f"\n📅 Date Range: {start_date} to {end_date}")
    print(f"📊 Target: 10 hotspots")
    
    total_start = time.time()
    
    try:
        # Test each component
        infra_df, ride_df = test_load_perception()
        print(f"   → Loaded {len(infra_df)} infra + {len(ride_df)} ride reports")
        
        db = test_athena_init()
        print(f"   → Athena connected")
        
        metrics = test_metrics(db)
        print(f"   → Got metrics: {metrics['total_readings']:,} total readings")
        
        sensor_count = test_sensor_hotspots(db, start_date, end_date)
        print(f"   → Found {sensor_count['total'].iloc[0]:,} abnormal events in date range")
        
        # The big one - full detection
        print("\n" + "="*60)
        print("🎯 RUNNING FULL DETECTION (This is where it hangs)")
        print("="*60)
        
        hotspots = test_full_detection(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            infra_df,
            ride_df
        )
        
        print(f"   → Detected {len(hotspots)} hotspots")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    total_elapsed = time.time() - total_start
    print("\n" + "="*60)
    print(f"⏱️  TOTAL TIME: {total_elapsed:.2f} seconds ({total_elapsed/60:.1f} minutes)")
    print("="*60)
    
    if total_elapsed > 60:
        print("\n🐌 DIAGNOSIS:")
        print("   Your system is taking >60 seconds for 10 hotspots")
        print("   Likely causes:")
        print("   1. Athena query is slow (large dataset)")
        print("   2. Multiple Athena queries in detection loop")
        print("   3. Perception matching doing expensive distance calcs")
        print("   4. DBSCAN clustering on large dataset")
