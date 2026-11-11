
import threading

import pytest

from queue_manager import QueueManager


def add(a, b):
    return a + b


def failing_task():
    raise ValueError("Test failure")


def test_successful_task():
    manager = QueueManager(workers=2, max_queue_size=5)

    try:
        future = manager.submit(add, 10, 20)

        assert future is not None
        assert future.result(timeout=5) == 30

        metrics = manager.get_metrics()
        assert metrics["completed"] == 1
        assert metrics["failed"] == 0
    finally:
        manager.shutdown()


def test_failed_task():
    manager = QueueManager(workers=1, max_queue_size=5)

    try:
        future = manager.submit(failing_task)

        assert future is not None

        with pytest.raises(ValueError, match="Test failure"):
            future.result(timeout=5)

        metrics = manager.get_metrics()
        assert metrics["failed"] == 1
    finally:
        manager.shutdown()


def test_queue_full_rejects_request():
    manager = QueueManager(workers=1, max_queue_size=1)
    started = threading.Event()
    release = threading.Event()

    def blocking_task():
        started.set()
        release.wait(timeout=5)
        return "completed"

    try:
        first = manager.submit(blocking_task)
        assert first is not None
        assert started.wait(timeout=3)

        second = manager.submit(add, 1, 2)
        assert second is not None

        third = manager.submit(add, 3, 4)
        assert third is None

        assert manager.get_metrics()["rejected"] == 1

        release.set()

        assert first.result(timeout=5) == "completed"
        assert second.result(timeout=5) == 3
    finally:
        release.set()
        manager.shutdown()


def test_queue_metrics():
    manager = QueueManager(workers=2, max_queue_size=5)

    try:
        futures = [
            manager.submit(add, i, i)
            for i in range(5)
        ]

        assert all(future is not None for future in futures)

        results = [future.result(timeout=5) for future in futures]

        assert results == [0, 2, 4, 6, 8]

        metrics = manager.get_metrics()

        assert metrics["workers"] == 2
        assert metrics["queue_capacity"] == 5
        assert metrics["completed"] == 5
        assert metrics["queue_size"] == 0
        assert metrics["failed"] == 0
    finally:
        manager.shutdown()
