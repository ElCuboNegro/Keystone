# Project Context
This is a Cookiecutter template for scaffolding Python projects with Agentic CI infrastructure.

# Build & Test Commands
- **Generate template locally**: `cookiecutter . --no-input`

# Code Style & Guidelines
- **ADR-First Mandate**: Document architectural changes in `docs/adr/` before implementing.
- **Verification Criteria**: Always write tests or provide verification for changes made to the template or tools.
- **Manage Context**: Keep the context window lean by delegating deep investigation tasks to specialized agents (e.g., in `.agents/skills/`).
- **Plan Before Coding**: Use Plan Mode to research and design solutions before writing implementation code.

# Core Directives
Read @AGENTS.md for complete routing directives, deduplication mandates, and learning protocols.
