
import requests
import time

BASE_URL = "http://127.0.0.1:8001"

# ----------------------------------
# TEST 1: HEALTH CHECK
# ----------------------------------

print("\n--- RELAY HEALTH CHECK ---")

health = requests.get(
    f"{BASE_URL}/health",
    timeout=10
)

print("Status:", health.status_code)
print("Response:", health.json())


# ----------------------------------
# TEST 2: SEND API REQUEST
# ----------------------------------

print("\n--- TESTING MODEL REQUEST ---")

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

start = time.perf_counter()

response = requests.post(
    f"{BASE_URL}/v1/chat/completions",
    json=payload,
    timeout=70
)

elapsed = (
    time.perf_counter() - start
) * 1000

print("HTTP Status:", response.status_code)
print("Response time:", round(elapsed, 2), "ms")
print("Response:", response.json())


# ----------------------------------
# TEST 3: QUEUE METRICS
# ----------------------------------

print("\n--- RELAY QUEUE METRICS ---")

metrics = requests.get(
    f"{BASE_URL}/metrics",
    timeout=10
)

print("Metrics:", metrics.json())

print("\nRelay integration test completed.")
