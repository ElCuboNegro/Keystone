# AGENTS.md — My Project
**READ THIS FIRST. Every agent, every session, no exceptions.**

## 1. Project Mandate

* **Repository:** `github.com/myuser/my-project`
* **Description:** A Python project with agentic CI/CD and ADR-first mandate
* **Core Objective:** Understand, document, build, and evolve this codebase with full traceability.

## 2. Repository Layout

```
my-project/
├── CLAUDE.md            <- Claude Code entry point (imports this file)
├── AGENTS.md            <- single source of truth for all AI agents
├── .agents/skills/              <- agent skill files
├── tools/               <- project tooling (ADR gate, analysis scripts)
├── .github/workflows/   <- CI/CD
│
├── library/           <- LIBRARY
│   ├── my_package/       <- Python package
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
│
└── docs/adr/               <- ARCHITECTURE DECISIONS
    └── index.md
```

## 3. Initialization & Setup

Run environment setup before any analysis. Do not ask the user.

* **Windows:** `setup\install.bat`
* **Linux / macOS:** `bash setup/install.sh`

**Setup Failure Protocol:** Run setup silently. Continue with available tools and note gaps.

## 4. Execution Directives & Permissions

The following actions are assumed granted. **NEVER block progress waiting for confirmation on these.**

* **Traceability Mandate:** Every legacy function or transformation must be "Excavated" — its meaning must be documented in Markdown specs using `sql_logic_parser.py` before re-implementation. No placeholders are permitted in the final archaeology output.
* **BDD Extraction Mandate:** The logic isolated in `docs/archeology/logic/*` MUST also be extracted in the form of BDD.
* **Bottom-Up Protocol:** Analysis MUST start from the "Leaf" procedures (those that call no others) to build a foundation of understanding before tackling orchestrators.
* **Environment:** Auto-install missing Python packages via `pip`. Execute internal tools.
* **Self-Repair Mandate:** If you detect any discrepancies in agent documentation or configurations (e.g., outdated file paths pointing to `skills/` instead of `.agents/skills/`), you must self-repair them by fixing the references across the workspace and committing the fix locally. Furthermore, if the issue stems from a template, you must clone the upstream template repository (`git clone git@github.com:deagentic/cookiecutter-agentic-ci.git` or equivalent), apply the same self-repairing changes there, and submit a Pull Request to fix the issue at the source.

**STOP & ASK PERMISSION ONLY FOR:**
* Writing outside this repository.
* Modifying system configurations.
* Executing destructive write-operations to hardware or external services.

## 5. Context & Knowledge Management

```
Raw discovery
    |
output/findings/FINDINGS.md  <-  append entry
    |
context/run_context.md        <-  update confirmed facts
    |
knowledge/                    <-  canonical reference docs
    |
docs/adr/    <-  open ADR only when a decision is made
```

## 6. Agent Skills (`.agents/skills/`)

| Skill                          | Purpose                                          |
| ------------------------------ | ------------------------------------------------ |
| [[architect]].md               | System design, component boundaries, ADR-first   |
| [[code-reviewer]].md           | Code quality, security, ADR coverage check       |
| [[adr-writer]].md              | Write and maintain Architecture Decision Records |
| [[decision-logger]].md         | Extract decisions embedded in code               |
| [[unknown-domain-protocol]].md | What to do when encountering something unknown   |

## 7. Role Separation

| Role                 | Skill              | Handles                                     |
| -------------------- | ------------------ | ------------------------------------------- |
| **[[Archeologist]]** | domain specialists | Reading, probing, documenting existing code |
| **[[Architect]]**    | `architect`        | Designing and writing NEW code              |
| **[[Reviewer]]**     | `code-reviewer`    | Reviewing all changes before merge          |

## 8. Output Standards

* `output/findings/FINDINGS.md` -- archaeology ledger (update on every finding)
* `output/probe_results.json` -- hardware/system probe output
* `output/retro-report.md` -- codebase analysis report

## 9. Layer Separation

| Layer | Location | What it is |
|-------|----------|------------|
| **Library** | `library/` | Reusable package |
| **Experiment** | `experiments/` | Isolated probes to test behavior |

Rules:
* Libraries must be importable independently
* Install with `pip install -e "library/.[extras]"` from repo root
* Every component must have its own ADR trail

## 10. Experiment Isolation

All code executions for testing behavior run in Docker containers.

* Experiment Dockerfiles live in `experiments/docker/`
* Results are written to `output/` via volume mounts
* Exception: hardware experiments may run natively when Docker cannot pass through the device

## 11. ADR-First Mandate

**HARD STOP. No exceptions. No bypasses except trivial fixes.**

> **You must write an ADR before changing any library source code.**

This applies to:
- Any file in `library/my_package/*.py`
- Any new library module added to `library/`

### The rule

1. **Discovery** -- identify the design decision or integration change needed
2. **Write the ADR** -- create `docs/adr/ADR-NNNN-<decision-title>.md`
   - Next sequence number from `docs/adr/index.md`
   - Document: context, considered options, decision, positive/negative consequences
   - Include `Implementation: library/...` link
   - Add to `docs/adr/index.md`
3. **Then write the code** -- commit the ADR and the code change together

### CI enforcement

`tools/check_adr_gate.py` runs on every push and PR.
It exits 1 (blocks merge) if library files change without a new `ADR-*.md`.

**Bypass** (trivial fixes only): add `[skip-adr]` to the commit message.

### Decision table

| Requires ADR | `[skip-adr]` OK |
|---|---|
| New public API | Typo fix in docstring |
| Changed behavior of existing API | Comment clarification |
| New cryptographic primitive | Test addition for existing behavior |
| New threading model | Dependency version bump |
| Any breaking change | Lint/format fix |
