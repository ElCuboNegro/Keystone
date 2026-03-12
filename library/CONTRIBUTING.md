# Contributing to keystone-nfc

Thank you for your interest. This covers dev setup, running tests, code style, hardware
testing, and the PR process.

---

## Repository layout

This library lives inside the `library/` folder of the
[ElCuboNegro/Keystone](https://github.com/ElCuboNegro/Keystone) monorepo:

```
Keystone/
├── library/           <- you are here (this package)
│   ├── keystone_nfc/
│   ├── folder_lock.py
│   ├── tests/
│   └── pyproject.toml
├── retro/             <- reverse-engineering research, experiments, ADRs
│   ├── tools/
│   ├── experiments/
│   ├── knowledge/
│   └── docs/adr/      <- architectural decision records
└── skills/            <- Claude Code agent skills
```

---

## Development setup

```bash
git clone https://github.com/ElCuboNegro/Keystone.git
cd Keystone/library

# Editable install with all dev + vault dependencies
pip install -e ".[dev,vault]"

# Windows only (WMI card-removal detection)
pip install pywin32
```

Python 3.11 or later required.

---

## Running tests

```bash
# Software-only tests — runs in CI, no hardware needed
pytest tests/ -m "not hardware" -v

# Full suite with a physical Keystone card in the reader
pytest tests/ -v -s

# Single module
pytest tests/test_card.py -v

# With coverage
pytest tests/ -m "not hardware" --cov=keystone_nfc --cov-report=term-missing
```

### Hardware tests

Tests marked `@pytest.mark.hardware` require a Keystone NFC card physically in the reader.
They are skipped automatically in CI.

**Critical:** the correct workflow for hardware tests on Windows with ASUS ArmouryCrate is:
1. Remove the card from the reader
2. Run `pytest tests/ -m "hardware" -v -s`
3. When the prompt appears (`[HARDWARE] Insert your Keystone card NOW`), insert the card

If the card is already inserted when the test starts, ArmouryCrate will have already killed
the RF field and the detection will fail. See `README.md` — ASUS ArmouryCrate section.

The expected card UID is hardcoded in `tests/test_e2e_vault.py` as `_KNOWN_UID`. Update it
to match your card if you are using a different one.

---

## Code style

```bash
# Lint
ruff check keystone_nfc/ folder_lock.py tests/

# Auto-fix safe issues
ruff check --fix keystone_nfc/ folder_lock.py tests/

# Type check
mypy keystone_nfc/ --strict
```

All new code must pass `ruff` and `mypy --strict` with no new errors.
Line length: 100 characters.

---

## Submitting changes

1. Fork the repository, create a branch: `git checkout -b feat/my-change`
2. Write tests for any new behavior. Hardware-only paths must have `@pytest.mark.hardware`.
3. Run the full local check: `pytest -m "not hardware"` + `ruff check` + `mypy keystone_nfc/`
4. Write or update an ADR if you are making an architectural decision — see
   [`retro/docs/adr/index.md`](../retro/docs/adr/index.md).
5. Open a pull request against `master`. Describe the problem, the solution, and trade-offs.

PRs that change the public API (`keystone_nfc/__init__.py` exports) must update
`CHANGELOG.md`.

---

## Architectural Decision Records

This project uses MADR-format ADRs. They live in `retro/docs/adr/` in the monorepo root
(not inside `library/`) because many decisions span the archaeology work that informed the
implementation.

Before making a significant design decision, check whether an existing ADR already covers it.
If not, create a new one using the existing ADRs as templates.
