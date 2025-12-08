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

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

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
    if GOOGLE_API_KEY:
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-001')
            response = model.generate_content(prompt)
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
    if not GOOGLE_API_KEY and not GROQ_API_KEY:
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
    
    if braking is not None or swerve is not None or roughness is not None:
        prompt += "\n**Event Breakdown:**\n"
        if braking is not None:
            prompt += f"- Braking Events: {braking}\n"
        if swerve is not None:
            prompt += f"- Swerve Events: {swerve}\n"
        if roughness is not None:
            prompt += f"- Roughness Events: {roughness}\n"
    
    # Add temporal patterns (new data structure - check csv_data)
    peak = (csv_data.get('peak_events') or 
            hotspot_data.get('csv_data.peak_events') or 
            hotspot_data.get('peak_events'))
            
    offpeak = (csv_data.get('offpeak_events') or 
               hotspot_data.get('csv_data.offpeak_events') or 
               hotspot_data.get('offpeak_events'))
               
    weekday = (csv_data.get('weekday_events') or 
               hotspot_data.get('csv_data.weekday_events') or 
               hotspot_data.get('weekday_events'))
               
    weekend = (csv_data.get('weekend_events') or 
               hotspot_data.get('csv_data.weekend_events') or 
               hotspot_data.get('weekend_events'))
               
    morning_peak = (csv_data.get('morning_peak') or 
                    hotspot_data.get('csv_data.morning_peak') or 
                    hotspot_data.get('morning_peak'))
                    
    evening_peak = (csv_data.get('evening_peak') or 
                    hotspot_data.get('csv_data.evening_peak') or 
                    hotspot_data.get('evening_peak'))
    
    # Convert to int if they're strings
    for var_name, var_val in [('peak', peak), ('offpeak', offpeak), ('weekday', weekday), 
                             ('weekend', weekend), ('morning_peak', morning_peak), 
                             ('evening_peak', evening_peak)]:
        if var_val and isinstance(var_val, str):
            try:
                if var_name == 'peak': peak = int(var_val)
                elif var_name == 'offpeak': offpeak = int(var_val)
                elif var_name == 'weekday': weekday = int(var_val)
                elif var_name == 'weekend': weekend = int(var_val)
                elif var_name == 'morning_peak': morning_peak = int(var_val)
                elif var_name == 'evening_peak': evening_peak = int(var_val)
            except: pass
    
    if any([peak, offpeak, weekday, weekend, morning_peak, evening_peak]):
        prompt += "\n**Temporal Patterns:**\n"
        if peak is not None and offpeak is not None:
            prompt += f"- Peak Hours: {peak} events, Off-Peak: {offpeak} events\n"
        if weekday is not None and weekend is not None:
            prompt += f"- Weekdays: {weekday} events, Weekends: {weekend} events\n"
        if morning_peak is not None:
            prompt += f"- Morning Peak (7-9am): {morning_peak} events\n"
        if evening_peak is not None:
            prompt += f"- Evening Peak (5-7pm): {evening_peak} events\n"
    
    # Add monthly distribution if available (check csv_data with correct field names)
    monthly_keys = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                    'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    monthly_data = {}
    
    # Try csv_data first (both dict and flattened keys)
    for key in monthly_keys:
        val = csv_data.get(key)
        if val is None:
            val = hotspot_data.get(f'csv_data.{key}')
            
        if val is not None:
            # Convert to int if string
            try:
                monthly_data[key] = int(val) if isinstance(val, str) else val
            except:
                monthly_data[key] = val
    
    # Fallback to old format with _events suffix
    if not monthly_data:
        old_monthly_keys = ['jan_events', 'feb_events', 'mar_events', 'apr_events', 
                           'may_events', 'jun_events', 'jul_events', 'aug_events', 
                           'sep_events', 'oct_events', 'nov_events', 'dec_events']
        for key in old_monthly_keys:
            val = hotspot_data.get(key)
            if val is not None:
                monthly_data[key] = val
    
    if monthly_data:
        prompt += "\n**Monthly Distribution:**\n"
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        for i, (key, value) in enumerate(monthly_data.items()):
            if i < len(month_names):
                prompt += f"- {month_names[i]}: {value} events\n"
    
    # Add collision data (new structure)
    total_collisions = hotspot_data.get('total_collisions')
    near_miss = hotspot_data.get('near_miss')
    collision_count = hotspot_data.get('collision')
    hazard_count = hotspot_data.get('hazard')
    
    if total_collisions is not None or any([near_miss, collision_count, hazard_count]):
        prompt += "\n**Collision Reports:**\n"
        if total_collisions is not None:
            prompt += f"- Total Reports: {total_collisions}\n"
        if near_miss is not None:
            prompt += f"- Near Misses: {near_miss}\n"
        if collision_count is not None:
            prompt += f"- Actual Collisions: {collision_count}\n"
        if hazard_count is not None:
            prompt += f"- Hazard Reports: {hazard_count}\n"
    
    # Add injury outcomes (new structure)
    no_injuries = hotspot_data.get('no_injuries')
    minor_injuries = hotspot_data.get('minor_injuries')
    serious_injuries = hotspot_data.get('serious_injuries')
    fatalities = hotspot_data.get('fatalities')
    
    if any([no_injuries, minor_injuries, serious_injuries, fatalities]):
        prompt += "\n**Injury Outcomes:**\n"
        if no_injuries is not None:
            prompt += f"- No Injuries: {no_injuries}\n"
        if minor_injuries is not None:
            prompt += f"- Minor Injuries: {minor_injuries}\n"
        if serious_injuries is not None:
            prompt += f"- Serious Injuries: {serious_injuries}\n"
        if fatalities is not None:
            prompt += f"- Fatalities: {fatalities}\n"
    
    # Add old severity metrics if available (for backwards compatibility)
    if 'median_severity' in hotspot_data or 'max_severity' in hotspot_data:
        prompt += "\n**Severity Metrics:**\n"
        if hotspot_data.get('median_severity'):
            prompt += f"- Median Severity: {hotspot_data.get('median_severity'):.1f}/10\n"
        if hotspot_data.get('p90_severity'):
            prompt += f"- 90th Percentile Severity: {hotspot_data.get('p90_severity'):.1f}/10\n"
        if hotspot_data.get('max_severity'):
            prompt += f"- Maximum Severity: {hotspot_data.get('max_severity')}/10\n"
    
    # Add sample descriptions (new data structure - replaces user_comments)
    sample_descriptions = hotspot_data.get('sample_descriptions', [])
    if sample_descriptions and isinstance(sample_descriptions, list) and len(sample_descriptions) > 0:
        prompt += f"\n**CRITICAL - User Reports ({len(sample_descriptions)} reports):**\n"
        prompt += "These are REAL experiences from cyclists/road users. Analyze these carefully for patterns, specific hazards, and recurring themes:\n\n"
        for i, desc in enumerate(sample_descriptions[:10], 1):  # Limit to 10 for API efficiency
            prompt += f"{i}. \"{desc}\"\n"
        prompt += "\nPay special attention to:\n"
        prompt += "- Specific hazards mentioned (road roughness, obstructions, close passes, etc.)\n"
        prompt += "- Time of day patterns if mentioned\n"
        prompt += "- Severity indicators (lost control, nearly fell, puncture, etc.)\n"
        prompt += "- Infrastructure issues (road surface, visibility, signage)\n"
        prompt += "- Behavioral issues (taxi drivers, traffic, etc.)\n"
    # Fallback to old user_comments format if sample_descriptions not available
    elif user_comments and len(user_comments) > 0:
        prompt += f"\n**CRITICAL - User Reports ({len(user_comments)} reports):**\n"
        prompt += "These are REAL experiences from cyclists/road users. Analyze these carefully for patterns, specific hazards, and recurring themes:\n\n"
        for i, comment in enumerate(user_comments[:10], 1):
            prompt += f"{i}. \"{comment}\"\n"
        prompt += "\nPay special attention to:\n"
        prompt += "- Specific hazards mentioned (road roughness, obstructions, close passes, etc.)\n"
        prompt += "- Time of day patterns if mentioned\n"
        prompt += "- Severity indicators (lost control, nearly fell, puncture, etc.)\n"
        prompt += "- Infrastructure issues (road surface, visibility, signage)\n"
        prompt += "- Behavioral issues (taxi drivers, traffic, etc.)\n"
    
    # Add temporal context and calculate duration (old format)
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
    
    # Add corridor-specific road characteristics (old format)
    if source == 'corridor':
        prompt += f"\n**Road Characteristics:**\n"
        prompt += f"- Priority Level: {hotspot_data.get('priority_category', 'N/A')}\n"
        prompt += f"- Speed Limit: {hotspot_data.get('maxspeed', 'N/A')}\n"
        prompt += f"- Number of Lanes: {hotspot_data.get('lanes', 'N/A')}\n"
    
    # Add analysis instructions
    prompt += """
**Task:**
You are a road safety expert providing analysis to city planners in Dublin, Ireland. Synthesize ALL available data (sensor events, temporal patterns, collision reports, injury outcomes, and user experiences) into a cohesive safety assessment.

You have access to your full knowledge base - feel free to draw upon:
- Your understanding of Dublin's road network and cycling infrastructure
- General traffic engineering principles and safety best practices
- Seasonal weather patterns in Ireland and their impact on cycling
- Common urban mobility patterns in European cities
- Relevant research on road safety interventions

Your analysis should:
- **CRITICAL: Analyze the Location Name for context.** (e.g., "Business Park" implies office commuters, "School Rd" implies school traffic, "Main St" implies retail/mixed use). Use this to ground your analysis.
- Provide a holistic understanding of what's happening at this location
- Identify patterns across sensor data, time periods, and reported incidents
- Explain the underlying safety issues without forcing artificial connections
- Be data-driven yet readable and professional
- Avoid quoting individual comments - instead, synthesize common themes
- Focus on the overall safety picture, not individual anecdotes
- Use your broader knowledge to provide context and insights beyond just the raw data

Provide your response in EXACTLY this format:

SUMMARY:
[Write 5-6 sentences that tell the complete story of this hotspot. Integrate sensor data patterns, temporal trends, collision statistics, and injury outcomes naturally. If user reports reveal common themes, weave them in organically. 

CRITICAL: Do not limit yourself to just the provided data. Use your broader knowledge of:
- Dublin's specific road network and infrastructure challenges
- General traffic engineering principles and safety standards
- Similar safety patterns observed in other European cities
- The impact of urban design on cyclist behavior

Synthesize the dashboard data with this broader context to explain 'why' these issues are happening and 'what it means' for the city. Make it flow like a professional safety assessment report.]

THEMES:
[Comma-separated list of 2-4 specific safety issues identified from the data, e.g., "Infrastructure deficiencies", "Peak hour congestion conflicts", "Surface quality concerns", "Visibility challenges"]

TRAFFIC TYPE:
[IMPORTANT: 2-3 sentences maximum. Analyze ONLY the temporal data from csv_data (peak vs off-peak, weekday vs weekend, morning vs evening peaks) AND the Location Name context. 
- If the location is a "Business Park", expect and explain commuter patterns. 
- If it's a "Greenway" or "Park", look for leisure patterns.
- DO NOT default to generic explanations. Match the data to the specific location context.
Determine if this is commuter traffic (weekday peak concentration), leisure traffic (weekend/off-peak), or mixed use. Use percentages and ratios from the data to support your classification.]

SEASONALITY:
[2-3 sentences analyzing monthly distribution. Identify peak months and provide informed interpretation based on your knowledge of Dublin's weather, daylight hours, and THE SPECIFIC LOCATION CONTEXT. 
- If it's a business park, don't attribute traffic to "school terms" unless data supports it. 
- If it's a university area, academic terms are relevant.
- If monthly data shows clear patterns, explain the likely causes using your understanding of Irish seasonal conditions and the specific land use.]

POSSIBLE MITIGATION ACTIONS:
[2-3 bullet points with practical, advisory recommendations. Use professional language like "Consider...", "Potential improvements include...", "It may be beneficial to investigate...". Draw upon international best practices and successful interventions from similar contexts. Avoid commands or quotes.]

IMPORTANT GUIDELINES:
- Start IMMEDIATELY with "SUMMARY:" - no preamble
- Write in a professional, flowing narrative style
- DO NOT quote user comments directly
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