"""
Generate single-hotspot PDF report
"""
from fpdf import FPDF
import os
from datetime import datetime
import io
import folium
from PIL import Image

class HotspotPDF(FPDF):
    """PDF generator for individual hotspot one-pagers"""
    
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=False)
        self.set_margins(15, 15, 15)
        
        # Brand Colors
        self.brand_primary = (3, 105, 161)
        self.brand_text = (55, 65, 81)
        self.brand_red = (220, 38, 38)
        self.brand_amber = (245, 158, 11)
        self.brand_blue = (59, 130, 246)
        
    def sanitize_text(self, text):
        """Replace incompatible unicode characters"""
        if not isinstance(text, str):
            return str(text)
            
        replacements = {
            '\u2018': "'", '\u2019': "'",
            '\u201c': '"', '\u201d': '"',
            '\u2013': '-', '\u2014': '-',
            '\u2026': '...', '\u2022': '-',
            '\u00a0': ' ',
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
            
        return text.encode('latin-1', 'replace').decode('latin-1')


def generate_hotspot_pdf(hotspot_data: dict, insights: dict, lat: float = None, lng: float = None) -> bytes:
    """
    Generate a professional one-page PDF for a single hotspot.
    
    Args:
        hotspot_data: Dictionary with hotspot information
        insights: Dictionary with AI analysis (summary, themes, recommendations)
        lat: Latitude for map
        lng: Longitude for map
    
    Returns:
        bytes: PDF file content
    """
    pdf = HotspotPDF()
    pdf.add_page()
    
    # Logo paths
    logo_path = 'assets/logo.png'
    dcc_logo_path = 'assets/dcc-logo.png'
    
    # Both logos at top right - smaller size and separated by a line
    logo_x = 145
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=logo_x, y=10, w=25, h=0, type='PNG')
    
    # Vertical separator line
    pdf.set_draw_color(200, 200, 200)
    pdf.line(logo_x + 27, 10, logo_x + 27, 25)
    
    if os.path.exists(dcc_logo_path):
        pdf.image(dcc_logo_path, x=logo_x + 30, y=10, w=25, h=0, type='PNG')
    
    # Title
    pdf.set_font('Arial', 'B', 18)
    pdf.set_text_color(*pdf.brand_primary)
    pdf.set_xy(15, 15)
    pdf.cell(125, 8, pdf.sanitize_text(hotspot_data.get('hotspot_name', 'Hotspot')), ln=True)
    
    # Location
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(15)
    pdf.cell(125, 6, pdf.sanitize_text(hotspot_data.get('location', 'Unknown')), ln=True)
    
    # Date
    pdf.set_font('Arial', '', 9)
    pdf.set_x(15)
    pdf.cell(125, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    
    # Reset position
    pdf.set_y(35)
    
    # Map - Generate static map if coordinates provided
    if lat and lng:
        try:
            import requests
            from io import BytesIO
            
            # Use OpenStreetMap static map (using staticmap.openstreetmap.de)
            zoom = 16
            width = 700
            height = 300
            
            # Build static map URL with marker
            map_url = f"https://staticmap.openstreetmap.de/staticmap.php?center={lat},{lng}&zoom={zoom}&size={width}x{height}&markers={lat},{lng},red-pushpin"
            
            # Download map image
            response = requests.get(map_url, timeout=10)
            if response.status_code == 200:
                # Save temporarily
                temp_map_path = '/tmp/hotspot_map_temp.png'
                with open(temp_map_path, 'wb') as f:
                    f.write(response.content)
                
                # Add to PDF
                pdf.image(temp_map_path, x=15, y=40, w=180, h=70)
                pdf.set_y(115)
            else:
                pdf.set_y(40)
        except Exception as e:
            print(f"Could not generate map: {e}")
            pdf.set_y(40)
    else:
        pdf.set_y(40)
    
    # Key Statistics (4 boxes in a row)
    pdf.set_y(pdf.get_y() + 5)
    stats_y = pdf.get_y()
    
    stats = [
        ('Urgency Score', hotspot_data.get('urgency_score', 'N/A')),
        ('Priority', hotspot_data.get('priority', 'N/A')),
        ('Event Type', hotspot_data.get('event_type', 'N/A')),
        ('Reports', str(hotspot_data.get('reports', 'N/A')))
    ]
    
    box_width = 43
    x_positions = [15, 61, 107, 153]
    
    for i, (label, value) in enumerate(stats):
        pdf.set_xy(x_positions[i], stats_y)
        
        # Box background
        pdf.set_fill_color(248, 250, 252)
        pdf.rect(x_positions[i], stats_y, box_width, 18, 'F')
        pdf.set_draw_color(229, 231, 235)
        pdf.rect(x_positions[i], stats_y, box_width, 18, 'D')
        
        # Label
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(107, 114, 128)
        pdf.set_xy(x_positions[i], stats_y + 3)
        pdf.cell(box_width, 4, pdf.sanitize_text(label), align='C')
        
        # Value
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(*pdf.brand_text)
        
        # Color code priority
        if label == 'Priority':
            if value == 'CRITICAL':
                pdf.set_text_color(*pdf.brand_red)
            elif value == 'HIGH':
                pdf.set_text_color(*pdf.brand_amber)
            else:
                pdf.set_text_color(*pdf.brand_blue)
        
        pdf.set_xy(x_positions[i], stats_y + 9)
        pdf.cell(box_width, 5, pdf.sanitize_text(str(value)), align='C')
    
    pdf.set_y(stats_y + 22)
    
    # AI Analysis Section
    pdf.set_y(pdf.get_y() + 8)
    pdf.set_font('Arial', 'B', 13)
    pdf.set_text_color(*pdf.brand_primary)
    pdf.cell(0, 6, 'AI Safety Analysis', ln=True)
    
    # Summary
    pdf.set_y(pdf.get_y() + 3)
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(*pdf.brand_text)
    summary = pdf.sanitize_text(insights.get('summary', 'No analysis available'))
    pdf.multi_cell(0, 4, summary)
    
    # Themes
    if insights.get('themes'):
        pdf.set_y(pdf.get_y() + 5)
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*pdf.brand_primary)
        pdf.cell(0, 5, 'Key Safety Themes', ln=True)
        
        pdf.set_y(pdf.get_y() + 2)
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(*pdf.brand_text)
        
        # Display themes as tags in a row
        theme_y = pdf.get_y()
        theme_x = 15
        for theme in insights['themes'][:4]:  # Limit to 4
            theme_text = pdf.sanitize_text(theme)
            theme_width = pdf.get_string_width(theme_text) + 6
            
            # Check if we need to wrap
            if theme_x + theme_width > 195:
                theme_y += 8
                theme_x = 15
            
            # Draw theme box
            pdf.set_fill_color(243, 244, 246)
            pdf.set_draw_color(229, 231, 235)
            pdf.rect(theme_x, theme_y, theme_width, 6, 'FD')
            
            pdf.set_xy(theme_x + 3, theme_y + 1)
            pdf.cell(theme_width - 6, 4, theme_text)
            
            theme_x += theme_width + 3
        
        pdf.set_y(theme_y + 8)
    
    # Recommendations
    if insights.get('recommendations'):
        pdf.set_y(pdf.get_y() + 3)
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*pdf.brand_primary)
        pdf.cell(0, 5, 'Recommended Actions', ln=True)
        
        pdf.set_y(pdf.get_y() + 2)
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(*pdf.brand_text)
        
        for rec in insights['recommendations'][:3]:  # Limit to 3
            rec_text = pdf.sanitize_text(rec)
            pdf.set_x(18)
            pdf.multi_cell(0, 4, f"- {rec_text}")
    
    # Footer
    pdf.set_y(280)
    pdf.set_font('Arial', 'I', 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, 'Generated by Spinovate Safety Dashboard', align='C')
    
    # Return PDF as bytes
    return pdf.output(dest='S').encode('latin-1')


def save_map_as_image(lat: float, lng: float, hotspot_name: str, temp_path: str = '/tmp/hotspot_map.png'):
    """
    Generate a map and save it as an image for PDF embedding.
    
    Args:
        lat: Latitude
        lng: Longitude
        hotspot_name: Name for the marker
        temp_path: Path to save temporary image
    
    Returns:
        str: Path to saved image file
    """
    try:
        # Create folium map
        m = folium.Map(location=[lat, lng], zoom_start=16, tiles='CartoDB positron')
        folium.Marker([lat, lng], popup=hotspot_name).add_to(m)
        
        # Save as HTML then convert to image (requires additional dependencies)
        # For now, return None and skip map in PDF
        # TODO: Implement proper map screenshot functionality
        return None
        
    except Exception as e:
        print(f"Error generating map image: {e}")
        return None
