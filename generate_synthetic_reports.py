"""
Synthetic Perception Report Generator for Dublin Road Safety Dashboard
Generates realistic perception reports based on actual sensor hotspots

STANDALONE SCRIPT - Run separately from dashboard to generate enhanced dataset
This uses Groq AI to create sophisticated, realistic comments

Usage:
    python generate_synthetic_reports.py
    
Output:
    - dublin_ride_reports_SYNTHETIC.csv (~1000 reports total)
    - dublin_infra_reports_SYNTHETIC.csv (~1000 reports total)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from typing import List, Dict, Tuple
import os
from dotenv import load_dotenv

# Load environment for Groq API
load_dotenv()

# Try to import Groq (optional - will fallback to templates if not available)
try:
    from groq import Groq
    GROQ_AVAILABLE = True
    print("✅ Groq AI available for sophisticated comment generation")
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq not available - will use template-based comments")


class SyntheticPerceptionGenerator:
    """Generate realistic perception reports based on sensor hotspots"""
    
    def __init__(self, sensor_data_path: str, existing_infra_path: str, existing_ride_path: str):
        """
        Initialize generator with real data for context
        
        Args:
            sensor_data_path: Path to sensor CSV
            existing_infra_path: Path to existing infrastructure reports
            existing_ride_path: Path to existing ride reports
        """
        # Load existing data for patterns
        print("📊 Loading existing data...")
        self.sensor_df = pd.read_csv(sensor_data_path)
        self.existing_infra = pd.read_csv(existing_infra_path)
        self.existing_ride = pd.read_csv(existing_ride_path)
        
        print(f"   ✓ Loaded {len(self.sensor_df):,} sensor readings")
        print(f"   ✓ Loaded {len(self.existing_infra)} infrastructure reports")
        print(f"   ✓ Loaded {len(self.existing_ride)} ride reports")
        
        # Theme mappings based on sensor event types
        self.sensor_to_theme = {
            'hard_brake': ['Close pass', 'Dangerous junction', 'Traffic'],
            'brake': ['Close pass', 'Dangerous junction', 'Traffic'],
            'pothole': ['Pothole', 'Poor surface', 'Damage to road'],
            'swerve': ['Obstruction', 'Parked car', 'Poor surface'],
            'acceleration': ['Traffic light', 'Junction']
        }
        
        # Realistic comment templates by theme
        self.comment_templates = {
            'Close pass': [
                "Very close pass by {vehicle} - felt unsafe",
                "Driver passed way too close, almost clipped me",
                "Dangerous overtake by {vehicle} with oncoming traffic",
                "Close call with {vehicle}, no space given",
                "Nearly knocked off by {vehicle} passing too close"
            ],
            'Pothole': [
                "Large pothole in cycle lane, nearly caused me to swerve into traffic",
                "Deep hole in road surface - very dangerous at speed",
                "Pothole cluster causing cyclists to move into traffic lane",
                "Road surface badly damaged with multiple holes",
                "Crater-sized pothole, needs urgent repair"
            ],
            'Poor surface': [
                "Very rough surface, uncomfortable and unsafe",
                "Road surface breaking up, lots of loose gravel",
                "Uneven surface causing bike to bounce around",
                "Cracked and potholed surface throughout this section",
                "Surface quality very poor, needs resurfacing"
            ],
            'Dangerous junction': [
                "Junction design makes it very difficult to see oncoming traffic",
                "Blind corner - drivers can't see cyclists approaching",
                "Poor visibility and tight turns make this very dangerous",
                "Junction layout unclear, drivers cutting across cycle lane",
                "No safe way for cyclists to navigate this junction"
            ],
            'Obstruction': [
                "Cycle lane blocked by parked {vehicle}",
                "Overgrown vegetation forcing cyclists into traffic",
                "Bins left in cycle lane on collection day",
                "Construction materials blocking path",
                "Parked {vehicle} completely blocking cycle lane"
            ],
            'Traffic': [
                "Heavy traffic makes cycling here very stressful",
                "Constant stream of vehicles passing very close",
                "Traffic volumes too high for road width",
                "Rush hour traffic makes this route dangerous",
                "No space for safe cycling due to traffic volume"
            ],
            'Parked car': [
                "Cars consistently parked in cycle lane",
                "Vehicle parked forcing cyclists into traffic",
                "Parked {vehicle} blocking cycle lane daily",
                "No enforcement of parking restrictions in cycle lane",
                "Cars using cycle lane as parking space"
            ]
        }
        
        # Vehicle types for realistic comments
        self.vehicles = ['car', 'van', 'bus', 'truck', 'taxi', 'lorry']
        
        # Generate synthetic user IDs
        self.synthetic_users = [f"synth_user_{i:03d}" for i in range(1, 151)]
        
        # Initialize Groq client if available
        self.groq_client = None
        if GROQ_AVAILABLE:
            try:
                api_key = os.getenv("GROQ_API_KEY")
                if api_key:
                    self.groq_client = Groq(api_key=api_key)
                    print("✅ Groq AI client initialized")
                else:
                    print("⚠️ GROQ_API_KEY not found in .env")
            except Exception as e:
                print(f"⚠️ Could not initialize Groq: {e}")
        
        # Batch comment generation for efficiency
        self.comment_cache = {}
    
    def _generate_groq_comments_batch(self, theme: str, count: int = 20) -> List[str]:
        """
        Generate batch of realistic comments using Groq AI
        
        Args:
            theme: Theme/incident type
            count: Number of comments to generate
            
        Returns:
            List of comment strings
        """
        if not self.groq_client:
            return []
        
        prompt = f"""Generate {count} realistic cyclist safety reports about "{theme}" in Dublin, Ireland.

