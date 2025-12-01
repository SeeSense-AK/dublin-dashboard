
import sys
import os
sys.path.append(os.getcwd())
from src.hotspot_pdf import generate_hotspot_pdf

# Dummy data
hotspot_data = {
    'hotspot_name': 'Test Hotspot',
    'location': 'Test Location',
    'urgency_score': '85.0%',
    'priority': 'CRITICAL',
    'event_type': 'Braking',
    'reports': 10
}

insights = {
    'summary': 'This is a test summary.',
    'themes': ['Theme 1', 'Theme 2'],
    'recommendations': ['Rec 1', 'Rec 2']
}

# Coordinates for Dublin
lat = 53.3498
lng = -6.2603

try:
    pdf_bytes = generate_hotspot_pdf(hotspot_data, insights, lat=lat, lng=lng)
    print(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
    # Save to check manually if needed
    with open('test_output.pdf', 'wb') as f:
        f.write(pdf_bytes)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
