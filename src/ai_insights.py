"""
AI-powered insights using Google Gemini for hotspot and route analysis.

This module provides AI-generated safety analysis by:
1. Building structured prompts with sensor data and user reports
2. Calling Google Gemini API for analysis
3. Parsing responses into actionable insights
"""
import os
from datetime import datetime
from google import genai  # UPDATED: New package
from dotenv import load_dotenv

# Load environment variables and configure Gemini
load_dotenv()

# Try to get API key from environment first, then Streamlit secrets
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# If not in environment, try Streamlit secrets (for Cloud deployment)
if not GOOGLE_API_KEY:
    try:
        import streamlit as st
        # Try flat structure first
        GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
        # If not found, try nested under 'credentials'
        if not GOOGLE_API_KEY and "credentials" in st.secrets:
            GOOGLE_API_KEY = st.secrets["credentials"].get("GOOGLE_API_KEY")
    except:
        pass

# UPDATED: Initialize client instead of configure
if GOOGLE_API_KEY:
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
else:
    gemini_client = None

# Load Groq API key (fallback)
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    try:
        import streamlit as st
        # Try flat structure first
        GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
        # If not found, try nested under 'credentials'
        if not GROQ_API_KEY and "credentials" in st.secrets:
            GROQ_API_KEY = st.secrets["credentials"].get("GROQ_API_KEY")
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════
# HOTSPOT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def generate_hotspot_insights(hotspot_data: dict, user_comments: list = None) -> dict:
    """
    Generate AI insights for a hotspot location.
    Uses Gemini API with Groq (Llama 3.3 70B) as fallback.
    
    Args:
        hotspot_data: Hotspot metadata (event type, location, severity, etc.)
        user_comments: List of user-reported safety concerns (optional)
    
    Returns:
        dict: {'summary': str, 'themes': list, 'recommendations': list}
    """
    # Build prompt once (works for both APIs)
    prompt = build_analysis_prompt(hotspot_data, user_comments)
    
    # Try Gemini first
    if gemini_client:  # UPDATED: Check client instead of API key
        try:
            # UPDATED: New API call format
            response = gemini_client.models.generate_content(
                model='gemini-2.0-flash-exp-0827',
                contents=prompt
            )
            return parse_ai_response(response.text)
        except Exception as e:
            error_str = str(e)
            print(f"DEBUG: Gemini API failed: {error_str}")
            # If quota exceeded or any Gemini error, try Groq
            if "429" in error_str or "quota" in error_str.lower():
                print("DEBUG: Quota exceeded, trying Groq fallback...")
    
    # Try Groq as fallback (Llama 3.3 70B - very intelligent)
    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # Best model for intelligence
                messages=[
                    {"role": "system", "content": "You are a road safety analyst providing insights for city planners."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return parse_ai_response(response.choices[0].message.content)
        except Exception as e:
            print(f"DEBUG: Groq API also failed: {str(e)}")
            return {
                'summary': f'Error generating insights (both APIs failed): Gemini and Groq unavailable',
                'themes': [],
                'recommendations': []
            }
    
    # No API keys available
    if not gemini_client and not GROQ_API_KEY:  # UPDATED: Check client
        # Build diagnostic message
        diagnostics = []
        diagnostics.append("Checked: os.getenv('GOOGLE_API_KEY') = " + ("None" if not os.getenv('GOOGLE_API_KEY') else "Found"))
        diagnostics.append("Checked: os.getenv('GROQ_API_KEY') = " + ("None" if not os.getenv('GROQ_API_KEY') else "Found"))
        
        try:
            import streamlit as st
            diagnostics.append("st.secrets accessible: Yes")
            diagnostics.append("st.secrets keys: " + str(list(st.secrets.keys())))
            diagnostics.append("st.secrets.get('GOOGLE_API_KEY') = " + ("None" if not st.secrets.get('GOOGLE_API_KEY') else "Found"))
            diagnostics.append("st.secrets.get('GROQ_API_KEY') = " + ("None" if not st.secrets.get('GROQ_API_KEY') else "Found"))
        except Exception as e:
            diagnostics.append(f"st.secrets error: {str(e)}")
            
        return {
            'summary': 'AI insights unavailable - No API keys configured. DIAGNOSTICS: ' + ' | '.join(diagnostics),
            'themes': [],
            'recommendations': []
        }
    
    # Gemini failed and no Groq key
    return {
        'summary': 'AI insights unavailable - Gemini API failed and Groq not configured',
        'themes': [],
        'recommendations': []
    }


def build_analysis_prompt(hotspot_data: dict, user_comments: list = None) -> str:
    """Build structured prompt for hotspot AI analysis."""
    
    source = hotspot_data.get('source', 'unknown')
    
    # Extract location - handle both new and old formats
    location = (hotspot_data.get('street_name') or 
                hotspot_data.get('identification.street_name') or 
                hotspot_data.get('road_name') or 
                'Unknown')
    
    # Extract event type
    event_type = (hotspot_data.get('event_type') or 
                  hotspot_data.get('sensor_data.event_type') or 
                  hotspot_data.get('dominant_category') or 
                  'N/A')
    
    # Extract total events (new: total_events, old: size)
    total_events = (hotspot_data.get('total_events') or 
                    hotspot_data.get('sensor_data.size') or 
                    hotspot_data.get('event_count') or 
                    0)
    
    # Base hotspot information
    prompt = f"""You are a road safety analyst. Analyze this hotspot and provide concise, actionable insights.

**Hotspot Data:**
- Location: {location}
- Source: {source}
- Primary Event Type: {event_type}
- Total Sensor Events: {total_events}
"""
    
    # Add event breakdown if available (new data structure)
    # Try csv_data first (new format), then top-level (old format)
    csv_data = hotspot_data.get('csv_data', {})
    if not isinstance(csv_data, dict):
        csv_data = {}
    
    braking = (csv_data.get('braking_events') or 
               hotspot_data.get('csv_data.braking_events') or
               hotspot_data.get('braking_events') or
               hotspot_data.get('sensor_data.braking_events'))
    swerve = (csv_data.get('swerve_events') or 
              hotspot_data.get('csv_data.swerve_events') or
              hotspot_data.get('swerve_events') or
              hotspot_data.get('sensor_data.swerve_events'))
    roughness = (csv_data.get('roughness_events') or 
                 hotspot_data.get('csv_data.roughness_events') or
                 hotspot_data.get('roughness_events') or
                 hotspot_data.get('sensor_data.roughness_events'))
    
    # Convert to int if they're strings
    if braking and isinstance(braking, str):
        try: braking = int(braking)
        except: pass
    if swerve and isinstance(swerve, str):
        try: swerve = int(swerve)
        except: pass
    if roughness and isinstance(roughness, str):
        try: roughness = int(roughness)
        except: pass
    
    if braking or swerve or roughness:
        prompt += "\n**Event Breakdown:**\n"
        if braking:
            prompt += f"  - Harsh Braking: {braking}\n"
        if swerve:
            prompt += f"  - Swerves: {swerve}\n"
        if roughness:
            prompt += f"  - Road Roughness: {roughness}\n"
    
    # Add temporal data if available (weekday vs weekend)
    weekday_events = hotspot_data.get('weekday_events') or hotspot_data.get('temporal_data.weekday_events')
    weekend_events = hotspot_data.get('weekend_events') or hotspot_data.get('temporal_data.weekend_events')
    
    if weekday_events or weekend_events:
        prompt += "\n**Temporal Patterns:**\n"
        if weekday_events:
            prompt += f"  - Weekday Events: {weekday_events}\n"
        if weekend_events:
            prompt += f"  - Weekend Events: {weekend_events}\n"
    
    # Add peak/off-peak data
    peak_events = hotspot_data.get('peak_events') or hotspot_data.get('temporal_data.peak_events')
    offpeak_events = hotspot_data.get('offpeak_events') or hotspot_data.get('temporal_data.offpeak_events')
    
    if peak_events or offpeak_events:
        if not (weekday_events or weekend_events):
            prompt += "\n**Temporal Patterns:**\n"
        if peak_events:
            prompt += f"  - Peak Hours (7-10am, 4-7pm): {peak_events}\n"
        if offpeak_events:
            prompt += f"  - Off-Peak Hours: {offpeak_events}\n"
    
    # Add seasonal data if available
    monthly_data = hotspot_data.get('monthly_distribution') or hotspot_data.get('temporal_data.monthly_distribution')
    if monthly_data and isinstance(monthly_data, dict):
        prompt += "\n**Monthly Distribution:**\n"
        for month, count in sorted(monthly_data.items()):
            prompt += f"  - {month}: {count}\n"
    
    # Add weather data if available
    avg_temp = hotspot_data.get('avg_temp') or hotspot_data.get('weather_data.avg_temp')
    avg_rainfall = hotspot_data.get('avg_rainfall') or hotspot_data.get('weather_data.avg_rainfall')
    
    if avg_temp or avg_rainfall:
        prompt += "\n**Weather Conditions:**\n"
        if avg_temp:
            prompt += f"  - Average Temperature: {avg_temp:.1f}°C\n"
        if avg_rainfall:
            prompt += f"  - Average Rainfall: {avg_rainfall:.1f}mm\n"
    
    # Add user comments if provided
    if user_comments:
        # Filter out generic placeholder comments
        meaningful_comments = [
            c for c in user_comments 
            if c.lower() not in ['issue reported at this location', 'n/a', '']
        ]
        
        if meaningful_comments:
            prompt += "\n**User-Reported Safety Concerns:**\n"
            for i, comment in enumerate(meaningful_comments[:10], 1):  # Limit to 10 comments
                prompt += f"{i}. {comment}\n"
    
    # Add severity if available
    severity = hotspot_data.get('severity_label') or hotspot_data.get('identification.severity_label')
    if severity:
        prompt += f"\n**Risk Level:** {severity}\n"
    
    # Add accident data if available
    total_accidents = hotspot_data.get('total_accidents') or hotspot_data.get('accident_data.total_accidents')
    if total_accidents:
        prompt += f"\n**Historical Accidents:** {total_accidents} reported incidents\n"
        
        # Add injury breakdown if available
        fatal = hotspot_data.get('fatal_injuries') or hotspot_data.get('accident_data.fatal_injuries')
        serious = hotspot_data.get('serious_injuries') or hotspot_data.get('accident_data.serious_injuries')
        slight = hotspot_data.get('slight_injuries') or hotspot_data.get('accident_data.slight_injuries')
        
        if fatal or serious or slight:
            prompt += "**Injury Breakdown:**\n"
            if fatal:
                prompt += f"  - Fatal: {fatal}\n"
            if serious:
                prompt += f"  - Serious: {serious}\n"
            if slight:
                prompt += f"  - Slight: {slight}\n"
    
    # Add analysis instructions
    prompt += """

**Task:**
Based on the data above, provide your response in EXACTLY this format:

SUMMARY:
[5-6 sentences providing a comprehensive analysis of the hotspot's safety issues and their severity. Synthesize sensor data, user reports, and accident statistics into a professional narrative. If user comments highlight specific concerns (e.g., "aggressive drivers", "poor road surface"), reference these insights in your summary to show we're listening to community feedback.]

THEMES:
[Comma-separated list of 2-4 specific themes that capture the core issues, e.g., "Aggressive Driving Behavior", "Infrastructure Deficit", "Poor Road Surface Quality", "High Pedestrian Risk"]

TRAFFIC TYPE:
[2-3 sentences describing traffic patterns based STRICTLY on temporal data provided above. Use phrases like "Predominantly weekday commuter traffic" or "Evening peak concentrated" or "Balanced weekday/weekend usage". Focus on peak/offpeak ratios and weekday/weekend splits. Keep this data-driven and concise.]

SEASONALITY:
[2-3 sentences analyzing seasonal patterns from the monthly distribution data above. Consider Irish weather patterns and cycling seasonality when interpreting the data. Use your knowledge to explain why certain months might be higher/lower (e.g., "May peak aligns with favorable cycling weather" or "Winter months show reduced activity due to shorter daylight hours"). Keep this insightful but concise.]

POSSIBLE MITIGATION ACTIONS:
[2-3 bullet points with specific, advisory actions. Use soft, non-prescriptive language like "Consider...", "Potential options include...", "It may be beneficial to...". Avoid direct commands like "Fix this" or "Install that". Draw upon global best practices and reference successful interventions from similar contexts.]

IMPORTANT:
- Start IMMEDIATELY with "SUMMARY:"
- Be professional and data-driven
- Use short, sharp sentences that get to the point
- DO NOT use phrases like "One user said..." or "According to reports..."
- Instead, synthesize patterns: "Reports indicate...", "The data suggests...", "Common experiences include..."
- Let the data tell the story naturally - don't force connections
- If temporal patterns are significant (peak hours, seasonal), weave them into the narrative
- If injuries are severe, convey the seriousness professionally without being alarmist
- Think like a consultant writing an executive summary, not a journalist quoting sources
- **CRITICAL: NEVER mention "lack of sensor data" or "insufficient data". Work with whatever data is available (especially user comments) and provide analysis based on that. If sensor data is missing, focus on user reports and your broader knowledge without calling out the absence.**
- For Traffic Type: STRICTLY use only temporal data - peak/offpeak, weekday/weekend, morning/evening ratios. Keep to 2-3 lines maximum. If temporal data is unavailable, make reasonable inferences based on location context and user comments.
- For Seasonality: Use your knowledge of Irish weather and cycling patterns to interpret the monthly data. If monthly data is unavailable, provide general insights based on location context without mentioning data limitations.
- For Recommendations: Draw upon global best practices and similar successful interventions
- Feel free to reference Dublin-specific context (e.g., "typical of Dublin's commuter corridors") where relevant"""

    
    return prompt



def parse_ai_response(response_text: str) -> dict:
    """Parse AI response into structured insights dictionary."""
    
    insights = {
        'summary': '',
        'themes': [],
        'traffic_type': '',
        'seasonality': '',
        'recommendations': []
    }
    
    try:
        # Split response by section markers
        sections = response_text.split('THEMES:')
        
        if len(sections) >= 2:
            # Extract summary
            insights['summary'] = sections[0].replace('SUMMARY:', '').strip()
            
            # Extract remaining sections
            remaining = sections[1].split('TRAFFIC TYPE:')
            
            if len(remaining) >= 1:
                themes_text = remaining[0].strip()
                themes = [t.strip() for t in themes_text.split(',') if t.strip()]
                insights['themes'] = themes[:4]  # Limit to 4 themes
            
            if len(remaining) >= 2:
                # Split traffic type and seasonality
                traffic_sections = remaining[1].split('SEASONALITY:')
                
                if len(traffic_sections) >= 1:
                    insights['traffic_type'] = traffic_sections[0].strip()
                
                if len(traffic_sections) >= 2:
                    # Split seasonality and recommendations
                    season_sections = traffic_sections[1].split('POSSIBLE MITIGATION ACTIONS:')
                    
                    if len(season_sections) >= 1:
                        insights['seasonality'] = season_sections[0].strip()
                    
                    if len(season_sections) >= 2:
                        recs_text = season_sections[1].strip()
                        # Split by bullet points or newlines
                        recs = [r.strip('- •*').strip() for r in recs_text.split('\n') 
                               if r.strip() and r.strip() not in ['', '-', '•', '*']]
                        insights['recommendations'] = recs[:3]  # Limit to 3 recommendations
        else:
            # Fallback: use raw text if format not followed
            insights['summary'] = response_text[:500]
    
    except Exception:
        # Fallback on parsing error
        insights['summary'] = response_text[:500]
    
    return insights



def extract_user_comments(hotspot_data: dict) -> list:
    """
    Extract user comments from hotspot data based on source type.
    
    Different data sources use different comment delimiters:
    - Corridor: pipe-separated (|)
    - Perception: semicolon-separated (;)
    """
    comments = []
    source = hotspot_data.get('source', 'unknown')
    
    if source == 'corridor':
        # Corridor data uses pipe delimiter
        all_comments = hotspot_data.get('all_comments', '')
        if all_comments:
            comment_list = all_comments.split('|')
            comments = [
                c.strip() 
                for c in comment_list 
                if c.strip() and c.strip().lower() != 'issue reported at this location'
            ]
    
    elif source == 'perception':
        # Perception data uses semicolon delimiter
        combined_text = hotspot_data.get('combined_text', '')
        if combined_text:
            comment_list = combined_text.split(';')
            comments = [
                c.strip() 
                for c in comment_list 
                if c.strip() and c.strip().lower() != 'issue reported at this location'
            ]
    
    return comments

# ═══════════════════════════════════════════════════════════════════════════
# ROUTE ANALYSIS (Tab 2)
# ═══════════════════════════════════════════════════════════════════════════

# def generate_route_insights(route_data: dict) -> dict:
#     """
#     Generate AI insights for a route (used in Tab 2).
    
#     Args:
#         route_data: Route metadata (popularity, trends, weather impact, etc.)
    
#     Returns:
#         dict: {'summary': str, 'themes': list, 'recommendations': list}
#     """
#     if not gemini_client:  # UPDATED: Check client instead of API key
#         return {
#             'summary': 'AI insights unavailable - Google API key not configured',
#             'themes': [],
#             'recommendations': []
#         }
    
#     try:
#         # Build prompt and generate insights
#         prompt = build_route_prompt(route_data)
#         
#         # UPDATED: New API call format
#         response = gemini_client.models.generate_content(
#             model='gemini-2.0-flash-exp-0827',
#             contents=prompt
#         )
        
#         # Reuse hotspot parser (same format)
#         return parse_ai_response(response.text)
        
#     except Exception as e:
#         return {
#             'summary': f'Error generating insights: {str(e)}',
#             'themes': [],
#             'recommendations': []
#         }


# def build_route_prompt(route_data: dict) -> str:
#     """Build structured prompt for route AI analysis."""
    
#     # Determine route status from color
#     status = 'Neutral'
#     if route_data.get('Colour') == 'Green':
#         status = 'Improved Safety'
#     elif route_data.get('Colour') == 'Red':
#         status = 'High Risk'
    
#     prompt = f"""You are a traffic flow and road safety analyst. Analyze this route and provide concise, actionable insights.

# **Route Data:**
# - Name: {route_data.get('street_name', 'Unknown')}
# - Status: {status}
# - Peak Trips: {route_data.get('peak_trips', 'N/A')}
# - Weather Impact: {route_data.get('weather_impact_note', 'N/A')}
# - Existing Summary: {route_data.get('summary', 'N/A')}
# """

#     # Add optional trend data
#     if 'Trend' in route_data:
#         prompt += f"- Trend Observation: {route_data.get('Trend')}\n"
#     if 'Observation' in route_data:
#         prompt += f"- General Observation: {route_data.get('Observation')}\n"
#     if 'Possible Contributing Factors' in route_data:
#         prompt += f"- Contributing Factors: {route_data.get('Possible Contributing Factors')}\n"

#     prompt += """
# **Task:**
# Based on the data above, provide your response in EXACTLY this format:

# SUMMARY:
# [5-6 sentences providing a comprehensive analysis of the route's performance and safety status. Synthesize the existing observations into a professional narrative.]

# THEMES:
# [Comma-separated list of 2-4 specific themes, e.g., "High Commuter Volume", "Weather Sensitive", "Safety Improvement", "Infrastructure Deficit"]

# POSSIBLE MITIGATION ACTIONS:
# [2-3 bullet points with specific, advisory actions. Use soft, non-prescriptive language like "Consider...", "Potential options include...", "It may be beneficial to...". Avoid direct commands like "Fix this" or "Install that".]

# IMPORTANT:
# - Start IMMEDIATELY with "SUMMARY:"
# - Be professional and data-driven
# """
#     return prompt