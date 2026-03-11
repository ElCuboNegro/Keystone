---
type: index
purpose: Master catalogue of all knowledge files in this project
---

# Knowledge Base Index

Every file in this directory was either fetched from a standard, extracted from a
datasheet, or reverse-engineered via experiment. Each entry shows its source and
confidence level.

---

## NFC / RFID

| File | Type | Source | Confidence | Used by |
|------|------|--------|-----------|---------|
| [iso-15693.md](nfc/iso-15693.md) | Standard | ISO 15693-2/3 | High | nfc-rfid-specialist |
| [acr122u-commands.md](nfc/acr122u-commands.md) | Datasheet | ACS ACR122U API + NXP PN532 UM | High | nfc-rfid-specialist |
| [rf-field-timing.md](nfc/rf-field-timing.md) | Research | Code analysis + experimentation | High | nfc-rfid-specialist, smart-card-specialist |

---

## Smart Card / PC-SC

| File | Type | Source | Confidence | Used by |
|------|------|--------|-----------|---------|
| [pcsc-api.md](smartcard/pcsc-api.md) | Standard | PC/SC Workgroup spec + MSDN | High | smart-card-specialist |
| [apdu-reference.md](smartcard/apdu-reference.md) | Standard | ISO 7816-4 | High | smart-card-specialist, nfc-rfid-specialist |

---

## Reverse-Engineered / Research Findings

| File | Status | What it covers | Confidence |
|------|--------|---------------|-----------|
| [soulkey-architecture-research.md](nfc/soulkey-architecture-research.md) | Reverse-engineered | Full ASUS SoulKey/Keystone internal architecture, call flow, card state machine, root cause of millisecond problem | High |

---

## Agent Skills Index

| Skill file | Tier | Purpose |
|-----------|------|---------|
| `skills/retro-engineer.md` | 0 — Orchestrator | Entry point, dispatches to Tier 1 |
| `skills/hardware-analyst.md` | 1 — Dispatcher | Detects hardware domain, invokes Tier 2 |
| `skills/nfc-rfid-specialist.md` | 2 — Specialist | ISO 14443/15693, ACR122U, PN532, NfcCx |
| `skills/smart-card-specialist.md` | 2 — Specialist | PC/SC, APDU, ISO 7816, ATR |
| `skills/usb-hid-specialist.md` | 2 — Specialist | libusb, hidapi, CCID, HID reports |
| `skills/serial-specialist.md` | 2 — Specialist | UART, RS-232/485, pyserial, Modbus |
| `skills/bluetooth-specialist.md` | 2 — Specialist | BLE, GATT, BlueZ, bleak |
| `skills/embedded-specialist.md` | 2 — Specialist | GPIO, SPI, I2C, interrupts, RTOS |
| `skills/bdd-writer.md` | 3 — Cross-cutting | Generates Gherkin BDD specs from retro output |
| `skills/decision-logger.md` | 3 — Cross-cutting | Extracts and catalogues software decisions |
| `skills/unknown-domain-protocol.md` | 3 — Cross-cutting | Standard procedure for unknown variables |
| `skills/architect.md` | Advisor | System design, coupling, boundaries, ADR recommendations |
| `skills/security-expert.md` | Advisor | Threat modeling, crypto review, auth failure standards |
| `skills/database-expert.md` | Advisor | Schema, queries, migrations, SQLite specifics |
| `skills/ux-expert.md` | Advisor | User flows, heuristics, error messages, accessibility |
| `skills/gitops-expert.md` | Advisor | CI/CD, branching, secrets, release management |

---

## How to add a new entry

1. Create the knowledge file in the appropriate subdirectory
2. Add the frontmatter header (see `skills/unknown-domain-protocol.md`)
3. Add a row to the table above
4. Link the file from the relevant agent's skill file
