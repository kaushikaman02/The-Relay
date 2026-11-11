
import os
import csv
import json
import time
import uuid
import requests

from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "openai/gpt-oss-20b"

if not API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")

URL = "https://api.groq.com/openai/v1/chat/completions"
CSV_FILE = "results.csv"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "user",
            "content": "Explain what an AI research assistant does in two sentences."
        }
    ],
    "stream": True,
    "stream_options": {"include_usage": True}
}

request_id = str(uuid.uuid4())
start_time = datetime.now(timezone.utc).isoformat()
start = time.perf_counter()

first_token_ms = None
total_ms = None
tokens_in = None
tokens_out = None
status = "error"
answer = ""

print("Sending request to Groq...")

try:
    with requests.post(
        URL,
        headers=headers,
        json=payload,
        stream=True,
        timeout=(10, 90)
    ) as response:

        print("HTTP status:", response.status_code)

        # Capture actual rate-limit headers
        rate_headers = {
            k: v for k, v in response.headers.items()
            if "ratelimit" in k.lower() or "retry-after" in k.lower()
        }

        print("Rate-limit headers:", rate_headers)

        if response.status_code == 429:
            status = "rate_limited"
            raise RuntimeError("Groq rate limit reached")

        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=True):

            if not line:
                continue

            if isinstance(line, bytes):
                line = line.decode("utf-8")

            if not line.startswith("data:"):
                continue

            data = line[5:].strip()

            if data == "[DONE]":
                break

            chunk = json.loads(data)

            # Capture usage from the final streaming chunk
            usage = chunk.get("usage")

            if usage:
                tokens_in = usage.get("prompt_tokens")
                tokens_out = usage.get("completion_tokens")

            choices = chunk.get("choices", [])

            if not choices:
                continue

            content = choices[0].get("delta", {}).get("content")

            if content:
                if first_token_ms is None:
                    first_token_ms = (
                        time.perf_counter() - start
                    ) * 1000

                answer += content
                print(content, end="", flush=True)

        total_ms = (time.perf_counter() - start) * 1000
        status = "ok"

except requests.Timeout:
    total_ms = (time.perf_counter() - start) * 1000
    status = "timeout"
    print("\nRequest timed out.")

except Exception as e:
    total_ms = (time.perf_counter() - start) * 1000

    if status != "rate_limited":
        status = "error"

    print("\nError:", str(e))

finally:
    row = {
        "request_id": request_id,
        "scenario": "baseline",
        "source": "real",
        "start_time": start_time,
        "first_token_ms": first_token_ms,
        "total_ms": total_ms,
        "status": status,
        "retries": 0,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "retrieval_setting": "not_applicable",
        "answer_grade": ""
    }

    columns = [
        "request_id", "scenario", "source", "start_time",
        "first_token_ms", "total_ms", "status", "retries",
        "tokens_in", "tokens_out", "retrieval_setting",
        "answer_grade"
    ]

    file_exists = os.path.exists(CSV_FILE)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)

    print("\n\n--- Performance Report ---")
    print("Model:", MODEL)
    print("Status:", status)
    print("First token:", first_token_ms, "ms")
    print("Total time:", total_ms, "ms")
    print("Input tokens:", tokens_in)
    print("Output tokens:", tokens_out)
    print("Saved to:", CSV_FILE)
