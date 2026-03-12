# cookiecutter-agentic-ci

A [cookiecutter](https://cookiecutter.readthedocs.io/) template that scaffolds a Python project
with a complete **agentic CI/CD infrastructure** and **ADR-first mandate**.

## What you get

| Component | Location | Purpose |
|-----------|----------|---------|
| `AGENTS.md` | repo root | Single source of truth for all AI agents |
| `CLAUDE.md` | repo root | Claude Code entry point (imports AGENTS.md) |
| `.agents/skills/` | repo root | 5 cross-cutting agent skills |
| `.github/workflows/ci.yml` | workflows | ADR gate + test job |
| `docs/adr/index.md` | repo | ADR index (start here) |
| `tools/check_adr_gate.py` | repo | ADR enforcement gate script |

## Quickstart

```bash
pip install cookiecutter
cookiecutter gh:deagentic/cookiecutter-agentic-ci
```

Or from a local copy:

```bash
cookiecutter path/to/cookiecutter-agentic-ci
```

## Template variables

| Variable | Default | Description |
|----------|---------|-------------|
| `project_name` | My Project | Human-readable project name |
| `project_slug` | my-project | Repo / directory name (kebab-case) |
| `package_name` | my_package | Python package name (snake_case) |
| `github_username` | myuser | GitHub username or org |
| `description` | ... | One-line project description |
| `author` | Your Name | Author name |
| `python_version` | 3.11 | Minimum Python version for CI |
| `library_path` | library | Subdirectory containing the Python package |
| `adr_path` | docs/adr | Subdirectory for ADR files |

## After generation

1. `cd {{project_slug}}`
2. Copy `.agents/skills/*.md` to `~/.claude/.agents/skills/` to install agent skills globally
3. Open `docs/adr/index.md` -- write ADR-0001 before any code
4. Push to GitHub -- the ADR gate runs automatically on every PR

## The ADR-first mandate

Any change to `library/<package_name>/*.py` requires a new ADR in `docs/adr/`.
The CI gate (`tools/check_adr_gate.py`) enforces this automatically.

Bypass for trivial fixes: add `[skip-adr]` to the commit message.

## Claude Code Best Practices

This template is strictly configured following [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices), including:
- Lean `CLAUDE.md` contexts with direct test commands
- Sub-agent delegation for specific investigations
- The "Plan before code" methodology through `.cursorrules` and Agent instructions.
