# AGENTS.md — Cookiecutter Agentic CI Template
**READ THIS FIRST. Every agent, every session, no exceptions.**

## 1. Project Mandate

* **Repository:** `github.com/deagentic/cookiecutter-agentic-ci`
* **Description:** A Cookiecutter template for scaffolding Python projects with Agentic CI infrastructure.
* **Core Objective:** Evolve, document, and improve the Agentic CI template, including its core agent skills (`.agents/skills/`) and ADR mandate enforcement.

## 2. Core Routing Directives
You are operating within the Agentic CI template repository itself. Your behavior must be highly structured and strictly delegated to specialized sub-agents. All agent skills and instructions are located in `.agents/skills/`.

Depending on your platform (Gemini, Claude, Cursor), either use the `/activate_skill` tool OR read the corresponding `SKILL.md` file before proceeding:

1. **Reverse Engineering & Analysis**: If asked to reverse engineer, analyze, GENERATE THE EXECUTIONS GRAPH, or BACKTRACK the template or hooks, you MUST read/activate `.agents/skills/software/discovery/software-archeologist/SKILL.md`.
2. **Tool Creation**: If you determine a new tool or script is needed, or if instructed to create one, DO NOT write it yourself. You MUST read/activate `.agents/skills/core/tool-writer/SKILL.md` and delegate the task.
3. **Architecture**: If asked to design a system, review component boundaries, or make structural trade-offs, you MUST read/activate `.agents/skills/software/architecture/architect/SKILL.md`.
4. **Behavior Driven Development**: If asked to write Gherkin specs or BACKTRACK TO BDD FEATURE FILES, you MUST read/activate `.agents/skills/software/quality/bdd-writer/SKILL.md`.
5. **Decision Logging**: If analyzing code to extract why a hardcoded value or architectural choice was made, read/activate `.agents/skills/software/architecture/decision-logger/SKILL.md`.
6. **Architecture Decision Records**: If an architectural decision is made or confirmed, read/activate `.agents/skills/software/architecture/adr-writer/SKILL.md` to document it.
7. **The Learning Protocol**: If you learn a new domain concept, solve a recurring issue, discover a reusable pattern, or create a new generalized sub-agent, you MUST read/activate `.agents/skills/core/learning-protocol/SKILL.md` and persist the knowledge to the repository.
8. **Self-Repair Mandate**: If you detect any discrepancies in agent documentation or configurations (e.g., outdated file paths pointing to `skills/` instead of `.agents/skills/`), you must self-repair them by fixing the references across the workspace and committing the fix locally. Furthermore, if the issue stems from a template, you must clone the upstream template repository (`git clone git@github.com:deagentic/cookiecutter-agentic-ci.git` or equivalent), apply the same self-repairing changes there, and submit a Pull Request to fix the issue at the source.

## 3. DEDUPLICATION MANDATE
Before writing any new tool, script, or proposing a new agent, you MUST consult this `AGENTS.md` and `docs/tools/index.md`. Reuse and refine existing capabilities. If merging two similar tools, keep the CLI contract compatible.

## 4. Initialization & Setup

This repository is a cookiecutter template. No automated setup scripts are present at the root level.
Ensure you test changes to the template by generating a local project:
`cookiecutter . --no-input`

## 5. Context & Knowledge Management

```
Raw discovery
    |
docs/findings/FINDINGS.md  <-  append entry
    |
context/run_context.md        <-  update confirmed facts
    |
docs/knowledge/                    <-  canonical reference docs
    |
docs/adr/    <-  open ADR only when a decision is made
```

## 6. ADR-First Mandate

**HARD STOP. No exceptions. No bypasses except trivial fixes.**
> **You must write an ADR before changing any template architecture or core agent skill.**

1. **Discovery** -- identify the design decision or integration change needed
2. **Write the ADR** -- create `docs/adr/ADR-NNNN-<decision-title>.md`
3. **Then write the code** -- commit the ADR and the code change together



## 4. Golden Master Testing Mandate
**CRITICAL:** Standard BDD tests are not enough to prove parity for legacy migrations.
Every ported procedure MUST pass a Dual Execution test against the original database.
- Use the golden-master-validator agent.
- Generate seeds with boundary values, NULLs, and temporal edge cases.
- Execute SQL on DB -> Output A.
- Execute Python code -> Output B.
- Require Output A == Output B bit-by-bit.
