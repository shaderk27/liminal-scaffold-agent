import os
import re
from datetime import datetime
from pydantic import BaseModel, Field
from ollama import chat

MODEL_NAME = "qwen2.5-coder:7b"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = f"generated_repo_{TIMESTAMP}"


# --- STAGE 1 SCHEMAS: PLANNING & IRC AUDIT ---
class ServiceSpec(BaseModel):
    service_name: str = Field(description="Name of the docker-compose service, e.g., backend, frontend, db")
    directory: str = Field(description="Relative folder path for this service, e.g., backend or frontend")
    port: int = Field(description="Exposed port number")
    stack: str = Field(description="Frameworks and languages used")


class ArchitectureBlueprint(BaseModel):
    project_summary: str
    irc_missing_requirements_resolved: list[str] = Field(
        description="List of missing or ambiguous requirements caught by the Incongruous Requirements Checklist (IRC) and how the architect resolved them."
    )
    services: list[ServiceSpec]
    required_files: list[str] = Field(
        description="Exact relative file paths to generate. Do NOT create duplicate backend or frontend folders."
    )


# --- STAGE 2 SCHEMA: SINGLE FILE GENERATION ---
class GeneratedFile(BaseModel):
    file_path: str
    code: str


def stage_1_plan_architecture(user_prompt: str) -> ArchitectureBlueprint:
    print("[Stage 1/3] Running Incongruous Requirements Checklist (IRC) & Locking Blueprint...")

    planner_system_prompt = """
    You are a Principal Systems Architect. Analyze the user's project prompt and produce a strict ArchitectureBlueprint.

    CRITICAL ARCHITECTURAL RULES:
    1. Run an Incongruous Requirements Checklist (IRC): Identify unstated requirements needed for the system to actually build and talk over a network (e.g., CORS headers, database environment variables, automatic table seeding, container networking, dependency manifests).
    2. Enforce a SINGLE canonical directory per service. Never create both 'backend/' and 'web/', or split frontend files between 'frontend/' and a root 'src/'.
    3. For a containerized Flask + React + PostgreSQL stack, your 'required_files' list MUST strictly follow this exact order and structure:
       - docker-compose.yml
       - backend/Dockerfile
       - backend/requirements.txt
       - backend/app.py
       - frontend/Dockerfile
       - frontend/package.json
       - frontend/public/index.html
       - frontend/src/index.js
       - frontend/src/App.js
    """

    response = chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": planner_system_prompt},
            {"role": "user", "content": f"Create the architecture blueprint for: {user_prompt}"}
        ],
        format=ArchitectureBlueprint.model_json_schema(),
        options={"temperature": 0}
    )

    blueprint = ArchitectureBlueprint.model_validate_json(response.message.content)

    print(f"  -> IRC caught {len(blueprint.irc_missing_requirements_resolved)} implicit architectural gaps.")
    print(f"  -> Locked {len(blueprint.required_files)} canonical file paths.")
    return blueprint


