
import time

from queue_manager import QueueManager


def simulated_task(request_id):

    time.sleep(1)

    return f"Request {request_id} completed"


if __name__ == "__main__":

    manager = QueueManager(
        workers=3,
        max_queue_size=5
    )

    futures = []

    start = time.perf_counter()

    print("\nSubmitting 15 requests...\n")

    for i in range(1, 16):

        future = manager.submit(
            simulated_task,
            i
        )

        if future is not None:
            futures.append(future)

    manager.shutdown()

    total_time = time.perf_counter() - start

    print("\n--- QUEUE PERFORMANCE REPORT ---")

    for future in futures:

        print(future.result())

    metrics = manager.get_metrics()

    for key, value in metrics.items():
        print(f"{key}: {value}")

    print("Total execution time:", round(total_time, 2), "seconds")
