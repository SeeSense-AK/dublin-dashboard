"""
AI-powered insights using Google Gemini for hotspot and route analysis.

This module provides AI-generated safety analysis by:
1. Building structured prompts with sensor data and user reports
2. Calling Google Gemini API for analysis
3. Parsing responses into actionable insights
"""
import os
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables and configure Gemini
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# ═══════════════════════════════════════════════════════════════════════════
# HOTSPOT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def generate_hotspot_insights(hotspot_data: dict, user_comments: list = None) -> dict:
    """
    Generate AI insights for a hotspot location.
    
    Args:
        hotspot_data: Hotspot metadata (event type, location, severity, etc.)
        user_comments: List of user-reported safety concerns (optional)
    
    Returns:
        dict: {'summary': str, 'themes': list, 'recommendations': list}
    """
    if not GOOGLE_API_KEY:
        return {
            'summary': 'AI insights unavailable - Google API key not configured',
            'themes': [],
            'recommendations': []
        }
    
    try:
        # Build prompt and generate insights
        prompt = build_analysis_prompt(hotspot_data, user_comments)
        model = genai.GenerativeModel('gemini-2.0-flash-001')
        response = model.generate_content(prompt)
        
        return parse_ai_response(response.text)
        
    except Exception as e:
        return {
            'summary': f'Error generating insights: {str(e)}',
            'themes': [],
            'recommendations': []
        }


