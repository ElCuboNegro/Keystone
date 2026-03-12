# Software Archeology Index

This is the central index mapping the architecture and key components of the `cookiecutter-agentic-ci` template repository.

## 1. Technology Stack
- **Languages**: Python (Hooks), Markdown (Documentation, Skills), JSON (Configuration), YAML (GitHub Actions).
- **Framework**: Cookiecutter (Template Engine).
- **Core Abstraction**: Markdown-based Agentic Prompts (`.agents/skills/*.md`).

## 2. Architecture Map
- `/cookiecutter.json`: The core template variable configuration.
- `/hooks/post_gen_project.py`: Python script that executes immediately after project generation to patch specific files that bypassed Jinja rendering.
- `/{{cookiecutter.project_slug}}/`: The blueprint directory.
  - `/AGENTS.md`: The supreme instruction set for all AI agents.
  - `/.agents/skills/`: The specialized sub-agent definitions.
  - `/tools/check_adr_gate.py`: Python script for CI that enforces the ADR presence on PRs.
  - `/.github/workflows/ci.yml`: The GitHub Actions pipeline running the ADR gate and tests.

## 3. Data Flow
1. User runs `cookiecutter gh:deagentic/cookiecutter-agentic-ci`
2. Cookiecutter prompts user based on `cookiecutter.json`.
3. Cookiecutter renders the `{{cookiecutter.project_slug}}` directory structure and replaces variables inside files.
4. Cookiecutter skips rendering for files listed in `_copy_without_render`.
5. Cookiecutter executes `hooks/post_gen_project.py`.
6. The hook script manually reads, patches (`__LIBRARY_PATH__`, etc.), and overwrites `tools/check_adr_gate.py` and `.github/workflows/ci.yml`.
7. Output is a fully initialized Agentic CI Python project.