Requirements:
- Write from perspective of actual cyclists
- Use Irish English spelling (e.g., "behaviour" not "behavior")
- Mix of brief (10-20 words) and detailed (30-50 words) comments
- Include specific details: times of day, weather, vehicle types, road names (use Dublin patterns)
- Range from calm/factual to frustrated/concerned tones
- Some with suggestions, some just describing issues
- Make them sound like real people wrote them quickly on a phone

Examples of good comments:
- "White van passed inches from my elbow heading towards town during rush hour"
- "Massive pothole cluster forcing everyone into the middle of the road. Been like this for weeks."
- "Junction design is terrible - no safe way to turn right without crossing two lanes of traffic"

Format: Return ONLY the comments, one per line, no numbering or extra text."""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are helping generate realistic cycling safety reports. Be authentic and varied."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,
                max_tokens=2000
            )
            
            # Parse response
            comments_text = response.choices[0].message.content
            comments = [c.strip() for c in comments_text.split('\n') if c.strip() and len(c.strip()) > 10]
            
            return comments[:count]
            
        except Exception as e:
            print(f"⚠️ Groq generation failed for {theme}: {e}")
            return []
    
    def _prefill_comment_cache(self):
        """Pre-generate comments using Groq to speed up report generation"""
        if not self.groq_client:
            print("ℹ️ Skipping comment pre-generation (Groq not available)")
            return
        
        print("\n🤖 Pre-generating sophisticated comments with Groq AI...")
        print("   This may take 2-3 minutes but will speed up overall generation")
        
        all_themes = list(self.comment_templates.keys())
        
        for theme in all_themes:
            print(f"   • Generating {theme} comments...")
            comments = self._generate_groq_comments_batch(theme, count=60)
            
            if comments:
                self.comment_cache[theme] = comments
            else:
                # Fallback to templates if Groq fails
                self.comment_cache[theme] = self.comment_templates[theme]
        
        total_comments = sum(len(v) for v in self.comment_cache.values())
        print(f"   ✅ Pre-generated {total_comments} unique comments")
    
    def _get_sophisticated_comment(self, theme: str) -> str:
        """
        Get a sophisticated comment - from cache if available, otherwise from template
        
        Args:
            theme: Theme/incident type
            
        Returns:
            Comment string
        """
        # Try to get from Groq cache first
        if theme in self.comment_cache and self.comment_cache[theme]:
            comment = random.choice(self.comment_cache[theme])
            
            # Replace vehicle placeholder if present
            if '{vehicle}' in comment:
                comment = comment.format(vehicle=random.choice(self.vehicles))
            
            return comment
        
        # Fallback to templates
        template = random.choice(self.comment_templates.get(theme, ["Issue reported at this location"]))
        return template.format(vehicle=random.choice(self.vehicles))
    
    def detect_sensor_hotspots(self, min_severity: int = 4, top_n: int = 30) -> pd.DataFrame:
        """
        Detect hotspots from sensor data
        
        Args:
            min_severity: Minimum severity threshold
            top_n: Number of top hotspots to detect
            
        Returns:
            DataFrame with hotspot locations and characteristics
        """
        print(f"🔍 Detecting top {top_n} sensor hotspots (severity >= {min_severity})...")
        
        # Filter for abnormal events
        abnormal = self.sensor_df[
            (self.sensor_df['is_abnormal_event'] == True) &
            (self.sensor_df['max_severity'] >= min_severity) &
            (self.sensor_df['position_latitude'].notna()) &
            (self.sensor_df['position_longitude'].notna())
        ].copy()
        
        if abnormal.empty:
            print("⚠️ No abnormal events found! Lowering severity threshold...")
            abnormal = self.sensor_df[
                (self.sensor_df['is_abnormal_event'] == True) &
                (self.sensor_df['position_latitude'].notna()) &
                (self.sensor_df['position_longitude'].notna())
            ].copy()
        
        # Cluster by rounding coordinates (simple grid clustering)
        precision = 3  # ~111m precision
        abnormal['lat_cluster'] = abnormal['position_latitude'].round(precision)
        abnormal['lng_cluster'] = abnormal['position_longitude'].round(precision)
        
        # Aggregate into hotspots
        hotspots = abnormal.groupby(['lat_cluster', 'lng_cluster']).agg({
            'position_latitude': 'mean',
            'position_longitude': 'mean',
            'max_severity': ['mean', 'max', 'count'],
            'primary_event_type': lambda x: x.mode()[0] if len(x) > 0 else 'unknown',
            'timestamp': ['min', 'max']
        }).reset_index()
        
        # Flatten column names
        hotspots.columns = ['lat_cluster', 'lng_cluster', 'lat', 'lng', 
                           'avg_severity', 'max_severity', 'event_count',
                           'dominant_event_type', 'first_event', 'last_event']
        
        # Calculate risk score
        hotspots['risk_score'] = hotspots['avg_severity'] * np.log1p(hotspots['event_count'])
        
        # Get top N by risk score
        hotspots = hotspots.nlargest(top_n, 'risk_score').reset_index(drop=True)
        
        print(f"✅ Found {len(hotspots)} hotspots")
        
        return hotspots
    
    def generate_perception_reports_for_hotspot(
        self, 
        hotspot: pd.Series,
        num_reports: int = None,
        radius_m: float = 50
    ) -> List[Dict]:
        """
        Generate perception reports near a specific hotspot
        
        Args:
            hotspot: Hotspot data (from detect_sensor_hotspots)
            num_reports: Number of reports to generate (calculated if None)
            radius_m: Radius around hotspot to scatter reports
            
        Returns:
            List of perception report dictionaries
        """
        if num_reports is None:
            # Scale reports based on severity - aim for ~1000 total
            if hotspot['avg_severity'] >= 7:
                num_reports = random.randint(25, 45)
            elif hotspot['avg_severity'] >= 6:
                num_reports = random.randint(20, 35)
            elif hotspot['avg_severity'] >= 5:
                num_reports = random.randint(15, 28)
            elif hotspot['avg_severity'] >= 4:
                num_reports = random.randint(10, 20)
            else:
                num_reports = random.randint(5, 12)
        
        reports = []
        
        # Get appropriate themes based on dominant event type
        dominant_event = str(hotspot['dominant_event_type']).lower()
        possible_themes = []
        
        for event_key, themes in self.sensor_to_theme.items():
            if event_key in dominant_event:
                possible_themes.extend(themes)
        
        if not possible_themes:
            possible_themes = list(self.comment_templates.keys())
        
        # Generate temporal spread
        first_event = pd.to_datetime(hotspot['first_event'])
        last_event = pd.to_datetime(hotspot['last_event'])
        time_span = (last_event - first_event).days
        
        for i in range(num_reports):
            # Scatter around hotspot location
            lat_offset = np.random.normal(0, radius_m / 111000)
            lng_offset = np.random.normal(0, radius_m / 111000)
            
            lat = hotspot['lat'] + lat_offset
            lng = hotspot['lng'] + lng_offset
            
            # Choose theme
            theme = random.choice(possible_themes)
            
            # Generate comment - USE SOPHISTICATED VERSION
            comment = self._get_sophisticated_comment(theme)
            
            # Generate timestamp within hotspot date range
            if time_span > 0:
                days_offset = random.randint(0, max(1, time_span))
                report_date = first_event + timedelta(days=days_offset)
            else:
                report_date = first_event + timedelta(days=random.randint(0, 30))
            
            # Determine report type (70% ride, 30% infrastructure)
            is_ride_report = random.random() < 0.7
            
            if is_ride_report:
                # Ride report
                report = {
                    'lat': lat,
                    'lng': lng,
                    'incidenttype': theme,
                    'commentfinal': comment,
                    'incidentrating': self._get_rating_for_severity(hotspot['avg_severity']),
                    'annoyance': True,
                    'userid': random.choice(self.synthetic_users),
                    'date': report_date.strftime('%d-%m-%Y'),
                    'time': f"{random.randint(6, 21):02d}:{random.randint(0, 59):02d}:00",
                    'year': report_date.year,
                    'month': report_date.month,
                    'day': report_date.day,
                    'hour': report_date.hour,
                    'commentnoannoyance': None,
                    'commentincidentothertype': None,
                    'type': 'ride'
                }
            else:
                # Infrastructure report
                report = {
                    'lat': lat,
                    'lng': lng,
                    'infrastructuretype': theme,
                    'finalcomment': comment,
                    'userid': random.choice(self.synthetic_users),
                    'date': report_date.strftime('%d-%m-%Y'),
                    'time': f"{random.randint(6, 21):02d}:{random.randint(0, 59):02d}:00",
                    'year': report_date.year,
                    'month': report_date.month,
                    'day': report_date.day,
                    'hour': report_date.hour,
                    'othertypecomment': None,
                    'type': 'infrastructure'
                }
            
            reports.append(report)
        
        return reports
    
    def _get_rating_for_severity(self, avg_severity: float) -> int:
        """Map sensor severity to perception rating (1-5, lower is worse)"""
        if avg_severity >= 7:
            return random.choice([1, 1, 2])
        elif avg_severity >= 5:
            return random.choice([2, 2, 3])
        else:
            return random.choice([3, 4])
    
    def generate_all_synthetic_reports(
        self, 
        num_hotspots: int = 30,
        output_dir: str = '.',
        use_groq: bool = True
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Main function: Generate all synthetic reports and save to CSV
        
        Args:
            num_hotspots: Number of hotspots to generate reports for
            output_dir: Directory to save output files
            use_groq: Whether to use Groq AI for sophisticated comments
            
        Returns:
            Tuple of (infrastructure_df, ride_df)
        """
        print("\n" + "="*60)
        print("🚀 SYNTHETIC PERCEPTION REPORT GENERATOR")
        print(f"   Target: ~1000 sophisticated reports")
        print("="*60 + "\n")
        
        # Pre-fill comment cache with Groq if available
        if use_groq and self.groq_client:
            self._prefill_comment_cache()
        
        # Step 1: Detect hotspots
        hotspots = self.detect_sensor_hotspots(min_severity=4, top_n=num_hotspots)
        
        # Step 2: Generate reports for each hotspot
        all_infra_reports = []
        all_ride_reports = []
        
        print(f"\n📝 Generating synthetic reports for {len(hotspots)} hotspots...")
        
        for idx, hotspot in hotspots.iterrows():
            reports = self.generate_perception_reports_for_hotspot(hotspot)
            
            for report in reports:
                if report['type'] == 'ride':
                    all_ride_reports.append(report)
                else:
                    all_infra_reports.append(report)
            
            if (idx + 1) % 10 == 0:
                print(f"   ✓ Processed {idx + 1}/{len(hotspots)} hotspots...")
        
        print(f"\n✅ Generated:")
        print(f"   • {len(all_ride_reports)} ride reports")
        print(f"   • {len(all_infra_reports)} infrastructure reports")
        print(f"   • Total: {len(all_ride_reports) + len(all_infra_reports)} synthetic reports")
        
        if self.groq_client:
            print(f"   • 🤖 Generated using Groq AI (sophisticated comments)")
        else:
            print(f"   • 📝 Generated using templates (Groq not available)")
        
        # Step 3: Convert to DataFrames
        ride_df = pd.DataFrame(all_ride_reports)
        infra_df = pd.DataFrame(all_infra_reports)
        
        # Remove 'type' column (was just for internal use)
        ride_df = ride_df.drop('type', axis=1)
        infra_df = infra_df.drop('type', axis=1)
        
        # Step 4: Combine with existing reports
        print("\n🔗 Combining with existing reports...")
        
        # Add synthetic flags
        self.existing_ride['is_synthetic'] = False
        ride_df['is_synthetic'] = True
        self.existing_infra['is_synthetic'] = False
        infra_df['is_synthetic'] = True
        
        ride_combined = pd.concat([self.existing_ride, ride_df], ignore_index=True)
        infra_combined = pd.concat([self.existing_infra, infra_df], ignore_index=True)
        
        # Assign proper IDs
        ride_combined['rowidx'] = range(len(ride_combined))
        infra_combined['rowidx'] = range(len(infra_combined))
        
        ride_combined['reportid'] = [f"RIDE_{i:06d}" for i in range(len(ride_combined))]
        infra_combined['reportid'] = [f"INFRA_{i:06d}" for i in range(len(infra_combined))]
        
        # Step 5: Save to CSV
        print(f"\n💾 Saving to {output_dir}...")
        
        os.makedirs(output_dir, exist_ok=True)
        
        ride_output = os.path.join(output_dir, 'dublin_ride_reports_SYNTHETIC.csv')
        infra_output = os.path.join(output_dir, 'dublin_infra_reports_SYNTHETIC.csv')
        
        ride_combined.to_csv(ride_output, index=False)
        infra_combined.to_csv(infra_output, index=False)
        
        print(f"   ✓ Saved: {ride_output}")
        print(f"   ✓ Saved: {infra_output}")
        
        print("\n" + "="*60)
        print("✅ GENERATION COMPLETE!")
        print("="*60)
        print(f"\n📊 Final Dataset:")
        print(f"   • Ride reports: {len(self.existing_ride)} real + {len(ride_df)} synthetic = {len(ride_combined)} total")
        print(f"   • Infra reports: {len(self.existing_infra)} real + {len(infra_df)} synthetic = {len(infra_combined)} total")
        print(f"\n💡 Tips:")
        print(f"   • Synthetic reports marked with 'is_synthetic = True'")
        print(f"   • Can filter them out for production: df[df['is_synthetic'] == False]")
        print(f"   • Generated reports are clustered around actual sensor hotspots")
        print(f"\n📁 Files created:")
        print(f"   • {ride_output}")
        print(f"   • {infra_output}")
        
        return infra_combined, ride_combined


