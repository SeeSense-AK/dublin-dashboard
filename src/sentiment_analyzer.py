"""
Sentiment analysis module - IMPROVED VERSION WITH BETTER DEBUGGING
"""
import streamlit as st
import os
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()

# Try to import Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
    print("✅ Groq library imported successfully")
except ImportError as e:
    GROQ_AVAILABLE = False
    print(f"❌ Groq not available: {e}")
    print("   Install with: pip install groq")


def get_groq_client():
    """
    Initialize Groq API client with better error handling
    """
    if not GROQ_AVAILABLE:
        st.warning("⚠️ Groq library not installed. Using fallback analysis.")
        st.info("Install Groq with: `pip install groq`")
        return None
    
    try:
        # Get API key from environment
        api_key = os.getenv("GROQ_API_KEY")
        
        # Debug: Check if key exists
        if not api_key:
            st.error("❌ GROQ_API_KEY not found in environment variables!")
            st.info("Make sure your .env file has: GROQ_API_KEY=your_key_here")
            
            # Show what keys are available (for debugging)
            with st.expander("🔍 Debug: Environment Variables"):
                env_vars = [k for k in os.environ.keys() if 'GROQ' in k or 'API' in k]
                if env_vars:
                    st.write("Found these API-related variables:")
                    for var in env_vars:
                        st.write(f"- {var}")
                else:
                    st.write("No GROQ or API related variables found")
            
            return None
        
        # Debug: Show partial key
        st.success(f"✅ Found GROQ_API_KEY: {api_key[:10]}...{api_key[-4:]}")
        
        # Try to initialize client
        client = Groq(api_key=api_key)
        
        # Test the connection with a simple call
        try:
            test_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": "test"}
                ],
                max_tokens=5,
                temperature=0
            )
            st.success("✅ Groq API connection successful!")
            return client
            
        except Exception as api_error:
            st.error(f"❌ Groq API test failed: {str(api_error)}")
            
            # Provide specific guidance based on error
            error_str = str(api_error).lower()
            if "401" in error_str or "authentication" in error_str:
                st.warning("🔑 Authentication error. Check if your API key is valid.")
                st.info("Get a new key from: https://console.groq.com/keys")
            elif "rate limit" in error_str:
                st.warning("⏰ Rate limit reached. Try again in a few moments.")
            elif "network" in error_str or "connection" in error_str:
                st.warning("🌐 Network error. Check your internet connection.")
            
            return None
        
    except Exception as e:
        st.error(f"❌ Error initializing Groq client: {str(e)}")
        with st.expander("🔍 Full Error Details"):
            st.code(str(e))
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def analyze_perception_sentiment(comments_list, debug=False):
    """
    Analyze sentiment - tries Groq AI first, falls back to keywords
    
    Args:
        comments_list: List of comment strings
        debug: If True, show debug information
    
    Returns:
        Dict with sentiment analysis
    """
    # Always have a fallback ready
    if not comments_list or len(comments_list) == 0:
        return {
            'sentiment': 'unknown',
            'severity': 'unknown',
            'summary': 'No comments available',
            'key_issues': [],
            'method': 'none'
        }
    
    # Try Groq AI analysis first
    if debug:
        st.info("🤖 Attempting Groq AI analysis...")
    
    client = get_groq_client()
    
    if client:
        try:
            result = analyze_with_groq(client, comments_list)
            result['method'] = 'groq_ai'
            if debug:
                st.success("✅ Using Groq AI analysis")
            return result
            
        except Exception as e:
            if debug:
                st.warning(f"⚠️ Groq analysis failed: {e}")
            print(f"Groq analysis error: {e}")
            # Fall through to fallback
    
    # Fallback: Keyword-based analysis
    if debug:
        st.info("📊 Using fallback keyword analysis")
    
    result = analyze_without_api(comments_list)
    result['method'] = 'keyword_fallback'
    return result


