# Project Context
{{cookiecutter.description}}

# Build & Test Commands
- **Install dependencies**: `pip install -e ".[dev]"`
- **Lint**: `ruff check {{cookiecutter.package_name}}/ tests/`
- **Type check**: `mypy {{cookiecutter.package_name}}/`
- **Run tests**: `pytest tests/ -v`

# Code Style & Guidelines
- **ADR-First Mandate**: You must write an Architecture Decision Record (ADR) in `{{cookiecutter.adr_path}}/` before changing any library source code.
- **Verification Criteria**: Always include tests (e.g., Gherkin specs or pytest) to verify code changes.
- **Context Management**: Use specialized subagents from `.agents/skills/` to keep this main context window lean and focused.
- **Plan Before Coding**: Use Plan Mode to research and design complex implementations before writing code.

# Core Directives
Read @AGENTS.md for complete routing directives, deduplication mandates, and learning protocols.
