# 🌌 Illuminati — Unified Autonomous AI Agent & Reliability Observatory

<p align="center">
  <b>Geek Room AI Global Hackathon (November 2026)</b><br>
  <b>Title Partner:</b> Bifrost by Maxim AI &nbsp;•&nbsp; <b>Track Partner:</b> Tavily by Nebius<br>
  <b>Team:</b> <code>Illuminati</code> &nbsp;•&nbsp; <b>Lead Architect & Developer:</b> <b>Aryan Vishwakarma</b> (<a href="https://github.com/Aryanxp1">@Aryanxp1</a>)
</p>

---

## 🧭 Executive Overview

**Illuminati** is an all-in-one AI platform that combines all four hackathon problem statements into a single, cohesive, unified monorepo. It features a unified FastAPI backend, shared gateway infrastructure (**Bifrost** + **Tavily**), a SQLite telemetry database, an interactive glassmorphic web dashboard, and a unified CLI.

```
                               ┌─────────────────────────────────────────────────────────────┐
                               │                    ILLUMINATI PLATFORM                      │
                               │           Single Entrypoint: python main.py                 │
                               └──────────────────────────────┬──────────────────────────────┘
                                                              │
                     ┌──────────────────┬─────────────────────┴───────────────┬──────────────────┐
                     ▼                  ▼                                     ▼                  ▼
              ┌──────────────┐   ┌──────────────┐                      ┌──────────────┐   ┌──────────────┐
              │   Engine 1   │   │   Engine 2   │                      │   Engine 3   │   │   Engine 4   │
              │ Coding Agent │   │  AgentBench  │                      │  StaleGuard  │   │  Pre-Meeting │
              │Fewest Tokens │   │    Arena     │                      │  Freshness   │   │   Briefing   │
              └──────┬───────┘   └──────┬───────┘                      └──────┬───────┘   └──────┬───────┘
                     │                  │                                     │                  │
                     └──────────────────┼─────────────────────────────────────┼──────────────────┘
                                        ▼                                     ▼
                               ┌─────────────────┐                   ┌─────────────────┐
                               │ Bifrost Gateway │                   │   Tavily API    │
                               │  (Model Plane)  │                   │(Knowledge Plane)│
                               └─────────────────┘                   └─────────────────┘
```

---

## 🏆 Problem Statements Covered in the Unified Platform

| # | Track | Problem Statement | Unified Engine | Core Capabilities |
|---|---|---|---|---|
| **01** | **Bifrost Priority Track** | **Coding Agent on Fewest Tokens** | `backend/modules/coding_agent` | 3-Phase Model Cascade (Explore ➔ Edit ➔ Verify), token budgets, context compaction, approval gates, SHA-256 receipts. |
| **02** | **Bifrost Priority Track** | **AgentBench Arena (Benchmarking)** | `backend/modules/arena` | Chaos fault injection (HTTP 500, 429, malformed JSON), multi-agent duels, ARS scoring, counterfactual what-if replay. |
| **03** | **Tavily Partner Track** | **Stale-Answer Detector** | `backend/modules/staleguard` | Time-sensitive claim extraction, volatility ranking, Tavily real-time verification, 0–100 freshness score, word-level diff patch. |
| **04** | **Tavily Partner Track** | **Pre-Meeting Briefing Agent** | `backend/modules/briefing` | 30-day temporal research window across 6–8 angles, code-level verbatim quote match, numerical verification, rejected-claims ledger. |

---

## ⚡ Quickstart (Run in 30 Seconds)

### 1. Setup Environment
```bash
# Clone the repository
git clone https://github.com/Aryanxp1/illuminati.git
cd illuminati

# Install unified dependencies with uv (or standard pip)
uv venv .venv
.\.venv\Scripts\activate
uv pip install -r requirements.txt
```

### 2. Launch the Unified Web Dashboard
```bash
python main.py
```
Open your browser and navigate to:  
👉 **`http://localhost:8000`**

---

## 🖥️ Command-Line Interface (Instant One-Word Commands)

You can run any engine with simple **one-word commands** in your terminal:

```bash
# 1. Run Token-Governed Coding Agent (Instant one-shot)
code "Implement LRU cached Fibonacci function with type hints"

# 2. Start Interactive Conversational Mode (Claude Code / Antigravity style with '/' slash commands)
chat
# (or just: run)

# 3. Run AgentBench Arena 12 Chaos Benchmark Suites
run bench

# 4. Check factual freshness with StaleGuard
run check "Spotify Premium individual plan costs $9.99 per month."

# 5. Generate Pre-Meeting 30-day executive brief
run brief "Anthropic"

# 6. Open Documentation or Web Console
run docs
run web
```

---

## 📁 Unified Repository Structure

```
illuminati/
├── main.py                  # Unified launcher: CLI + Web Server entrypoint
├── requirements.txt         # Consolidated dependencies
├── illuminati.db            # Unified SQLite database for runs, checks & briefs
├── backend/
│   ├── main.py              # Central FastAPI app with all module routes
│   ├── config.py            # Unified environment & model settings
│   ├── database.py          # Unified database tables & connection pooling
│   ├── gateway/
│   │   ├── bifrost.py       # Bifrost proxy client, virtual keys, model failover
│   │   └── tavily_client.py # Tavily search, extract, news filtering & mock fixtures
│   └── modules/
│       ├── coding_agent/    # [Bifrost PS 01] Token-Governed Coding Agent
│       │   ├── runner.py    # Phase cascade, context economics, turn receipts
│       │   └── router.py    # REST endpoints: /api/coding-agent/*
│       ├── arena/           # [Bifrost PS 02] AgentBench Arena & Observatory
│       │   ├── orchestrator.py # Benchmark runner & agent adapters
│       │   ├── lab_engine.py   # ARS calculation & counterfactual replay
│       │   └── routes/         # REST endpoints: /api/benchmarks/*, /api/lab/*
│       ├── staleguard/      # [Tavily PS 01] StaleGuard Freshness Detector
│       │   ├── pipeline.py  # Claim extractor, volatility checker, judge
│       │   ├── scoring.py   # 0–100 Freshness score & word-level diffs
│       │   └── router.py    # REST endpoints: /api/freshness/*
│       └── briefing/        # [Tavily PS 02] Pre-Meeting Briefing Agent
│           ├── research.py  # 30-day temporal window Tavily search
│           ├── verify.py    # Deterministic code-level quote verification
│           └── router.py    # REST endpoints: /api/briefing/*
├── frontend/
│   ├── index.html           # Unified Glassmorphic Web Dashboard (Tailwind + Lucide)
│   └── docs.html            # Documentation & architecture portal
├── run.bat                  # One-word CLI launcher (run code, run bench, run check, etc.)
└── code.bat                 # Direct shortcut for the token-governed coding agent
```

---

## 🔌 Gateway Infrastructure (Bifrost & Tavily)

- **Bifrost by Maxim AI (`http://localhost:8080/v1`)**:
  - Acts as the unified model plane for all LLM calls.
  - Manages virtual keys (`bf-illuminati-key`), budget caps ($0.05/task), token limits, and multi-provider failover routing (`openai/gpt-4o-mini` ➔ `claude-3-5-haiku` ➔ `groq/gpt-oss-120b` ➔ `ollama/llama3`).
  - Automatically switches to simulation mode when the local gateway is offline.
- **Tavily by Nebius**:
  - Serves as the real-time knowledge plane across the briefing and freshness engines.
  - Queries live web news within 30-day temporal windows.
  - Features zero-key deterministic mock fixtures for seamless offline evaluation.

---

## 👥 Team & Attribution

- **Team Name:** `Illuminati`
- **Lead Architect & Developer:** **Aryan Vishwakarma**
  - **GitHub:** [@Aryanxp1](https://github.com/Aryanxp1)
  - **Repository:** [https://github.com/Aryanxp1/illuminati](https://github.com/Aryanxp1/illuminati)
- **Event:** Geek Room AI Global Hackathon (November 2026)
- **License:** MIT License
