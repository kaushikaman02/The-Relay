
import queue
import threading
import time

from concurrent.futures import Future


class QueueManager:

    def __init__(self, workers=3, max_queue_size=5):

        self.request_queue = queue.Queue(maxsize=max_queue_size)

        self.workers = workers
        self.max_queue_size = max_queue_size

        self.completed = 0
        self.rejected = 0
        self.failed = 0

        self.total_wait_time = 0.0
        self.total_processing_time = 0.0

        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()

        self.threads = []

        for i in range(workers):

            thread = threading.Thread(
                target=self.worker,
                args=(i + 1,),
                daemon=True
            )

            thread.start()
            self.threads.append(thread)

        print("Queue Manager initialized")
        print("Workers:", workers)
        print("Queue capacity:", max_queue_size)

    def submit(self, task, *args, **kwargs):

        future = Future()

        request = {
            "task": task,
            "args": args,
            "kwargs": kwargs,
            "future": future,
            "submitted_at": time.perf_counter()
        }

        try:
            self.request_queue.put_nowait(request)

            print("Request accepted")

            return future

        except queue.Full:

            with self.lock:
                self.rejected += 1

            print("Request rejected: Queue full")

            return None

    def worker(self, worker_id):

        while True:

            request = self.request_queue.get()

            if request is None:
                self.request_queue.task_done()
                break

            future = request["future"]

            if not future.set_running_or_notify_cancel():
                self.request_queue.task_done()
                continue

            start = time.perf_counter()

            wait_time = start - request["submitted_at"]

            try:

                print(f"Worker {worker_id} processing request")

                result = request["task"](
                    *request["args"],
                    **request["kwargs"]
                )

                processing_time = time.perf_counter() - start

                future.set_result(result)

                with self.lock:
                    self.completed += 1
                    self.total_wait_time += wait_time
                    self.total_processing_time += processing_time

            except Exception as error:

                future.set_exception(error)

                with self.lock:
                    self.failed += 1
                    self.total_wait_time += wait_time
                    self.total_processing_time += (
                        time.perf_counter() - start
                    )

            finally:

                self.request_queue.task_done()

    def get_metrics(self):

        with self.lock:

            return {
                "workers": self.workers,
                "queue_capacity": self.max_queue_size,
                "queue_size": self.request_queue.qsize(),
                "completed": self.completed,
                "rejected": self.rejected,
                "failed": self.failed,
                "average_wait_ms": (
                    self.total_wait_time /
                    (self.completed + self.failed) * 1000
                    if self.completed + self.failed else 0
                ),
                "average_processing_ms": (
                    self.total_processing_time /
                    (self.completed + self.failed) * 1000
                    if self.completed + self.failed else 0
                )
            }

    def shutdown(self):

        self.shutdown_event.set()

        self.request_queue.join()

        for _ in self.threads:
            self.request_queue.put(None)

        for thread in self.threads:
            thread.join()

        print("Queue Manager stopped")
