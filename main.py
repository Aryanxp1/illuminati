#!/usr/bin/env python3
"""
🌌 ILLUMINATI — UNIFIED AUTONOMOUS AI AGENT & RELIABILITY OBSERVATORY
Geek Room AI Global Hackathon
Team: Illuminati | Author: Aryan Vishwakarma (@Aryanxp1)

Satisfies All Problem Statements:
- Bifrost Priority Track PS 01: Coding Agent on Fewest Tokens
- Bifrost Priority Track PS 02: AgentBench Arena (Agent Benchmarking Platform)
- Tavily Track PS 01: Stale-Answer Detector & Freshness Scoring
- Tavily Track PS 02: Pre-Meeting Briefing Intelligence Agent
"""

import os
import sys
import types
import uuid
import asyncio
import argparse
from datetime import UTC, datetime

# Windows Defender Application Control compatibility guard:
try:
    import _multiprocessing
except (ImportError, OSError):
    mock_mp = types.ModuleType("_multiprocessing")
    mock_mp.closesocket = lambda fd: None
    mock_mp.send = lambda fd, buf, flags=0: None
    mock_mp.recv = lambda fd, size, flags=0: b""
    sys.modules["_multiprocessing"] = mock_mp

# Ensure project root is in python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

BANNER = r"""
======================================================================
                                  ▲
                                 • •
                                •   •
                               •     •
                              •       •
                             •  •••••  •
                            •   •   •   •
                           •  •••   •••  •
                          •  ◖ • (●) • ◗  •
                         •    •••   •••    •
                        •       •   •       •
                       •        •••••        •
                      •                       •
                     •••••••••••••••••••••••••••
                    •••••••••••••••••••••••••••••

               ✦  E Y E   O F   P R O V I D E N C E  ✦

 ██╗██╗     ██╗     ██╗   ██╗███╗   ███╗██╗███╗   ██╗ █████╗ ████████╗██╗
 ██║██║     ██║     ██║   ██║████╗ ████║██║████╗  ██║██╔══██╗╚══██╔══╝██║
 ██║██║     ██║     ██║   ██║██╔████╔██║██║██╔██╗ ██║███████║   ██║   ██║
 ██║██║     ██║     ██║   ██║██║╚██╔╝██║██║██║╚██╗██║██╔══██║   ██║   ██║
 ██║███████╗███████╗╚██████╔╝██║ ╚═╝ ██║██║██║ ╚████║██║  ██║   ██║   ██║
 ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝   ╚═╝
   AUTONOMOUS AI AGENT & RELIABILITY OBSERVATORY · BIFROST × TAVILY
======================================================================
 Team: Illuminati | Author: Aryan Vishwakarma (@Aryanxp1)
 Hackathon: Geek Room AI Global Hackathon
 Partners: Bifrost by Maxim AI & Tavily by Nebius
======================================================================
"""

def run_server(host: str = None, port: int = None, reload: bool = False):
    host = host or os.getenv("HOST", "0.0.0.0")
    if port is None:
        port = int(os.getenv("PORT", 8000))
    import uvicorn
    print(BANNER)
    print(f" 🚀 Web Observatory Dashboard: http://{host}:{port}")
    print(f"    ⚡ 1. Token-Governed Coding Agent     -> http://{host}:{port}/#coding")
    print(f"    ⚔️ 2. AgentBench Arena & Duels        -> http://{host}:{port}/#arena")
    print(f"    🛡️ 3. StaleGuard Freshness Detector   -> http://{host}:{port}/#freshness")
    print(f"    📋 4. Pre-Meeting Briefing Agent      -> http://{host}:{port}/#briefing")
    print(f"    🔌 5. Unified Gateway Status          -> http://{host}:{port}/api/gateway/status")
    print("=" * 70 + "\n")
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)