def stage_2_generate_files(user_prompt: str, blueprint: ArchitectureBlueprint):
    print(f"\n[Stage 2/3] Generating Files in '{OUTPUT_DIR}' with Locked Blueprint & Chained Context...")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    blueprint_json = blueprint.model_dump_json(indent=2)
    generated_context_cache: dict[str, str] = {}

    for index, target_file in enumerate(blueprint.required_files, start=1):
        print(f"  -> [{index}/{len(blueprint.required_files)}] Generating {target_file}...")

        upstream_context_str = ""
        for ctx_path, ctx_code in generated_context_cache.items():
            upstream_context_str += f"\n--- ALREADY GENERATED {ctx_path} ---\n{ctx_code}\n"

        coder_system_prompt = f"""
        You are a Senior Full-Stack Engineer implementing one specific file from a locked Architecture Blueprint.

        LOCKED ARCHITECTURE BLUEPRINT:
        {blueprint_json}
        {upstream_context_str}

        CRITICAL CODING RULES:
        1. Rely exclusively on generic, standardized mock data. Never reference or hardcode specific teammate names.
        2. Ensure all ports, service names, environment variables, and API routes match the LOCKED ARCHITECTURE BLUEPRINT and any ALREADY GENERATED files above.
        3. Do NOT import any local files (such as './App.css', './index.css', or './logo.svg') unless they are explicitly listed in 'required_files'. Use inline styles in React components.
        4. If generating 'docker-compose.yml':
           - Do NOT include the obsolete top-level 'version:' key.
           - Use 'postgres:15-alpine' for the db service with POSTGRES_DB=ecommerce, POSTGRES_USER=user, POSTGRES_PASSWORD=password.
           - Do NOT mount a persistent volume to '/var/lib/postgresql/data' on the db service so every build starts with a clean database state.
           - Pass DB_HOST=db, DB_NAME=ecommerce, DB_USER=user, DB_PASSWORD=password in the backend service environment.
        5. If generating 'backend/Dockerfile', use 'python:3.11-slim' and run the app with 'python app.py'.
        6. If generating 'backend/requirements.txt', pin exact versions: Flask==3.0.0, flask-cors==4.0.0, psycopg2-binary==2.9.9.
        7. If generating 'backend/app.py':
           - Use only standard imports: 'import os', 'import psycopg2', 'from flask import Flask, jsonify, request', 'from flask_cors import CORS'. Do NOT use RealDictCursor.
           - Enable CORS(app).
           - Read DB_HOST, DB_NAME, DB_USER, DB_PASSWORD from os.environ with fallback defaults ('db', 'ecommerce', 'user', 'password').
           - Create a helper function 'init_db()' decorated with '@app.before_request' that connects to the DB, sets 'conn.autocommit = True', runs 'CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, name VARCHAR(100), price NUMERIC(10,2));', and inserts 3 generic sample products if 'SELECT COUNT(*) FROM products' is 0. Do not return anything from 'init_db()'.
           - In '@app.route("/products", methods=["GET"])', query 'SELECT id, name, price FROM products' and return 'jsonify([{{'id': r[0], 'name': r[1], 'price': float(r[2])}} for r in rows])'.
        8. If generating 'frontend/src/App.js':
           - Use React useState and useEffect to fetch from the exact full URL 'http://localhost:5000/products' (NEVER use a relative path like '/products').
           - Render the returned array of product objects (id, name, price) in an inline-styled HTML table.
        9. If generating 'frontend/Dockerfile', use 'node:18-alpine', copy package.json, run 'npm install', copy source files, and run 'npm start'.
        """

        code_content = ""
        for attempt in range(1, 4):
            response = chat(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": coder_system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Original Request: {user_prompt}\n"
                            f"Write the complete, non-empty raw code for '{target_file}'. "
                            f"The 'code' field MUST contain the full file implementation."
                        )
                    }
                ],
                format=GeneratedFile.model_json_schema(),
                options={"temperature": 0.1 if attempt > 1 else 0}
            )

            file_data = GeneratedFile.model_validate_json(response.message.content)
            if file_data.code and file_data.code.strip():
                code_content = file_data.code
                break
            print(f"     [Retry {attempt}/3] Model emitted empty content for {target_file}, regenerating...")

        if target_file in ("docker-compose.yml", "backend/app.py"):
            generated_context_cache[target_file] = code_content

        full_path = os.path.join(OUTPUT_DIR, target_file)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(code_content)


