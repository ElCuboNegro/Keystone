# Keystone

Monorepo for the Keystone NFC smart-card project. Three layers, clearly separated.

```
keystone/
├── retro/     ← reverse-engineering, archaeology, hardware research
└── library/   ← keystone-nfc Python package + tests
```

Demo application lives in a separate repo: [ElCuboNegro/Keystone_encrypt](https://github.com/ElCuboNegro/Keystone_encrypt)

---

## Quick start

```bash
# Install the library (from repo root)
pip install -e "library/.[gui,vault]"

# Run tests
cd library && pytest tests/ -m "not hardware"

# Hardware tests (requires NFC card and reader)
cd library && pytest tests/ -m "hardware" -v -s
```

---

## Layers

### `library/` — keystone-nfc

Python package for NFC card event monitoring via PC/SC (WinSCard / pcsc-lite).

- `keystone_nfc/` — the installable package
- `folder_lock.py` — AES-GCM vault encryption utility
- `tests/` — pytest suite (unit + e2e vault + hardware)
- `pyproject.toml` — package metadata and build config

See [`library/README.md`](library/README.md) for full API docs.

### `retro/` — Reverse Engineering Layer

Tools, experiments, and knowledge base built while analyzing the ASUS ArmouryCrate/Keystone hardware and software stack.

- `retro/tools/` — static analysis tools (DLL analyzer, PC/SC probe, call-tree builder)
- `retro/experiments/` — NFC/hardware experiment scripts
- `retro/knowledge/` — ISO 15693, PC/SC, ACR122U, APDU reference docs
- `retro/output/` — generated reports and findings
- `retro/docs/adr/` — architectural decision records

---

## Agent skills

Reusable Claude Code skills live in `skills/` and are installed to `~/.claude/skills/`.

| Skill | Purpose |
|-------|---------|
| `retro-engineer` | Orchestrator for archaeology tasks |
| `hardware-analyst` | Hardware domain dispatcher |
| `nfc-rfid-specialist` | ISO 14443/15693, ACR122U, PN532 |
| `smart-card-specialist` | PC/SC, APDU, ISO 7816 |
| `code-reviewer` | Code quality, security, hardware correctness |
| `architect` | System design and component boundaries |
| `bdd-writer` | Gherkin specs from reverse-engineered behavior |

See `CLAUDE.md` for the full operating manual.
