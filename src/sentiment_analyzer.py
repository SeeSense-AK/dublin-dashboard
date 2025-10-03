"""
Sentiment analysis module using Groq API
Analyzes perception report comments to understand context and severity
FIXED: Compatible with latest Groq library
"""
import streamlit as st
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL


def get_groq_client():
    """
    Initialize Groq API client
    Returns: Groq client
    """
    if not GROQ_API_KEY:
        st.warning("Groq API key not configured. Sentiment analysis will be disabled.")
        return None
    
    try:
        # Simple client initialization - no extra parameters
        return Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        st.warning(f"Could not initialize Groq client: {e}")
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def analyze_perception_sentiment(comments_list):
    """
    Analyze sentiment and themes from a list of perception reports
    
    Args:
        comments_list: List of comment strings
    
    Returns:
        dict with sentiment analysis results
    """
    client = get_groq_client()
    
    if not client or not comments_list:
        return {
            'sentiment': 'neutral',
            'severity': 'medium',
            'summary': 'No analysis available',
            'key_issues': []
        }
    
    # Combine comments for analysis (limit to avoid token limits)
    comments_to_analyze = comments_list[:20]  # Max 20 comments
    comments_text = "\n".join([f"- {c}" for c in comments_to_analyze if c and isinstance(c, str)])
    
    # Limit length
    if len(comments_text) > 2000:
        comments_text = comments_text[:2000] + "..."
    
    prompt = f"""Analyze these road safety perception reports and provide a structured assessment:

Reports:
{comments_text}

Provide your analysis in this exact format:

SENTIMENT: [positive/neutral/negative]
SEVERITY: [low/medium/high/critical]
SUMMARY: [2-3 sentence summary of the main issues]
KEY_ISSUES: [comma-separated list of 3-5 key problems mentioned]

Be concise and focus on actionable insights."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a road safety analyst. Provide brief, actionable analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        
        analysis_text = response.choices[0].message.content
        
        # Parse the structured response
        result = parse_sentiment_response(analysis_text)
        return result
        
    except Exception as e:
        st.error(f"Error calling Groq API: {str(e)}")
        # Return fallback analysis
        return {
            'sentiment': 'negative',
            'severity': 'medium',
            'summary': f'Analysis of {len(comments_list)} user reports. API error occurred.',
            'key_issues': ['API analysis unavailable']
        }


def parse_sentiment_response(response_text):
    """
    Parse the structured response from Groq
    
    Args:
        response_text: Raw response from Groq
    
    Returns:
        dict with parsed fields
    """
    result = {
        'sentiment': 'neutral',
        'severity': 'medium',
        'summary': '',
        'key_issues': []
    }
    
    lines = response_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('SENTIMENT:'):
            result['sentiment'] = line.split(':', 1)[1].strip().lower()
        
        elif line.startswith('SEVERITY:'):
            result['severity'] = line.split(':', 1)[1].strip().lower()
        
        elif line.startswith('SUMMARY:'):
            result['summary'] = line.split(':', 1)[1].strip()
        
        elif line.startswith('KEY_ISSUES:'):
            issues_text = line.split(':', 1)[1].strip()
            result['key_issues'] = [issue.strip() for issue in issues_text.split(',')]
    
    # Fallback if parsing fails
    if not result['summary']:
        result['summary'] = response_text[:200]
    
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def batch_analyze_hotspots(hotspots_with_comments):
    """
    Analyze sentiment for multiple hotspots in batch
    
    Args:
        hotspots_with_comments: List of dicts with hotspot_id and comments
    
    Returns:
        dict mapping hotspot_id to sentiment analysis
    """
    results = {}
    
    for hotspot in hotspots_with_comments:
        hotspot_id = hotspot['hotspot_id']
        comments = hotspot['comments']
        
        if comments:
            analysis = analyze_perception_sentiment(comments)
            results[hotspot_id] = analysis
        else:
            results[hotspot_id] = {
                'sentiment': 'unknown',
                'severity': 'unknown',
                'summary': 'No perception reports available',
                'key_issues': []
            }
    
    return results


def get_simple_sentiment(comments_list):
    """
    Get simple sentiment without API call (fallback method)
    Uses keyword matching for basic sentiment
    
    Args:
        comments_list: List of comments
    
    Returns:
        str: 'positive', 'neutral', or 'negative'
    """
    if not comments_list:
        return 'neutral'
    
    # Simple keyword-based sentiment
    negative_keywords = ['dangerous', 'bad', 'poor', 'terrible', 'unsafe', 'hazard', 
                         'pothole', 'broken', 'damaged', 'awful', 'worst', 'close', 'pass',
                         'nearly', 'almost', 'scary', 'frightening']
    positive_keywords = ['good', 'safe', 'excellent', 'great', 'improved', 'better']
    
    text = ' '.join([str(c) for c in comments_list if c]).lower()
    
    negative_count = sum(1 for keyword in negative_keywords if keyword in text)
    positive_count = sum(1 for keyword in positive_keywords if keyword in text)
    
    if negative_count > positive_count:
        return 'negative'
    elif positive_count > negative_count:
        return 'positive'
    else:
        return 'neutral'


def analyze_without_api(comments_list):
    """
    Fallback analysis without API - used when Groq is unavailable
    
    Args:
        comments_list: List of comments
    
    Returns:
        dict with basic analysis
    """
    if not comments_list:
        return {
            'sentiment': 'unknown',
            'severity': 'unknown',
            'summary': 'No comments available',
            'key_issues': []
        }
    
    sentiment = get_simple_sentiment(comments_list)
    
    # Extract common themes from comments
    text = ' '.join([str(c) for c in comments_list if c]).lower()
    
    issues = []
    if 'pothole' in text or 'hole' in text:
        issues.append('pothole')
    if 'close pass' in text or 'too close' in text:
        issues.append('close_pass')
    if 'dangerous' in text or 'unsafe' in text:
        issues.append('dangerous_conditions')
    if 'surface' in text or 'rough' in text:
        issues.append('poor_surface')
    
    # Determine severity
    danger_words = ['dangerous', 'scary', 'nearly', 'almost', 'terrible', 'awful']
    danger_count = sum(1 for word in danger_words if word in text)
    
    if danger_count >= 3:
        severity = 'high'
    elif danger_count >= 1:
        severity = 'medium'
    else:
        severity = 'low'
    
    return {
        'sentiment': sentiment,
        'severity': severity,
        'summary': f'Analysis of {len(comments_list)} reports. Main themes: {", ".join(issues) if issues else "general concerns"}',
        'key_issues': issues if issues else ['general_safety_concerns']
    }