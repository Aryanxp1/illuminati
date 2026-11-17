"""
🌉 ILLUMINATI — WEBSOCKET PTY TERMINAL BRIDGE
Platform: Cross-platform (Windows ConPTY via winpty + Linux POSIX pty via openpty)
Author: Aryan Vishwakarma (@Aryanxp1)
Security: Isolated session manager, command allowlist, process sandbox, output secret redaction.
"""

import os
import sys
import time
import re
import signal
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("terminal_bridge")
logger.setLevel(logging.INFO)

ROOT_DIR = Path(__file__).resolve().parent.parent
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        import winpty
    except ImportError:
        winpty = None
else:
    import pty
    import fcntl
    import termios
    import struct
    import subprocess

# ── Security & Resource Limits ──────────────────────────────────────────────
MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_TERMINAL_SESSIONS", "5"))
IDLE_TIMEOUT_SECONDS = int(os.getenv("TERMINAL_IDLE_TIMEOUT", "300"))     # 5 min idle
MAX_SESSION_DURATION_SECONDS = int(os.getenv("TERMINAL_MAX_DURATION", "900")) # 15 min max
MAX_RATE_LIMIT_CHARS_PER_SEC = 2048                                      # Flooding guard

# ── Credential & Secret Redaction Regexes ──────────────────────────────────
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"tvly-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"bf-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{30,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{25,}"),
]

def sanitize_output(text: str) -> str:
    """Scrub sensitive API tokens or secrets from the terminal output stream."""
    if not text:
        return text
    clean = text
    clean = re.sub(r"sk-[a-zA-Z0-9_\-]{15,}", "sk-***[REDACTED]***", clean)
    clean = re.sub(r"tvly-[a-zA-Z0-9_\-]{15,}", "tvly-***[REDACTED]***", clean)
    clean = re.sub(r"bf-[a-zA-Z0-9_\-]{15,}", "bf-***[REDACTED]***", clean)
    clean = re.sub(r"ghp_[a-zA-Z0-9]{20,}", "ghp_***[REDACTED]***", clean)
    clean = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]{25,}", "Bearer [REDACTED]", clean)
    return clean