# Example usage
if __name__ == "__main__":
    print("🚴 Dublin Road Safety - Synthetic Report Generator")
    print("="*60)
    
    # Configuration
    config = {
        'sensor_data_path': '20250831_complete_dataset.csv',
        'existing_infra_path': 'dublin_infra_reports_dublin2025_upto20250924.csv',
        'existing_ride_path': 'dublin_ride_reports_dublin2025_upto20250924.csv',
        'num_hotspots': 40,
        'output_dir': '.',
        'use_groq': True
    }
    
    print("\n📋 Configuration:")
    for key, value in config.items():
        print(f"   • {key}: {value}")
    
    print("\n⏳ Starting generation process...\n")
    
    try:
        generator = SyntheticPerceptionGenerator(
            sensor_data_path=config['sensor_data_path'],
            existing_infra_path=config['existing_infra_path'],
            existing_ride_path=config['existing_ride_path']
        )
        
        # Generate synthetic reports
        infra_df, ride_df = generator.generate_all_synthetic_reports(
            num_hotspots=config['num_hotspots'],
            output_dir=config['output_dir'],
            use_groq=config['use_groq']
        )
        
        print("\n✨ You can now use these enhanced datasets in your dashboard!")
        print("   Just update your data loading paths to point to the SYNTHETIC files")
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()