import requests
import json
from datetime import datetime

def test_current_models(api_key):
    # Current production models (as of late 2024)
    current_models = [
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest", 
        "gemini-1.0-pro-latest",
        "gemini-2.0-flash-latest",
        "gemini-2.0-flash-thinking-exp-1219",  # New experimental
        "gemini-2.0-pro-exp-1205"
    ]
    
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{
                "text": "Say just 'OK' to confirm this works."
            }]
        }]
    }
    
    print("Testing current model names...")
    
    for model in current_models:
        url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}"
        
        print(f"\nTrying: {model}")
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                text = result['candidates'][0]['content']['parts'][0]['text']
                print(f"✅ SUCCESS! Response: {text}")
                print(f"🎯 WORKING MODEL: {model}")
                return model
            elif response.status_code == 429:
                error = response.json()
                print(f"❌ Quota exceeded: {error.get('error', {}).get('message', 'Unknown')}")
                return "quota_exceeded"
            elif response.status_code == 404:
                continue  # Try next model
            else:
                print(f"Other status: {response.text[:100]}...")
                
        except Exception as e:
            print(f"Request error: {e}")
    
    print("\n❌ No current models worked. Let's list what's actually available...")
    return None


# Replace with your actual API key
API_KEY = "AIzaSyAMdZ1YjOr29e7Y1fr2Vr5mEmCGG2w3CYg"
check_gemini_quota(API_KEY)