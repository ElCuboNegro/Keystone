"""Tests for keystone_nfc.registry — VaultEntry, VaultRegistry, find_encrypted."""
import json
from pathlib import Path

import pytest

from keystone_nfc.registry import (
    DEFAULT_WORK,
    ENC_EXT,
    VaultEntry,
    VaultRegistry,
    find_encrypted,
)


# ── VaultEntry ────────────────────────────────────────────────────────────────

def test_vault_property(tmp_path: Path) -> None:
    e = VaultEntry(id='1', name='Test', vault_path=str(tmp_path))
    assert e.vault == tmp_path


def test_workdir_default_is_working_subdir(tmp_path: Path) -> None:
    e = VaultEntry(id='1', name='Test', vault_path=str(tmp_path))
    assert e.workdir == tmp_path / DEFAULT_WORK


def test_workdir_custom(tmp_path: Path) -> None:
    custom = tmp_path / 'mywork'
    e = VaultEntry(id='1', name='Test',
                   vault_path=str(tmp_path),
                   workdir_path=str(custom))
    assert e.workdir == custom


def test_is_present_true(tmp_path: Path) -> None:
    e = VaultEntry(id='1', name='Test', vault_path=str(tmp_path))
    assert e.is_present() is True


def test_is_present_false(tmp_path: Path) -> None:
    missing = tmp_path / 'nonexistent'
    e = VaultEntry(id='1', name='Test', vault_path=str(missing))
    assert e.is_present() is False


def test_status_not_found(tmp_path: Path) -> None:
    e = VaultEntry(id='1', name='Test', vault_path=str(tmp_path / 'gone'))
    assert e.status() == 'not_found'


def test_status_empty(tmp_path: Path) -> None:
    e = VaultEntry(id='1', name='Test', vault_path=str(tmp_path))
    assert e.status() == 'empty'


def test_status_locked(tmp_path: Path) -> None:
    (tmp_path / 'abc123.enc').write_bytes(b'\x00')
    e = VaultEntry(id='1', name='Test', vault_path=str(tmp_path))
    assert e.status() == 'locked'


def test_status_open(tmp_path: Path) -> None:
    workdir = tmp_path / DEFAULT_WORK
    workdir.mkdir()
    (tmp_path / 'abc123.enc').write_bytes(b'\x00')
    e = VaultEntry(id='1', name='Test', vault_path=str(tmp_path))
    assert e.status() == 'open'


# ── find_encrypted ────────────────────────────────────────────────────────────

def test_find_encrypted_empty_vault(tmp_path: Path) -> None:
    assert find_encrypted(tmp_path) == []


def test_find_encrypted_finds_enc_files(tmp_path: Path) -> None:
    f1 = tmp_path / 'aaa.enc'
    f2 = tmp_path / 'bbb.enc'
    f1.write_bytes(b'x')
    f2.write_bytes(b'x')
    result = find_encrypted(tmp_path)
    assert f1 in result
    assert f2 in result


def test_find_encrypted_excludes_working_dir(tmp_path: Path) -> None:
    workdir = tmp_path / DEFAULT_WORK
    workdir.mkdir()
    enc_in_workdir = workdir / 'secret.enc'
    enc_in_workdir.write_bytes(b'x')
    enc_in_vault = tmp_path / 'real.enc'
    enc_in_vault.write_bytes(b'x')
    result = find_encrypted(tmp_path)
    assert enc_in_vault in result
    assert enc_in_workdir not in result


def test_find_encrypted_recursive(tmp_path: Path) -> None:
    sub = tmp_path / 'subdir'
    sub.mkdir()
    f = sub / 'deep.enc'
    f.write_bytes(b'x')
    assert f in find_encrypted(tmp_path)


def test_find_encrypted_ignores_non_enc(tmp_path: Path) -> None:
    (tmp_path / 'notes.md').write_bytes(b'x')
    (tmp_path / 'image.png').write_bytes(b'x')
    assert find_encrypted(tmp_path) == []


