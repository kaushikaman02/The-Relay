
import requests
import time
import csv
import random
import uuid

URL = "http://127.0.0.1:8000/v1/chat/completions"

MAX_RETRIES = 3
BASE_DELAY = 1

def send_with_retry(request_number):

    request_id = str(uuid.uuid4())
    retries = 0
    start = time.perf_counter()

    while True:

        try:
            response = requests.post(
                URL,
                json={
                    "model": "relay-simulator",
                    "messages": [{
                        "role": "user",
                        "content": f"Research question {request_number}"
                    }],
                    "stream": False
                },
                timeout=30
            )

            if response.status_code == 200:
                status = "success"
                break

            if response.status_code not in (429, 503):
                status = f"permanent_error_{response.status_code}"
                break

            if retries >= MAX_RETRIES:
                status = f"failed_{response.status_code}"
                break

            retry_after = response.headers.get("Retry-After")

            if retry_after:
                delay = float(retry_after)
            else:
                delay = BASE_DELAY * (2 ** retries)

            # Small random jitter reduces synchronized retries
            delay += random.uniform(0, 0.25)

            retries += 1

            print(
                f"Request {request_number}: "
                f"retry {retries} after {delay:.2f}s"
            )

            time.sleep(delay)

        except requests.RequestException:
            if retries >= MAX_RETRIES:
                status = "connection_failed"
                break

            delay = BASE_DELAY * (2 ** retries)
            retries += 1

            print(f"Connection retry {retries}")
            time.sleep(delay)

    latency = (time.perf_counter() - start) * 1000

    return {
        "request_id": request_id,
        "request_number": request_number,
        "status": status,
        "retries": retries,
        "latency_ms": round(latency, 2)
    }


if __name__ == "__main__":

    results = []

    print("Starting retry experiment...")

    for i in range(1, 11):

        result = send_with_retry(i)
        results.append(result)

        print(result)

    with open(
        "retry_results.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(results[0].keys())
        )

        writer.writeheader()
        writer.writerows(results)

    print("\nRetry experiment completed.")
    print("Results saved to retry_results.csv")
