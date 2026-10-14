import json
import urllib.request


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"


headline = "Tesla recalls nearly 3 million vehicles in China over emergency door handle concerns."

summary = (
    "Tesla is recalling nearly 3 million vehicles in China because emergency "
    "door releases may make it harder for occupants to exit after power loss."
)


prompt = f"""
You are a financial-news analysis engine.

Analyze this news for its likely effect on the associated stock.

Headline:
{headline}

Summary:
{summary}

Return ONLY valid JSON using exactly this structure:

{{
  "sentiment": "bullish | bearish | neutral",
  "sentiment_score": -1.0,
  "importance": 1,
  "time_horizon": "intraday | days | weeks | months",
  "reason": "brief explanation"
}}

Rules:
- sentiment_score must be between -1.0 and 1.0
- importance must be an integer from 1 to 10
- do not output markdown
- do not output anything outside the JSON
"""


payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "user",
            "content": prompt
        }
    ],
    "stream": False,
    "think": False,
    "format": "json"
}


request = urllib.request.Request(
    OLLAMA_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json"
    },
    method="POST"
)


with urllib.request.urlopen(request) as response:

    result = json.loads(
        response.read().decode("utf-8")
    )


content = result["message"]["content"]

analysis = json.loads(content)


print()
print("========================================")
print("          AI NEWS BRAIN v0.1")
print("========================================")
print(f"Sentiment:       {analysis['sentiment']}")
print(f"Sentiment score: {analysis['sentiment_score']}")
print(f"Importance:      {analysis['importance']}/10")
print(f"Time horizon:    {analysis['time_horizon']}")
print(f"Reason:          {analysis['reason']}")
print("========================================")