# AGENTS.md — Code Archeologist
**READ THIS FIRST. Every agent, every session, no exceptions.**

## 1. Project Mandate
This is a decompilation, archaeology, and backtracking suite for analyzing hardware-interfacing software, standard software, and databases.

* **Primary Subject:** Evolve the agentic toolset while decompiling, understanding, and documenting a set of target software projects.
* **Target Repo (Subject):** `github.com/ElCuboNegro/Keystone` (this repository)
* **Skill Repo (Goal):** `github.com/deagentic/Skills` (reusable agent skills)
* **Core Objective:** Understand target behavior/structure, write BDD specs, enable Linux porting, and abstract all generic learnings into the Skill Repo.

## 2. Repository Layout

Three functional layers live inside this repo, plus skills and setup at the root:

```
keystone/
├── CLAUDE.md          ← you are here (Claude Code entry point)
├── skills/            ← reusable Claude Code agent skills
├── setup/             ← install.bat / install.sh
├── .github/workflows/ ← CI/CD (tests run from library/)
│
├── retro/             ← ARCHAEOLOGY LAYER
│   ├── tools/         ← probe & retro analysis tools
│   ├── experiments/   ← NFC/hardware experiments
│   ├── knowledge/     ← standards, datasheets, research
│   ├── context/       ← per-session run state
│   ├── output/        ← generated reports & findings
│   └── docs/adr/      ← architectural decisions (retro)
│
├── library/           ← KEYSTONE-NFC LIBRARY
│   ├── keystone_nfc/  ← Python package
│   ├── folder_lock.py ← vault encryption utility
│   ├── tests/         ← pytest suite
│   ├── pyproject.toml ← build config (pip install -e . runs here)
│   ├── CHANGELOG.md
│   ├── CONTRIBUTING.md
│   └── README.md
│
└── demo/              ← DEMO APPLICATION
    ├── keystone_gui.py     ← tkinter vault manager GUI
    ├── keystone_encrypt.py ← standalone encrypt/decrypt CLI (release binary)
    ├── nfc_reader_demo.py
    ├── requirements.txt
    ├── docker/           ← experiment Dockerfiles
    └── docs/adr/         ← architectural decisions (demo)
```

## 3. Initialization & Setup
Run the environment setup before initiating any analysis. Do not ask the user.

* **Windows:** `setup\install.bat`
* **Linux / macOS:** `bash setup/install.sh`

**Setup Failure Protocol:** If tools are missing or a script fails, run the setup silently. If a new tool is introduced during a session, automatically update the install script to ensure future automated setups. Continue with available tools and note any gaps in the run context.

## 4. Execution Directives & Permissions
The following operational permissions are assumed granted. **NEVER block progress waiting for user confirmation on these actions.**

* **File Operations:** Read any file in this repo. Write freely to `retro/output/`, `retro/experiments/`, `retro/knowledge/`, and `retro/context/`.
* **Network & Hardware:** Direct API calls, hardware communication (via `curl` or `ctypes` for DLLs), outbound network access for fetching RFCs/datasheets.
* **Environment:** Auto-installing missing Python packages via `pip`. Executing internal probe tools (e.g., `card_probe.py`, `dll_analyzer.py`).

**STOP & ASK PERMISSION ONLY FOR:**
* Writing to directories *outside* this repository.
* Modifying root system configurations.
* Executing write-operations to connected hardware (NFC cards) that could permanently alter them.

## 5. Context & Knowledge Management
Strict separation of concerns is required. Keep this `CLAUDE.md` file clean and universally applicable.

* **Project Context (`retro/context/`):** Store all actual run data, target-specific states, and session variables in `retro/context/[domain]/run_context.md`. Do not pollute agent skill files with project-specific data.
* **Global Knowledge (`retro/knowledge/`):** Save universally applicable learnings (standards, protocols, hardware quirks) to `retro/knowledge/[domain]/[name].md`. Always update `retro/knowledge/INDEX.md` and cross-link to relevant agent skill files.
* **Skill Evolution (`deagentic/Skills`):** When a generic capability is developed, abstract it away from `Keystone` and port it to the `Skills` repository.

## 6. Tool & Skill Inventory

