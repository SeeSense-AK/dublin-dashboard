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
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
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
- Location: {hotspot_data.get('street_name', 'Unknown')}
- Source: {source}
- Event Type: {hotspot_data.get('event_type', 'N/A')}
- Event Count: {hotspot_data.get('event_count', 0)}
- Device Count: {hotspot_data.get('device_count', 0)}
- Concern Score: {hotspot_data.get('concern_score', 0):.2f}
"""
    
    if source == 'corridor':
        prompt += f"""- Priority: {hotspot_data.get('priority_category', 'N/A')}
- Issue Type: {hotspot_data.get('dominant_category', 'N/A')}
- Speed Limit: {hotspot_data.get('maxspeed', 'N/A')}
- Lanes: {hotspot_data.get('lanes', 'N/A')}
"""
    
    # Add user comments if available
    if user_comments and len(user_comments) > 0:
        prompt += f"\n**User Reports ({len(user_comments)}):**\n"
        for i, comment in enumerate(user_comments[:5], 1):  # Limit to 5 comments
            prompt += f"{i}. {comment}\n"
    
    prompt += """
**Task:**
Provide your response in EXACTLY this format:

SUMMARY:
[2-3 sentences describing what's happening at this location and why it's concerning]

THEMES:
[Comma-separated list of 2-4 specific safety themes, e.g., "Poor road surface", "Visibility issues", "Heavy traffic"]

RECOMMENDATIONS:
[2-3 bullet points with specific, actionable recommendations]

Keep it concise, factual, and focused on safety. Use the user reports to understand real-world experiences."""
    
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
        # Corridor has all_comments field
        all_comments = hotspot_data.get('all_comments', '')
        if all_comments and all_comments != '':
            # Split by common delimiters
            comment_list = all_comments.split('|')
            comments = [c.strip() for c in comment_list if c.strip()]
    
    elif source == 'perception':
        # Perception hotspots might have combined_text
        combined_text = hotspot_data.get('combined_text', '')
        if combined_text and combined_text != '':
            comment_list = combined_text.split('|')
            comments = [c.strip() for c in comment_list if c.strip()]
    
    return comments
