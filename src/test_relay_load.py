
import requests
import time
import csv
import random

from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://127.0.0.1:8001"

TOTAL_REQUESTS = 15
CONCURRENT_USERS = 15

MAX_RETRIES = 2


def send_request(number):

    start = time.perf_counter()
    retries = 0

    payload = {
        "model": "relay-simulator",
        "messages": [
            {
                "role": "user",
                "content": f"Explain AI concept {number}."
            }
        ],
        "stream": False
    }

    while True:

        try:

            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                json=payload,
                timeout=90
            )

            # Retry only explicit Relay queue-full errors
            try:
                body = response.json()
            except ValueError:
                body = {}

            error = body.get("error", {})
            error_type = (
                error.get("type")
                if isinstance(error, dict)
                else None
            )


            if (
                response.status_code == 503
                and error_type == "queue_full"
                and retries < MAX_RETRIES
            ):

                retry_after = response.headers.get(
                    "Retry-After", "1"
                )

                try:
                    server_delay = float(retry_after)
                except ValueError:
                    server_delay = 1.0

                # Exponential backoff
                base_delay = 1.0
                max_delay = 8.0

                exponential_delay = min(
                    base_delay * (2 ** retries),
                    max_delay
                )

                # Respect server Retry-After
                delay = max(
                    server_delay,
                    exponential_delay
                )

                # Add random jitter
                jitter = random.uniform(0.1, 0.5)
                delay += jitter

                retries += 1

                print(
                    f"Request {number}: "
                    f"retry {retries}/{MAX_RETRIES} "
                    f"after {delay:.2f}s "
                    f"(exponential backoff)"
                )

                time.sleep(delay)
                continue


                retry_after = response.headers.get(
                    "Retry-After", "1"
                )

                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 1.0

                delay += random.uniform(0.1, 0.5)

                retries += 1

                print(
                    f"Request {number}: retry {retries} "
                    f"after {delay:.2f}s"
                )

                time.sleep(delay)
                continue

            latency = (
                time.perf_counter() - start
            ) * 1000

            return {
                "request": number,
                "status_code": response.status_code,
                "retries": retries,
                "latency_ms": round(latency, 2)
            }

        except requests.RequestException:

            latency = (
                time.perf_counter() - start
            ) * 1000

            return {
                "request": number,
                "status_code": 0,
                "retries": retries,
                "latency_ms": round(latency, 2)
            }


print("=" * 45)
print("THE RELAY - RETRY-AWARE LOAD TEST")
print("=" * 45)

print("Total requests:", TOTAL_REQUESTS)
print("Concurrent users:", CONCURRENT_USERS)
print("Maximum retries:", MAX_RETRIES)

start = time.perf_counter()

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
            f"Request {result['request']}: "
            f"HTTP {result['status_code']} | "
            f"Retries: {result['retries']} | "
            f"{result['latency_ms']} ms"
        )

total_time = time.perf_counter() - start

success = sum(
    r["status_code"] == 200 for r in results
)

failed = len(results) - success

total_retries = sum(
    r["retries"] for r in results
)

successful_latencies = sorted(
    r["latency_ms"]
    for r in results
    if r["status_code"] == 200
)

print("\n--- RETRY-AWARE LOAD SUMMARY ---")

print("Original requests:", len(results))
print("Successful:", success)
print("Failed:", failed)
print("Total retry attempts:", total_retries)

print(
    "Success rate:",
    round(success / len(results) * 100, 2),
    "%"
)

if successful_latencies:

    n = len(successful_latencies)

    print(
        "Average successful latency:",
        round(sum(successful_latencies) / n, 2),
        "ms"
    )

    print(
        "P50:",
        round(successful_latencies[int((n - 1) * 0.50)], 2),
        "ms"
    )

    print(
        "P95:",
        round(successful_latencies[int((n - 1) * 0.95)], 2),
        "ms"
    )

print("Total test time:", round(total_time, 2), "seconds")

with open(
    "relay_retry_load_results.csv",
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=[
            "request",
            "status_code",
            "retries",
            "latency_ms"
        ]
    )

    writer.writeheader()
    writer.writerows(results)

print("\nSaved to relay_retry_load_results.csv")

# Retrieve queue metrics

try:

    metrics = requests.get(
        f"{BASE_URL}/metrics",
        timeout=10
    ).json()

    print("\n--- QUEUE METRICS ---")

    for key, value in metrics.items():
        print(f"{key}: {value}")

except requests.RequestException as error:

    print("Metrics unavailable:", error)
