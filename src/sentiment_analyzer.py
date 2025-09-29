"""
Sentiment analysis module using Groq API
Analyzes perception report comments to understand context and severity
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
    
    return Groq(api_key=GROQ_API_KEY)


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
    
    # Combine comments for analysis
    comments_text = "\n".join([f"- {c}" for c in comments_list if c])
    
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
        return {
            'sentiment': 'neutral',
            'severity': 'medium',
            'summary': f'Analysis failed: {str(e)}',
            'key_issues': []
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
                         'pothole', 'broken', 'damaged', 'awful', 'worst']
    positive_keywords = ['good', 'safe', 'excellent', 'great', 'improved', 'better']
    
    text = ' '.join(comments_list).lower()
    
    negative_count = sum(1 for keyword in negative_keywords if keyword in text)
    positive_count = sum(1 for keyword in positive_keywords if keyword in text)
    
    if negative_count > positive_count:
        return 'negative'
    elif positive_count > negative_count:
        return 'positive'
    else:
        return 'neutral'