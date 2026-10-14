# Context-Aware MVP Scaffold Agent
**Eliminating "Boilerplate-to-Launch" Engineering Drag via Constrained Local LLM Orchestration**

> **Liminal Apprentice Case Assessment — AI / Software Engineering Track**  
> **Stack:** Python, Ollama (`qwen2.5-coder:7b`), Pydantic (Structured Outputs), Docker Compose



## 1. Problem Framing: The "Boilerplate-to-Launch" Drag

In a venture studio or rapid prototyping environment, the primary engineering bottleneck during the Zero-to-One phase is rarely business logic—it is **configuration drift and setup fatigue**. 

Every time an engineering team spins up a new MVP, hours or days are lost to repetitive infrastructural wiring before a single feature is tested:
* Initializing separate frontend and backend directories with matching dependency manifests (`requirements.txt`, `package.json`).
* Configuring Cross-Origin Resource Sharing (CORS) so the client and API can communicate.
* Wiring environment variables and database connection strings (e.g., Flask to PostgreSQL).
* Writing multi-container `Dockerfile` and `docker-compose.yml` specifications with proper port mappings and network bridges.

### Why Existing Tools Fall Short
1. **Static Templates (Cookiecutter / GitHub Templates):** High reliability, zero flexibility. The moment an MVP requires a slightly different data model, authentication flow, or service topology, developers spend just as much time ripping out boilerplate code as writing it from scratch.
2. **Free-Form Chat Prompts (ChatGPT / Claude UI):** High flexibility, low structural reliability. Asking an LLM in a chat window to "build a full-stack app" yields fragmented code blocks, omitted configuration files, and hallucinated directory paths that require manual copy-pasting and debugging.

**The Objective:** Build a local, zero-cost, stack-agnostic **Scaffold Agent** that takes a plain-text architectural prompt (`prompt.txt`), validates it for missing operational requirements, and deterministically generates a complete, containerized repository ready to run via `docker compose up --build`.


## 2. Solution Design: Constraining Non-Deterministic Models

To run entirely locally within a tight turnaround window without external API costs or data privacy leakage, this system uses Alibaba's open-weights **`qwen2.5-coder:7b`** via **Ollama**, orchestrated by Python and **Pydantic**.

Rather than treating the 7B model as an all-knowing oracle, the architecture separates **reasoning/planning** from **code emission** and wraps the LLM in deterministic Python guardrails.

### System Architecture (`v2` 3-Stage Pipeline)

```text
+-------------------+
|    prompt.txt     |  ("Build a Flask and React e-commerce API with PostgreSQL...")
+---------+---------+
          |
          v
+-----------------------------------------------------------------------+
| STAGE 1: IRC Audit & Blueprint Lock (LLM + Pydantic Schema)           |
|  - Runs Incongruous Requirements Checklist (IRC) on untrusted input   |
|  - Infers missing glue (CORS, env vars, Docker build contexts)        |
|  - Locks a canonical list of allowed file paths (ArchitectureBlueprint)|
+---------+-------------------------------------------------------------+
          |
          v
+-----------------------------------------------------------------------+
| STAGE 2: Context-Locked File Generator (Iterative LLM Loop)           |
|  - Iterates over locked file list 1-by-1                              |
|  - Injects read-only ArchitectureBlueprint into system context        |
|  - Enforces strict data hygiene (generic mock data, zero PII/names)   |
+---------+-------------------------------------------------------------+
          |
          v
+-----------------------------------------------------------------------+
| STAGE 3: Deterministic Verification & Self-Healing (Pure Python)      |
|  - Verifies all locked files exist on disk and are non-empty          |
|  - Regex-strips deprecated Docker Compose syntax (`version:` tag)     |
|  - Emits `IRC_AUDIT_REPORT.md` documenting resolved ambiguities       |
+---------+-------------------------------------------------------------+
          |
          v
+-------------------+
|  generated_repo/  |  --> Ready for `docker compose up --build`
+-------------------+
```

### Core Engineering Guardrails
1. **Incongruous Requirements Checklist (IRC):** Prompts written by humans are almost always underspecified (e.g., requesting "a React and Flask app in Docker" without mentioning CORS, `Dockerfile`s, or `requirements.txt`). Stage 1 treats the user prompt as incomplete and explicitly logs every implicit architectural requirement it resolves before locked paths are created.
2. **Strict Data Sanitization:** System prompts enforce enterprise repository hygiene—relying strictly on generic, standardized mock data and prohibiting hardcoded personal or teammate names in seed data, comments, or configuration files.


## 3. Execution & Proof: The Evolution from V1 to V2

The most valuable findings came from observing where the 7B local model failed during initial iterations and re-architecting the Python orchestrator to eliminate those failure modes.

### Iteration 1: Naive Single-Shot Generation (`scaffold_agent_v1.py` - Initial)
In the first prototype, the model was prompted to return the entire repository inside a single Pydantic dictionary (`files: dict[str, str]`).

```text
generated_repo/
├── docker-compose.yml
├── backend/
│   └── app.py
└── frontend/
    └── App.js
```

* **What Happened:** Running `docker compose up --build` immediately failed with `failed to read dockerfile: open Dockerfile: no such file or directory`.
* **Root Cause:** The prompt hardcoded references to `app.py` and `App.js` without forcing the model to infer build artifacts (`Dockerfile`) and dependency manifests (`requirements.txt`, `package.json`). Furthermore, hardcoding "Flask" and "React" in the system instructions meant the prompt would break if the user requested a different stack (e.g., FastAPI + Vue).

### Iteration 2: Stack-Agnostic Single-Shot & "Context Schism"
I refactored the system prompt to be stack-agnostic and required `Dockerfile`s and dependency files for every service—while still asking the 7B model to output all files in a single JSON payload.

