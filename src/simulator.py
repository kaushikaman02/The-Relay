
import json
import time
import random
import threading

from collections import deque
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------
# SIMULATOR CONFIGURATION
# ---------------------------------

HOST = "127.0.0.1"
PORT = 8000

# Calibrated from real Groq streaming experiment
BASE_FIRST_TOKEN_MS = 1026
CHUNK_DELAY_MS = 20

# Account limits
RPM_LIMIT = 300
TPM_LIMIT = 8000
RPD_LIMIT = 1000
TPD_LIMIT = 200000

# ---------------------------------
# SIMULATION CONTROLS
# ---------------------------------

# Random server failures
FAILURE_PROBABILITY = 0.02

# Controlled server failures
SIMULATE_FIRST_N_FAILURES = 0
simulated_failures_remaining = SIMULATE_FIRST_N_FAILURES

# Controlled rate-limit experiment
SIMULATE_FIRST_N_RATE_LIMITS = 0
rate_limit_failures_remaining = SIMULATE_FIRST_N_RATE_LIMITS

RETRY_AFTER_SECONDS = 2

# Performance settings
EXTRA_DELAY_PER_REQUEST_MS = 100
MAX_IN_FLIGHT = 20

# ---------------------------------
# GLOBAL STATE
# ---------------------------------

lock = threading.Lock()

request_times = deque()

daily_requests = 0
daily_tokens = 0
daily_date = date.today()

in_flight = 0


# ---------------------------------
# TOKEN ESTIMATION
# ---------------------------------

def estimate_tokens(text):
    return max(1, len(text.split()))


# ---------------------------------
# DAILY COUNTER RESET
# ---------------------------------

def reset_daily_counters():

    global daily_requests
    global daily_tokens
    global daily_date

    if date.today() != daily_date:

        daily_requests = 0
        daily_tokens = 0
        daily_date = date.today()


# ---------------------------------
# HTTP SIMULATOR HANDLER
# ---------------------------------

class SimulatorHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print("[SIMULATOR]", format % args)

    # ---------------------------------
    # JSON RESPONSE
    # ---------------------------------

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

                self.send_header(
                    name,
                    str(value)
                )

        self.end_headers()

        self.wfile.write(body)

    # ---------------------------------
    # HEALTH CHECK
    # ---------------------------------

    def do_GET(self):

        if self.path == "/health":

            self.send_json(200, {
                "status": "running",
                "service": "The Relay Stand-in"
            })


        elif self.path == "/metrics":

         with lock:

          now = time.monotonic()

        while request_times and now - request_times[0] >= 60:
            request_times.popleft()

        metrics = {
            "daily_requests": daily_requests,
            "daily_tokens": daily_tokens,
            "requests_last_minute": len(request_times),
            "in_flight": in_flight,
            "rate_limits_remaining": max(0, RPM_LIMIT - len(request_times)),
            "forced_failures_remaining": simulated_failures_remaining
        }

        self.send_json(200, metrics)


    # ---------------------------------
    # CHAT COMPLETION ENDPOINT
    # ---------------------------------

    def do_POST(self):

        global daily_requests
        global daily_tokens
        global in_flight
        global simulated_failures_remaining
        global rate_limit_failures_remaining

        if self.path != "/v1/chat/completions":

            self.send_json(404, {
                "error": "Unknown endpoint"
            })

            return

        # ---------------------------------
        # READ REQUEST
        # ---------------------------------

        try:

            length = int(
                self.headers.get("Content-Length", 0)
            )

            if length <= 0 or length > 1_000_000:

                self.send_json(400, {
                    "error": "Invalid request body size"
                })

                return

            payload = json.loads(
                self.rfile.read(length)
            )

            if not isinstance(payload, dict):

                self.send_json(400, {
                    "error": "Request must be a JSON object"
                })

                return

            messages = payload.get("messages", [])

            user_text = " ".join(
                str(message.get("content", ""))
                for message in messages
                if isinstance(message, dict)
            )

            input_tokens = estimate_tokens(user_text)

        except (ValueError, TypeError):

            self.send_json(400, {
                "error": "Invalid JSON request"
            })

            return

        # ---------------------------------
        # RATE LIMIT CHECKS
        # ---------------------------------

        with lock:

            reset_daily_counters()

            now = time.monotonic()

            while (
                request_times
                and now - request_times[0] >= 60
            ):

                request_times.popleft()

            # Controlled HTTP 429 experiment
            if rate_limit_failures_remaining > 0:

                rate_limit_failures_remaining -= 1

                print(
                    "[SIMULATOR] Forced HTTP 429"
                )

                self.send_json(
                    429,
                    {
                        "error": {
                            "message": "Simulated rate limit exceeded",
                            "type": "rate_limit_error"
                        }
                    },
                    headers={
                        "Retry-After": RETRY_AFTER_SECONDS
                    }
                )

                return

            # Requests per minute
            if len(request_times) >= RPM_LIMIT:

                self.send_json(
                    429,
                    {
                        "error": {
                            "message": "Requests per minute limit reached",
                            "type": "rate_limit_error"
                        }
                    },
                    headers={
                        "Retry-After": 60
                    }
                )

                return

            # Requests per day
            if daily_requests >= RPD_LIMIT:

                self.send_json(
                    429,
                    {
                        "error": {
                            "message": "Daily request budget exhausted",
                            "type": "daily_limit_error"
                        }
                    }
                )

                return

            # Token limits
            if (
                input_tokens > TPM_LIMIT
                or daily_tokens + input_tokens > TPD_LIMIT
            ):

                self.send_json(
                    429,
                    {
                        "error": {
                            "message": "Token budget exhausted",
                            "type": "token_limit_error"
                        }
                    }
                )

                return

            request_times.append(now)

            daily_requests += 1
            daily_tokens += input_tokens

            in_flight += 1

            current_load = in_flight

        # ---------------------------------
        # PROCESS REQUEST
        # ---------------------------------

        try:

            # Simulated server failures

            with lock:

                force_failure = (
                    simulated_failures_remaining > 0
                )

                if force_failure:

                    simulated_failures_remaining -= 1

            if (
                force_failure
                or random.random() < FAILURE_PROBABILITY
            ):

                time.sleep(0.2)

                self.send_json(503, {
                    "error": {
                        "message": "Simulated service unavailable",
                        "type": "server_error"
                    }
                })

                return

            # ---------------------------------
            # CAPACITY CHECK
            # ---------------------------------

            if current_load > MAX_IN_FLIGHT:

                self.send_json(503, {
                    "error": {
                        "message": "Simulator capacity exceeded",
                        "type": "overload_error"
                    }
                })

                return

            print(
                "[SIMULATOR] Active requests:",
                current_load
            )

            # ---------------------------------
            # SIMULATE LATENCY
            # ---------------------------------

            first_token_delay = (
                BASE_FIRST_TOKEN_MS
                + max(0, current_load - 1)
                * EXTRA_DELAY_PER_REQUEST_MS
            )

            time.sleep(
                first_token_delay / 1000
            )

            answer = (
                "This is a simulated research assistant response. "
                "The stand-in service reproduces latency and traffic "
                "behavior but does not perform real model reasoning."
            )

            output_tokens = estimate_tokens(answer)

            with lock:

                if (
                    daily_tokens + output_tokens
                    > TPD_LIMIT
                ):

                    self.send_json(429, {
                        "error": {
                            "message": "Daily token budget exhausted",
                            "type": "token_limit_error"
                        }
                    })

                    return

                daily_tokens += output_tokens

            usage = {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            }

            # ---------------------------------
            # STREAMING RESPONSE
            # ---------------------------------

            if payload.get("stream", False):

                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    "text/event-stream"
                )

                self.send_header(
                    "Cache-Control",
                    "no-cache"
                )

                self.send_header(
                    "Connection",
                    "close"
                )

                self.end_headers()

                words = answer.split()

                for i in range(0, len(words), 5):

                    piece = " ".join(
                        words[i:i + 5]
                    ) + " "

                    chunk = {
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "content": piece
                            },
                            "finish_reason": None
                        }]
                    }

                    event = (
                        "data: "
                        + json.dumps(chunk)
                        + "\n\n"
                    ).encode("utf-8")

                    self.wfile.write(event)
                    self.wfile.flush()

                    time.sleep(
                        CHUNK_DELAY_MS / 1000
                    )

                final_chunk = {
                    "choices": [],
                    "usage": usage
                }

                event = (
                    "data: "
                    + json.dumps(final_chunk)
                    + "\n\n"
                ).encode("utf-8")

                self.wfile.write(event)
                self.wfile.write(
                    b"data: [DONE]\n\n"
                )

                self.wfile.flush()

            # ---------------------------------
            # NORMAL JSON RESPONSE
            # ---------------------------------

            else:

                self.send_json(200, {
                    "id": "relay-simulated",
                    "object": "chat.completion",
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": answer
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": usage
                })

        except (BrokenPipeError, ConnectionResetError):

            print("[SIMULATOR] Client disconnected")

        except Exception as error:

            print(
                "[SIMULATOR] Error:",
                str(error)
            )

            try:

                self.send_json(500, {
                    "error": str(error)
                })

            except Exception:
                pass

        finally:

            with lock:
                in_flight -= 1


# ---------------------------------
# START SIMULATOR
# ---------------------------------

if __name__ == "__main__":

    server = ThreadingHTTPServer(
        (HOST, PORT),
        SimulatorHandler
    )

    print("=" * 55)
    print("THE RELAY - STAND-IN MODEL SERVICE")
    print("=" * 55)

    print("Address:", f"http://{HOST}:{PORT}")

    print("RPM:", RPM_LIMIT)
    print("TPM:", TPM_LIMIT)
    print("RPD:", RPD_LIMIT)
    print("TPD:", TPD_LIMIT)

    print(
        "Base first-token delay:",
        BASE_FIRST_TOKEN_MS,
        "ms"
    )

    print(
        "Random failure probability:",
        FAILURE_PROBABILITY
    )

    print(
        "Forced server failures:",
        SIMULATE_FIRST_N_FAILURES
    )

    print(
        "Forced rate limits:",
        SIMULATE_FIRST_N_RATE_LIMITS
    )

    print(
        "Retry-After:",
        RETRY_AFTER_SECONDS,
        "seconds"
    )

    print(
        "Maximum in-flight requests:",
        MAX_IN_FLIGHT
    )

    print("\nSimulator is running.")
    print("Press CTRL+C to stop.")

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print("\nStopping simulator...")

    finally:

        server.server_close()

        print("Simulator stopped.")
