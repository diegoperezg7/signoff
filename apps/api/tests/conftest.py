import os
import time

import pytest

# Agents and verification runs pace themselves for the demo; tests run instantly.
os.environ.setdefault("SIGNOFF_AGENT_STEP_DELAY", "0")
os.environ.setdefault("SIGNOFF_RUN_DELAY", "0")


def wait_for_run(client, run_id: str, timeout: float = 5.0) -> dict:
    """Poll an agent run until it leaves the queued/running states."""
    deadline = time.monotonic() + timeout
    while True:
        body = client.get(f"/api/v1/agent-runs/{run_id}").json()
        if body["status"] not in {"queued", "running"} or time.monotonic() > deadline:
            return body
        time.sleep(0.02)


@pytest.fixture
def fresh_store():
    from app.main import reset_demo_state

    reset_demo_state()
    yield
    reset_demo_state()