```text
generated_repo/
├── backend/
│   └── app.py
├── frontend/
│   └── App.js
├── src/
│   ├── App.js
│   ├── index.js
│   └── reportWebVitals.js
├── web/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── Dockerfile.web
└── package.json
```

* **What Happened:** The 7B model suffered from severe **context drift (directory schism)** mid-generation:
  1. **The Backend Schism:** It created `backend/app.py`, forgot the folder name halfway through the JSON token stream, and created a second backend inside `web/` containing another `app.py`, `Dockerfile`, and `requirements.txt`.
  2. **The Frontend Schism:** It split the React app across three locations—placing `package.json` in the root, entry points in `src/`, and an isolated `App.js` in `frontend/`.

* **Key Technical Insight:** Small local models (7B parameters) cannot reliably track cross-file directory state while simultaneously writing raw code for 8+ files inside one monolithic JSON response. **Prompt engineering alone could not fix this; the orchestration architecture had to change.**

### Iteration 3: Multi-Stage Agentic Pipeline (`scaffold_agent_v2.py`)
By decoupling **Stage 1 (Blueprint Locking)** from **Stage 2 (File-by-File Generation)**, the model is never allowed to invent directory paths while writing code. Python holds the state (the locked `ArchitectureBlueprint`), and the LLM only writes one isolated file per API call using that blueprint as read-only context.

```text
generated_repo/
├── docker-compose.yml
├── IRC_AUDIT_REPORT.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── public/
    │   └── index.html
    └── src/
        ├── index.js
        └── App.js
```


## 4. Impact Analysis: Before vs. After AI

### Quantitative & Qualitative Comparison

| Dimension | Manual Setup (Before AI) | V1 Single-Shot LLM Wrapper | V2 3-Stage Scaffold Agent |
| :--- | :--- | :--- | :--- |
| **Time to Initial Repo** | ~2–3 Hours | ~45 Seconds | ~90 Seconds |
| **Directory Consistency** | High (Human-managed) | Broken (Duplicate `web/` & `backend/` folders) | High (Locked via Stage 1 Pydantic Blueprint) |
| **Cross-Service Wiring** | Prone to manual typos / CORS bugs | Broken build contexts in `docker-compose.yml` | Aligned via shared read-only blueprint context |
| **Auditability** | None | None (Black-box generation) | Automated `IRC_AUDIT_REPORT.md` artifact |

### Where AI Augmentation Broke Down
1. **Simultaneous Planning + Execution Overload:** When forced to plan directory trees and write code in a single pass, `qwen2.5-coder:7b` hallucinated duplicate folders.
2. **Training Data Staleness (Deprecated Syntax):** Because LLM weights reflect historical GitHub repositories, the model repeatedly included the obsolete `version: '3.8'` attribute in `docker-compose.yml` (triggering Docker CLI warnings) and defaulted to older base images like `postgres:13`.
3. **Deterministic Post-Processing > Prompt Begging:** Even when instructed in the system prompt not to include the `version:` key in `docker-compose.yml`, the 7B model occasionally still emitted it due to strong pre-training priors. Adding a 3-line Python regex in Stage 3 (`stage_3_verify_and_heal`) guaranteed 100% removal. **Lesson:** *Never rely on an LLM for a deterministic rule that 3 lines of standard code can guarantee.*

### What Still Requires Human Judgment
While the V2 agent eliminates initial setup drag, it is a **starting scaffold, not a production release**. Human engineering judgment remains mandatory for:
* **Security & Secrets Hardening:** Moving fallback database credentials out of `docker-compose.yml` into secret managers, implementing proper password hashing (e.g., Argon2) and token authentication (JWT/TOTP), and locking down permissive `CORS(*)` rules before deployment.
* **Data Persistence & Migrations:** Verifying that named Docker volumes (`pgdata:/var/lib/postgresql/data`) and schema migration tools (Alembic) are properly configured so container restarts do not wipe state.
* **Dependency Pinning:** Auditing `requirements.txt` and `package.json` for vulnerable or conflicting package versions.


## 5. Future Improvements

1. **Run Against Other Models for Output Comparison**
2. **Interactive IRC Approval CLI:**
   * Pause after Stage 1 in the terminal so the developer can review, edit, or approve the `ArchitectureBlueprint` and IRC resolutions before Stage 2 spends compute generating the files.


## 6. Repository Structure & Quickstart

```text
liminal-scaffold-agent/
├── prompt.txt               # Plain-text architectural prompt input
├── scaffold_agent_v1.py     # Baseline single-shot generator (demonstrates context schism)
├── scaffold_agent_v2.py     # 3-Stage Agentic Pipeline (IRC + Blueprint Lock + Self-Healing)
├── .gitignore               # Excludes venv/, .env, prompt.txt and generated_repo/
└── README.md                # Case study documentation & architectural analysis
```

### Prerequisites
1. **Python 3.10+**
2. **Docker Desktop** (running with Compose v2 CLI plugin)
3. **Ollama** installed locally with `qwen2.5-coder:7b`:
   ```bash
   ollama pull qwen2.5-coder:7b
   ```

### Installation & Execution
1. **Clone and activate the virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install ollama pydantic
   ```
2. **Edit your architectural prompt (optional):**
   Modify `prompt.txt` with your desired MVP stack.
3. **Run the V2 3-Stage Scaffold Agent:**
   ```powershell
   python scaffold_agent_v2.py
   ```
4. **Verify and launch the generated repository:**
   ```powershell
   cd generated_repo
   type IRC_AUDIT_REPORT.md
   docker compose up --build
   ```