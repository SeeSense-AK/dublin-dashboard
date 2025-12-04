"""
Tab 1: Hotspot Analysis - Enhanced Professional Version
Displays combined hotspots from Top 30 analysis and corridors
Power BI/Tableau-level professional styling using CSS classes
"""

import streamlit as st
import pandas as pd
import json
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
from pathlib import Path
from datetime import datetime, timedelta
from branca.element import MacroElement, Template  

# Import your original utilities and functions
try:
    from utils.constants import STREET_VIEW_URL_TEMPLATE
    from src.ai_insights import generate_hotspot_insights, extract_user_comments
except ImportError:
    # Fallback for any missing imports
    STREET_VIEW_URL_TEMPLATE = "https://www.google.com/maps?layer=c&cbll={lat},{lng}&cbp=12,{heading},0,0,0"

# ────────────────────────────────────────────────
# PROFESSIONAL COMPONENTS USING CSS CLASSES
# ────────────────────────────────────────────────

def create_section_header(title, description=None):
    """Create professional section headers using CSS classes"""
    if description:
        st.markdown(f"""
        <div class="section-header">
            <h2>{title}</h2>
            <p class="section-description">{description}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="section-header">
            <h2>{title}</h2>
        </div>
        """, unsafe_allow_html=True)

def render_summary_panel(top_30_selected, corridor_selected):
    """Render high-level summary panel with color-coded metrics"""
    
    total_hotspots = len(top_30_selected) + len(corridor_selected)
    
    # Calculate counts based on urgency/priority
    critical_count = 0
    medium_count = 0
    low_count = 0
    
    # Process Top 30
    for _, row in top_30_selected.iterrows():
        score = row.get('scores.composite_score', 0) * 100
        if score >= 80:
            critical_count += 1
        elif score >= 60:
            medium_count += 1
        else:
            low_count += 1
            
    # Process Corridors
    for _, row in corridor_selected.iterrows():
        score = row.get('weighted_score', 0)
        if score >= 80:
            critical_count += 1
        elif score >= 60:
            medium_count += 1
        else:
            low_count += 1

    # Add the hover card CSS
    st.markdown("""
    <style>
    .summary-card-hover {
        text-align: center; 
        background: #f8fafc; 
        padding: 1.5rem; 
        border-radius: 8px; 
        margin: 0.5rem;
        transition: all 0.3s;
        cursor: pointer;
        border: 1px solid #e5e7eb;  /* Light grey border */
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);  /* Subtle shadow by default */
    }
    .summary-card-hover:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);  /* Increased shadow on hover */
        background: #f1f5f9;
        border: 1px solid #e5e7eb;  /* Keep light grey border on hover */
    }
    
    .summary-value {
        font-size: 36px;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .summary-label {
        font-size: 14px;
        font-weight: bold;
        color: #888;
    }
    .text-red { color: #DC2626; }
    .text-amber { color: #F59E0B; }
    .text-blue { color: #3B82F6; }
    .text-white { color: #1f2937; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="summary-card-hover">
            <div class="summary-value text-white">{total_hotspots}</div>
            <div class="summary-label">Total Hotspots</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="summary-card-hover">
            <div class="summary-value text-red">{critical_count}</div>
            <div class="summary-label">Critical Priority</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="summary-card-hover">
            <div class="summary-value text-amber">{medium_count}</div>
            <div class="summary-label">High Priority</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class="summary-card-hover">
            <div class="summary-value text-blue">{low_count}</div>
            <div class="summary-label">Medium Priority</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")

def render_compact_hotspot_list(top_30_selected, corridor_selected):
    """Render hotspots in a compact list format"""
    
    # Combine and sort all hotspots
    all_hotspots = []
    for idx, row in top_30_selected.iterrows():
        all_hotspots.append((row, 'top_30'))
    for idx, row in corridor_selected.iterrows():
        all_hotspots.append((row, 'corridor'))
    
    # Sort by hotspot name to ensure correct order (Hotspot 1, Hotspot 2...)
    def get_id(item):
        name = item[0].get('hotspot_name', 'Hotspot 999')
        try:
            return int(name.replace('Hotspot ', ''))
        except:
            return 999
            
    all_hotspots.sort(key=get_id)
        
    # Header Row
    st.markdown("""
    <div style="display: grid; grid-template-columns: 0.7fr 1.5fr 0.8fr 2fr 1.5fr 0.8fr 0.8fr 1fr; gap: 10px; padding: 10px; background-color: #262626; border-radius: 5px; font-weight: bold; font-size: 0.9em; color: #CCC; text-align: center; align-items: center;">
        <div>Priority</div>
        <div>Hotspot Name</div>
        <div>Score</div>
        <div>Location</div>
        <div>Event Type</div>
        <div>Riders</div>
        <div>Reports</div>
        <div>Analysis</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Add separator after header for consistent spacing
    st.markdown("<hr style='margin: 0; border-color: #333;'>", unsafe_allow_html=True)
    
    # List Items
    for i, (row, source) in enumerate(all_hotspots):
        # Extract Data
        hotspot_name = row.get('hotspot_name', 'Hotspot')
        
        if source == 'corridor':
            urgency_val = float(row.get('weighted_score', 0))
            urgency_score = f"{urgency_val:.1f}%"
            location = row.get('road_name', 'Unknown')
            event_type = row.get('dominant_category', 'N/A')
            device_count = "-"
            user_reports = int(row.get('report_count', 0))
            lat, lng = row.get('center_lat'), row.get('center_lng')
            priority_cat = row.get('priority_category', 'MEDIUM')
            
            # Determine Color
            color = get_color_by_score(urgency_val)
                
        else: # Top 30
            score_val = row.get('scores.composite_score', 0)
            urgency_val = score_val * 100
            urgency_score = f"{urgency_val:.1f}%"
            
            # Handle list-type street names
            location = row.get('identification.street_name', 'Unknown')
            if isinstance(location, list):
                location = " / ".join(location)
                
            event_type = row.get('sensor_data.event_type', 'N/A')
            device_count = int(row.get('sensor_data.device_count', 0))
            user_reports = int(row.get('collision_reports.total_count', 0))
            lat, lng = row.get('identification.latitude'), row.get('identification.longitude')
            
            # Determine Color
            color = get_color_by_score(urgency_val)

        # Clean Event Type
        if event_type and event_type != 'N/A':
            event_type = event_type.replace('_', ' ').title()
            event_type = transform_event_type_for_display(event_type)
            
        # Render Row
        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([0.7, 1.5, 0.8, 2, 1.5, 0.8, 0.8, 1])
        
        with col1:
            st.markdown(f'<div style="background-color: {color}; width: 12px; height: 12px; border-radius: 50%; margin: 12px auto;"></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div style='text-align: center; padding: 10px 0;'>{hotspot_name}</div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div style='text-align: center; padding: 10px 0;'>{urgency_score}</div>", unsafe_allow_html=True)
        with col4:
            st.markdown(f"<div style='text-align: center; padding: 10px 0;'>{location}</div>", unsafe_allow_html=True)
        with col5:
            st.markdown(f"<div style='text-align: center; padding: 10px 0;'>{event_type}</div>", unsafe_allow_html=True)
        with col6:
            st.markdown(f"<div style='text-align: center; padding: 10px 0;'>{device_count}</div>", unsafe_allow_html=True)
        with col7:
            st.markdown(f"<div style='text-align: center; padding: 10px 0;'>{user_reports}</div>", unsafe_allow_html=True)
        with col8:
            # Center the button vertically using a container with padding if needed, 
            # but st.button is hard to style directly. 
            # We rely on the text padding to match the button's natural height/spacing.
            if st.button("View", key=f"btn_{i}", use_container_width=True):
                st.session_state['selected_hotspot'] = row
                st.session_state['selected_source'] = source
                st.session_state['view_mode'] = 'detail'
                st.rerun()
                
        st.markdown("<hr style='margin: 0; border-color: #333;'>", unsafe_allow_html=True)

def transform_event_type_for_display(event_type):
    """Transform event type names for user-friendly display"""
    if not event_type or event_type == 'N/A':
        return event_type
    # Replace 'Pothole' with 'Road Roughness'
    return event_type.replace('Pothole', 'Road Roughness')

def render_hotspot_details_page():
    """Render dedicated full-page view for hotspot analysis with professional styling"""
    
    row = st.session_state.get('selected_hotspot')
    source = st.session_state.get('selected_source')
    
    if row is None:
        st.session_state['view_mode'] = 'list'
        st.rerun()
        return

    # Professional CSS
    st.markdown("""
    <style>
    .detail-header {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 2.5rem;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 0.5rem;
    }
    .detail-subhead {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 1.1rem;
        color: #6b7280;
        margin-bottom: 2rem;
    }
    .stat-box {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        padding: 1.5rem;
        text-align: center;
    }
    .stat-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #6b7280;
        margin-bottom: 0.5rem;
    }
    .stat-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #111827;
    }
    .tooltip-container {
        position: relative;
        display: inline-block;
    }
    .info-icon {
        display: inline-block;
        margin-left: 6px;
        color: #9ca3af;
        cursor: help;
        font-size: 0.9rem;
    }
    .tooltip-text {
        visibility: hidden;
        width: 280px;
        background-color: #1f2937;
        color: #fff;
        text-align: left;
        border-radius: 6px;
        padding: 12px;
        position: absolute;
        z-index: 1000;
        bottom: 125%;
        left: 50%;
        margin-left: -140px;
        opacity: 0;
        transition: opacity 0.3s;
        font-size: 0.75rem;
        line-height: 1.4;
        text-transform: none;
        letter-spacing: normal;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .tooltip-text::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -5px;
        border-width: 5px;
        border-style: solid;
        border-color: #1f2937 transparent transparent transparent;
    }
    .tooltip-container:hover .tooltip-text {
        visibility: visible;
        opacity: 1;
    }
    .analysis-container {
        background-color: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 2rem;
        margin-top: 2rem;
    }
    .analysis-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: #111827;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid #e5e7eb;
        padding-bottom: 1rem;
    }
    .analysis-subtitle {
        font-size: 1.1rem;
        font-weight: 600;
        color: #374151;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .analysis-list {
        list-style-type: none;
        padding-left: 0;
    }
    .analysis-list li {
        position: relative;
        padding-left: 1.5rem;
        margin-bottom: 0.5rem;
        color: #4b5563;
        line-height: 1.6;
    }
    .analysis-list li::before {
        content: "•";
        position: absolute;
        left: 0;
        color: #9ca3af;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

    # Back Button
    if st.button("← Back to List"):
        st.session_state['view_mode'] = 'list'
        st.rerun()
        
    # Extract Data
    hotspot_name = row.get('hotspot_name', 'Hotspot')
    
    if source == 'corridor':
        location = row.get('road_name', 'Unknown')
        lat, lng = row.get('center_lat'), row.get('center_lng')
        urgency_score = f"{row.get('weighted_score', 0):.1f}%"
        event_type = row.get('dominant_category', 'N/A')
        reports = row.get('report_count', 0)
        priority = row.get('priority_category', 'MEDIUM')
    else:
        # Handle list-type street names
        location = row.get('identification.street_name', 'Unknown')
        if isinstance(location, list):
            location = " / ".join(location)
            
        lat, lng = row.get('identification.latitude'), row.get('identification.longitude')
        score_val = row.get('scores.composite_score', 0) * 100
        urgency_score = f"{score_val:.1f}%"
        event_type = row.get('sensor_data.event_type', 'N/A')
        reports = row.get('collision_reports.total_count', 0)
        
        # Determine priority based on score
        if score_val >= 80:
            priority = 'CRITICAL'
        elif score_val >= 60:
            priority = 'HIGH'
        else:
            priority = 'MEDIUM'
        
    # Transform event type for display
    if event_type and event_type != 'N/A':
        event_type = event_type.replace('_', ' ').title()
        event_type = transform_event_type_for_display(event_type)
    
    # Determine priority color
    if priority == 'CRITICAL':
        priority_color = '#DC2626'  # Red
    elif priority == 'HIGH':
        priority_color = '#F59E0B'  # Amber
    else:
        priority_color = '#3B82F6'  # Blue

    # Header
    st.markdown(f'<div class="detail-header">{hotspot_name}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="detail-subhead">Location: {location}</div>', unsafe_allow_html=True)
    
    # Map and Street View Container
    col_map, col_sv = st.columns([2, 1])
    
    with col_map:
        try:
            m = folium.Map(location=[lat, lng], zoom_start=16, tiles='CartoDB positron')
            
            # Check for geometry (Top 30 with corridor match)
            has_geometry = False
            if source == 'top_30':
                geom_type = row.get('corridor_data.geometry.geometry_type')
                coords = row.get('corridor_data.geometry.coordinates')
                
                if geom_type and isinstance(coords, list) and len(coords) > 0:
                    has_geometry = True
                    if geom_type == 'Polygon':
                        # Polygon: [[[lon, lat], ...]] - Extract exterior ring
                        poly_coords = [(p[1], p[0]) for p in coords[0]]
                        folium.Polygon(
                            locations=poly_coords,
                            popup=hotspot_name,
                            color=priority_color,
                            fill=True,
                            fillColor=priority_color,
                            fillOpacity=0.4,
                            weight=3
                        ).add_to(m)
                    elif geom_type == 'LineString':
                        # LineString: [[lon, lat], ...]
                        line_coords = [(p[1], p[0]) for p in coords]
                        folium.PolyLine(
                            locations=line_coords,
                            popup=hotspot_name,
                            color=priority_color,
                            weight=5,
                            opacity=0.8
                        ).add_to(m)
                    elif geom_type == 'MultiLineString':
                        # MultiLineString: [[[lon, lat], ...], ...]
                        for line in coords:
                            line_coords = [(p[1], p[0]) for p in line]
                            folium.PolyLine(
                                locations=line_coords,
                                popup=hotspot_name,
                                color=priority_color,
                                weight=5,
                                opacity=0.8
                            ).add_to(m)
            elif source == 'corridor':
                # Corridor source - draw polygon from geometry
                has_geometry = True
                coords_folium = [(coord[1], coord[0]) for coord in row['geometry']]
                folium.Polygon(
                    locations=coords_folium,
                    popup=hotspot_name,
                    color=priority_color,
                    fill=True,
                    fillColor=priority_color,
                    fillOpacity=0.4,
                    weight=3
                ).add_to(m)

            # Only add point marker if no geometry exists
            # Do NOT display point coordinate if using polygon coordinates
            if not has_geometry:
                folium.Marker([lat, lng], popup=hotspot_name).add_to(m)
            
            folium_static(m, height=300)
        except Exception as e:
            st.error(f"Could not render map: {e}")
            
    with col_sv:
        st.markdown("<br>", unsafe_allow_html=True) # Spacing
        st.markdown(f"""
        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center;">
            <p style="color: #4b5563; margin-bottom: 15px;">View actual road conditions</p>
            <a href="{STREET_VIEW_URL_TEMPLATE.format(lat=lat, lng=lng, heading=0)}" target="_blank" style="text-decoration: none;">
                <button style="background-color: white; border: 1px solid #d1d5db; color: #374151; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 500; width: 100%;">
                    Open Street View
                </button>
            </a>
        </div>
        """, unsafe_allow_html=True)
    
    # Key Statistics Grid
    st.markdown("<br>", unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    
    with s1:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-label">
                <span class="tooltip-container">
                    Urgency Score
                    <span class="info-icon">ℹ️</span>
                    <span class="tooltip-text">A composite score (0-100) indicating the severity of safety risks based on event frequency, type, and user reports.</span>
                </span>
            </div>
            <div class="stat-value">{urgency_score}</div>
        </div>
        """, unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-label">
                <span class="tooltip-container">
                    Priority Level
                    <span class="info-icon">ℹ️</span>
                    <span class="tooltip-text">CRITICAL: Score ≥ 80%<br>HIGH: Score 60-79%<br>MEDIUM: Score < 60%</span>
                </span>
            </div>
            <div class="stat-value" style="color: {priority_color};">{priority}</div>
        </div>
        """, unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-label">Event Type</div>
            <div class="stat-value">{event_type}</div>
        </div>
        """, unsafe_allow_html=True)
    with s4:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-label">Reports</div>
            <div class="stat-value">{reports}</div>
        </div>
        """, unsafe_allow_html=True)

    # AI Safety Analysis
    st.markdown('<div class="analysis-container">', unsafe_allow_html=True)
    st.markdown('<div class="analysis-title">AI Safety Analysis</div>', unsafe_allow_html=True)
    
    with st.spinner("Generating analysis..."):
        hotspot_data = row.to_dict()
        hotspot_data['source'] = source
        
        # Data is now correctly accessed from csv_data object
        
        try:
            # Extract sample descriptions properly
            if source == 'top_30':
                # Try multiple possible field names for sample descriptions
                user_comments = (hotspot_data.get('sample_descriptions') or 
                               hotspot_data.get('narrative.sample_descriptions') or 
                               row.get('narrative.sample_descriptions', []))
                
                # Also add sample_descriptions directly to hotspot_data for AI to access
                if 'sample_descriptions' not in hotspot_data and user_comments:
                    hotspot_data['sample_descriptions'] = user_comments
            else:
                user_comments = extract_user_comments(hotspot_data)
                
            insights = generate_hotspot_insights(hotspot_data, user_comments)

            
            # Summary
            st.markdown(f'<p style="color: #374151; font-size: 1.05rem; line-height: 1.6;">{insights["summary"]}</p>', unsafe_allow_html=True)
            
            st.markdown("<hr style='border-color: #e5e7eb; margin: 2rem 0;'>", unsafe_allow_html=True)
            
            # Two Column Layout for Themes and Actions
            ac1, ac2 = st.columns(2, gap="large")
            
            with ac1:
                st.markdown('<div class="analysis-subtitle">Key Safety Themes</div>', unsafe_allow_html=True)
                if insights.get('themes'):
                    # Display themes as horizontal boxes
                    themes_html = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 2rem;">'
                    for theme in insights['themes']:
                        themes_html += f'<div style="background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px 16px; font-size: 0.9rem; color: #374151;">{theme}</div>'
                    themes_html += '</div>'
                    st.markdown(themes_html, unsafe_allow_html=True)
                else:
                    st.markdown('<p style="color: #6b7280; font-style: italic;">No specific themes identified.</p>', unsafe_allow_html=True)
            
            # Traffic Type and Seasonality sections (full width)
            st.markdown("<hr style='border-color: #e5e7eb; margin: 2rem 0;'>", unsafe_allow_html=True)
            
            st.markdown('<div class="analysis-subtitle">Traffic Type Analysis</div>', unsafe_allow_html=True)
            if insights.get('traffic_type'):
                st.markdown(f'<p style="color: #374151; font-size: 0.95rem; line-height: 1.6;">{insights["traffic_type"]}</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p style="color: #6b7280; font-style: italic;">Insufficient data for traffic type analysis.</p>', unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown('<div class="analysis-subtitle">Seasonality Analysis</div>', unsafe_allow_html=True)
            if insights.get('seasonality'):
                st.markdown(f'<p style="color: #374151; font-size: 0.95rem; line-height: 1.6;">{insights["seasonality"]}</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p style="color: #6b7280; font-style: italic;">Insufficient data for seasonality analysis.</p>', unsafe_allow_html=True)
            
            # Full-width section for recommended actions below themes
            st.markdown("<hr style='border-color: #e5e7eb; margin: 2rem 0;'>", unsafe_allow_html=True)
            st.markdown('<div class="analysis-subtitle">Treatments to Consider</div>', unsafe_allow_html=True)
            if insights.get('recommendations'):
                recs_html = '<ul class="analysis-list">' + ''.join([f'<li>{r}</li>' for r in insights['recommendations']]) + '</ul>'
                st.markdown(recs_html, unsafe_allow_html=True)
            else:
                st.markdown('<p style="color: #6b7280; font-style: italic;">No specific recommendations available.</p>', unsafe_allow_html=True)

                    
        except Exception as e:
            st.error(f"Analysis unavailable: {e}")
            
    st.markdown('</div>', unsafe_allow_html=True)  # End analysis container
    
    # PDF Export Button
    st.markdown("<br>", unsafe_allow_html=True)
    col_pdf1, col_pdf2, col_pdf3 = st.columns([1, 1, 1])
    
    with col_pdf2:
        if st.button("📄 Save as PDF", use_container_width=True, type="primary"):
            try:
                from src.hotspot_pdf import generate_hotspot_pdf
                
                # Prepare data for PDF
                pdf_data = {
                    'hotspot_name': hotspot_name,
                    'location': location,
                    'urgency_score': urgency_score,
                    'priority': priority,
                    'event_type': event_type,
                    'reports': reports
                }
                
                # Generate PDF with map
                pdf_bytes = generate_hotspot_pdf(pdf_data, insights, lat=lat, lng=lng)
                
                # Offer download
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"hotspot_{hotspot_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                st.success("PDF generated successfully!")
                
            except Exception as e:
                st.error(f"Error generating PDF: {e}")
    
    st.markdown("<br><br>", unsafe_allow_html=True)

# ────────────────────────────────────────────────
# DATA LOADING AND PROCESSING
# ────────────────────────────────────────────────

def load_preprocessed_data():
    """Load Top 30 hotspots and Corridor data"""
    data_dir = Path("data/processed/tab1_hotspots")
    
    # Load Top 30 Hotspots (JSON)
    try:
        with open(data_dir / "lights-hotspots.json", 'r') as f:
            top_30_data = json.load(f)
        # Normalize nested JSON to flat DataFrame
        top_30_df = pd.json_normalize(top_30_data)
    except FileNotFoundError:
        st.error("lights-hotspots.json not found. Please check data directory.")
        top_30_df = pd.DataFrame()

    # Load corridor hotspots (P2)
    with open(data_dir / "perception_corridors_polys.geojson", 'r') as f:
        corridors_geojson = json.load(f)
    
    # Load abnormal events for heatmap
    abnormal_events_df = pd.read_csv(data_dir / "spinovate_abnormal_events.csv")
    
    # Parse timestamps
    abnormal_events_df['timestamp'] = pd.to_datetime(abnormal_events_df['timestamp'])
    
    # Convert corridors to DataFrame
    corridors_data = []
    for feature in corridors_geojson['features']:
        props = feature['properties']
        geom = feature['geometry']
        
        # Get centroid for marker placement
        coords = geom['coordinates'][0]
        lats = [coord[1] for coord in coords]
        lngs = [coord[0] for coord in coords]
        center_lat = sum(lats) / len(lats)
        center_lng = sum(lngs) / len(lngs)
        
        # Use avg_severity for scoring (0-100 scale)
        avg_severity = props.get('avg_severity', 0)
        
        # Convert to numeric if it's a string
        try:
            severity_score = float(avg_severity)
        except:
            severity_score = 0
        
        corridors_data.append({
            'road_name': props.get('road_name', 'Unknown'),
            'center_lat': center_lat,
            'center_lng': center_lng,
            'report_count': props.get('report_count', 0),
            'weighted_score': severity_score,  # Use avg_severity as the score
            'priority_rank': props.get('priority_rank', 999),
            'priority_category': props.get('priority_category', 'MEDIUM'),
            'dominant_category': props.get('dominant_category', 'Unknown'),
            'all_comments': props.get('all_comments', ''),
            'maxspeed': props.get('maxspeed', 'N/A'),
            'lanes': props.get('lanes', 'N/A'),
            'avg_severity': severity_score,  # Store original value as well
            'geometry': coords
        })
    
    corridor_df = pd.DataFrame(corridors_data)
    
    return top_30_df, corridor_df, abnormal_events_df

def select_top_hotspots(top_30_df, corridor_df, total_count=10):
    """
    Select top hotspots based on unified ranking:
    - Combine all sources
    - Normalize scores (0-100)
    - Sort by score and take top N
    """
    if top_30_df.empty and corridor_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 1. Prepare Top 30
    t30 = top_30_df.copy()
    if not t30.empty:
        t30['source'] = 'top_30'
        t30['source_label'] = 'Top 30 Priority'
        # Normalize score to 0-100
        t30['sorting_score'] = t30.get('scores.composite_score', 0) * 100
    
    # 2. Prepare Corridors
    corr = corridor_df.copy()
    if not corr.empty:
        corr['source'] = 'corridor'
        corr['source_label'] = 'Corridor Reports'
        # Use weighted_score directly for sorting
        corr['sorting_score'] = corr.get('weighted_score', 0)
        
    # 3. Combine and Sort
    combined = pd.concat([t30, corr], ignore_index=True)
    combined = combined.sort_values('sorting_score', ascending=False)
    
    # 4. Take Top N
    top_n = combined.head(total_count).copy()
    
    # 5. Assign Sequential IDs
    hotspot_ids = [f"Hotspot {i+1}" for i in range(len(top_n))]
    top_n['hotspot_name'] = hotspot_ids
    
    # 6. Split back for UI rendering
    top_30_selected = top_n[top_n['source'] == 'top_30'].copy()
    corridor_selected = top_n[top_n['source'] == 'corridor'].copy()
    
    return top_30_selected, corridor_selected

def get_color_by_score(score):
    """Get color based on score (0-100)"""
    if score >= 80:
        return '#DC2626'  # Red
    elif score >= 60:
        return '#F59E0B'  # Amber
    else:
        return '#3B82F6'  # Blue

def create_popup_html(row, source='top_30'):
    """Create simplified HTML popup content."""
    
    # Extract basic info
    if source == 'top_30':
        location = row.get('identification.street_name', 'Unknown Location')
        event_type = row.get('sensor_data.event_type', 'N/A')
        raw_score = row.get('scores.composite_score', 0)
        # Top 30 score is 0-1, convert to %
        try:
            score_val = float(raw_score) * 100
        except:
            score_val = 0
            
        lat = row.get('identification.latitude')
        lon = row.get('identification.longitude')
    else:
        # Corridor / Perception data
        location = row.get('road_name', 'Unknown Location')
        event_type = row.get('dominant_category', 'N/A')
        raw_score = row.get('weighted_score', 0)
        # Corridor score is already 0-100
        try:
            score_val = float(raw_score)
        except:
            score_val = 0
            
        lat = row.get('center_lat')
        lon = row.get('center_lng')
        
    # Format score display
    score_display = f"{score_val:.1f}%"

    # Street View Link
    street_view_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
    
    html = f"""
    <div style="font-family: sans-serif; min-width: 200px;">
        <h4 style="margin: 0 0 8px 0; color: #1f2937; font-size: 14px; font-weight: 600;">{location}</h4>
        
        <div style="margin-bottom: 4px;">
            <span style="color: #6b7280; font-size: 12px;">Event Type:</span>
            <span style="color: #111827; font-size: 12px; font-weight: 500;">{event_type}</span>
        </div>
        
        <div style="margin-bottom: 12px;">
            <span style="color: #6b7280; font-size: 12px;">Score:</span>
            <span style="color: #ef4444; font-size: 12px; font-weight: 600;">{score_display}</span>
        </div>
        
        <a href="{street_view_url}" target="_blank" 
           style="display: inline-block; background-color: #3b82f6; color: white; 
                  padding: 6px 12px; text-decoration: none; border-radius: 4px; 
                  font-size: 12px; font-weight: 500;">
            View Street View ↗
        </a>
    </div>
    """
    return html

def create_hotspot_map(top_30_selected, corridor_selected, 
                       abnormal_events_df=None, show_heatmap=False):
    """Create Folium map with all hotspots and optional heatmap"""
    
    # Initialize map centered on Dublin
    m = folium.Map(
        location=[53.3498, -6.2603],
        zoom_start=12,
        tiles='CartoDB positron'
    )
    
    # Add heatmap layer if enabled
    if show_heatmap and abnormal_events_df is not None:
        # Prepare heatmap data
        heat_data = [[row['lat'], row['lng'], row['max_severity']] 
                     for idx, row in abnormal_events_df.iterrows() 
                     if pd.notna(row['lat']) and pd.notna(row['lng'])]
        
        # Add heatmap
        HeatMap(
            heat_data,
            min_opacity=0.3,
            max_zoom=13,
            radius=15,
            blur=20,
            gradient={0.4: 'blue', 0.6: 'yellow', 0.8: 'orange', 1: 'red'}
        ).add_to(m)
    
    # Add JavaScript for dynamic scaling
    template = """
    {% macro script(this, kwargs) %}
    <script>
    console.log('[Dynamic Scaling] Script loaded!');
    
    // Store original styles
    var polygonStyles = {};
    var polylineStyles = {};
    var circleStyles = {};
    
    function updateAllScales() {
        console.log('[Dynamic Scaling] updateAllScales called');
        
        var map = {{this._parent.get_name()}};
        if (!map) {
            console.error('[Dynamic Scaling] Map not found!');
            return;
        }
        
        var zoom = map.getZoom();
        // AGGRESSIVE SCALING: Multiply by 2.0 instead of 0.5 for much bigger difference
        var scaleFactor = Math.pow(2, (12 - zoom)) * 2.0;
        console.log('[Dynamic Scaling] Zoom:', zoom, 'ScaleFactor:', scaleFactor);
        
        var polygonCount = 0;
        var polylineCount = 0;
        var circleCount = 0;
        
        // Update all polygons
        map.eachLayer(function(layer) {
            if (layer instanceof L.Polygon) {
                polygonCount++;
                
                if (!layer._scaleId) {
                    layer._scaleId = 'poly_' + Date.now() + Math.random();
                    polygonStyles[layer._scaleId] = {
                        weight: layer.options.weight || 3,
                        fillOpacity: layer.options.fillOpacity || 0.4,
                        opacity: layer.options.opacity || 0.8
                    };
                    console.log('[Dynamic Scaling] Stored polygon base:', polygonStyles[layer._scaleId]);
                }
                
                var base = polygonStyles[layer._scaleId];
                if (base) {
                    var newWeight = Math.max(1, base.weight * scaleFactor);
                    var newFillOpacity = Math.min(0.8, base.fillOpacity + (scaleFactor - 1) * 0.15);
                    var newOpacity = Math.min(1, base.opacity + (scaleFactor - 1) * 0.15);
                    
                    layer.setStyle({
                        weight: newWeight,
                        fillOpacity: newFillOpacity,
                        opacity: newOpacity
                    });
                    
                    if (polygonCount === 1) {
                        console.log('[Dynamic Scaling] Applied to polygon - weight:', newWeight, 'fillOpacity:', newFillOpacity);
                    }
                }
            }
            else if (layer instanceof L.Polyline) {
                polylineCount++;
                
                if (!layer._scaleId) {
                    layer._scaleId = 'line_' + Date.now() + Math.random();
                    polylineStyles[layer._scaleId] = {
                        weight: layer.options.weight || 5,
                        opacity: layer.options.opacity || 0.8
                    };
                }
                
                var base = polylineStyles[layer._scaleId];
                if (base) {
                    var newWeight = Math.max(2, base.weight * scaleFactor);
                    var newOpacity = Math.min(1, base.opacity + (scaleFactor - 1) * 0.15);
                    
                    layer.setStyle({
                        weight: newWeight,
                        opacity: newOpacity
                    });
                }
            }
            else if (layer instanceof L.CircleMarker) {
                circleCount++;
                
                if (!layer._scaleId) {
                    layer._scaleId = 'circle_' + Date.now() + Math.random();
                    circleStyles[layer._scaleId] = {
                        radius: layer.options.radius || 8
                    };
                }
                
                var base = circleStyles[layer._scaleId];
                if (base) {
                    var newRadius = Math.max(4, base.radius * scaleFactor);
                    layer.setRadius(newRadius);
                }
            }
        });
        
        console.log('[Dynamic Scaling] Processed - Polygons:', polygonCount, 'Polylines:', polylineCount, 'Circles:', circleCount);
    }
    
    // Initialize on map load
    {{this._parent.get_name()}}.whenReady(function() {
        console.log('[Dynamic Scaling] Map ready, initializing...');
        setTimeout(updateAllScales, 100);
    });
    
    // Update on zoom
    {{this._parent.get_name()}}.on('zoomend', function() {
        console.log('[Dynamic Scaling] Zoom ended, updating scales...');
        updateAllScales();
    });
    
    console.log('[Dynamic Scaling] Event listeners attached');
    </script>
    {% endmacro %}
    """
    
    # Add the JavaScript to the map
    macro = MacroElement()
    macro._template = Template(template)
    m.get_root().add_child(macro)
    
    # Add Top 30 hotspots
    for idx, row in top_30_selected.iterrows():
        color = get_color_by_score(row.get('scores.composite_score', 0) * 100)
        popup_html = create_popup_html(row, 'top_30')
        
        # Check for geometry (from corridor matching)
        has_geometry = False
        geom_type = row.get('corridor_data.geometry.geometry_type')
        coords = row.get('corridor_data.geometry.coordinates')
        
        if geom_type and isinstance(coords, list) and len(coords) > 0:
            has_geometry = True
            
            if geom_type == 'Polygon':
                # Polygon: [[[lon, lat], ...]]
                poly_coords = [(p[1], p[0]) for p in coords[0]]
                folium.Polygon(
                    locations=poly_coords,
                    popup=folium.Popup(popup_html, max_width=350),
                    tooltip=f"{row['identification.street_name']}",
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.4,
                    weight=3
                ).add_to(m)
                
            elif geom_type == 'LineString':
                # LineString: [[lon, lat], ...]
                line_coords = [(p[1], p[0]) for p in coords]
                folium.PolyLine(
                    locations=line_coords,
                    popup=folium.Popup(popup_html, max_width=350),
                    tooltip=f"{row['identification.street_name']}",
                    color=color,
                    weight=5,
                    opacity=0.8
                ).add_to(m)
                
            elif geom_type == 'MultiLineString':
                # MultiLineString: [[[lon, lat], ...], ...]
                for line in coords:
                    line_coords = [(p[1], p[0]) for p in line]
                    folium.PolyLine(
                        locations=line_coords,
                        popup=folium.Popup(popup_html, max_width=350),
                        tooltip=f"{row['identification.street_name']}",
                        color=color,
                        weight=5,
                        opacity=0.8
                    ).add_to(m)
        
        # Only add point marker if no geometry exists
        if not has_geometry:
            folium.CircleMarker(
                location=[row['identification.latitude'], row['identification.longitude']],
                radius=8,
                popup=folium.Popup(popup_html, max_width=350),
                tooltip=f"{row['identification.street_name']}",
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2
            ).add_to(m)
    
    # Add corridor hotspots (as polygons)
    for idx, row in corridor_selected.iterrows():
        color = get_color_by_score(row['weighted_score'])
        popup_html = create_popup_html(row, 'corridor')
        
        # Draw polygon
        coords_folium = [(coord[1], coord[0]) for coord in row['geometry']]
        
        folium.Polygon(
            locations=coords_folium,
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"{row['road_name']}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.4,
            weight=3
        ).add_to(m)
    
    return m

# ────────────────────────────────────────────────
# ENHANCED MAIN RENDER FUNCTION
# ────────────────────────────────────────────────

def render_tab1_enhanced():
    """Enhanced main function to render Tab 1 with professional styling"""
    
    # Initialize Session State
    if 'view_mode' not in st.session_state:
        st.session_state['view_mode'] = 'list'
    if 'selected_hotspot' not in st.session_state:
        st.session_state['selected_hotspot'] = None
        
    # Check View Mode
    if st.session_state['view_mode'] == 'detail':
        render_hotspot_details_page()
        return

    create_section_header("Hotspot Analysis", "Analysis combining Top 30 Priority Hotspots and Corridor Surveys")
    
    # Load data
    try:
        top_30_df, corridor_df, abnormal_events_df = load_preprocessed_data()
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return
    
    # Enhanced sidebar controls
    st.sidebar.markdown("---")
    st.sidebar.subheader("Tab 1: Hotspot Analysis Settings")
    
    # Hotspot count selector
    total_hotspots = st.sidebar.selectbox(
        "Number of hotspots to display",
        options=[10, 20, 30],
        index=0
    )
    
    # Heatmap toggle
    show_heatmap = st.sidebar.checkbox("Show Heatmap Layer", value=False)
    
    # Select top hotspots (70/30 split)
    top_30_selected, corridor_selected = select_top_hotspots(
        top_30_df, corridor_df, total_hotspots
    )
    
    # 1. Summary Panel
    render_summary_panel(top_30_selected, corridor_selected)
    
    # 2. Map Section
    create_section_header("Interactive Map", "Visual representation of safety hotspots across Dublin")
    
    if show_heatmap:
        st.info("Heatmap shows density and severity of all abnormal events")
    
    st.markdown('<div class="map-container">', unsafe_allow_html=True)
    with st.spinner("Loading enhanced map visualization..."):
        m = create_hotspot_map(
            top_30_selected, corridor_selected,
            abnormal_events_df, show_heatmap
        )
        folium_static(m, width=1200, height=600)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 3. Compact List Section
    st.markdown("---")
    create_section_header("Hotspot Action List", "Prioritized list of safety concerns requiring attention")
    
    render_compact_hotspot_list(top_30_selected, corridor_selected)

# For testing
if __name__ == "__main__":
    render_tab1_enhanced()
