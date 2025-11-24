from fpdf import FPDF
import pandas as pd
from datetime import datetime
import tempfile
import os

class SafetyReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()

    def header(self):
        # Logo or Brand Name
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Spinovate Safety Dashboard', 0, 1, 'L')
        
        # Subtitle
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'AI-Powered Road Safety Analysis for Dublin', 0, 1, 'L')
        
        # Line break
        self.ln(5)
        
        # Horizontal line
        self.line(10, 30, 200, 30)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        self.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 0, 'R')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 6, body)
        self.ln()

    def add_metric_card(self, label, value, description):
        self.set_font('Arial', 'B', 12)
        self.cell(60, 10, label, 0, 0)
        self.set_font('Arial', '', 12)
        self.cell(40, 10, str(value), 0, 0)
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, description, 0, 1)

def generate_pdf_report(sensor_df, perception_df, corridor_df, route_df, abnormal_events_df):
    """
    Generate a PDF report from the provided dataframes.
    Returns the binary content of the PDF.
    """
    pdf = SafetyReport()
    
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
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "Key Metrics:", 0, 1)
    
    pdf.add_metric_card("Total Hotspots", total_hotspots, "Across all data sources")
    pdf.add_metric_card("Monitored Routes", total_routes, "Key cycling/transit routes")
    pdf.add_metric_card("High Risk Routes", high_risk_routes, "Routes requiring immediate attention")
    
    pdf.ln(10)
    
    # 2. Hotspot Analysis
    pdf.chapter_title("Hotspot Analysis")
    
    # Sensor Data
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "Top Sensor Hotspots (Core Data)", 0, 1)
    pdf.set_font('Arial', '', 10)
    
    if not sensor_df.empty:
        # Header
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(80, 8, "Location", 1, 0, 'L', 1)
        pdf.cell(60, 8, "Event Type", 1, 0, 'L', 1)
        pdf.cell(40, 8, "Concern Score", 1, 1, 'L', 1)
        
        # Top 5 rows
        top_sensor = sensor_df.nlargest(5, 'concern_score') if 'concern_score' in sensor_df.columns else sensor_df.head(5)
        
        for _, row in top_sensor.iterrows():
            name = str(row.get('street_name', 'Unknown'))[:35]
            event = str(row.get('event_type', 'N/A'))[:25]
            score = f"{row.get('concern_score', 0):.2f}"
            
            pdf.cell(80, 8, name, 1)
            pdf.cell(60, 8, event, 1)
            pdf.cell(40, 8, score, 1, 1)
    else:
        pdf.cell(0, 10, "No sensor data available.", 0, 1)
        
    pdf.ln(5)
    
    # Perception Data
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "Top Perception Hotspots (User Reports)", 0, 1)
    pdf.set_font('Arial', '', 10)
    
    if not perception_df.empty:
        # Header
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(80, 8, "Location", 1, 0, 'L', 1)
        pdf.cell(60, 8, "Report Count", 1, 0, 'L', 1)
        pdf.cell(40, 8, "Concern Score", 1, 1, 'L', 1)
        
        # Top 5 rows
        top_perception = perception_df.nlargest(5, 'total_perception_count') if 'total_perception_count' in perception_df.columns else perception_df.head(5)
        
        for _, row in top_perception.iterrows():
            name = str(row.get('street_name', 'Unknown'))[:35]
            count = str(row.get('total_perception_count', 0))
            score = f"{row.get('concern_score', 0):.2f}"
            
            pdf.cell(80, 8, name, 1)
            pdf.cell(60, 8, count, 1)
            pdf.cell(40, 8, score, 1, 1)
    else:
        pdf.cell(0, 10, "No perception data available.", 0, 1)
        
    pdf.ln(10)
    
    # 3. Route Trends
    pdf.chapter_title("Route Popularity & Trends")
    
    if not route_df.empty:
        pdf.chapter_body(
            "The following routes have been identified as high priority based on recent trend analysis. "
            "Routes marked as 'Red' indicate declining popularity or safety concerns."
        )
        
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(80, 8, "Route Name", 1, 0, 'L', 1)
        pdf.cell(40, 8, "Status", 1, 0, 'L', 1)
        pdf.cell(60, 8, "Peak Trips", 1, 1, 'L', 1)
        
        pdf.set_font('Arial', '', 10)
        
        # Show top 10 routes (prioritize Red ones)
        if 'Colour' in route_df.columns:
            sorted_routes = route_df.sort_values('Colour', ascending=False).head(10) # Red is usually after Green alphabetically? No, R after G. So descending puts Red first? 
            # Actually let's be explicit
            red_routes = route_df[route_df['Colour'] == 'Red']
            green_routes = route_df[route_df['Colour'] == 'Green']
            sorted_routes = pd.concat([red_routes, green_routes]).head(15)
        else:
            sorted_routes = route_df.head(15)
            
        for _, row in sorted_routes.iterrows():
            name = str(row.get('street_name', 'Unknown'))[:35]
            color = row.get('Colour', 'Gray')
            status = "Needs Attention" if color == 'Red' else "Good"
            trips = str(row.get('peak_trips', 'N/A'))[:25]
            
            pdf.cell(80, 8, name, 1)
            pdf.cell(40, 8, status, 1)
            pdf.cell(60, 8, trips, 1, 1)
            
    else:
        pdf.chapter_body("No route trend data available.")

    # Output
    return pdf.output(dest='S').encode('latin-1')
