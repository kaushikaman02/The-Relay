
import requests
import pytest

BASE_URL = "http://127.0.0.1:8000"

PAYLOAD = {
    "model": "relay-simulator",
    "messages": [
        {
            "role": "user",
            "content": "Explain multi-head attention."
        }
    ],
    "stream": False
}


@pytest.fixture(scope="module", autouse=True)
def check_simulator_available():
    try:
        response = requests.get(
            f"{BASE_URL}/health",
            timeout=5
        )
        response.raise_for_status()
    except requests.RequestException as error:
        pytest.fail(
            f"Simulator is unavailable at {BASE_URL}: {error}"
        )


def test_simulator_health():
    response = requests.get(
        f"{BASE_URL}/health",
        timeout=10
    )

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_simulator_chat_completion():
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json=PAYLOAD,
        timeout=30
    )

    assert response.status_code == 200

    result = response.json()
    assert isinstance(result, dict)
    assert "choices" in result
    assert len(result["choices"]) > 0


def test_simulator_metrics():
    response = requests.get(
        f"{BASE_URL}/metrics",
        timeout=10
    )

    assert response.status_code == 200

    metrics = response.json()

    assert isinstance(metrics, dict)
    assert "daily_requests" in metrics
    assert "daily_tokens" in metrics
    assert "requests_last_minute" in metrics
