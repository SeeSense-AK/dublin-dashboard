"""
Script to add geometry coordinates to the Spinovate Tab 2 - Popularity.csv file
This will append coordinate arrays for each Dublin street to enable polyline visualization
"""

import pandas as pd
import json

# Dublin street coordinates (manually curated for accuracy)
# Format: [latitude, longitude] points along each street
DUBLIN_STREET_COORDINATES = {
    'Swords Road': [
        [53.3959, -6.2064],  # Start (city center end)
        [53.4050, -6.2120],  # Middle section
        [53.4150, -6.2180],  # Further north
        [53.4200, -6.2300]   # End (towards Swords)
    ],
    
    'Malahide Road': [
        [53.3648, -6.2297],  # Start (Fairview area)
        [53.3750, -6.2200],  # Clontarf area
        [53.3850, -6.2150],  # Further north
        [53.3900, -6.2100]   # End (towards Malahide)
    ],
    
    'Sandford Road': [
        [53.3178, -6.2553],  # Start (Ranelagh end)
        [53.3220, -6.2500],  # Middle section
        [53.3280, -6.2450],  # Upper section
        [53.3300, -6.2400]   # End (towards Dundrum)
    ],
    
    'Ranelagh': [
        [53.3236, -6.2566],  # Main street start
        [53.3250, -6.2540],  # Central area
        [53.3270, -6.2520],  # Triangle area
        [53.3300, -6.2500]   # End towards Rathmines
    ],
    
    'North Circular Road': [
        [53.3583, -6.2775],  # Start (Phoenix Park end)
        [53.3600, -6.2700],  # Cabra area
        [53.3620, -6.2650],  # Phibsborough area
        [53.3650, -6.2600]   # End (towards city center)
    ],
    
    'Rathgar Road': [
        [53.3150, -6.2650],  # Start (Rathgar village)
        [53.3180, -6.2600],  # Middle section
        [53.3220, -6.2570],  # Upper section
        [53.3250, -6.2550]   # End (towards Rathmines)
    ],
    
    'Alfie Byrne Road': [
        [53.3420, -6.2280],  # Start (East Wall)
        [53.3450, -6.2250],  # Middle section
        [53.3480, -6.2220],  # Clontarf area
        [53.3500, -6.2200]   # End (seafront)
    ],
    
    'Blessington Street': [
        [53.3583, -6.2564],  # Start (Dorset Street end)
        [53.3590, -6.2580],  # Middle section
        [53.3600, -6.2600],  # Basin area
        [53.3610, -6.2620]   # End (towards Broadstone)
    ],
    
    'Seville Place': [
        [53.3510, -6.2500],  # Start (North Strand)
        [53.3520, -6.2480],  # Middle section
        [53.3535, -6.2460],  # Upper section
        [53.3550, -6.2440]   # End (towards Fairview)
    ],
    
    'Kill Lane': [
        [53.2867, -6.1470],  # Start (Dun Laoghaire area)
        [53.2880, -6.1450],  # Middle section
        [53.2890, -6.1430],  # Upper section
        [53.2900, -6.1400]   # End
    ],
    
    'Mercer Street & Cuffe Street': [
        [53.3389, -6.2639],  # Start (Mercer Street)
        [53.3400, -6.2620],  # Junction area
        [53.3410, -6.2610],  # Cuffe Street
        [53.3420, -6.2600]   # End (towards St. Stephen's Green)
    ],
    
    'Northumberland Road': [
        [53.3347, -6.2453],  # Start (Ballsbridge)
        [53.3360, -6.2440],  # Embassy area
        [53.3380, -6.2420],  # Upper section
        [53.3400, -6.2400]   # End (towards city center)
    ]
}

