
import requests
import time

URL = "http://127.0.0.1:8000/v1/chat/completions"

payload = {
    "model": "relay-simulator",
    "messages": [
        {
            "role": "user",
            "content": "Explain multi-head attention."
        }
    ],
    "stream": False
}

print("Sending request to simulator...")

start = time.perf_counter()

try:
    response = requests.post(
        URL,
        json=payload,
        timeout=30
    )

    elapsed = (time.perf_counter() - start) * 1000

    print("\nHTTP Status:", response.status_code)
    print("Response time:", round(elapsed, 2), "ms")
    print("Response:", response.text)

except requests.RequestException as e:
    print("Request failed:", e)
