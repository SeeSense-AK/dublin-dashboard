"""
Sentiment analysis module - ULTRA SIMPLE VERSION
No fancy parameters, just works
"""
import streamlit as st
import os

# Try to import Groq, but don't fail if it doesn't work
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("Groq not available - using fallback analysis")


def get_groq_client():
    """
    Initialize Groq API client - SIMPLEST POSSIBLE VERSION
    """
    if not GROQ_AVAILABLE:
        return None
    
    try:
        # Get API key from environment
        api_key = os.getenv("GROQ_API_KEY")
        
        if not api_key:
            st.warning("⚠️ Groq API key not found. Using basic analysis.")
            return None
        
        # SIMPLEST POSSIBLE INITIALIZATION - NO EXTRA PARAMETERS
        client = Groq(api_key=api_key)
        return client
        
    except Exception as e:
        st.warning(f"⚠️ Could not use Groq API: {str(e)}. Using basic analysis.")
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def analyze_perception_sentiment(comments_list):
    """
    Analyze sentiment - tries AI first, falls back to keywords
    """
    # Always have a fallback ready
    if not comments_list or len(comments_list) == 0:
        return {
            'sentiment': 'unknown',
            'severity': 'unknown',
            'summary': 'No comments available',
            'key_issues': []
        }
    
    # Try AI analysis
    client = get_groq_client()
    
    if client:
        try:
            return analyze_with_groq(client, comments_list)
        except Exception as e:
            print(f"Groq analysis failed: {e}, using fallback")
            # Fall through to fallback
    
    # Fallback: Simple keyword analysis
    return analyze_without_api(comments_list)


def analyze_with_groq(client, comments_list):
    """
    Use Groq API for analysis
    """
    # Limit comments to avoid token limits
    comments_to_analyze = comments_list[:15]
    comments_text = "\n".join([f"- {c}" for c in comments_to_analyze if c and isinstance(c, str) and len(str(c).strip()) > 0])
    
    # Truncate if too long
    if len(comments_text) > 1500:
        comments_text = comments_text[:1500] + "..."
    
    prompt = f"""Analyze these road safety reports. Be brief.

Reports:
{comments_text}

Format:
SENTIMENT: [negative/neutral/positive]
SEVERITY: [low/medium/high/critical]
SUMMARY: [1-2 sentences]
KEY_ISSUES: [3-4 main problems, comma-separated]"""

    # Call API
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a road safety analyst. Be concise."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=250
    )
    
    # Parse response
    analysis_text = response.choices[0].message.content
    return parse_sentiment_response(analysis_text)


def parse_sentiment_response(response_text):
    """
    Parse structured response from AI
    """
    result = {
        'sentiment': 'negative',
        'severity': 'medium',
        'summary': '',
        'key_issues': []
    }
    
    lines = response_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        if 'SENTIMENT:' in line.upper():
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['sentiment'] = parts[1].strip().lower()
        
        elif 'SEVERITY:' in line.upper():
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['severity'] = parts[1].strip().lower()
        
        elif 'SUMMARY:' in line.upper():
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['summary'] = parts[1].strip()
        
        elif 'KEY_ISSUES:' in line.upper() or 'KEY ISSUES:' in line.upper():
            parts = line.split(':', 1)
            if len(parts) > 1:
                issues_text = parts[1].strip()
                result['key_issues'] = [issue.strip() for issue in issues_text.split(',') if issue.strip()]
    
    # Fallback if parsing failed
    if not result['summary']:
        result['summary'] = response_text[:150]
    
    if not result['key_issues']:
        result['key_issues'] = ['road_safety_concerns']
    
    return result


def analyze_without_api(comments_list):
    """
    Fallback: Simple keyword-based analysis
    NO API REQUIRED
    """
    if not comments_list or len(comments_list) == 0:
        return {
            'sentiment': 'unknown',
            'severity': 'unknown',
            'summary': 'No comments available',
            'key_issues': []
        }
    
    # Combine all comments
    text = ' '.join([str(c).lower() for c in comments_list if c and len(str(c).strip()) > 0])
    
    # Keyword lists
    danger_keywords = ['dangerous', 'scary', 'terrifying', 'nearly', 'almost', 'crashed', 'hit']
    pothole_keywords = ['pothole', 'hole', 'crater', 'damage', 'broken', 'rough']
    close_pass_keywords = ['close', 'pass', 'too close', 'nearly hit', 'close call']
    surface_keywords = ['surface', 'road', 'pavement', 'bumpy', 'uneven']
    traffic_keywords = ['traffic', 'cars', 'vehicles', 'junction', 'turning']
    
    # Count keywords
    danger_count = sum(1 for word in danger_keywords if word in text)
    
    # Identify main issues
    issues = []
    if any(word in text for word in pothole_keywords):
        issues.append('potholes')
    if any(word in text for word in close_pass_keywords):
        issues.append('close_passes')
    if any(word in text for word in surface_keywords):
        issues.append('poor_surface')
    if any(word in text for word in traffic_keywords):
        issues.append('traffic_issues')
    
    if not issues:
        issues = ['general_safety_concerns']
    
    # Determine severity
    if danger_count >= 3 or 'terrifying' in text or 'dangerous' in text:
        severity = 'high'
    elif danger_count >= 1:
        severity = 'medium'
    else:
        severity = 'low'
    
    # Sentiment
    negative_words = ['bad', 'poor', 'terrible', 'awful', 'dangerous', 'unsafe']
    negative_count = sum(1 for word in negative_words if word in text)
    
    if negative_count >= 2:
        sentiment = 'very_negative'
    elif negative_count >= 1:
        sentiment = 'negative'
    else:
        sentiment = 'neutral'
    
    # Summary
    num_comments = len(comments_list)
    main_issue = issues[0].replace('_', ' ')
    summary = f"Analysis of {num_comments} user report{'s' if num_comments != 1 else ''} highlighting {main_issue} and related safety concerns."
    
    return {
        'sentiment': sentiment,
        'severity': severity,
        'summary': summary,
        'key_issues': issues[:5]  # Max 5 issues
    }


def get_simple_sentiment(comments_list):
    """
    Quick sentiment check - positive/neutral/negative
    """
    if not comments_list:
        return 'neutral'
    
    text = ' '.join([str(c).lower() for c in comments_list if c])
    
    negative_keywords = ['dangerous', 'bad', 'poor', 'terrible', 'unsafe', 'hazard', 
                         'pothole', 'broken', 'damaged', 'awful', 'worst', 'nearly',
                         'close pass', 'scary']
    positive_keywords = ['good', 'safe', 'excellent', 'great', 'improved', 'better']
    
    negative_count = sum(1 for keyword in negative_keywords if keyword in text)
    positive_count = sum(1 for keyword in positive_keywords if keyword in text)
    
    if negative_count > positive_count:
        return 'negative'
    elif positive_count > negative_count:
        return 'positive'
    else:
        return 'neutral'


# For backwards compatibility
@st.cache_data(ttl=3600, show_spinner=False)
def batch_analyze_hotspots(hotspots_with_comments):
    """
    Analyze sentiment for multiple hotspots
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