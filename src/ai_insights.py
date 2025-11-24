"""
AI-powered hotspot insights using Google Gemini
"""
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


def generate_hotspot_insights(hotspot_data: dict, user_comments: list = None) -> dict:
    """
    Generate AI insights for a hotspot
    
    Args:
        hotspot_data: Dictionary containing hotspot metadata
        user_comments: List of user comment strings (optional)
    
    Returns:
        Dictionary with insights, themes, and summary
    """
    
    if not GOOGLE_API_KEY:
        return {
            'summary': 'AI insights unavailable - Google API key not configured',
            'themes': [],
            'recommendations': []
        }
    
    # Build prompt
    prompt = build_analysis_prompt(hotspot_data, user_comments)
    
    try:
        # Initialize model
        model = genai.GenerativeModel('gemini-2.0-flash-001')
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Parse response
        insights = parse_ai_response(response.text)
        
        return insights
        
    except Exception as e:
        return {
            'summary': f'Error generating insights: {str(e)}',
            'themes': [],
            'recommendations': []
        }


def build_analysis_prompt(hotspot_data: dict, user_comments: list = None) -> str:
    """Build structured prompt for AI analysis"""
    
    source = hotspot_data.get('source', 'unknown')
    
    prompt = f"""You are a road safety analyst. Analyze this hotspot and provide concise, actionable insights.

**Hotspot Data:**
- Location: {hotspot_data.get('street_name', hotspot_data.get('road_name', 'Unknown'))}
- Source: {source}
- Event Type: {hotspot_data.get('event_type', hotspot_data.get('dominant_category', 'N/A'))}
- Event Count: {hotspot_data.get('event_count', 0)}
- Device Count: {hotspot_data.get('device_count', 0)}
"""
    
    # Add severity metrics if available
    if 'median_severity' in hotspot_data or 'max_severity' in hotspot_data:
        prompt += "\n**Severity Metrics:**\n"
        if 'median_severity' in hotspot_data and hotspot_data.get('median_severity'):
            prompt += f"- Median Severity: {hotspot_data.get('median_severity'):.1f}/10\n"
        if 'p90_severity' in hotspot_data and hotspot_data.get('p90_severity'):
            prompt += f"- 90th Percentile Severity: {hotspot_data.get('p90_severity'):.1f}/10\n"
        if 'max_severity' in hotspot_data and hotspot_data.get('max_severity'):
            prompt += f"- Maximum Severity: {hotspot_data.get('max_severity')}/10\n"
    
    # Add temporal context if available
    if 'first_seen' in hotspot_data or 'last_seen' in hotspot_data:
        prompt += "\n**Temporal Context:**\n"
        if 'first_seen' in hotspot_data and hotspot_data.get('first_seen'):
            prompt += f"- First Reported: {hotspot_data.get('first_seen')}\n"
        if 'last_seen' in hotspot_data and hotspot_data.get('last_seen'):
            prompt += f"- Last Reported: {hotspot_data.get('last_seen')}\n"
        
        # Calculate duration if both dates available
        if 'first_seen' in hotspot_data and 'last_seen' in hotspot_data:
            try:
                from datetime import datetime
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
    
    # Add road characteristics for corridors
    if source == 'corridor':
        prompt += f"\n**Road Characteristics:**\n"
        prompt += f"- Priority Level: {hotspot_data.get('priority_category', 'N/A')}\n"
        prompt += f"- Speed Limit: {hotspot_data.get('maxspeed', 'N/A')}\n"
        prompt += f"- Number of Lanes: {hotspot_data.get('lanes', 'N/A')}\n"
    
    # Add user comments with emphasis
    if user_comments and len(user_comments) > 0:
        prompt += f"\n**CRITICAL - User Reports ({len(user_comments)} reports):**\n"
        prompt += "These are REAL experiences from cyclists/road users. Analyze these carefully for patterns, specific hazards, and recurring themes:\n\n"
        for i, comment in enumerate(user_comments[:10], 1):  # Include up to 10 comments
            prompt += f"{i}. \"{comment}\"\n"
        prompt += "\nPay special attention to:\n"
        prompt += "- Specific hazards mentioned (potholes, obstructions, close passes, etc.)\n"
        prompt += "- Time of day patterns if mentioned\n"
        prompt += "- Severity indicators (lost control, nearly fell, puncture, etc.)\n"
        prompt += "- Infrastructure issues (road surface, visibility, signage)\n"
        prompt += "- Behavioral issues (taxi drivers, traffic, etc.)\n"
    
    prompt += """
**Task:**
Based on ALL the information above, especially the user reports, provide your response in EXACTLY this format:

SUMMARY:
[5-6 sentences providing a comprehensive analysis. Focus on what the user comments reveal about this location. If multiple users report similar issues, emphasize this pattern. Mention severity levels and temporal aspects if available. Be specific about the actual hazards present.]

THEMES:
[Comma-separated list of 2-4 specific safety themes based primarily on user comments, e.g., "Severe pothole damage", "Poor road surface quality", "Cyclist-vehicle conflicts", "Visibility issues"]

RECOMMENDATIONS:
[2-3 bullet points with specific, actionable recommendations. If user comments mention specific problems, address those directly. Prioritize based on severity metrics if available.]

IMPORTANT:
- Start IMMEDIATELY with "SUMMARY:" - do not include any preamble, acknowledgments, or meta-commentary
- Do not say things like "I will analyze" or "Here is my analysis" - just provide the analysis 
- Use the actual details from user comments - don't be generic
- If users mention specific hazards (potholes, close passes, etc.), name them explicitly
- If temporal data shows this is a long-standing issue, mention it
- If severity metrics are high, emphasize the urgency
- Make recommendations specific to the actual problems reported"""
    
    return prompt


