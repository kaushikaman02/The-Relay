
import requests
import pytest

BASE_URL = "http://127.0.0.1:8001"

PAYLOAD = {
    "model": "test-model",
    "messages": [
        {
            "role": "user",
            "content": "Hello, this is a Relay integration test."
        }
    ]
}


@pytest.fixture(scope="module", autouse=True)
def check_relay_available():
    """Ensure the Relay server is running before integration tests."""
    try:
        response = requests.get(
            f"{BASE_URL}/health",
            timeout=5
        )
        response.raise_for_status()
    except requests.RequestException as error:
        pytest.fail(
            f"Relay server is unavailable at {BASE_URL}: {error}"
        )


def test_relay_health():
    response = requests.get(
        f"{BASE_URL}/health",
        timeout=10
    )

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_relay_model_request():
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json=PAYLOAD,
        timeout=70
    )

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_relay_queue_metrics():
    response = requests.get(
        f"{BASE_URL}/metrics",
        timeout=10
    )

    assert response.status_code == 200

    metrics = response.json()

    assert isinstance(metrics, dict)
    assert "workers" in metrics
    assert "queue_capacity" in metrics
    assert "completed" in metrics
    assert "rejected" in metrics
    assert "failed" in metrics