def test_find_encrypted_returns_sorted(tmp_path: Path) -> None:
    names = ['zzz.enc', 'aaa.enc', 'mmm.enc']
    for n in names:
        (tmp_path / n).write_bytes(b'x')
    result = find_encrypted(tmp_path)
    assert result == sorted(result)


# ── VaultRegistry ─────────────────────────────────────────────────────────────

@pytest.fixture
def registry(tmp_path: Path) -> VaultRegistry:
    """Registry backed by a temp file — isolated from ~/.keystone."""
    return VaultRegistry(path=tmp_path / 'vaults.json')


def test_registry_starts_empty(registry: VaultRegistry) -> None:
    assert registry.all() == []


def test_registry_add(registry: VaultRegistry, tmp_path: Path) -> None:
    vault_dir = tmp_path / 'vault'
    vault_dir.mkdir()
    entry = registry.add('My Vault', vault_dir)
    assert entry.name == 'My Vault'
    assert entry.vault == vault_dir.resolve()
    assert len(registry.all()) == 1


def test_registry_add_persists(tmp_path: Path) -> None:
    """Data survives creating a new VaultRegistry instance from the same file."""
    path = tmp_path / 'reg.json'
    vault_dir = tmp_path / 'vault'
    vault_dir.mkdir()

    r1 = VaultRegistry(path=path)
    r1.add('Persistent', vault_dir)

    r2 = VaultRegistry(path=path)
    assert len(r2.all()) == 1
    assert r2.all()[0].name == 'Persistent'


def test_registry_get(registry: VaultRegistry, tmp_path: Path) -> None:
    vault_dir = tmp_path / 'vault'
    vault_dir.mkdir()
    entry = registry.add('V', vault_dir)
    found = registry.get(entry.id)
    assert found is not None
    assert found.id == entry.id


def test_registry_get_missing(registry: VaultRegistry) -> None:
    assert registry.get('nonexistent-id') is None


def test_registry_remove(registry: VaultRegistry, tmp_path: Path) -> None:
    vault_dir = tmp_path / 'vault'
    vault_dir.mkdir()
    entry = registry.add('V', vault_dir)
    assert registry.remove(entry.id) is True
    assert registry.all() == []


def test_registry_remove_missing(registry: VaultRegistry) -> None:
    assert registry.remove('no-such-id') is False


def test_registry_present_filters_missing(registry: VaultRegistry, tmp_path: Path) -> None:
    existing = tmp_path / 'real'
    existing.mkdir()
    missing = tmp_path / 'gone'  # not created

    registry.add('Exists', existing)
    registry.add('Missing', missing)

    present = registry.present()
    assert len(present) == 1
    assert present[0].name == 'Exists'


def test_registry_update(registry: VaultRegistry, tmp_path: Path) -> None:
    vault_dir = tmp_path / 'vault'
    vault_dir.mkdir()
    entry = registry.add('Old Name', vault_dir)
    result = registry.update(entry.id, name='New Name')
    assert result is True
    assert registry.get(entry.id).name == 'New Name'


def test_registry_update_missing(registry: VaultRegistry) -> None:
    assert registry.update('no-id', name='X') is False


def test_registry_json_is_valid(registry: VaultRegistry, tmp_path: Path) -> None:
    vault_dir = tmp_path / 'vault'
    vault_dir.mkdir()
    registry.add('V', vault_dir)

    # The file must be valid JSON with expected structure
    path = tmp_path / 'vaults.json'
    data = json.loads(path.read_text())
    assert 'vaults' in data
    assert isinstance(data['vaults'], list)
    assert data['vaults'][0]['name'] == 'V'


def test_registry_atomic_write_no_partial(registry: VaultRegistry, tmp_path: Path) -> None:
    """After add(), no .tmp file should remain."""
    vault_dir = tmp_path / 'vault'
    vault_dir.mkdir()
    registry.add('V', vault_dir)
    tmp_file = tmp_path / 'vaults.tmp'
    assert not tmp_file.exists()
