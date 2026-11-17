"""
Regression and Integration Tests for Illuminati Platform APIs
Author: Aryan Vishwakarma (@Aryanxp1)
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_dashboard_endpoint(client):
    """Verify GET / serves frontend index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "ILLUMINATI" in response.text

def test_gateway_status_endpoint(client):
    """Verify unified gateway telemetry endpoint."""
    response = client.get("/api/gateway/status")
    assert response.status_code == 200
    data = response.json()
    assert "bifrost" in data
    assert "tavily" in data
    assert data["author"] == "Aryan Vishwakarma (@Aryanxp1)"

def test_system_stats_endpoint(client):
    """Verify aggregated platform statistics."""
    response = client.get("/api/system/stats")
    assert response.status_code == 200
    data = response.json()
    assert "engines" in data
    assert "bifrost_ps01_coding_agent" in data["engines"]
    assert "bifrost_ps02_agentbench_arena" in data["engines"]
    assert "tavily_ps01_freshness_detector" in data["engines"]
    assert "tavily_ps02_pre_meeting_briefing" in data["engines"]

def test_coding_agent_api(client):
    """Verify Bifrost PS 01: Coding Agent execution and token receipt."""
    payload = {
        "prompt": "Implement binary search in Python",
        "token_budget": 8000,
        "max_cost_usd": 0.05
    }
    response = client.post("/api/coding-agent/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "diff" in data or "code" in data or "response" in data
    assert "receipt" in data
    assert "receipt_hash" in data["receipt"]
    assert data["receipt"]["total_tokens"] > 0

def test_freshness_detector_api(client):
    """Verify Tavily PS 01: StaleGuard freshness scoring."""
    payload = {
        "text": "Python 3.12 is the latest stable version of Python."
    }
    response = client.post("/api/freshness/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "status" in data

def test_pre_meeting_briefing_api(client):
    """Verify Tavily PS 02: Pre-meeting intelligence brief generation."""
    payload = {
        "target": "Anthropic",
        "purpose": "partnership"
    }
    response = client.post("/api/briefing/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "target" in data
    assert data["target"] == "Anthropic"
    assert "verified_stories" in data or "summary" in data

def test_arena_tasks_api(client):
    """Verify Bifrost PS 02: Arena tasks listing."""
    response = client.get("/api/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert isinstance(tasks, list)
    assert len(tasks) >= 5

def test_arena_agents_api(client):
    """Verify Bifrost PS 02: Reference agents listing."""
    response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()
    assert isinstance(agents, list)
    assert len(agents) >= 3
