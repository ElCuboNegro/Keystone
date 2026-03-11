# DEMO — Keystone Implementations

This directory contains concrete implementations built to demonstrate and validate the knowledge
gained through code archaeology on the ASUS SoulKey/Keystone system.

---

## Structure

```
DEMO/
├── README.md               <- this file
├── docs/adr/               <- Architecture Decision Records for this DEMO
│   ├── index.md
│   └── ADR-XXXX-*.md
├── docker/                 <- isolated experiment containers
│   └── Dockerfile.experiment
├── keystone_gui.py         <- vault manager GUI (demo application)
└── (keystone_nfc/ and folder_lock.py live at repo root as library outputs)
```

---

## Separation of concerns

| Layer | Location | What it is |
|-------|----------|------------|
| **Library output** | `/keystone_nfc/` | Reusable NFC package (the archeology result) |
| **Application output** | `/folder_lock.py` | Vault CLI (the architecture result) |
| **Demo application** | `/DEMO/keystone_gui.py` | GUI that uses the library + application |
| **Experiments** | `/DEMO/docker/` | Isolated Docker containers for probing/testing |

---

## Running the GUI

```bash
# From repo root
pip install cryptography watchdog pystray Pillow
python DEMO/keystone_gui.py
```

The window will be hidden on start. Insert your Keystone NFC card to reveal it.

---

## Architecture Decision Records

All architectural decisions for this DEMO are in `docs/adr/`. See `docs/adr/index.md`.

---

## Experiment isolation

All code executions for understanding/testing behavior run inside Docker containers
to avoid any modification of the host OS. See `docker/Dockerfile.experiment`.
