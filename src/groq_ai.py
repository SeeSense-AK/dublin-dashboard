from groq import Groq

def generate_hotspot_summary(lat, lon, theme, sentiment, sensor_events, perception_reports, avg_severity):
    prompt = f"""
    Generate a short summary of a traffic/cycling hotspot at coordinates ({lat}, {lon}).
    - Theme: {theme}
    - Sentiment: {sentiment}
    - Sensor events: {sensor_events} (avg severity {avg_severity:.2f})
    - Perception reports: {perception_reports}

    Summarize in 2 concise sentences what this might mean for cyclists or local planners.
    """

    try:
        client = Groq(api_key="YOUR_GROQ_API_KEY")
        response = client.chat.completions.create(
            model="mixtral-8x7b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI summary unavailable: {e}"
