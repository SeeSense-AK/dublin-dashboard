"""
Debug script to understand why no hotspots are detected
Run this to see what's filtering out your data
"""

from src.athena_database import get_athena_database
import pandas as pd

def debug_hotspot_detection():
    """
    Step-by-step debugging of hotspot detection
    """
    db = get_athena_database()
    
    print("=" * 60)
    print("HOTSPOT DETECTION DEBUGGING")
    print("=" * 60)
    
    # Step 1: Check total abnormal events
    print("\n📊 Step 1: Checking abnormal events...")
    query1 = """
    SELECT 
        COUNT(*) as total_abnormal_events,
        MIN(max_severity) as min_severity,
        MAX(max_severity) as max_severity,
        AVG(max_severity) as avg_severity,
        COUNT(DISTINCT device_id) as unique_devices
    FROM spinovate_production.spinovate_production_optimised
    WHERE is_abnormal_event = true
        AND lat IS NOT NULL 
        AND lng IS NOT NULL
    """
    
    result1 = pd.read_sql(query1, db.conn)
    print(result1.to_string())
    
    total_abnormal = result1['total_abnormal_events'].iloc[0]
    
    if total_abnormal == 0:
        print("\n❌ PROBLEM: No abnormal events found!")
        print("   Check: is_abnormal_event column might all be false")
        return
    
    # Step 2: Check events by severity threshold
    print("\n📊 Step 2: Events by severity level...")
    query2 = """
    SELECT 
        max_severity,
        COUNT(*) as event_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
    FROM spinovate_production.spinovate_production_optimised
    WHERE is_abnormal_event = true
        AND lat IS NOT NULL 
        AND lng IS NOT NULL
    GROUP BY max_severity
    ORDER BY max_severity
    """
    
    result2 = pd.read_sql(query2, db.conn)
    print(result2.to_string())
    
    # Step 3: Check grid clusters (before filtering)
    print("\n📊 Step 3: Grid clusters formed (before min_events filter)...")
    query3 = """
    WITH abnormal_events AS (
        SELECT 
            lat,
            lng,
            max_severity,
            timestamp,
            device_id
        FROM spinovate_production.spinovate_production_optimised
        WHERE is_abnormal_event = true 
            AND max_severity >= 2
            AND lat IS NOT NULL 
            AND lng IS NOT NULL
    )
    SELECT 
        COUNT(DISTINCT CONCAT(CAST(ROUND(lat, 3) AS VARCHAR), ',', CAST(ROUND(lng, 3) AS VARCHAR))) as total_grid_cells,
        MIN(event_count) as min_events_per_cell,
        MAX(event_count) as max_events_per_cell,
        AVG(event_count) as avg_events_per_cell,
        APPROX_PERCENTILE(event_count, 0.5) as median_events_per_cell,
        APPROX_PERCENTILE(event_count, 0.75) as p75_events_per_cell
    FROM (
        SELECT 
            ROUND(lat, 3) as lat_cluster,
            ROUND(lng, 3) as lng_cluster,
            COUNT(*) as event_count
        FROM abnormal_events
        GROUP BY ROUND(lat, 3), ROUND(lng, 3)
    )
    """
    
    result3 = pd.read_sql(query3, db.conn)
    print(result3.to_string())
    
    # Step 4: Check how many clusters pass min_events threshold
    print("\n📊 Step 4: Testing different min_events thresholds...")
    
    for min_events in [3, 5, 10, 15, 20]:
        query4 = f"""
        WITH abnormal_events AS (
            SELECT 
                lat,
                lng,
                max_severity,
                timestamp,
                device_id
            FROM spinovate_production.spinovate_production_optimised
            WHERE is_abnormal_event = true 
                AND max_severity >= 2
                AND lat IS NOT NULL 
                AND lng IS NOT NULL
        ),
        grid_clusters AS (
            SELECT 
                ROUND(lat, 3) as lat_cluster,
                ROUND(lng, 3) as lng_cluster,
                COUNT(*) as event_count,
                COUNT(DISTINCT DATE_TRUNC('day', timestamp)) as days_with_events
            FROM abnormal_events
            GROUP BY ROUND(lat, 3), ROUND(lng, 3)
            HAVING COUNT(*) >= {min_events}
                AND COUNT(DISTINCT DATE_TRUNC('day', timestamp)) >= 2
        )
        SELECT COUNT(*) as clusters_passing_filter
        FROM grid_clusters
        """
        
        result = pd.read_sql(query4, db.conn)
        count = result['clusters_passing_filter'].iloc[0]
        print(f"   min_events >= {min_events:2d} AND days >= 2: {count:4d} clusters")
    
    # Step 5: Check without days_with_events filter
    print("\n📊 Step 5: Testing WITHOUT days_with_events >= 2 filter...")
    
    for min_events in [5, 10, 15]:
        query5 = f"""
        WITH abnormal_events AS (
            SELECT 
                lat,
                lng,
                max_severity
            FROM spinovate_production.spinovate_production_optimised
            WHERE is_abnormal_event = true 
                AND max_severity >= 2
                AND lat IS NOT NULL 
                AND lng IS NOT NULL
        ),
        grid_clusters AS (
            SELECT 
                COUNT(*) as event_count
            FROM abnormal_events
            GROUP BY ROUND(lat, 3), ROUND(lng, 3)
            HAVING COUNT(*) >= {min_events}
        )
        SELECT COUNT(*) as clusters_passing_filter
        FROM grid_clusters
        """
        
        result = pd.read_sql(query5, db.conn)
        count = result['clusters_passing_filter'].iloc[0]
        print(f"   min_events >= {min_events:2d} (no days filter): {count:4d} clusters")
    
    # Step 6: Sample some clusters to see actual data
    print("\n📊 Step 6: Sample of top clusters...")
    query6 = """
    WITH abnormal_events AS (
        SELECT 
            lat,
            lng,
            max_severity,
            timestamp,
            device_id
        FROM spinovate_production.spinovate_production_optimised
        WHERE is_abnormal_event = true 
            AND max_severity >= 2
            AND lat IS NOT NULL 
            AND lng IS NOT NULL
    )
    SELECT 
        ROUND(lat, 3) as lat_cluster,
        ROUND(lng, 3) as lng_cluster,
        COUNT(*) as event_count,
        AVG(max_severity) as avg_severity,
        COUNT(DISTINCT DATE_TRUNC('day', timestamp)) as days_with_events,
        COUNT(DISTINCT device_id) as unique_devices
    FROM abnormal_events
    GROUP BY ROUND(lat, 3), ROUND(lng, 3)
    ORDER BY COUNT(*) DESC
    LIMIT 10
    """
    
    result6 = pd.read_sql(query6, db.conn)
    print(result6.to_string())
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)
    
    # Provide recommendations
    print("\n💡 RECOMMENDATIONS:")
    
    if total_abnormal == 0:
        print("❌ No abnormal events in database")
    elif result3['total_grid_cells'].iloc[0] == 0:
        print("❌ No grid clusters formed - data might be too sparse")
    else:
        max_in_cluster = result3['max_events_per_cell'].iloc[0]
        print(f"✅ Max events in any cluster: {max_in_cluster}")
        print(f"   → Set min_incidents to: {max(1, int(max_in_cluster * 0.3))}-{max(3, int(max_in_cluster * 0.5))}")
        
        # Check severity distribution
        high_sev = result2[result2['max_severity'] >= 3]['event_count'].sum() if not result2.empty else 0
        total = result2['event_count'].sum() if not result2.empty else 1
        pct_high = (high_sev / total) * 100
        
        print(f"✅ {pct_high:.1f}% of events are severity >= 3")
        if pct_high < 10:
            print(f"   → Try severity_threshold = 2 instead of 3")
    
    db.close()

if __name__ == "__main__":
    debug_hotspot_detection()
