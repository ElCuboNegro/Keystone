"""
keystone_nfc.watcher — Real-time file watcher for an open vault's working directory.

Watches for file system events in the workdir and fires encrypted-vault sync
operations. Uses a 500ms debounce to handle editors that write multiple events
per save (write-to-tmp + rename pattern used by VS Code, Obsidian, etc.).

Threading: all callbacks fire from the watchdog observer thread.
The caller must post to a UI queue if they need to update widgets.
"""

import threading
import logging
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger('keystone_nfc.watcher')

# File patterns to ignore (editor temp files, OS metadata)
_IGNORE_SUFFIXES = {'.tmp', '.swp', '.swo', '.bak', '.orig', '.DS_Store'}
_IGNORE_PREFIXES = {'.', '~'}


def _should_ignore(rel_path: str) -> bool:
    name = Path(rel_path).name
    return (
        any(name.startswith(p) for p in _IGNORE_PREFIXES) or
        any(name.endswith(s) for s in _IGNORE_SUFFIXES) or
        name == '.working' or
        rel_path.endswith('.enc')
    )


class VaultWatcher:
    """Watches a workdir and keeps the vault in sync.

    Args:
        workdir:    Path being watched (plaintext working directory)
        on_encrypt: callable(rel_path: str, content: bytes) — file created/modified
        on_delete:  callable(rel_path: str) — file deleted
        on_move:    callable(old_rel: str, new_rel: str, content: bytes) — file renamed/moved
        on_error:   optional callable(exc: Exception)
        debounce:   seconds between last event and actual encrypt (default 0.5)
    """

    def __init__(
        self,
        workdir:    Path,
        on_encrypt: Callable[[str, bytes], None],
        on_delete:  Callable[[str], None],
        on_move:    Callable[[str, str, bytes], None],
        on_error:   Optional[Callable[[Exception], None]] = None,
        debounce:   float = 0.5,
    ):
        self._workdir    = workdir
        self._on_encrypt = on_encrypt
        self._on_delete  = on_delete
        self._on_move    = on_move
        self._on_error   = on_error
        self._debounce   = debounce
        self._pending: dict = {}   # rel_path -> threading.Timer
        self._lock   = threading.Lock()
        self._observer = None

    def start(self) -> None:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        watcher = self

        class _Handler(FileSystemEventHandler):
            def _rel(self, path):
                try:
                    return Path(path).relative_to(watcher._workdir).as_posix()
                except ValueError:
                    return None

            def on_created(self, event):
                if event.is_directory:
                    return
                rel = self._rel(event.src_path)
                if rel and not _should_ignore(rel):
                    watcher._schedule(rel)

            def on_modified(self, event):
                if event.is_directory:
                    return
                rel = self._rel(event.src_path)
                if rel and not _should_ignore(rel):
                    watcher._schedule(rel)

            def on_deleted(self, event):
                if event.is_directory:
                    return
                rel = self._rel(event.src_path)
                if rel and not _should_ignore(rel):
                    watcher._cancel(rel)
                    watcher._fire_delete(rel)

            def on_moved(self, event):
                if event.is_directory:
                    return
                old_rel = self._rel(event.src_path)
                new_rel = self._rel(event.dest_path)
                if not old_rel or not new_rel:
                    return
                if _should_ignore(new_rel):
                    return
                watcher._cancel(old_rel)
                watcher._fire_move(old_rel, new_rel)

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(self._workdir), recursive=True)
        self._observer.start()
        log.info('Watcher started: %s', self._workdir)

    def stop(self) -> None:
        # Cancel all pending debounce timers
        with self._lock:
            for t in self._pending.values():
                t.cancel()
            self._pending.clear()
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3.0)
            self._observer = None
        log.info('Watcher stopped.')

    # ── Debounce ──────────────────────────────────────────────────────────────

    def _schedule(self, rel_path: str):
        """Cancel existing timer for rel_path and start a fresh debounce timer."""
        with self._lock:
            if rel_path in self._pending:
                self._pending[rel_path].cancel()
            t = threading.Timer(self._debounce, self._fire_encrypt, args=(rel_path,))
            self._pending[rel_path] = t
            t.start()

    def _cancel(self, rel_path: str):
        with self._lock:
            if rel_path in self._pending:
                self._pending.pop(rel_path).cancel()

    # ── Fire operations ───────────────────────────────────────────────────────

    def _fire_encrypt(self, rel_path: str):
        with self._lock:
            self._pending.pop(rel_path, None)
        try:
            path = self._workdir / rel_path
            if not path.exists():
                return   # deleted before debounce fired
            content = path.read_bytes()
            self._on_encrypt(rel_path, content)
            log.debug('Synced to vault: %s', rel_path)
        except Exception as e:
            log.error('Encrypt error for %s: %s', rel_path, e)
            if self._on_error:
                self._on_error(e)

    def _fire_delete(self, rel_path: str):
        try:
            self._on_delete(rel_path)
            log.debug('Deleted from vault: %s', rel_path)
        except Exception as e:
            log.error('Delete error for %s: %s', rel_path, e)
            if self._on_error:
                self._on_error(e)

    def _fire_move(self, old_rel: str, new_rel: str):
        try:
            path = self._workdir / new_rel
            if not path.exists():
                return
            content = path.read_bytes()
            self._on_move(old_rel, new_rel, content)
            log.debug('Moved in vault: %s -> %s', old_rel, new_rel)
        except Exception as e:
            log.error('Move error %s -> %s: %s', old_rel, new_rel, e)
            if self._on_error:
                self._on_error(e)
