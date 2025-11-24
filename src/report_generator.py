from fpdf import FPDF
import pandas as pd
from datetime import datetime
import time
import os

class SafetyReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 20, 20)
        
        # Brand Colors
        self.brand_primary = (3, 105, 161)    # #0369a1
        self.brand_secondary = (240, 249, 255) # #f0f9ff
        self.brand_text = (55, 65, 81)        # #374151
        self.brand_red = (220, 38, 38)       # #dc2626
        self.brand_green = (16, 185, 129)    # #10b981
        self.brand_orange = (245, 158, 11)   # #f59e0b
        
    def header(self):
        if self.page_no() > 1:
            # Logo/Brand Text
            self.set_font('Arial', 'B', 10)
            self.set_text_color(*self.brand_primary)
            
            # Check for logo
            if os.path.exists("assets/logo.png"):
                self.image("assets/logo.png", 10, 8, 30)
                self.set_xy(45, 12)
                self.cell(0, 10, 'SPINOVATE SAFETY DASHBOARD', 0, 0, 'L')
            else:
                self.cell(0, 10, 'SPINOVATE SAFETY DASHBOARD', 0, 0, 'L')
            
            # Date
            self.set_font('Arial', 'I', 9)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, datetime.now().strftime("%Y-%m-%d"), 0, 1, 'R')
            
            # Line
            self.set_draw_color(*self.brand_primary)
            self.line(20, 30, 190, 30)
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def create_cover_page(self):
        self.add_page()
        
        # Background accent
        self.set_fill_color(*self.brand_secondary)
        self.rect(0, 0, 210, 297, 'F')
        
        # Logo on Cover
        if os.path.exists("assets/logo_fixed.png"):
            self.image("assets/logo_fixed.png", 75, 40, 60)
            self.ln(80)
        else:
            self.ln(60)
        
        # Title
        self.set_font('Arial', 'B', 36)
        self.set_text_color(*self.brand_primary)
        self.multi_cell(0, 15, 'ROAD SAFETY\nANALYSIS REPORT', 0, 'C')
        
        self.ln(20)
        
        # Subtitle
        self.set_font('Arial', '', 14)
        self.set_text_color(*self.brand_text)
        self.multi_cell(0, 8, 'Comprehensive analysis of safety hotspots,\nroute trends, and infrastructure insights', 0, 'C')
        
        self.ln(40)
        
        # Date Box
        self.set_fill_color(255, 255, 255)
        self.set_draw_color(*self.brand_primary)
        self.rect(70, 180, 70, 30, 'DF')
        
        self.set_y(188)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 6, 'GENERATED ON', 0, 1, 'C')
        self.set_font('Arial', '', 12)
        self.cell(0, 8, datetime.now().strftime("%B %d, %Y"), 0, 1, 'C')
        
        # Footer Branding
        self.set_y(-40)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(*self.brand_primary)
        self.cell(0, 10, 'SPINOVATE', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(*self.brand_text)
        self.cell(0, 5, 'AI-Powered Road Safety Intelligence', 0, 1, 'C')

    def chapter_title(self, title):
        self.ln(5)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(*self.brand_primary)
        self.cell(0, 10, title.upper(), 0, 1, 'L')
        
        # Underline
        self.set_draw_color(*self.brand_primary)
        self.set_line_width(1)
        self.line(20, self.get_y(), 190, self.get_y())
        self.set_line_width(0.2)
        self.ln(5)

    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        self.set_text_color(*self.brand_text)
        self.multi_cell(0, 6, body)
        self.ln()

    def add_metric_grid(self, metrics):
        """
        metrics: list of tuples (label, value, subtext, color_type)
        color_type: 'primary', 'red', 'green', 'orange'
        """
        self.ln(5)
        col_width = 60
        start_x = 15
        
        # Calculate positions
        y = self.get_y()
        
        for i, (label, value, subtext, color_type) in enumerate(metrics):
            x = start_x + (i * col_width)
            
            # Determine color
            if color_type == 'red':
                color = self.brand_red
            elif color_type == 'green':
                color = self.brand_green
            elif color_type == 'orange':
                color = self.brand_orange
            else:
                color = self.brand_primary
            
            # Box
            self.set_fill_color(250, 250, 250)
            self.set_draw_color(220, 220, 220)
            self.rect(x, y, 55, 30, 'DF')
            
            # Label
            self.set_xy(x, y + 3)
            self.set_font('Arial', 'B', 9)
            self.set_text_color(100, 100, 100)
            self.cell(55, 5, label, 0, 1, 'C')
            
            # Value
            self.set_xy(x, y + 10)
            self.set_font('Arial', 'B', 16)
            self.set_text_color(*color)
            self.cell(55, 8, str(value), 0, 1, 'C')
            
            # Subtext
            self.set_xy(x, y + 20)
            self.set_font('Arial', '', 8)
            self.set_text_color(128, 128, 128)
            self.cell(55, 5, subtext, 0, 1, 'C')
            
        self.ln(35)

    def add_ai_analysis_card(self, title, subtitle, stats, insights):
        """
        Add a detailed AI analysis card
        """
        # Check page break
        if self.get_y() > 220:
            self.add_page()
            
        self.ln(5)
        
        # Header Box
        self.set_fill_color(*self.brand_secondary)
        self.set_draw_color(*self.brand_primary)
        self.rect(20, self.get_y(), 170, 15, 'DF')
        
        # Title
        self.set_font('Arial', 'B', 12)
        self.set_text_color(*self.brand_primary)
        self.cell(100, 15, f"  {title}", 0, 0, 'L')
        
        # Subtitle (Type/Score)
        self.set_font('Arial', 'B', 10)
        self.set_text_color(*self.brand_text)
        self.cell(70, 15, subtitle, 0, 1, 'R')
        
        self.ln(2)
        
        # Stats Row
        self.set_font('Arial', 'B', 9)
        self.set_text_color(100, 100, 100)
        stats_text = " | ".join([f"{k}: {v}" for k, v in stats.items()])
        self.cell(0, 8, stats_text, 0, 1, 'L')
        
        self.ln(2)
        
        # AI Summary
        if insights.get('summary'):
            self.set_font('Arial', 'B', 10)
            self.set_text_color(*self.brand_primary)
            self.cell(0, 6, "AI Analysis Summary", 0, 1)
            
            self.set_font('Arial', '', 10)
            self.set_text_color(*self.brand_text)
            self.multi_cell(0, 5, insights['summary'])
            self.ln(3)
            
        # Themes
        if insights.get('themes'):
            self.set_font('Arial', 'B', 10)
            self.set_text_color(*self.brand_primary)
            self.cell(0, 6, "Key Themes", 0, 1)
            
            self.set_font('Arial', 'I', 10)
            self.set_text_color(*self.brand_text)
            themes_text = ", ".join(insights['themes'])
            self.multi_cell(0, 5, themes_text)
            self.ln(3)
            
        # Recommendations
        if insights.get('recommendations'):
            self.set_font('Arial', 'B', 10)
            self.set_text_color(*self.brand_primary)
            self.cell(0, 6, "Recommendations", 0, 1)
            
            self.set_font('Arial', '', 10)
            self.set_text_color(*self.brand_text)
            for rec in insights['recommendations']:
                self.cell(5) # indent
                self.cell(2, 5, "-", 0, 0)
                self.multi_cell(0, 5, rec)
        
        self.ln(5)
        self.set_draw_color(220, 220, 220)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(5)

def generate_pdf_report(sensor_df, perception_df, corridor_df, route_df, abnormal_events_df, 
                       ai_hotspot_func=None, ai_route_func=None, user_comments_func=None,
                       progress_callback=None):
    """
    Generate a professional PDF report with AI insights.
    """
    pdf = SafetyReport()
    pdf.create_cover_page()
    pdf.add_page()
    
    # 1. Executive Summary
    pdf.chapter_title("Executive Summary")
    
    total_hotspots = len(sensor_df) + len(perception_df) + len(corridor_df)
    total_routes = len(route_df) if not route_df.empty else 0
    high_risk_routes = len(route_df[route_df['Colour'] == 'Red']) if not route_df.empty and 'Colour' in route_df.columns else 0
    
    pdf.chapter_body(
        f"This report provides a comprehensive analysis of road safety in Dublin based on data from sensors, "
        f"public perception reports, and corridor surveys. The dashboard is currently tracking {total_hotspots} "
        f"active safety hotspots and monitoring {total_routes} key routes."
    )
    
    # Metrics Grid
    metrics = [
        ("Total Hotspots", total_hotspots, "All Sources", "primary"),
        ("Monitored Routes", total_routes, "Key Corridors", "primary"),
        ("High Risk Routes", high_risk_routes, "Immediate Action", "red")
    ]
    pdf.add_metric_grid(metrics)
    
    # 2. Hotspot Analysis
    pdf.add_page()
    pdf.chapter_title("Priority Hotspot Analysis")
    pdf.chapter_body("Detailed AI-powered analysis of the most critical safety hotspots identified through sensor data and user reports.")
    
    # Select top hotspots (Top 3 from each source to save time/tokens)
    top_sensor = sensor_df.nlargest(3, 'concern_score') if not sensor_df.empty else pd.DataFrame()
    top_perception = perception_df.nlargest(3, 'total_perception_count') if not perception_df.empty else pd.DataFrame()
    
    # Process Sensor Hotspots
    if not top_sensor.empty:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(*pdf.brand_primary)
        pdf.cell(0, 10, "Sensor-Detected Hotspots", 0, 1)
        
        for i, (_, row) in enumerate(top_sensor.iterrows()):
            if progress_callback:
                progress_callback(f"Analyzing Sensor Hotspot {i+1}...")
                
            name = str(row.get('street_name', 'Unknown'))
            score = row.get('concern_score', 0)
            
            # Prepare data for AI
            hotspot_data = row.to_dict()
            hotspot_data['source'] = 'sensor'
            
            insights = {}
            if ai_hotspot_func:
                try:
                    insights = ai_hotspot_func(hotspot_data, [])
                except:
                    insights = {'summary': 'Analysis unavailable.'}
            
            stats = {
                "Event Type": row.get('event_type', 'N/A'),
                "Devices": row.get('device_count', 0),
                "Score": f"{score:.2f}"
            }
            
            pdf.add_ai_analysis_card(name, f"Concern Score: {score:.2f}", stats, insights)

    # Process Perception Hotspots
    if not top_perception.empty:
        pdf.add_page()
        pdf.chapter_title("User Perception Hotspots")
        
        for i, (_, row) in enumerate(top_perception.iterrows()):
            if progress_callback:
                progress_callback(f"Analyzing Perception Hotspot {i+1}...")
                
            name = str(row.get('street_name', 'Unknown'))
            count = row.get('total_perception_count', 0)
            
            # Prepare data for AI
            hotspot_data = row.to_dict()
            hotspot_data['source'] = 'perception'
            
            comments = []
            if user_comments_func:
                comments = user_comments_func(hotspot_data)
            
            insights = {}
            if ai_hotspot_func:
                try:
                    insights = ai_hotspot_func(hotspot_data, comments)
                except:
                    insights = {'summary': 'Analysis unavailable.'}
            
            stats = {
                "Reports": count,
                "Score": f"{row.get('concern_score', 0):.2f}"
            }
            
            pdf.add_ai_analysis_card(name, f"User Reports: {count}", stats, insights)

    # 3. Route Analysis
    pdf.add_page()
    pdf.chapter_title("Route Trend Analysis")
    pdf.chapter_body("AI analysis of key route performance, identifying trends, safety improvements, and areas of concern.")
    
    if not route_df.empty:
        # Select interesting routes (Top 3 Red, Top 2 Green)
        red_routes = route_df[route_df['Colour'] == 'Red'].head(3)
        green_routes = route_df[route_df['Colour'] == 'Green'].head(2)
        selected_routes = pd.concat([red_routes, green_routes])
        
        for i, (_, row) in enumerate(selected_routes.iterrows()):
            if progress_callback:
                progress_callback(f"Analyzing Route {i+1}...")
                
            name = str(row.get('street_name', 'Unknown'))
            color = row.get('Colour', 'Gray')
            status = "High Risk" if color == 'Red' else "Improved" if color == 'Green' else "Stable"
            
            # Prepare data for AI
            route_data = row.to_dict()
            
            insights = {}
            if ai_route_func:
                try:
                    insights = ai_route_func(route_data)
                except:
                    insights = {'summary': 'Analysis unavailable.'}
            
            stats = {
                "Status": status,
                "Peak Trips": row.get('peak_trips', 'N/A'),
                "Weather": str(row.get('weather_impact_note', 'N/A'))[:30] + "..."
            }
            
            pdf.add_ai_analysis_card(name, status, stats, insights)
            
    else:
        pdf.chapter_body("No route data available for analysis.")

    return pdf.output(dest='S').encode('latin-1', errors='replace')