def build_analysis_prompt(hotspot_data: dict, user_comments: list = None) -> str:
    """Build structured prompt for hotspot AI analysis."""
    
    source = hotspot_data.get('source', 'unknown')
    
    # Extract event type - handle both flattened (Top 30) and direct (Corridor) keys
    event_type = (hotspot_data.get('sensor_data.event_type') or 
                  hotspot_data.get('event_type') or 
                  hotspot_data.get('dominant_category') or 
                  'N/A')
    
    # Extract event count - handle both flattened and direct keys
    event_count = (hotspot_data.get('sensor_data.event_count') or 
                   hotspot_data.get('event_count') or 
                   0)
    
    # Extract device count
    device_count = (hotspot_data.get('sensor_data.device_count') or 
                    hotspot_data.get('device_count') or 
                    0)
    
    # Extract location - handle both flattened and direct keys
    location = (hotspot_data.get('identification.street_name') or 
                hotspot_data.get('street_name') or 
                hotspot_data.get('road_name') or 
                'Unknown')
    
    # Base hotspot information
    prompt = f"""You are a road safety analyst. Analyze this hotspot and provide concise, actionable insights.

**Hotspot Data:**
- Location: {location}
- Source: {source}
- Event Type: {event_type}
- Event Count: {event_count}
- Device Count: {device_count}
"""
    
    # Add severity metrics if available
    if 'median_severity' in hotspot_data or 'max_severity' in hotspot_data:
        prompt += "\n**Severity Metrics:**\n"
        if hotspot_data.get('median_severity'):
            prompt += f"- Median Severity: {hotspot_data.get('median_severity'):.1f}/10\n"
        if hotspot_data.get('p90_severity'):
            prompt += f"- 90th Percentile Severity: {hotspot_data.get('p90_severity'):.1f}/10\n"
        if hotspot_data.get('max_severity'):
            prompt += f"- Maximum Severity: {hotspot_data.get('max_severity')}/10\n"
    
    # Add temporal context and calculate duration
    if 'first_seen' in hotspot_data or 'last_seen' in hotspot_data:
        prompt += "\n**Temporal Context:**\n"
        if hotspot_data.get('first_seen'):
            prompt += f"- First Reported: {hotspot_data.get('first_seen')}\n"
        if hotspot_data.get('last_seen'):
            prompt += f"- Last Reported: {hotspot_data.get('last_seen')}\n"
        
        # Calculate persistence duration
        if hotspot_data.get('first_seen') and hotspot_data.get('last_seen'):
            try:
                first = hotspot_data.get('first_seen')
                last = hotspot_data.get('last_seen')
                if isinstance(first, str):
                    first = datetime.fromisoformat(first.replace('Z', '+00:00'))
                if isinstance(last, str):
                    last = datetime.fromisoformat(last.replace('Z', '+00:00'))
                duration_days = (last - first).days
                if duration_days > 0:
                    prompt += f"- Duration: {duration_days} days (persistent issue)\n"
            except:
                pass
    
    # Add corridor-specific road characteristics
    if source == 'corridor':
        prompt += f"\n**Road Characteristics:**\n"
        prompt += f"- Priority Level: {hotspot_data.get('priority_category', 'N/A')}\n"
        prompt += f"- Speed Limit: {hotspot_data.get('maxspeed', 'N/A')}\n"
        prompt += f"- Number of Lanes: {hotspot_data.get('lanes', 'N/A')}\n"
    
    # Add user comments with analysis guidelines
    if user_comments and len(user_comments) > 0:
        prompt += f"\n**CRITICAL - User Reports ({len(user_comments)} reports):**\n"
        prompt += "These are REAL experiences from cyclists/road users. Analyze these carefully for patterns, specific hazards, and recurring themes:\n\n"
        for i, comment in enumerate(user_comments[:10], 1):  # Limit to 10 for API efficiency
            prompt += f"{i}. \"{comment}\"\n"
        prompt += "\nPay special attention to:\n"
        prompt += "- Specific hazards mentioned (road roughness, obstructions, close passes, etc.)\n"
        prompt += "- Time of day patterns if mentioned\n"
        prompt += "- Severity indicators (lost control, nearly fell, puncture, etc.)\n"
        prompt += "- Infrastructure issues (road surface, visibility, signage)\n"
        prompt += "- Behavioral issues (taxi drivers, traffic, etc.)\n"
    
    # Add analysis instructions
    prompt += """
**Task:**
Synthesize the available data to explain the safety situation.
CRITICAL: You must explicitly link the 'Event Type' (e.g., Braking, Swerving) with the specific details found in the 'User Reports'.
- Explain WHY the sensors are detecting these events based on what users are saying.
- Example: "The high number of Braking events is likely attributed to the severe road roughness reported by cyclists."

Based on this synthesis, provide your response in EXACTLY this format:

SUMMARY:
[5-6 sentences. Start by explicitly connecting the Event Type to the User Reports. Then expand on the specific hazards, severity, and patterns. Be specific.]

THEMES:
[Comma-separated list of 2-4 specific safety themes based primarily on user comments, e.g., "Severe road roughness", "Poor road surface quality", "Cyclist-vehicle conflicts", "Visibility issues"]

POSSIBLE MITIGATION ACTIONS:
[2-3 bullet points with specific, advisory actions. Use soft, non-prescriptive language like "Consider...", "Potential options include...", "It may be beneficial to...". Avoid direct commands like "Fix this" or "Install that".]

IMPORTANT:
- Start IMMEDIATELY with "SUMMARY:" - do not include any preamble, acknowledgments, or meta-commentary
- Do not say things like "I will analyze" or "Here is my analysis" - just provide the analysis 
- Use the actual details from user comments - don't be generic
- Always explain the "Why" behind the event type using user feedback
- If users mention specific hazards (road roughness, close passes, etc.), name them explicitly
- If temporal data shows this is a long-standing issue, mention it
- If severity metrics are high, emphasize the urgency
- Position yourself as an advisor providing options, not an authority giving orders"""
    
    return prompt


def parse_ai_response(response_text: str) -> dict:
    """Parse AI response into structured insights dictionary."""
    
    insights = {
        'summary': '',
        'themes': [],
        'recommendations': []
    }
    
    try:
        # Split response by section markers
        sections = response_text.split('THEMES:')
        
        if len(sections) >= 2:
            # Extract summary
            insights['summary'] = sections[0].replace('SUMMARY:', '').strip()
            
            # Extract themes and recommendations
            remaining = sections[1].split('POSSIBLE MITIGATION ACTIONS:')
            
            if len(remaining) >= 1:
                themes_text = remaining[0].strip()
                themes = [t.strip() for t in themes_text.split(',') if t.strip()]
                insights['themes'] = themes[:4]  # Limit to 4 themes
            
            if len(remaining) >= 2:
                recs_text = remaining[1].strip()
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
#     if not GOOGLE_API_KEY:
#         return {
#             'summary': 'AI insights unavailable - Google API key not configured',
#             'themes': [],
#             'recommendations': []
#         }
    
#     try:
#         # Build prompt and generate insights
#         prompt = build_route_prompt(route_data)
#         model = genai.GenerativeModel('gemini-2.0-flash-001')
#         response = model.generate_content(prompt)
        
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