def parse_ai_response(response_text: str) -> dict:
    """Parse AI response into structured format"""
    
    insights = {
        'summary': '',
        'themes': [],
        'recommendations': []
    }
    
    try:
        # Split by sections
        sections = response_text.split('THEMES:')
        
        if len(sections) >= 2:
            # Extract summary
            summary_section = sections[0].replace('SUMMARY:', '').strip()
            insights['summary'] = summary_section
            
            # Extract themes and recommendations
            remaining = sections[1].split('RECOMMENDATIONS:')
            
            if len(remaining) >= 1:
                themes_text = remaining[0].strip()
                themes = [t.strip() for t in themes_text.split(',') if t.strip()]
                insights['themes'] = themes[:4]  # Limit to 4 themes
            
            if len(remaining) >= 2:
                recs_text = remaining[1].strip()
                # Split by bullet points or newlines
                recs = [r.strip('- •*').strip() for r in recs_text.split('\n') if r.strip() and r.strip() not in ['', '-', '•', '*']]
                insights['recommendations'] = recs[:3]  # Limit to 3 recommendations
        else:
            # Fallback if format not followed
            insights['summary'] = response_text[:500]
    
    except Exception as e:
        insights['summary'] = response_text[:500]  # Fallback to raw text
    
    return insights


def extract_user_comments(hotspot_data: dict) -> list:
    """Extract user comments from hotspot data"""
    
    comments = []
    source = hotspot_data.get('source', 'unknown')
    
    if source == 'corridor':
        # Corridor has all_comments field with pipe delimiter
        all_comments = hotspot_data.get('all_comments', '')
        if all_comments and all_comments != '':
            # Split by pipe (|)
            comment_list = all_comments.split('|')
            comments = [
                c.strip() 
                for c in comment_list 
                if c.strip() and c.strip().lower() != 'issue reported at this location'
            ]
    
    elif source == 'perception':
        # Perception hotspots have combined_text with semicolon delimiter
        combined_text = hotspot_data.get('combined_text', '')
        if combined_text and combined_text != '':
            # Split by semicolon (;)
            comment_list = combined_text.split(';')
            comments = [
                c.strip() 
                for c in comment_list 
                if c.strip() and c.strip().lower() != 'issue reported at this location'
            ]
    
    return comments

def generate_route_insights(route_data: dict) -> dict:
    """
    Generate AI insights for a route
    
    Args:
        route_data: Dictionary containing route metadata
    
    Returns:
        Dictionary with insights, themes, and summary
    """
    
    if not GOOGLE_API_KEY:
        return {
            'summary': 'AI insights unavailable - Google API key not configured',
            'themes': [],
            'recommendations': []
        }
    
    # Build prompt
    prompt = build_route_prompt(route_data)
    
    try:
        # Initialize model
        model = genai.GenerativeModel('gemini-2.0-flash-001')
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Parse response (reuse existing parser)
        insights = parse_ai_response(response.text)
        
        return insights
        
    except Exception as e:
        return {
            'summary': f'Error generating insights: {str(e)}',
            'themes': [],
            'recommendations': []
        }

def build_route_prompt(route_data: dict) -> str:
    """Build structured prompt for AI route analysis"""
    
    prompt = f"""You are a traffic flow and road safety analyst. Analyze this route and provide concise, actionable insights.

**Route Data:**
- Name: {route_data.get('street_name', 'Unknown')}
- Status: {'Improved Safety' if route_data.get('Colour') == 'Green' else 'High Risk' if route_data.get('Colour') == 'Red' else 'Neutral'}
- Peak Trips: {route_data.get('peak_trips', 'N/A')}
- Weather Impact: {route_data.get('weather_impact_note', 'N/A')}
- Existing Summary: {route_data.get('summary', 'N/A')}
"""

    # Add trend data if available
    if 'Trend' in route_data:
        prompt += f"- Trend Observation: {route_data.get('Trend')}\n"
    if 'Observation' in route_data:
        prompt += f"- General Observation: {route_data.get('Observation')}\n"
    if 'Possible Contributing Factors' in route_data:
        prompt += f"- Contributing Factors: {route_data.get('Possible Contributing Factors')}\n"

    prompt += """
**Task:**
Based on the data above, provide your response in EXACTLY this format:

SUMMARY:
[5-6 sentences providing a comprehensive analysis of the route's performance and safety status. Synthesize the existing observations into a professional narrative.]

THEMES:
[Comma-separated list of 2-4 specific themes, e.g., "High Commuter Volume", "Weather Sensitive", "Safety Improvement", "Infrastructure Deficit"]

RECOMMENDATIONS:
[2-3 bullet points with specific, actionable recommendations to improve or maintain the route.]

IMPORTANT:
- Start IMMEDIATELY with "SUMMARY:"
- Be professional and data-driven
"""
    return prompt