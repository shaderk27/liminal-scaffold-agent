import os
import json
from pydantic import BaseModel
from ollama import chat

# 1. Define the exact output structure required from the LLM
class Repository(BaseModel):
    files: dict[str, str]

def generate_boilerplate(user_prompt: str):
    # 2. Build the System Prompt with Guardrails
    system_instruction = """
    You are an expert software architect generating a project boilerplate based strictly on the user's requested tech stack.

    CRITICAL INSTRUCTIONS:
    1. Before writing any code, internally run an Incongruous Requirements Checklist (IRC) against the prompt to ensure no architectural constraints are missing.
    2. Ensure all generated code relies exclusively on generic, standardized mock data. You must never reference or hardcode specific names within generated code snippets, seed files, or documentation.
    3. Analyze the user's requested tech stack. Output all necessary files for a complete MVP using those specific technologies.
    4. IF the user requests a containerized setup, you MUST generate a valid 'docker-compose.yml' and the corresponding 'Dockerfile' for EVERY service.
    5. You MUST include the correct dependency tracking files for the inferred languages (e.g., 'requirements.txt' for Python, 'package.json' for Node/React, 'go.mod' for Go).
    """

    messages = [
        {'role': 'system', 'content': system_instruction},
        {'role': 'user', 'content': f"Generate a boilerplate for the following requirement: {user_prompt}"}
    ]

    print("Generating architecture... this may take a few minutes on local hardware.")
    
    # 3. Call the local model and enforce the JSON schema
    response = chat(
        model='qwen2.5-coder:7b',
        messages=messages,
        format=Repository.model_json_schema(),
        options={'temperature': 0} # 0 enforces deterministic output
    )

    # 4. Parse the output and write to disk
    repo_data = Repository.model_validate_json(response.message.content)
    
    output_dir = "generated_repo"
    os.makedirs(output_dir, exist_ok=True)

    for file_path, file_content in repo_data.files.items():
        full_path = os.path.join(output_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "w") as f:
            f.write(file_content)
            
        print(f"Created: {full_path}")

if __name__ == "__main__":
    prompt_file = "prompt.txt"
    
    # Create a default text file if one doesn't exist
    if not os.path.exists(prompt_file):
        with open(prompt_file, "w") as f:
            f.write("Build a Flask and React e-commerce API with PostgreSQL and a Docker setup.")
        print(f"Created default '{prompt_file}'. You can edit this file for future runs.")
        
    # Read the contents of the text file
    with open(prompt_file, "r") as f:
        user_prompt = f.read().strip()
        
    print(f"Reading architectural requirements from {prompt_file}...\n")
    generate_boilerplate(user_prompt)