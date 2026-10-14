import os
import re
import json
import shutil
from pydantic import BaseModel, Field
from ollama import chat

MODEL_NAME = "qwen2.5-coder:7b"
OUTPUT_DIR = "generated_repo"

# --- STAGE 1 SCHEMAS: PLANNING & IRC AUDIT ---
class ServiceSpec(BaseModel):
    service_name: str = Field(description="Name of the docker-compose service, e.g., backend, frontend, db")
    directory: str = Field(description="Relative folder path for this service, e.g., backend or frontend")
    port: int = Field(description="Exposed port number")
    stack: str = Field(description="Frameworks and languages used")

class ArchitectureBlueprint(BaseModel):
    project_summary: str
    irc_missing_requirements_resolved: list[str] = Field(
        description="List of missing or ambiguous requirements caught by the Incongruous Requirements Checklist (IRC) and how the architect resolved them (e.g., CORS, env vars, healthchecks)."
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
    1. Run an Incongruous Requirements Checklist (IRC): Identify unstated requirements needed for the system to actually build and talk over a network (e.g., CORS headers, database environment variables, container networking, dependency manifests).
    2. Enforce a SINGLE canonical directory per service. Never create both 'backend/' and 'web/', or split frontend files between 'frontend/' and a root 'src/'.
    3. For a containerized Flask + React + PostgreSQL stack, your 'required_files' list MUST strictly follow this clean structure:
       - docker-compose.yml
       - backend/Dockerfile
       - backend/requirements.txt
       - backend/app.py
       - frontend/Dockerfile
       - frontend/package.json
       - frontend/public/index.html
       - frontend/src/index.js
       - frontend/src/App.js
    4. If the user asks for a different stack, adapt the file tree cleanly with zero duplicate folders.
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
    print("\n[Stage 2/3] Generating Files with Locked Blueprint & Chained Code Context...")
    
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    blueprint_json = blueprint.model_dump_json(indent=2)
    
    # Store previously generated critical files (like docker-compose.yml and backend/app.py)
    # so downstream files (like frontend/src/App.js) can match exact API routes and env vars.
    generated_context_cache: dict[str, str] = {}

    for index, target_file in enumerate(blueprint.required_files, start=1):
        print(f"  -> [{index}/{len(blueprint.required_files)}] Generating {target_file}...")
        
        # Build dynamic upstream code context for cross-file contract alignment
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
        4. If generating 'docker-compose.yml', do NOT include the obsolete top-level 'version:' key.
        5. If generating 'backend/Dockerfile', use 'python:3.11-slim' and run the app with 'python app.py'.
        6. If generating 'backend/requirements.txt', pin compatible versions: Flask==3.0.0, flask-cors==4.0.0, psycopg2-binary==2.9.9.
        7. If generating 'backend/app.py', read DB credentials from os.environ (matching docker-compose.yml), automatically run 'CREATE TABLE IF NOT EXISTS' and insert 3 generic sample rows if the table is empty, and expose JSON endpoints.
        8. If generating 'frontend/src/App.js', you MUST use React useState and useEffect to fetch data from the exact GET endpoint defined in 'backend/app.py' (e.g., http://localhost:5000/products) and render the items in a clean inline-styled list or table.
        9. If generating 'frontend/Dockerfile', use 'node:18-alpine', install dependencies, and run with 'npm start'.
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

        # Cache key infrastructure/backend files so the frontend knows exact routes & env vars
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

    # 3. Check and auto-heal hallucinated CSS/SVG imports in React JS files
    for req_file in blueprint.required_files:
        if req_file.endswith(".js"):
            js_path = os.path.join(OUTPUT_DIR, req_file)
            if os.path.exists(js_path):
                with open(js_path, "r", encoding="utf-8") as f:
                    js_content = f.read()
                
                # Strip imports of .css or .svg files that were not generated
                cleaned_js, count = re.subn(
                    r"(?m)^\s*import\s+['\"].*\.(css|svg)['\"];?\s*\n",
                    "",
                    js_content
                )
                if count > 0:
                    with open(js_path, "w", encoding="utf-8") as f:
                        f.write(cleaned_js)
                    audit_notes.append(
                        f"[AUTO-HEALED] Stripped {count} unapproved CSS/SVG import(s) from {req_file}"
                    )

    # 4. Write an IRC & Verification Report into the generated repo
    report_path = os.path.join(OUTPUT_DIR, "IRC_AUDIT_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Automated Architecture & IRC Audit Report\n\n")
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
    
    blueprint = stage_1_plan_architecture(user_prompt)
    stage_2_generate_files(user_prompt, blueprint)
    stage_3_verify_and_heal(blueprint)
    
    print("\nScaffolding complete! Navigate to 'generated_repo' and run: docker compose up --build")