async def run_cli_code(prompt: str):
    from backend.modules.coding_agent.cli_ui import render_banner, execute_and_render, run_interactive_repl
    if not prompt or prompt == "__INTERACTIVE__":
        await run_interactive_repl()
    else:
        render_banner()
        await execute_and_render(prompt)

async def run_cli_freshness(text: str):
    from backend.modules.coding_agent.cli_ui import render_banner, execute_staleguard_check
    render_banner()
    await execute_staleguard_check(text)

async def run_cli_brief(target: str):
    from backend.modules.coding_agent.cli_ui import render_banner, execute_briefing
    render_banner()
    await execute_briefing(target)

def main():
    # Direct natural command routing (e.g. main.py check "...", main.py brief "...", main.py code "...", main.py bench)
    if len(sys.argv) > 1:
        first_cmd = sys.argv[1].lower()
        if first_cmd in ("chat", "--chat", "repl", "interactive"):
            asyncio.run(run_cli_code("__INTERACTIVE__"))
            return
        elif first_cmd in ("check", "--check-freshness"):
            claim = " ".join(sys.argv[2:]).strip().strip("'").strip('"') if len(sys.argv) > 2 else ""
            asyncio.run(run_cli_freshness(claim))
            return
        elif first_cmd in ("brief", "--brief"):
            target = " ".join(sys.argv[2:]).strip().strip("'").strip('"') if len(sys.argv) > 2 else "Anthropic"
            asyncio.run(run_cli_brief(target))
            return
        elif first_cmd in ("code", "--code"):
            prompt = " ".join(sys.argv[2:]).strip().strip("'").strip('"') if len(sys.argv) > 2 else "__INTERACTIVE__"
            asyncio.run(run_cli_code(prompt))
            return
        elif first_cmd in ("bench", "--suite", "benchmark", "suite"):
            from backend.modules.coding_agent.cli_ui import render_banner, execute_benchmark
            sub = sys.argv[2].lower() if len(sys.argv) > 2 else ""
            render_banner()
            asyncio.run(execute_benchmark(sub))
            return
        elif first_cmd in ("serve", "--serve", "server"):
            run_server()
            return

    parser = argparse.ArgumentParser(description="Illuminati: Unified Autonomous AI Agent & Reliability Observatory")
    parser.add_argument("--serve", action="store_true", help="Start the unified web server and dashboard (default)")
    parser.add_argument("--host", type=str, default=os.getenv("HOST", "0.0.0.0"), help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)), help="Server port (default: 8000 or $PORT)")
    parser.add_argument("--reload", action="store_true", default=False, help="Enable auto-reload")
    
    # CLI commands for individual Problem Statements
    parser.add_argument("--code", type=str, nargs="?", const="__INTERACTIVE__", help="Run coding agent on a prompt, or enter interactive chat mode if no prompt is given")
    parser.add_argument("--chat", action="store_true", help="Start interactive conversational coding agent session (Claude Code / Antigravity style)")
    parser.add_argument("--check-freshness", type=str, help="Run Stale-Answer Freshness Detector (Tavily PS 01) on text")
    parser.add_argument("--brief", type=str, help="Run Pre-Meeting Briefing Agent (Tavily PS 02) for an entity")
    parser.add_argument("--suite", type=str, help="Run AgentBench Arena (Bifrost PS 02) benchmark suite")

    args, unknown = parser.parse_known_args()

    if args.chat or (args.code == "__INTERACTIVE__"):
        asyncio.run(run_cli_code("__INTERACTIVE__"))
    elif args.code:
        asyncio.run(run_cli_code(args.code))
    elif args.check_freshness:
        asyncio.run(run_cli_freshness(args.check_freshness))
    elif args.brief:
        asyncio.run(run_cli_brief(args.brief))
    elif args.suite:
        from backend.modules.coding_agent.cli_ui import render_banner, execute_benchmark
        render_banner()
        asyncio.run(execute_benchmark(args.suite))
    else:
        run_server(host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