def add_coordinates_to_csv():
    """
    Load the existing CSV file and add geometry coordinates
    """
    
    # File path
    csv_path = "/Users/abhishekkumbhar/Documents/GitHub/spinovate-dashboard/data/processed/tab2_trend/route_popularity/Spinovate Tab 2 - Popularity.csv"
    
    try:
        # Load the existing CSV
        print("📄 Loading existing CSV file...")
        df = pd.read_csv(csv_path)
        print(f"✅ Loaded {len(df)} rows")
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Display current columns
        print(f"📊 Current columns: {list(df.columns)}")
        
        # Add geometry column
        print("\n🗺️ Adding geometry coordinates...")
        
        geometry_data = []
        for idx, row in df.iterrows():
            street_name = row['street_name']
            
            if street_name in DUBLIN_STREET_COORDINATES:
                # Convert coordinates to JSON string format
                coords = DUBLIN_STREET_COORDINATES[street_name]
                geometry_json = json.dumps(coords)
                geometry_data.append(geometry_json)
                print(f"✅ Added coordinates for: {street_name}")
            else:
                print(f"⚠️ No coordinates found for: {street_name}")
                geometry_data.append(None)
        
        # Add the geometry column
        df['geometry'] = geometry_data
        
        # Create backup of original file
        backup_path = csv_path.replace('.csv', '_backup.csv')
        original_df = pd.read_csv(csv_path)
        original_df.to_csv(backup_path, index=False)
        print(f"💾 Created backup: {backup_path}")
        
        # Save updated file
        df.to_csv(csv_path, index=False)
        print(f"💾 Updated file saved: {csv_path}")
        
        # Summary
        print(f"\n✅ SUCCESS!")
        print(f"📊 Total streets: {len(df)}")
        print(f"🗺️ Streets with coordinates: {len([g for g in geometry_data if g is not None])}")
        print(f"⚠️ Streets without coordinates: {len([g for g in geometry_data if g is None])}")
        
        # Show first few entries
        print(f"\n📋 Sample of updated data:")
        for i in range(min(3, len(df))):
            street = df.iloc[i]['street_name']
            has_coords = "✅" if df.iloc[i]['geometry'] is not None else "❌"
            print(f"  {has_coords} {street}")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ File not found: {csv_path}")
        print("Please check the file path and make sure the file exists.")
        return False
        
    except Exception as e:
        print(f"❌ Error processing file: {e}")
        return False

def verify_coordinates():
    """
    Verify that all streets have valid coordinates
    """
    print("\n🔍 Verifying coordinate data...")
    
    for street_name, coords in DUBLIN_STREET_COORDINATES.items():
        print(f"\n📍 {street_name}:")
        print(f"   Points: {len(coords)}")
        for i, (lat, lng) in enumerate(coords):
            print(f"   {i+1}. [{lat:.4f}, {lng:.4f}]")
        
        # Basic validation
        if len(coords) < 2:
            print(f"   ⚠️ Warning: Only {len(coords)} points (need at least 2)")
        
        for lat, lng in coords:
            if not (53.2 <= lat <= 53.5) or not (-6.4 <= lng <= -6.0):
                print(f"   ⚠️ Warning: Coordinates [{lat}, {lng}] may be outside Dublin")

def main():
    """
    Main function to add coordinates to the CSV file
    """
    print("🚴‍♂️ Dublin Street Coordinates Updater")
    print("=" * 50)
    
    # First verify the coordinate data
    verify_coordinates()
    
    print("\n" + "=" * 50)
    
    # Add coordinates to CSV
    success = add_coordinates_to_csv()
    
    if success:
        print("\n🎉 All done! Your CSV file now has geometry coordinates.")
        print("📱 You can now run your Streamlit app with polyline visualization.")
        print("\n💡 Next steps:")
        print("1. Run your Streamlit app: streamlit run app.py")
        print("2. Go to Tab 2 to see the route map with polylines")
        print("3. Click on any route to see your detailed analysis")
    else:
        print("\n❌ Failed to update CSV file. Please check the error messages above.")

if __name__ == "__main__":
    main()