def analyze_with_groq(client, comments_list):
    """
    Use Groq API for AI-powered analysis
    """
    # Limit comments to avoid token limits
    comments_to_analyze = comments_list[:15]
    comments_text = "\n".join([f"- {c}" for c in comments_to_analyze 
                               if c and isinstance(c, str) and len(str(c).strip()) > 0])
    
    # Truncate if too long
    if len(comments_text) > 1500:
        comments_text = comments_text[:1500] + "..."
    
    prompt = f"""Analyze these road safety reports. Be brief and structured.

Reports:
{comments_text}

Provide analysis in this exact format:
SENTIMENT: [negative/neutral/positive]
SEVERITY: [low/medium/high/critical]
SUMMARY: [1-2 sentences describing the main issues]
KEY_ISSUES: [list 3-4 main problems, comma-separated]"""

    # Call Groq API with updated model
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # Updated model name
        messages=[
            {"role": "system", "content": "You are a road safety analyst. Be concise and structured."},
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
                result['key_issues'] = [issue.strip() for issue in issues_text.split(',') 
                                       if issue.strip()]
    
    # Fallback if parsing failed
    if not result['summary']:
        result['summary'] = response_text[:150]
    
    if not result['key_issues']:
        result['key_issues'] = ['road_safety_concerns']
    
    return result


def analyze_without_api(comments_list):
    """
    Fallback: Simple keyword-based analysis
    NO API REQUIRED - Always works
    """
    if not comments_list or len(comments_list) == 0:
        return {
            'sentiment': 'unknown',
            'severity': 'unknown',
            'summary': 'No comments available',
            'key_issues': []
        }
    
    # Combine all comments
    text = ' '.join([str(c).lower() for c in comments_list 
                     if c and len(str(c).strip()) > 0])
    
    # Keyword lists
    danger_keywords = ['dangerous', 'scary', 'terrifying', 'nearly', 'almost', 
                      'crashed', 'hit', 'unsafe', 'hazard']
    pothole_keywords = ['pothole', 'hole', 'crater', 'damage', 'broken', 'rough']
    close_pass_keywords = ['close', 'pass', 'too close', 'nearly hit', 'close call']
    surface_keywords = ['surface', 'road', 'pavement', 'bumpy', 'uneven']
    traffic_keywords = ['traffic', 'cars', 'vehicles', 'junction', 'turning']
    
    # Count keywords
    danger_count = sum(1 for word in danger_keywords if word in text)
    
    # Identify main issues
    issues = []
    if any(word in text for word in pothole_keywords):
        issues.append('potholes_and_surface_damage')
    if any(word in text for word in close_pass_keywords):
        issues.append('close_passes_and_dangerous_driving')
    if any(word in text for word in surface_keywords):
        issues.append('poor_road_surface')
    if any(word in text for word in traffic_keywords):
        issues.append('traffic_and_junction_issues')
    
    if not issues:
        issues = ['general_safety_concerns']
    
    # Determine severity
    if danger_count >= 3 or 'terrifying' in text or 'crashed' in text:
        severity = 'critical'
    elif danger_count >= 2 or 'dangerous' in text:
        severity = 'high'
    elif danger_count >= 1:
        severity = 'medium'
    else:
        severity = 'low'
    
    # Sentiment
    negative_words = ['bad', 'poor', 'terrible', 'awful', 'dangerous', 'unsafe', 
                     'worst', 'horrible']
    negative_count = sum(1 for word in negative_words if word in text)
    
    if negative_count >= 3:
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


@st.cache_data(ttl=3600, show_spinner=False)
def batch_analyze_hotspots(hotspots_with_comments, debug=False):
    """
    Analyze sentiment for multiple hotspots
    """
    results = {}
    
    for hotspot in hotspots_with_comments:
        hotspot_id = hotspot['hotspot_id']
        comments = hotspot.get('comments', [])
        
        if comments:
            analysis = analyze_perception_sentiment(comments, debug=debug)
            results[hotspot_id] = analysis
        else:
            results[hotspot_id] = {
                'sentiment': 'unknown',
                'severity': 'unknown',
                'summary': 'No perception reports available',
                'key_issues': [],
                'method': 'none'
            }
    
    return results