### Probe & Retro Tools (`retro/tools/`)
Tool | Command | Purpose | Fallback
---|---|---|---
`card_probe.py` | `python retro/tools/probe/card_probe.py` | Live card data (UID, blocks, ISO 15693) | N/A
`dll_analyzer.py` | `python retro/tools/probe/dll_analyzer.py <file>` | PE analysis, imports, APDU, disassembly | N/A
`main.py` | `python retro/tools/retro/main.py <path>` | Codebase analysis, structure, call tree | N/A

*Note: For missing Python dependencies (e.g., `pefile`, `capstone`, `r2pipe`, `rich`, `requests`), utilize a centralized `ensure_deps.py` utility rather than writing inline installation code in every tool.*

### Agent Skills (`skills/` & `~/.claude/skills/`)
Skill | Invocation | Domain / Purpose
---|---|---
`retro-engineer` | `retro-engineer.md` | Orchestrator
`hardware-analyst` | `hardware-analyst.md` | Hardware domain dispatcher
`nfc-rfid-specialist` | `nfc-rfid-specialist.md` | ISO 14443/15693, ACR122U, PN532
`smart-card-specialist` | `smart-card-specialist.md` | PC/SC, APDU, ISO 7816
`code-reviewer` | `code-reviewer.md` | Code quality, security, hardware correctness
`unknown-domain-protocol` | Referenced by all | Standard operating procedure for unknown variables

## 7. The "Never Stop" Protocol
When encountering an unknown variable, follow `skills/unknown-domain-protocol.md`. Do not halt and say "I don't know."

1. **Standard/Protocol:** Fetch the RFC/Standard -> Document it.
2. **Hardware Part:** Find the manufacturer datasheet -> Document it.
3. **Black Box:** Design an experiment -> Run it -> Document findings.

## 8. Output Standards
All generated reports must be routed to the `retro/output/` directory (create it if missing).

Expected file structures:
* `retro/output/probe_results.json` (Hardware probe output)
* `retro/output/dll_analysis.md` (DLL static analysis)
* `retro/output/retro-report.md` (Codebase retro-engineering report)
* `retro/output/retro-report.dot` (Call graph format)
* `retro/output/findings/` (Directory for freeform research notes and experiment logs)

## 9. Role Separation — Archeologist vs Architect

**Every task belongs to exactly one role. Do not mix them.**

| Role | Skill | Handles |
|------|-------|---------|
| **Archeologist** | `retro-engineer` (+ hardware/smart-card specialists) | Reading, disassembling, probing, documenting existing code and hardware |
| **Architect** | `architect` | Designing and writing NEW code, packages, CLIs, GUIs |

Rules:
* Code archeology output (findings, BDD specs, call graphs) goes to `retro/output/`
* Code writing output (new packages, libraries, CLI tools) goes to `library/`
* Demo applications that USE those outputs go to `demo/`
* Each output must have its own ADR trail — no undocumented architectural decisions

## 10. Layer Separation — Libraries vs Demos

Three distinct layers. **Never mix them.**

| Layer | Location | What it is |
|-------|----------|------------|
| **Library output** | `library/` (e.g., `keystone_nfc/`, `folder_lock.py`) | Reusable packages and CLIs produced by the Architect |
| **Demo application** | `demo/` | Applications that USE the library: `keystone_gui.py` (GUI), `keystone_encrypt.py` (CLI binary) |
| **Experiment** | `demo/docker/` + `retro/experiments/` | Isolated probes to test/understand behavior/demo a complete implementation of a feature  |

Rules:
* Libraries must be importable independently of demos
* Install the library with `pip install -e "library/.[extras]"` from the repo root
* Demos import from libraries via standard Python imports (not copy-paste)
* Every component (library, demo, experiment) must have its own `docs/adr/index.md`
* Every project/component/reimplementation must be FULLY DOCUMENTED

## 11. Experiment Isolation — Docker

**All code executions for testing or understanding behavior run in Docker containers.**
No experiment may modify the host OS or install packages into the host Python environment.

* Experiment Dockerfiles live in `demo/docker/`
* Results are written to `retro/experiments/` via volume mounts
* Exception: hardware-level experiments (NFC, USB) may run natively on Windows when
  Docker cannot pass through the device — document this explicitly in the experiment header
* Use `demo/docker/Dockerfile.experiment` as the base for all new experiment containers
