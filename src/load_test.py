import numpy as np
import requests
import time
import csv
import uuid

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

URL = "http://127.0.0.1:8001/v1/chat/completions"

TOTAL_REQUESTS = 60
CONCURRENT_USERS = 3


def send_request(request_number):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    payload = {
        "model": "relay-simulator",
        "messages": [
            {
                "role": "user",
                "content": f"Explain AI research concept {request_number}"
            }
        ],
        "stream": False
    }

    max_retries = 2
    retries = 0
    status_code = 0

    while retries <= max_retries:
        try:
            response = requests.post(
                URL,
                json=payload,
                timeout=30
            )
            status_code = response.status_code

            if status_code == 200:
                break

            if status_code not in (429, 502, 503, 504):
                break

        except requests.RequestException:
            status_code = 0

        if retries < max_retries:
            time.sleep(2 ** retries)

        retries += 1

    latency = (time.perf_counter() - start) * 1000

    return {
        "request_id": request_id,
        "request_number": request_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status_code": status_code,
        "latency_ms": round(latency, 2),
        "success": status_code == 200,
        "retries": retries
    }


print("=" * 45)
print("THE RELAY - CONCURRENT LOAD TEST")
print("=" * 45)

print("Total requests:", TOTAL_REQUESTS)
print("Concurrent users:", CONCURRENT_USERS)

start_time = time.perf_counter()

results = []

with ThreadPoolExecutor(
    max_workers=CONCURRENT_USERS
) as executor:

    futures = [
        executor.submit(send_request, i)
        for i in range(1, TOTAL_REQUESTS + 1)
    ]

    for future in as_completed(futures):

        result = future.result()
        results.append(result)

        print(
            f"Request {result['request_number']}: "
            f"HTTP {result['status_code']} | "
            f"{result['latency_ms']} ms"
        )

total_time = (time.perf_counter() - start_time) * 1000

successes = sum(r["success"] for r in results)
failures = len(results) - successes

latencies = sorted(
    r["latency_ms"] for r in results
)

average = sum(latencies) / len(latencies)

p50 = np.percentile(latencies, 50)
p95 = np.percentile(latencies, 95)

with open(
    "relay_retry_load_results.csv",
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=list(results[0].keys())
    )

    writer.writeheader()
    writer.writerows(results)

print("\n--- LOAD TEST SUMMARY ---")
print("Total requests:", len(results))
print("Successful:", successes)
print("Failed:", failures)
print("Average latency:", round(average, 2), "ms")
print("P50 latency:", round(p50, 2), "ms")
print("P95 latency:", round(p95, 2), "ms")
print("Total test time:", round(total_time, 2), "ms")

print("\nResults saved to relay_retry_load_results.csv")
