# Contributing to keystone-nfc

Thank you for your interest in contributing. This document covers how to set up
the development environment, run tests, submit changes, and what to expect from
the review process.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Hardware Testing](#hardware-testing)
- [Submitting Changes](#submitting-changes)
- [Architecture Decisions](#architecture-decisions)

---

## Development Setup

```bash
# Clone
git clone https://github.com/ElCuboNegro/Keystone.git
cd Keystone

# Install in editable mode with all dev + vault dependencies
pip install -e ".[dev,vault]"

# Windows only (for WMI card-removal detection in the GUI demo)
pip install pywin32
```

Python 3.11 or later is required.

---

## Running Tests

```bash
# All tests that don't need hardware (runs in CI)
pytest tests/ -m "not hardware"

# Full suite with a physical card in the reader
pytest tests/ -v

# Single module
pytest tests/test_card.py -v

# With coverage
pytest tests/ -m "not hardware" --cov=keystone_nfc --cov-report=term-missing
```

### Hardware tests

Tests marked `@pytest.mark.hardware` require a Keystone NFC card in the reader.
They are skipped automatically in CI. The expected card UID is hardcoded in
`tests/test_e2e_vault.py` as `_KNOWN_UID` — update it to match your card if you
are using a different one.

---

## Code Style

```bash
# Lint
ruff check keystone_nfc/ folder_lock.py tests/

# Auto-fix safe issues
ruff check --fix keystone_nfc/ folder_lock.py tests/

# Type check
mypy keystone_nfc/
```

All new code must pass `ruff` and `mypy --strict` with no new errors.

Line length: 100 characters.

---

## Hardware Testing

The library communicates with NFC hardware via the PC/SC API (WinSCard on Windows,
pcsc-lite on Linux/macOS). If you are testing on Windows alongside ASUS ArmouryCrate:

- ArmouryCrate kills the RF field after every read (`SCardDisconnect(SCARD_UNPOWER_CARD)`).
- Physical card removal is detected via WMI (`AsusAtkWmiEvent`, EventID 180), not PC/SC.
- See `docs/adr/ADR-0010-hybrid-wmi-pcsc-monitor.md` for the full design rationale.

If you are on Linux or macOS (without ASUS software), the pure PC/SC path works as expected.

---

## Submitting Changes

1. **Fork** the repository and create a branch: `git checkout -b feat/my-change`
2. **Write tests** for any new behavior. Hardware-only paths must have `@pytest.mark.hardware`.
3. **Run the full local check**: `pytest -m "not hardware"` + `ruff check` + `mypy keystone_nfc/`
4. **Write or update the ADR** if you are making an architectural decision. See `docs/adr/index.md`.
5. **Open a pull request** against `main`. Describe the problem, the solution, and any trade-offs.

PRs that change the public API (`keystone_nfc/__init__.py` exports) must update `CHANGELOG.md`.

---

## Architecture Decisions

This project uses MADR-format Architecture Decision Records (ADRs).

- Library ADRs: `docs/adr/`
- Demo ADRs: `DEMO/docs/adr/`
- Index: `docs/adr/index.md`

Before making a significant design decision, check whether an existing ADR already covers it.
If not, create a new one using the existing ADRs as templates.

---

## Project Structure

```
keystone_nfc/      # The library — zero runtime dependencies
folder_lock.py     # Vault CLI/application that uses the library
DEMO/              # GUI demo that uses both keystone_nfc and folder_lock
tests/             # pytest test suite
docs/adr/          # Architecture Decision Records
knowledge/         # Domain knowledge (NFC, PC/SC, ASUS hardware)
experiments/       # Isolated probes and hardware experiments
```

See `CLAUDE.md` for the full project mandate and role separation rules.
