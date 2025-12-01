"""
Generate single-hotspot PDF report
"""
from fpdf import FPDF
import os
from datetime import datetime
import io
import folium
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO

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
    Generate a professional one-page PDF for a single hotspot using a PNG template.
    
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
    
    # 1. Add Template Background
    template_path = 'assets/hotspot-template.png'
    if os.path.exists(template_path):
        # Place image to cover full A4 page (210x297 mm)
        pdf.image(template_path, x=0, y=0, w=210, h=297)
    
    # 2. Define Content Area (based on user provided bounding box)
    # User provided: x1=160, y1=174, width=1274, height=1897 (likely in pixels for a high-res image)
    # Assuming standard A4 at 300dpi (2480 x 3508 px) or similar.
    # We'll map these to mm. A4 is 210mm wide.
    # Let's use a safe margin approach instead of exact pixel mapping to ensure it fits well.
    
    content_start_y = 45  # mm from top (below header)
    margin_x = 15         # mm from left
    content_width = 180   # mm
    
    # Title (Hotspot Name)
    pdf.set_font('Arial', 'B', 18)
    pdf.set_text_color(*pdf.brand_primary)
    pdf.set_xy(margin_x, 25)
    pdf.cell(120, 8, pdf.sanitize_text(hotspot_data.get('hotspot_name', 'Hotspot')), ln=True)
    
    # Location
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(margin_x)
    pdf.cell(120, 6, pdf.sanitize_text(hotspot_data.get('location', 'Unknown')), ln=True)
    
    # Date
    pdf.set_font('Arial', '', 9)
    pdf.set_x(margin_x)
    pdf.cell(120, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    
    # Map Section
    pdf.set_y(content_start_y)
    
    if lat and lng:
        map_img_data = get_static_map_image(lat, lng)
        if map_img_data:
            try:
                temp_map_path = '/tmp/hotspot_map_temp.png'
                with open(temp_map_path, 'wb') as f:
                    f.write(map_img_data)
                
                # Add map image
                pdf.image(temp_map_path, x=margin_x, y=content_start_y, w=content_width, h=70)
                pdf.set_y(content_start_y + 75) # Move cursor below map
            except Exception as e:
                print(f"Error adding map: {e}")
                pdf.set_y(content_start_y)
        else:
            pdf.set_y(content_start_y)
    else:
        pdf.set_y(content_start_y)
        
    # Key Statistics
    stats_y = pdf.get_y()
    
    stats = [
        ('Urgency Score', hotspot_data.get('urgency_score', 'N/A')),
        ('Priority', hotspot_data.get('priority', 'N/A')),
        ('Event Type', hotspot_data.get('event_type', 'N/A')),
        ('Reports', str(hotspot_data.get('reports', 'N/A')))
    ]
    
    # Calculate box width dynamically
    box_width = (content_width - (3 * 4)) / 4  # 3 gaps of 4mm
    
    for i, (label, value) in enumerate(stats):
        x_pos = margin_x + (i * (box_width + 4))
        
        pdf.set_xy(x_pos, stats_y)
        
        # Box background (White with border to stand out on template)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(229, 231, 235)
        pdf.rect(x_pos, stats_y, box_width, 18, 'FD')
        
        # Label
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(107, 114, 128)
        pdf.set_xy(x_pos, stats_y + 3)
        pdf.cell(box_width, 4, pdf.sanitize_text(label), align='C')
        
        # Value
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*pdf.brand_text)
        
        # Color code priority
        if label == 'Priority':
            if value == 'CRITICAL':
                pdf.set_text_color(*pdf.brand_red)
            elif value == 'HIGH':
                pdf.set_text_color(*pdf.brand_amber)
            else:
                pdf.set_text_color(*pdf.brand_blue)
        
        pdf.set_xy(x_pos, stats_y + 9)
        pdf.cell(box_width, 5, pdf.sanitize_text(str(value)), align='C')
    
    pdf.set_y(stats_y + 25)
    
    # AI Analysis Section
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(*pdf.brand_primary)
    pdf.cell(0, 8, 'AI Safety Analysis', ln=True)
    
    # Summary
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(*pdf.brand_text)
    summary = pdf.sanitize_text(insights.get('summary', 'No analysis available'))
    pdf.multi_cell(content_width, 5, summary)
    
    # Themes
    if insights.get('themes'):
        pdf.set_y(pdf.get_y() + 6)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(*pdf.brand_primary)
        pdf.cell(0, 6, 'Key Safety Themes', ln=True)
        
        pdf.set_y(pdf.get_y() + 2)
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(*pdf.brand_text)
        
        # Display themes as tags
        theme_y = pdf.get_y()
        theme_x = margin_x
        for theme in insights['themes'][:4]:
            theme_text = pdf.sanitize_text(theme)
            theme_width = pdf.get_string_width(theme_text) + 8
            
            if theme_x + theme_width > (margin_x + content_width):
                theme_y += 8
                theme_x = margin_x
            
            # Theme box
            pdf.set_fill_color(243, 244, 246)
            pdf.set_draw_color(209, 213, 219)
            pdf.rect(theme_x, theme_y, theme_width, 6, 'FD')
            
            pdf.set_xy(theme_x + 4, theme_y + 1)
            pdf.cell(theme_width - 8, 4, theme_text)
            
            theme_x += theme_width + 4
        
        pdf.set_y(theme_y + 10)
    
    # Recommendations
    if insights.get('recommendations'):
        pdf.set_y(pdf.get_y() + 4)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(*pdf.brand_primary)
        pdf.cell(0, 6, 'Recommended Actions', ln=True)
        
        pdf.set_y(pdf.get_y() + 2)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(*pdf.brand_text)
        
        for rec in insights['recommendations'][:3]:
            rec_text = pdf.sanitize_text(rec)
            pdf.set_x(margin_x + 3)
            pdf.multi_cell(content_width - 3, 5, f"- {rec_text}")
            pdf.ln(1)

    # Footer (if not in template)
    # pdf.set_y(-15)
    # pdf.set_font('Arial', 'I', 8)
    # pdf.set_text_color(150, 150, 150)
    # pdf.cell(0, 5, 'Generated by Spinovate Safety Dashboard', align='C')

    return pdf.output(dest='S').encode('latin-1')



