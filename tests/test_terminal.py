"""
Tests for Illuminati Browser CLI Terminal & WebSocket PTY Bridge
Author: Aryan Vishwakarma (@Aryanxp1)
"""

import sys
import time
import json
import asyncio
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.terminal_bridge import (
    sanitize_output,
    get_sanitized_env,
    PTYSession,
    TerminalSessionManager,
    terminal_manager,
    IDLE_TIMEOUT_SECONDS,
    MAX_SESSION_DURATION_SECONDS
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_terminal_page_serves_html(client):
    """Verify that GET /terminal returns the HTML page with xterm.js assets."""
    response = client.get("/terminal")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    content = response.text
    assert "xterm" in content
    assert "ILLUMINATI" in content
    assert "/ws/terminal" in content


def test_terminal_stats_api(client):
    """Verify GET /api/terminal/stats returns live telemetry and limits."""
    response = client.get("/api/terminal/stats")
    assert response.status_code == 200
    data = response.json()
    assert "active_sessions" in data
    assert "max_sessions" in data
    assert data["max_sessions"] >= 1
    assert data["idle_timeout_seconds"] == IDLE_TIMEOUT_SECONDS
    assert data["max_duration_seconds"] == MAX_SESSION_DURATION_SECONDS


def test_secret_redaction():
    """Verify that sensitive API tokens and credentials are intercepted and masked."""
    # Test OpenAI-style keys
    leak_sk = "Error with key sk-proj-1234567890abcdef1234567890 in gateway"
    clean_sk = sanitize_output(leak_sk)
    assert "sk-***[REDACTED]***" in clean_sk
    assert "sk-proj-1234567890" not in clean_sk

    # Test Tavily keys
    leak_tv = "Using Tavily key tvly-live-secretkey1234567890abc"
    clean_tv = sanitize_output(leak_tv)
    assert "tvly-***[REDACTED]***" in clean_tv
    assert "tvly-live-secretkey" not in clean_tv

    # Test Bifrost keys
    leak_bf = "Bifrost token: bf-99887766554433221100aabb"
    clean_bf = sanitize_output(leak_bf)
    assert "bf-***[REDACTED]***" in clean_bf

    # Test Bearer tokens
    leak_bearer = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIi"
    clean_bearer = sanitize_output(leak_bearer)
    assert "[REDACTED]" in clean_bearer


def test_sanitized_environment():
    """Verify child process environment is properly isolated and has required term vars."""
    env = get_sanitized_env()
    assert env.get("FORCE_COLOR") == "1"
    assert env.get("PYTHONUNBUFFERED") == "1"
    assert env.get("TERM") == "xterm-256color"
    assert env.get("COLORTERM") == "truecolor"
    # Ensure sensitive system keys are absent
    for sensitive_key in ["AWS_SECRET_ACCESS_KEY", "RENDER_GIT_COMMIT", "PRIVATE_KEY"]:
        assert sensitive_key not in env


def test_pty_session_lifecycle():
    """Verify spawning real CLI in PTY, reading initial banner, resizing, and clean exit."""
    async def _test():
        session = PTYSession(session_id="test-lifecycle-01", cols=80, rows=24)
        session.start()
        try:
            assert session.is_alive()
            assert session.pid is not None

            # Give PTY time to launch and output initial ANSI banner
            collected = []
            for _ in range(30):
                data = await session.read()
                if data:
                    collected.append(data)
                    if any("ILLUMINATI" in c or "Providence" in c or "illuminati" in c for c in collected):
                        break
                await asyncio.sleep(0.05)

            total_output = "".join(collected)
            assert len(total_output) > 0, "Expected initial output from CLI REPL"

            # Test terminal resize
            session.resize(cols=100, rows=30)
            assert session.cols == 100
            assert session.rows == 30

            # Test writing input
            await session.write("/help\r")
        finally:
            session.close()
            assert not session.is_alive()

    asyncio.run(_test())


def test_session_manager_concurrency_cap():
    """Verify session manager enforces max_sessions limit and rejects excess."""
    async def _test():
        manager = TerminalSessionManager(max_sessions=1)
        s1 = await manager.create_session("sess-1", cols=80, rows=24)
        assert manager.active_count() == 1

        try:
            with pytest.raises(RuntimeError) as exc_info:
                await manager.create_session("sess-2", cols=80, rows=24)
            assert "capacity reached" in str(exc_info.value).lower()
        finally:
            await manager.remove_session("sess-1")
            assert manager.active_count() == 0

    asyncio.run(_test())


def test_websocket_terminal_interaction(client):
    """Verify WebSocket connection, banner delivery, ping/pong, and clean disconnect."""
    with client.websocket_connect("/ws/terminal?cols=80&rows=24") as ws:
        # 1. Receive initial output chunk (banner/prompt from CLI)
        received_chunks = []
        start_time = time.time()
        while time.time() - start_time < 3.0:
            try:
                chunk = ws.receive_text()
                if chunk:
                    received_chunks.append(chunk)
                    if len(received_chunks) >= 2:
                        break
            except Exception:
                break

        assert len(received_chunks) > 0, "WebSocket should receive CLI initial output"

        # 2. Test ping/pong frame
        ws.send_text(json.dumps({"type": "ping", "client_time": 12345}))
        pong_frame = ws.receive_text()
        pong_data = json.loads(pong_frame)
        assert pong_data.get("type") == "pong"
        assert pong_data.get("client_time") == 12345

        # 3. Test resize control frame
        ws.send_text(json.dumps({"type": "resize", "cols": 110, "rows": 32}))

        # 4. Test interactive command execution
        ws.send_text("/help\r")
        time.sleep(0.3)
