
import json
import requests
import csv
import time
import uuid
import threading

from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from concurrent.futures import TimeoutError

from queue_manager import QueueManager


# ----------------------------------
# RELAY SERVER CONFIGURATION
# ----------------------------------

HOST = "127.0.0.1"
PORT = 8001

SIMULATOR_URL = "http://127.0.0.1:8000/v1/chat/completions"

WORKERS = 3
QUEUE_CAPACITY = 5

MAX_RETRIES = 2
BASE_BACKOFF = 1
MAX_RETRY_AFTER = 60
UPSTREAM_TIMEOUT = 30

RATE_LIMIT_LOG = Path("rate_limit_events.csv")
log_lock = threading.Lock()


# ----------------------------------
# INITIALIZE QUEUE
# ----------------------------------

manager = QueueManager(
    workers=WORKERS,
    max_queue_size=QUEUE_CAPACITY
)


# ----------------------------------
# RATE LIMIT CSV LOGGER
# ----------------------------------

def log_rate_limit(request_id, attempt, status, delay):

    with log_lock:

        file_exists = RATE_LIMIT_LOG.exists()

        with open(
            RATE_LIMIT_LOG,
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            if not file_exists:
                writer.writerow([
                    "timestamp",
                    "request_id",
                    "attempt",
                    "status_code",
                    "retry_delay_seconds"
                ])

            writer.writerow([
                datetime.now(timezone.utc).isoformat(),
                request_id,
                attempt,
                status,
                round(delay, 2)
            ])


# ----------------------------------
# RETRY-AFTER PARSER
# ----------------------------------

def get_retry_delay(header, attempt):

    if header:

        try:
            delay = float(header)

        except ValueError:

            try:
                retry_time = parsedate_to_datetime(header)

                if retry_time.tzinfo is None:
                    retry_time = retry_time.replace(
                        tzinfo=timezone.utc
                    )

                delay = (
                    retry_time -
                    datetime.now(timezone.utc)
                ).total_seconds()

            except (ValueError, TypeError, OverflowError):
                delay = BASE_BACKOFF * (2 ** attempt)

    else:

        delay = BASE_BACKOFF * (2 ** attempt)

    return max(0, min(delay, MAX_RETRY_AFTER))


# ----------------------------------
# FORWARD REQUEST TO SIMULATOR
# ----------------------------------

def forward_to_simulator(payload):

    request_id = str(uuid.uuid4())

    for attempt in range(MAX_RETRIES + 1):

        try:

            response = requests.post(
                SIMULATOR_URL,
                json=payload,
                timeout=UPSTREAM_TIMEOUT
            )

            try:
                body = response.json()

            except ValueError:
                body = {"error": response.text}

            status = response.status_code

            # Handle rate limiting and temporary overload
            if status in (429, 503):

                retry_header = response.headers.get(
                    "Retry-After"
                )

                if status == 429:

                    delay = get_retry_delay(
                        retry_header,
                        attempt
                    )

                    log_rate_limit(
                        request_id,
                        attempt + 1,
                        status,
                        delay
                    )

                else:

                    delay = get_retry_delay(
                        retry_header,
                        attempt
                    )

                if attempt < MAX_RETRIES:

                    print(
                        f"[RELAY] Request {request_id}: "
                        f"HTTP {status}, retry "
                        f"{attempt + 1}/{MAX_RETRIES} "
                        f"after {delay:.2f}s"
                    )

                    time.sleep(delay)
                    continue

            response_headers = {}

            if response.headers.get("Retry-After"):
                response_headers["Retry-After"] = (
                    response.headers["Retry-After"]
                )

            return status, body, response_headers

        except requests.RequestException as error:

            return 502, {
                "error": {
                    "message": str(error),
                    "type": "upstream_connection_error"
                }
            }, {}

    return 502, {
        "error": "Maximum retry attempts exceeded"
    }, {}


# ----------------------------------
# HTTP REQUEST HANDLER
# ----------------------------------

class RelayHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print("[RELAY]", format % args)

    def send_json(self, status, data, headers=None):

        body = json.dumps(data).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        if headers:

            for name, value in headers.items():

                if name.lower() not in (
                    "content-type",
                    "content-length"
                ):
                    self.send_header(name, str(value))

        self.end_headers()

        try:
            self.wfile.write(body)

        except (BrokenPipeError, ConnectionResetError):
            print("[RELAY] Client disconnected")

    # ----------------------------------
    # GET REQUESTS
    # ----------------------------------

    def do_GET(self):

        if self.path == "/health":

            self.send_json(200, {
                "status": "running",
                "service": "The Relay API Server"
            })

        elif self.path == "/metrics":

            self.send_json(
                200,
                manager.get_metrics()
            )

        else:

            self.send_json(404, {
                "error": "Endpoint not found"
            })

    # ----------------------------------
    # POST REQUESTS
    # ----------------------------------

    def do_POST(self):

        if self.path != "/v1/chat/completions":

            self.send_json(404, {
                "error": "Endpoint not found"
            })
            return

        try:

            content_length = int(
                self.headers.get("Content-Length", 0)
            )

            if content_length <= 0 or content_length > 1_000_000:

                self.send_json(400, {
                    "error": "Invalid request body size"
                })
                return

            payload = json.loads(
                self.rfile.read(content_length)
            )

            if not isinstance(payload, dict):

                self.send_json(400, {
                    "error": "Request body must be a JSON object"
                })
                return

        except (ValueError, json.JSONDecodeError):

            self.send_json(400, {
                "error": "Invalid JSON request"
            })
            return

        # Submit request to queue
        future = manager.submit(
            forward_to_simulator,
            payload
        )

        if future is None:

            self.send_json(
                503,
                {
                    "error": {
                        "message": "Relay queue is full",
                        "type": "queue_full"
                    }
                },
                headers={
                    "Retry-After": "1"
                }
            )
            return

        try:

            status_code, result, response_headers = (
                future.result(timeout=180)
            )

            self.send_json(
                status_code,
                result,
                headers=response_headers
            )

        except TimeoutError:

            self.send_json(504, {
                "error": "Model request timed out"
            })

        except Exception as error:

            self.send_json(500, {
                "error": str(error)
            })


# ----------------------------------
# START RELAY SERVER
# ----------------------------------

if __name__ == "__main__":

    server = ThreadingHTTPServer(
        (HOST, PORT),
        RelayHandler
    )

    print("=" * 50)
    print("THE RELAY API SERVER")
    print("=" * 50)

    print("Address:", f"http://{HOST}:{PORT}")
    print("Simulator:", SIMULATOR_URL)
    print("Workers:", WORKERS)
    print("Queue capacity:", QUEUE_CAPACITY)
    print("Maximum retries:", MAX_RETRIES)

    print("\nRelay server is running.")
    print("Press CTRL+C to stop.")

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print("\nStopping Relay server...")

    finally:

        server.server_close()
        manager.shutdown()

        print("Relay server stopped.")