def get_static_map_image(lat: float, lng: float) -> bytes:
    """
    Try to get a static map image from multiple services with fallback.
    Returns bytes of PNG image or None if all fail.
    """
    # Service 1: OpenStreetMap Static Map (often flaky but good quality)
    try:
        zoom = 16
        width = 700
        height = 300
        map_url = f"https://staticmap.openstreetmap.de/staticmap.php?center={lat},{lng}&zoom={zoom}&size={width}x{height}&markers={lat},{lng},red-pushpin"
        
        response = requests.get(map_url, timeout=5)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        print(f"OSM Static Map failed: {e}")

    # Service 2: Yandex Static Maps (Fallback)
    try:
        # Yandex uses lng,lat order
        # size max is 650x450
        width = 600
        height = 300
        map_url = f"https://static-maps.yandex.ru/1.x/?lang=en_US&ll={lng},{lat}&z={zoom}&l=map&size={width},{height}&pt={lng},{lat},pm2rdm"
        
        response = requests.get(map_url, timeout=5)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        print(f"Yandex Static Map failed: {e}")

    # Fallback: Generate Placeholder Image
    try:
        img = Image.new('RGB', (700, 300), color='#f3f4f6')
        d = ImageDraw.Draw(img)
        
        # Add text
        text = "Map Unavailable"
        # Try to load a font, fallback to default
        try:
            font = ImageFont.truetype("Arial", 24)
        except:
            font = ImageFont.load_default()
            
        # Center text (approximate)
        d.text((300, 140), text, fill='#6b7280', font=font)
        
        # Convert to bytes
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
        
    except Exception as e:
        print(f"Placeholder generation failed: {e}")
        return None


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
