# Findings Ledger

This ledger records chronological discoveries made during software archeology.

## Templates
Use this template for new findings:
```
### F-XXX: [Short Title]
- **Date**: YYYY-MM-DD
- **Context**: [File/Module/Path]
- **Finding**: [What was discovered?]
- **Implication**: [Why does this matter? Does it require an ADR?]
```

---

### F-001: Template Structure Detection
- **Date**: 2026-03-12
- **Context**: `/cookiecutter-agentic-ci`
- **Finding**: The repository is a Cookiecutter template structure rather than a raw Python application. It uses `{{cookiecutter.project_slug}}` syntax for directory generation.
- **Implication**: Archeology must analyze the *template structure* and its generated hooks, not a traditional execution path. The executions graph will represent the template generation and hook execution flow rather than a runtime call tree.

### F-002: Agentic Skills Distribution
- **Date**: 2026-03-12
- **Context**: `{{cookiecutter.project_slug}}/.agents/skills/`
- **Finding**: Contains 9 specific agent skills (adr-writer, architect, bdd-writer, code-reviewer, decision-logger, learning-protocol, software-archeologist, tool-writer, unknown-domain-protocol) that map directly to the workflows governed by `AGENTS.md`.
- **Implication**: This validates the Agentic CI concept. Any agent running on a generated project will be forced to obey these explicit `.md` rules.

### F-003: Post-Generation Hook Replaces Variables
- **Date**: 2026-03-12
- **Context**: `hooks/post_gen_project.py`
- **Finding**: Uses Python to replace variable placeholders like `__LIBRARY_PATH__` in files that are specified in `_copy_without_render` (such as `.github/workflows/ci.yml` and `tools/check_adr_gate.py`).
- **Implication**: The template execution is active, and the hook ensures that non-rendered files receive necessary project specifics after the primary cookiecutter render cycle.