def stage_3_verify_and_heal(blueprint: ArchitectureBlueprint):
    print("\n[Stage 3/3] Running Post-Generation Static Verification & Self-Healing...")
    audit_notes = []

    # 1. Verify all locked files exist and are non-empty
    for req_file in blueprint.required_files:
        full_path = os.path.join(OUTPUT_DIR, req_file)
        if not os.path.exists(full_path) or os.path.getsize(full_path) == 0:
            audit_notes.append(f"[FAIL] Missing or empty required file: {req_file}")
        else:
            audit_notes.append(f"[PASS] Verified file exists: {req_file}")

    # 2. Check and auto-heal obsolete 'version:' tag in docker-compose.yml
    compose_path = os.path.join(OUTPUT_DIR, "docker-compose.yml")
    if os.path.exists(compose_path):
        with open(compose_path, "r", encoding="utf-8") as f:
            compose_content = f.read()

        cleaned_content, count = re.subn(r"(?m)^version:\s*['\"]?[\d.]+['\"]?\s*\n", "", compose_content)
        if count > 0:
            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(cleaned_content)
            audit_notes.append("[AUTO-HEALED] Removed obsolete 'version:' attribute from docker-compose.yml")
        else:
            audit_notes.append("[PASS] docker-compose.yml is free of obsolete 'version:' attributes")

    # 3. Check and auto-heal hallucinated CSS/SVG imports and relative fetch() URLs in React JS files
    for req_file in blueprint.required_files:
        if req_file.endswith(".js"):
            js_path = os.path.join(OUTPUT_DIR, req_file)
            if os.path.exists(js_path):
                with open(js_path, "r", encoding="utf-8") as f:
                    js_content = f.read()

                # Strip unapproved .css or .svg imports
                cleaned_js, css_count = re.subn(
                    r"(?m)^\s*import\s+['\"].*\.(css|svg)['\"];?\s*\n",
                    "",
                    js_content
                )
                if css_count > 0:
                    audit_notes.append(
                        f"[AUTO-HEALED] Stripped {css_count} unapproved CSS/SVG import(s) from {req_file}"
                    )

                # Rewrite relative fetch('/...') calls to point directly to http://localhost:5000/...
                cleaned_js, fetch_count = re.subn(
                    r"fetch\(\s*['\"](/[^'\"]*)['\"]",
                    r"fetch('http://localhost:5000\1'",
                    cleaned_js
                )
                if fetch_count > 0:
                    audit_notes.append(
                        f"[AUTO-HEALED] Rewrote {fetch_count} relative fetch() URL(s) to http://localhost:5000 in {req_file}"
                    )

                if css_count > 0 or fetch_count > 0:
                    with open(js_path, "w", encoding="utf-8") as f:
                        f.write(cleaned_js)

    # 4. Check and auto-heal Flask 3.0 decorators & missing psycopg2.extras imports in backend/app.py
    backend_app_path = os.path.join(OUTPUT_DIR, "backend/app.py")
    if os.path.exists(backend_app_path):
        with open(backend_app_path, "r", encoding="utf-8") as f:
            py_content = f.read()

        modified_py = False
        if "@app.before_first_request" in py_content:
            py_content = py_content.replace("@app.before_first_request", "@app.before_request")
            modified_py = True
            audit_notes.append(
                "[AUTO-HEALED] Upgraded deprecated '@app.before_first_request' to '@app.before_request' in backend/app.py"
            )

        if "RealDictCursor" in py_content and "psycopg2.extras" not in py_content:
            py_content = "import psycopg2.extras\nfrom psycopg2.extras import RealDictCursor\n" + py_content
            modified_py = True
            audit_notes.append(
                "[AUTO-HEALED] Injected missing 'psycopg2.extras.RealDictCursor' import in backend/app.py"
            )

        if modified_py:
            with open(backend_app_path, "w", encoding="utf-8") as f:
                f.write(py_content)

    # 5. Write an IRC & Verification Report into the generated repo
    report_path = os.path.join(OUTPUT_DIR, "IRC_AUDIT_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Automated Architecture & IRC Audit Report\n\n")
        f.write(f"**Iteration Directory:** `{OUTPUT_DIR}`\n\n")
        f.write(f"**Project Summary:** {blueprint.project_summary}\n\n")
        f.write("## 1. Incongruous Requirements Checklist (IRC) Resolutions\n")
        for item in blueprint.irc_missing_requirements_resolved:
            f.write(f"- {item}\n")
        f.write("\n## 2. Static Verification & Self-Healing Log\n")
        for note in audit_notes:
            f.write(f"- `{note}`\n")

    for note in audit_notes:
        print(f"  -> {note}")
    print(f"  -> Saved audit artifact to {report_path}")


if __name__ == "__main__":
    prompt_file = "prompt.txt"
    if not os.path.exists(prompt_file):
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write("Build a Flask and React e-commerce API with PostgreSQL and a Docker setup.")

    with open(prompt_file, "r", encoding="utf-8") as f:
        user_prompt = f.read().strip()

    print(f"Reading requirements from {prompt_file}: '{user_prompt}'\n")
    print(f"Target output directory: {OUTPUT_DIR}\n")

    blueprint = stage_1_plan_architecture(user_prompt)
    stage_2_generate_files(user_prompt, blueprint)
    stage_3_verify_and_heal(blueprint)

    print(f"\nScaffolding complete! Run:\n  cd {OUTPUT_DIR}\n  docker compose up --build")