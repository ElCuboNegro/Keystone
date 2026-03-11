"""
keystone_nfc.reader — KeystoneReader: the main public API.

Example usage:

    from keystone_nfc import KeystoneReader

    reader = KeystoneReader()

    @reader.on_card_inserted
    def handle(card):
        print(f'Card: {card.uid_hex}')

    @reader.on_card_removed
    def removed():
        print('Card removed')

    reader.start()
    input('Press Enter to stop...')
    reader.stop()

Synchronous one-shot read:

    card = KeystoneReader().read_once(timeout=10.0)
    print(card.uid_hex)
"""

import threading
import time
import logging
from ctypes import byref
from typing import Callable, List, Optional

from ._pcsc import (
    SCARDCONTEXT, DWORD,
    SCardEstablishContext, SCardReleaseContext,
    SCARD_SCOPE_USER, list_readers,
)
from ._pcsc import _check
from .card import CardInfo
from .monitor import CardMonitor
from .exceptions import NoReaderError, NoCardError, KeystoneError

log = logging.getLogger(__name__)


class KeystoneReader:
    """High-level NFC card reader with event callbacks and synchronous read.

    Reader selection:
    - If reader_name is given: use that reader (raises NoReaderError if not found)
    - If reader_name is None: auto-select the first available reader

    Platform notes:
    - Windows: uses the built-in NfcCx reader ("Microsoft IFD 0") or any connected reader
    - Linux:   requires pcscd running and an ACR122U / compatible reader connected
    """

    def __init__(self, reader_name: Optional[str] = None):
        self._preferred_name = reader_name
        self._monitor: Optional[CardMonitor] = None
        self._inserted_callbacks: List[Callable[[CardInfo], None]] = []
        self._removed_callbacks:  List[Callable[[], None]]         = []
        self._error_callbacks:    List[Callable[[Exception], None]] = []

    # ── Decorator API ─────────────────────────────────────────────────────────

    def on_card_inserted(self, fn: Callable[[CardInfo], None]) -> Callable:
        """Decorator: register a callback for card insertion events.

        The callback receives a CardInfo object with uid_hex, uid_bytes, block0, etc.
        """
        self._inserted_callbacks.append(fn)
        return fn

    def on_card_removed(self, fn: Callable[[], None]) -> Callable:
        """Decorator: register a callback for card removal events."""
        self._removed_callbacks.append(fn)
        return fn

    def on_error(self, fn: Callable[[Exception], None]) -> Callable:
        """Decorator: register a callback for monitor errors."""
        self._error_callbacks.append(fn)
        return fn

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background card monitor thread.

        Raises NoReaderError if no reader is found.
        """
        if self._monitor:
            raise KeystoneError('Reader already started. Call stop() first.')

        reader = self._resolve_reader()
        log.info('Starting monitor on reader: %s', reader)

        m = CardMonitor(reader)
        m.on_inserted = self._dispatch_inserted
        m.on_removed  = self._dispatch_removed
        m.on_error    = self._dispatch_error
        m.start()

        self._monitor = m

    def stop(self, timeout: float = 3.0) -> None:
        """Stop the background monitor thread."""
        if self._monitor:
            self._monitor.stop(timeout=timeout)
            self._monitor = None

    def __enter__(self) -> 'KeystoneReader':
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    # ── Synchronous read ──────────────────────────────────────────────────────

    def read_once(self, timeout: float = 30.0) -> CardInfo:
        """Block until a card is detected, read it, and return CardInfo.

        timeout: max seconds to wait for a card (default 30s)
        Raises NoCardError if timeout elapses before a card is detected.
        Raises NoReaderError if no reader is available.
        """
        result: List[Optional[CardInfo]] = [None]
        done = threading.Event()

        def _on_insert(card: CardInfo):
            result[0] = card
            done.set()

        reader = self._resolve_reader()
        m = CardMonitor(reader)
        m.on_inserted = _on_insert
        m.start()

        try:
            if not done.wait(timeout=timeout):
                raise NoCardError(f'No card detected within {timeout}s')
        finally:
            m.stop()

        return result[0]

    # ── Reader discovery ──────────────────────────────────────────────────────

    def available_readers(self) -> List[str]:
        """Return list of all currently available PC/SC reader names."""
        hCtx = SCARDCONTEXT()
        _check(SCardEstablishContext(SCARD_SCOPE_USER, None, None, byref(hCtx)),
               'SCardEstablishContext')
        try:
            return list_readers(hCtx)
        finally:
            SCardReleaseContext(hCtx)

    def _resolve_reader(self) -> str:
        readers = self.available_readers()
        if not readers:
            raise NoReaderError('No PC/SC readers found. Is the reader connected and pcscd/WinSCard running?')

        if self._preferred_name:
            # Exact match first, then substring
            for r in readers:
                if r == self._preferred_name:
                    return r
            for r in readers:
                if self._preferred_name.lower() in r.lower():
                    return r
            raise NoReaderError(
                f'Reader "{self._preferred_name}" not found. Available: {readers}'
            )

        log.debug('Auto-selected reader: %s', readers[0])
        return readers[0]

    # ── Callback dispatch ─────────────────────────────────────────────────────

    def _dispatch_inserted(self, card: CardInfo) -> None:
        for fn in self._inserted_callbacks:
            try:
                fn(card)
            except Exception as e:
                log.exception('on_card_inserted callback %s raised: %s', fn.__name__, e)

    def _dispatch_removed(self) -> None:
        for fn in self._removed_callbacks:
            try:
                fn()
            except Exception as e:
                log.exception('on_card_removed callback %s raised: %s', fn.__name__, e)

    def _dispatch_error(self, exc: Exception) -> None:
        for fn in self._error_callbacks:
            try:
                fn(exc)
            except Exception as e:
                log.exception('on_error callback %s raised: %s', fn.__name__, e)
        if not self._error_callbacks:
            log.error('Unhandled monitor error: %s', exc)
