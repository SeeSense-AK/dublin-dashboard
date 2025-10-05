"""
Sentiment analysis module - FIXED FOR GROQ
Clean implementation that works with Groq API
"""
import streamlit as st
import os

# Try to import Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq not available - install with: pip install groq")


def get_groq_client():
    """
    Initialize Groq API client - CLEAN VERSION
    """
    if not GROQ_AVAILABLE:
        return None
    
    try:
        # Get API key from environment
        api_key = os.getenv("GROQ_API_KEY")
        
        if not api_key:
            return None
        
        # Initialize with ONLY the api_key parameter
        client = Groq(api_key=api_key)
        return client
        
    except Exception as e:
        print(f"Groq initialization error: {e}")
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def analyze_perception_sentiment(comments_list):
    """
    Analyze sentiment - tries Groq first, falls back to keywords
    """
    # Validate input
    if not comments_list or len(comments_list) == 0:
        return {
            'sentiment': 'unknown',
            'severity': 'unknown',
            'summary': 'No comments available',
            'key_issues': []
        }
    
    # Try Groq API
    client = get_groq_client()
    
    if client:
        try:
            return analyze_with_groq(client, comments_list)
        except Exception as e:
            print(f"Groq analysis failed: {e}")
            # Fall through to keyword analysis
    
    # Fallback: Simple keyword analysis
    return analyze_without_api(comments_list)


def analyze_with_groq(client, comments_list):
    """
    Use Groq API for analysis
    """
    # Limit comments to avoid token limits
    comments_to_analyze = comments_list[:10]
    comments_text = "\n".join([f"- {c}" for c in comments_to_analyze if c and isinstance(c, str) and len(str(c).strip()) > 0])
    
    # Truncate if too long
    if len(comments_text) > 1500:
        comments_text = comments_text[:1500] + "..."
    
    if not comments_text.strip():
        return {
            'sentiment': 'unknown',
            'severity': 'low',
            'summary': 'No valid comments to analyze',
            'key_issues': []
        }
    
    prompt = f"""Analyze these road safety reports. Be brief and factual.

Reports:
{comments_text}

Provide a structured analysis in this exact format:
SENTIMENT: [positive/neutral/negative]
SEVERITY: [low/medium/high/critical]
SUMMARY: [1-2 sentences describing the main safety concern]
KEY_ISSUES: [list 2-3 main problems, separated by commas]"""

    try:
        # Call Groq API
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a road safety analyst. Provide concise, structured analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=250
        )
        
        # Parse response
        analysis_text = response.choices[0].message.content
        return parse_groq_response(analysis_text)
        
    except Exception as e:
        print(f"Groq API call failed: {e}")
        raise  # Re-raise to trigger fallback


def parse_groq_response(response_text):
    """
    Parse structured response from Groq
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
                sentiment = parts[1].strip().lower()
                if sentiment in ['positive', 'neutral', 'negative']:
                    result['sentiment'] = sentiment
        
        elif 'SEVERITY:' in line.upper():
            parts = line.split(':', 1)
            if len(parts) > 1:
                severity = parts[1].strip().lower()
                if severity in ['low', 'medium', 'high', 'critical']:
                    result['severity'] = severity
        
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
    
    if not text.strip():
        return {
            'sentiment': 'unknown',
            'severity': 'low',
            'summary': 'No valid comments',
            'key_issues': []
        }
    
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
        sentiment = 'negative'
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
        'key_issues': issues[:5]
    }


def test_groq_connection():
    """
    Test if Groq API is working
    Returns: (success: bool, message: str)
    """
    client = get_groq_client()
    
    if not client:
        return False, "Groq client initialization failed. Check GROQ_API_KEY in .env"
    
    try:
        # Simple test call
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": "Say OK if you can read this"}],
            max_tokens=10
        )
        return True, "Groq API connected successfully"
    except Exception as e:
        return False, f"Groq API test failed: {str(e)}"