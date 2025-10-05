"""
Simple keyword/theme extractor for perception comments
Can be replaced later with a Groq or HuggingFace model
"""

import re
from collections import Counter

def extract_perception_themes(comments):
    """
    Extracts simple dominant themes and keywords from user comments.
    Returns a dict like:
      {"dominant_theme": "Close Pass", "keywords": ["driver", "close", "lane"]}
    """
    if not comments:
        return {"dominant_theme": None, "keywords": []}

    text = " ".join([c.lower() for c in comments if isinstance(c, str)])
    words = re.findall(r"\b[a-z]{4,}\b", text)
    common = Counter(words).most_common(5)

    # crude theme inference
    if any(w in text for w in ["close", "pass", "overtake"]):
        theme = "Close Pass"
    elif any(w in text for w in ["surface", "pothole", "rough"]):
        theme = "Poor Surface"
    elif any(w in text for w in ["obstruction", "block", "parked"]):
        theme = "Obstruction"
    else:
        theme = "General Safety"

    return {"dominant_theme": theme, "keywords": [w for w, _ in common]}
