"""
Debug script to test Groq API connection
Run this to identify the exact issue: python test_groq.py
"""

import os
from dotenv import load_dotenv

print("=" * 60)
print("GROQ API CONNECTION TEST")
print("=" * 60)

# Step 1: Load environment variables
print("\n1️⃣ Loading .env file...")
load_dotenv()
print("   ✅ .env loaded")

# Step 2: Check if API key exists
print("\n2️⃣ Checking for GROQ_API_KEY...")
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("   ❌ GROQ_API_KEY not found in environment!")
    print("   Check your .env file has: GROQ_API_KEY=your_key_here")
    exit(1)
else:
    # Show partial key for verification
    print(f"   ✅ GROQ_API_KEY found: {api_key[:10]}...{api_key[-4:]}")
    print(f"   Length: {len(api_key)} characters")

# Step 3: Try importing Groq
print("\n3️⃣ Importing Groq library...")
try:
    from groq import Groq
    print("   ✅ Groq library imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import Groq: {e}")
    print("   Run: pip install groq")
    exit(1)

# Step 4: Initialize client
print("\n4️⃣ Initializing Groq client...")
try:
    client = Groq(api_key=api_key)
    print("   ✅ Groq client initialized")
except Exception as e:
    print(f"   ❌ Failed to initialize client: {e}")
    print(f"   Error type: {type(e).__name__}")
    exit(1)

# Step 5: Test API call
print("\n5️⃣ Testing API call with simple prompt...")
try:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'test successful' if you can read this."}
        ],
        temperature=0.3,
        max_tokens=50
    )
    
    result = response.choices[0].message.content
    print(f"   ✅ API call successful!")
    print(f"   Response: {result}")
    
except Exception as e:
    print(f"   ❌ API call failed: {e}")
    print(f"   Error type: {type(e).__name__}")
    
    if "401" in str(e) or "authentication" in str(e).lower():
        print("\n   💡 This looks like an authentication error.")
        print("   Your API key might be:")
        print("   - Invalid or expired")
        print("   - Missing 'gsk_' prefix")
        print("   - Copied incorrectly (check for extra spaces)")
    elif "rate limit" in str(e).lower():
        print("\n   💡 Rate limit reached. Wait a bit and try again.")
    elif "network" in str(e).lower() or "connection" in str(e).lower():
        print("\n   💡 Network issue. Check your internet connection.")
    
    exit(1)

# Step 6: Test sentiment analysis
print("\n6️⃣ Testing sentiment analysis function...")
try:
    test_comments = [
        "Dangerous pothole nearly made me crash",
        "Very rough surface, needs urgent repair",
        "Close pass by car, felt unsafe"
    ]
    
    prompt = f"""Analyze these road safety reports. Be brief.

Reports:
- Dangerous pothole nearly made me crash
- Very rough surface, needs urgent repair
- Close pass by car, felt unsafe

Format:
SENTIMENT: [negative/neutral/positive]
SEVERITY: [low/medium/high/critical]
SUMMARY: [1-2 sentences]
KEY_ISSUES: [3-4 main problems, comma-separated]"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a road safety analyst. Be concise."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=250
    )
    
    analysis = response.choices[0].message.content
    print("   ✅ Sentiment analysis test successful!")
    print(f"\n   Analysis result:\n{analysis}")
    
except Exception as e:
    print(f"   ❌ Sentiment analysis failed: {e}")
    exit(1)

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nYour Groq integration is working correctly.")
print("If your dashboard still has issues, the problem is elsewhere.")
