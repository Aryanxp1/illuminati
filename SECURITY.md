# Security Policy

## Supported Versions

Security updates and vulnerability patches are actively maintained for the current release series of **Illuminati**.

| Version | Supported | Status |
| :--- | :---: | :--- |
| **v2.5.x** | :white_check_mark: | Current Active Release |
| **< v2.0** | :x: | End of Life / Unsupported |

---

## Autonomous Agent Security Architecture

Illuminati executes autonomous code generation, multi-agent benchmarking, and live search synthesis. To prevent runaway execution, data exfiltration, and unauthorized file mutations, the platform enforces five defense-in-depth guardrails:

### 1. Default-Deny Workspace Isolation
- Agent file modifications are strictly confined to target workspace directories.
- Path traversal sequences (`../`, symbolic link escapes, and absolute system paths) are rejected before execution.
- File overwrites require validated syntactic diffs and automated rollback snapshots.

### 2. Financial Budget & Token Exhaustion Gates
- Outbound model interactions are governed by a **\$0.05 USD hard expenditure ceiling** and an **8,000 token reserve gate**.
- Recursive tool invocations and cascading retry loops trigger circuit breakers before token starvation occurs.

### 3. Cryptographic Turn Integrity
- Every completed agent turn generates a deterministic **SHA-256 receipt** binding the input prompt, file diff, token consumption, and timestamp.
- Receipts provide an immutable audit trail verifying that execution traces have not been altered.

### 4. Local Loopback Isolation & Offline Privacy
- When configured in offline or confidential mode, model requests route strictly through local gateway loopback endpoints (`127.0.0.1`).
- External search queries are disabled or routed to deterministic mock fixtures, ensuring proprietary code and prompts never leave the local environment.

### 5. Telemetry & Secret Hygiene
- Telemetry logs and SQLite records automatically redact API keys, bearer tokens, and private `.env` environment variables.
- Repository configuration rules enforce the exclusion of all credentials and database files from version control.

---

## Reporting a Security Vulnerability

If you discover a security vulnerability or potential exploit within Illuminati, please practice responsible disclosure:

1. **Do not create public GitHub issues** for security vulnerabilities.
2. Email the maintainer directly at **vishwakarmaaryan606@gmail.com** with:
   - A descriptive summary of the issue.
   - Step-by-step instructions or a minimal proof-of-concept to reproduce the behavior.
   - Assessment of potential impact and affected components.
3. You will receive an initial acknowledgment within **48 hours**, followed by status updates as the patch is developed and verified.

Thank you for helping keep the Illuminati platform safe and reliable.
