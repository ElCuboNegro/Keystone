"""
keystone_nfc.registry — Persistent vault registry at ~/.keystone/vaults.json

Tracks configured vault locations across sessions. A vault is "present" when
its path exists on the filesystem — supports removable drives and network shares.
"""

__all__ = ['VaultEntry', 'VaultRegistry', 'find_encrypted', 'REGISTRY_FILE', 'ENC_EXT']

import json
import os
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

REGISTRY_DIR  = Path.home() / '.keystone'
REGISTRY_FILE = REGISTRY_DIR / 'vaults.json'
DEFAULT_WORK  = '.working'
ENC_EXT       = '.enc'


@dataclass
class VaultEntry:
    id:           str
    name:         str
    vault_path:   str
    workdir_path: Optional[str] = None   # None → vault/.working

    @property
    def vault(self) -> Path:
        return Path(self.vault_path)

    @property
    def workdir(self) -> Path:
        if self.workdir_path:
            return Path(self.workdir_path)
        return self.vault / DEFAULT_WORK

    def is_present(self) -> bool:
        """True when the vault folder exists (drive mounted, path accessible)."""
        return self.vault.is_dir()

    def status(self) -> str:
        """'not_found' | 'locked' | 'open' | 'empty'"""
        if not self.is_present():
            return 'not_found'
        if self.workdir.exists():
            return 'open'
        return 'locked' if find_encrypted(self.vault) else 'empty'


def find_encrypted(vault: Path) -> List[Path]:
    """All .enc files in the vault (recursive), excluding the working directory."""
    return sorted(
        p for p in vault.rglob('*' + ENC_EXT)
        if DEFAULT_WORK not in p.parts
    )


class VaultRegistry:
    def __init__(self, path: Path = REGISTRY_FILE):
        self._path   = path
        self._vaults: List[VaultEntry] = []
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            self._vaults = []
            return
        try:
            data = json.loads(self._path.read_text('utf-8'))
            self._vaults = [VaultEntry(**v) for v in data.get('vaults', [])]
        except Exception:
            self._vaults = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({'vaults': [asdict(v) for v in self._vaults]}, indent=2)
        # Atomic write
        tmp = self._path.with_suffix('.tmp')
        tmp.write_text(payload, encoding='utf-8')
        os.replace(tmp, self._path)

    # ── Public API ────────────────────────────────────────────────────────────

    def all(self) -> List[VaultEntry]:
        return list(self._vaults)

    def present(self) -> List[VaultEntry]:
        """Vaults whose path currently exists on the filesystem."""
        return [v for v in self._vaults if v.is_present()]

    def get(self, vault_id: str) -> Optional[VaultEntry]:
        return next((v for v in self._vaults if v.id == vault_id), None)

    def add(self, name: str, vault_path: Path,
            workdir_path: Optional[Path] = None) -> VaultEntry:
        entry = VaultEntry(
            id=str(uuid.uuid4()),
            name=name,
            vault_path=str(vault_path.resolve()),
            workdir_path=str(workdir_path.resolve()) if workdir_path else None,
        )
        self._vaults.append(entry)
        self._save()
        return entry

    def remove(self, vault_id: str) -> bool:
        before = len(self._vaults)
        self._vaults = [v for v in self._vaults if v.id != vault_id]
        if len(self._vaults) < before:
            self._save()
            return True
        return False

    def update(self, vault_id: str, **kwargs) -> bool:
        entry = self.get(vault_id)
        if not entry:
            return False
        for k, v in kwargs.items():
            if hasattr(entry, k):
                setattr(entry, k, v)
        self._save()
        return True