def get_sanitized_env() -> Dict[str, str]:
    """Build a hardened, isolated environment dictionary for the child process."""
    # Allowlist standard system and python runtime variables
    allowed_keys = {
        "PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
        "USERPROFILE", "HOME", "LANG", "LC_ALL", "PYTHONPATH", "SHELL",
        "BIFROST_OFFLINE_MODE", "TAVILY_MOCK_MODE", "HOST", "PORT",
        "MOCK_MODE", "BIFROST_URL", "BIFROST_API_KEY", "TAVILY_API_KEY",
        "OPENROUTER_API_KEY", "DEFAULT_TOKEN_BUDGET", "DEFAULT_MAX_COST_USD"
    }
    
    env: Dict[str, str] = {}
    for k, v in os.environ.items():
        if k in allowed_keys:
            env[k] = v

    # Enforce terminal & color capabilities
    env["FORCE_COLOR"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    
    # Ensure ROOT_DIR is in PYTHONPATH
    existing_pp = env.get("PYTHONPATH", "")
    if str(ROOT_DIR) not in existing_pp:
        env["PYTHONPATH"] = f"{ROOT_DIR}{os.pathsep}{existing_pp}" if existing_pp else str(ROOT_DIR)

    return env


class PTYSession:
    """Cross-platform pseudo-terminal wrapper for interactive Illuminati CLI."""
    def __init__(self, session_id: str, cols: int = 100, rows: int = 30):
        self.session_id = session_id
        self.cols = max(20, min(cols, 300))
        self.rows = max(10, min(rows, 100))
        self.created_at = time.time()
        self.last_active_at = time.time()
        self.pid: Optional[int] = None
        self._is_alive = False
        
        # Windows ConPTY
        self._winpty_pty = None
        
        # Linux POSIX PTY
        self._master_fd: Optional[int] = None
        self._proc = None

    def start(self):
        """Spawns the real Illuminati CLI `main.py chat` inside the pseudo-terminal."""
        clean_env = get_sanitized_env()

        if IS_WINDOWS:
            if winpty is None:
                raise RuntimeError("pywinpty is required on Windows platform.")
            
            self._winpty_pty = winpty.PTY(self.cols, self.rows)
            # winpty requires null-separated env string ending in double null
            env_str = "\0".join(f"{k}={v}" for k, v in clean_env.items()) + "\0\0"
            self._winpty_pty.spawn(
                sys.executable,
                "-u main.py chat",
                cwd=str(ROOT_DIR),
                env=env_str
            )
            self.pid = self._winpty_pty.pid
            self._is_alive = True
            logger.info(f"Spawned Windows PTY session {self.session_id} (PID {self.pid})")
        else:
            # POSIX / Linux (Render)
            master_fd, slave_fd = pty.openpty()
            self._master_fd = master_fd

            # Set initial terminal window size
            winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

            # Set master_fd to non-blocking
            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Spawn child process running Illuminati CLI
            cmd = [sys.executable, "-u", "main.py", "chat"]
            self._proc = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                preexec_fn=os.setsid,
                close_fds=True,
                env=clean_env,
                cwd=str(ROOT_DIR)
            )
            # Close slave fd in parent process so EOF propagates cleanly
            os.close(slave_fd)
            self.pid = self._proc.pid
            self._is_alive = True
            logger.info(f"Spawned Linux PTY session {self.session_id} (PID {self.pid})")

    async def read(self) -> str:
        """Reads available output string from the PTY asynchronously."""
        if not self.is_alive():
            return ""

        if IS_WINDOWS:
            try:
                # winpty.read(False) is non-blocking
                data = await asyncio.to_thread(self._winpty_pty.read, False)
                return data or ""
            except Exception as e:
                logger.debug(f"Winpty read error on {self.session_id}: {e}")
                self._is_alive = False
                return ""
        else:
            # Linux reading
            try:
                def _do_posix_read():
                    try:
                        raw = os.read(self._master_fd, 4096)
                        return raw.decode("utf-8", errors="replace")
                    except (BlockingIOError, InterruptedError):
                        return ""
                    except OSError:
                        # EIO indicates EOF (child exited)
                        return None
                
                res = await asyncio.to_thread(_do_posix_read)
                if res is None:
                    self._is_alive = False
                    return ""
                return res
            except Exception as e:
                logger.debug(f"POSIX read error on {self.session_id}: {e}")
                self._is_alive = False
                return ""

    async def write(self, data: str):
        """Writes text / keystrokes into the child CLI stdin."""
        if not self.is_alive() or not data:
            return
        
        self.last_active_at = time.time()

        if IS_WINDOWS:
            try:
                await asyncio.to_thread(self._winpty_pty.write, data)
            except Exception as e:
                logger.debug(f"Winpty write error on {self.session_id}: {e}")
                self._is_alive = False
        else:
            try:
                raw = data.encode("utf-8")
                await asyncio.to_thread(os.write, self._master_fd, raw)
            except Exception as e:
                logger.debug(f"POSIX write error on {self.session_id}: {e}")
                self._is_alive = False

    def resize(self, cols: int, rows: int):
        """Updates terminal window dimensions."""
        self.cols = max(20, min(cols, 300))
        self.rows = max(10, min(rows, 100))
        
        if not self.is_alive():
            return

        if IS_WINDOWS:
            try:
                self._winpty_pty.set_size(self.cols, self.rows)
            except Exception as e:
                logger.debug(f"Winpty resize error: {e}")
        else:
            if self._master_fd is not None:
                try:
                    winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
                    fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
                except Exception as e:
                    logger.debug(f"POSIX resize error: {e}")

    def is_alive(self) -> bool:
        """Checks whether the underlying PTY and process are running."""
        if not self._is_alive:
            return False

        if IS_WINDOWS:
            if self._winpty_pty is None:
                self._is_alive = False
                return False
            alive = self._winpty_pty.isalive()
            if not alive:
                self._is_alive = False
            return alive
        else:
            if self._proc is None:
                self._is_alive = False
                return False
            poll = self._proc.poll()
            if poll is not None:
                self._is_alive = False
                return False
            return True

    def close(self):
        """Terminates child process and cleans up file descriptors."""
        self._is_alive = False
        logger.info(f"Closing PTY session {self.session_id} (PID {self.pid})")

        if IS_WINDOWS:
            if self._winpty_pty is not None:
                try:
                    self._winpty_pty.cancel_io()
                except Exception:
                    pass
                try:
                    if self.pid:
                        os.kill(self.pid, signal.SIGTERM)
                except Exception:
                    pass
                self._winpty_pty = None
        else:
            if self._proc is not None:
                try:
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                except Exception:
                    try:
                        self._proc.terminate()
                    except Exception:
                        pass
                self._proc = None

            if self._master_fd is not None:
                try:
                    os.close(self._master_fd)
                except Exception:
                    pass
                self._master_fd = None


class TerminalSessionManager:
    """Manages active WebSocket terminal sessions, lifecycle, and limits."""
    def __init__(self, max_sessions: int = MAX_CONCURRENT_SESSIONS):
        self.max_sessions = max_sessions
        self.active_sessions: Dict[str, PTYSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, session_id: str, cols: int = 100, rows: int = 30) -> PTYSession:
        """Creates and starts a new PTY session, enforcing capacity limits."""
        async with self._lock:
            # First clean dead sessions
            dead_ids = [sid for sid, s in self.active_sessions.items() if not s.is_alive()]
            for sid in dead_ids:
                s = self.active_sessions.pop(sid, None)
                if s:
                    s.close()

            if len(self.active_sessions) >= self.max_sessions:
                raise RuntimeError(
                    f"Server terminal capacity reached ({len(self.active_sessions)}/{self.max_sessions}). "
                    "Please wait for an existing session to finish or try again in a few moments."
                )

            session = PTYSession(session_id=session_id, cols=cols, rows=rows)
            session.start()
            self.active_sessions[session_id] = session
            return session

    async def remove_session(self, session_id: str):
        """Closes and unregisters a session."""
        async with self._lock:
            session = self.active_sessions.pop(session_id, None)
            if session:
                session.close()

    def get_session(self, session_id: str) -> Optional[PTYSession]:
        return self.active_sessions.get(session_id)

    def active_count(self) -> int:
        return len([s for s in self.active_sessions.values() if s.is_alive()])

    def close_all(self):
        """Shuts down all active PTY processes (called during app lifespan shutdown)."""
        logger.info(f"Shutting down all {len(self.active_sessions)} active terminal sessions")
        for session in list(self.active_sessions.values()):
            session.close()
        self.active_sessions.clear()

# Global manager instance
terminal_manager = TerminalSessionManager()
