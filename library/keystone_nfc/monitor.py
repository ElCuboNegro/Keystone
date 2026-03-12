"""
keystone_nfc.monitor — Background thread that watches for card insert/remove events.

Uses SCardGetStatusChange with a short timeout so the thread can be stopped cleanly.
Works on NfcCx (Microsoft IFD 0) and ACR122U/pcsc-lite equally.

ASUS ArmouryCrate interaction notes
------------------------------------
ArmouryCrate reads the card via WM_INPUT (USB HID, WPARAM=0xB4) and then calls
SCardDisconnect(SCARD_UNPOWER_CARD), killing the RF field.  After that, NfcCx stops
RF polling and PC/SC reports SCARD_STATE_EMPTY even though the card is physically
present.  ArmouryCrate itself maintains persistent presence ("Enchufada") via HID
raw-input events — HandlePlugOut() only fires on a separate HID removal event.

Three mitigations this module applies:

1. Sharing violation on SCardConnect — ASUS holds an exclusive session for ~100 ms
   after card insertion.  We retry up to N times with a short sleep.

2. inserted_fired guard — on_removed only fires if on_inserted previously succeeded,
   preventing false removals when our initial card read fails.

3. Hybrid WMI/PCSC Monitor — When SCARD_STATE_EMPTY follows a successful insert,
   we suppress on_removed because ArmouryCrate killed the RF. Genuine physical
   removals are instead detected in real-time by a background WMI listener
   watching for AsusAtkWmiEvent (EventID 180).
"""

__all__ = ['CardMonitor']

import time
import threading
import logging
import platform
from ctypes import byref
from typing import Callable, Optional

try:
    import win32com.client
    import pywintypes
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

from ._pcsc import (
    SCARDCONTEXT, SCARDHANDLE, DWORD, SCARD_READERSTATE,
    SCARD_READERSTATE, SCardGetStatusChange, SCardConnect, SCardDisconnect,
    SCardBeginTransaction, SCardEndTransaction, SCardEstablishContext,
    SCardReleaseContext,
    SCARD_SCOPE_USER, SCARD_SHARE_SHARED, SCARD_PROTOCOL_ANY,
    SCARD_LEAVE_CARD,
    SCARD_STATE_UNAWARE, SCARD_STATE_PRESENT, SCARD_STATE_EMPTY,
    SCARD_STATE_CHANGED, SCARD_STATE_UNAVAILABLE,
    SCARD_E_TIMEOUT, SCARD_S_SUCCESS,
    transmit, list_readers, _str_arg,
)
from .card import CardInfo
from .exceptions import KeystoneError, PCSCError, CardRemovedError

log = logging.getLogger(__name__)

# APDUs — NfcCx-safe (confirmed by experiment)
_GET_UID    = [0xFF, 0xCA, 0x00, 0x00, 0x00]  # ISO 7816 pseudo-APDU: GET DATA (UID)
_READ_BLK0  = [0xFF, 0xB0, 0x00, 0x00, 0x04]  # READ BINARY block 0, 4 bytes

# Poll interval for SCardGetStatusChange — short enough for responsive detection,
# long enough to not busy-loop. 500ms is a good balance.
_POLL_MS = 500

# ArmouryCrate workaround: retry SCardConnect because ASUS holds an exclusive
# session for ~100 ms after card insertion.  5 × 50 ms = 250 ms total budget.
_CONNECT_RETRIES     = 5
_CONNECT_RETRY_DELAY = 0.05   # seconds between retries

# RF re-wake: after ArmouryCrate kills the RF field, we wait then try to
# re-trigger NfcCx RF polling via a fresh SCardConnect.  If the card is still
# physically present NfcCx rediscovers it within 1-2 poll cycles.
_REWAKE_DELAY   = 1.0    # seconds to wait before re-wake attempt
_REWAKE_RETRIES = 3      # number of SCardConnect attempts during re-wake
_REWAKE_RETRY_DELAY = 0.5  # seconds between re-wake attempts


class CardMonitor:
    """Background thread that fires callbacks on card insert/remove events.

    Usage:
        monitor = CardMonitor(reader_name)
        monitor.on_inserted = lambda card: print(card.uid_hex)
        monitor.on_removed  = lambda: print("removed")
        monitor.start()
        ...
        monitor.stop()
    """

    def __init__(self, reader: str):
        self.reader = reader
        self.on_inserted: Optional[Callable[[CardInfo], None]] = None
        self.on_removed:  Optional[Callable[[], None]] = None
        self.on_error:    Optional[Callable[[Exception], None]] = None

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._wmi_thread: Optional[threading.Thread] = None
        self._hCtx = SCARDCONTEXT()
        
        # Shared state between PC/SC and WMI threads
        self.inserted_fired = False

    def start(self) -> None:
        """Start the background monitor thread."""
        from ._pcsc import _check
        _check(SCardEstablishContext(SCARD_SCOPE_USER, None, None, byref(self._hCtx)),
               'SCardEstablishContext')
        self._stop_event.clear()
        
        # Start PC/SC polling thread
        self._thread = threading.Thread(target=self._run, name='keystone-monitor', daemon=True)
        self._thread.start()
        
        # Start WMI event listener thread (Windows only) for genuine physical removal
        if platform.system() == "Windows":
            if HAS_WMI:
                self._wmi_thread = threading.Thread(target=self._wmi_listener_run, name='keystone-wmi-monitor', daemon=True)
                self._wmi_thread.start()
            else:
                log.warning("pywin32 not installed. Real-time Keystone removal detection will not work!")
                
        log.debug('CardMonitor started for reader: %s', self.reader)

    def stop(self, timeout: float = 3.0) -> None:
        """Signal the monitor to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        if self._wmi_thread:
            self._wmi_thread.join(timeout=timeout)
        SCardReleaseContext(self._hCtx)
        log.debug('CardMonitor stopped.')

    def _run(self) -> None:
        """Main loop: poll SCardGetStatusChange and fire inserted/removed callbacks.

        ArmouryCrate mitigation: once on_inserted has fired, ALL subsequent
        SCARD_STATE_EMPTY events are suppressed.  NfcCx cannot distinguish
        "AC killed RF" from "card physically removed" — both report EMPTY.
        Since NfcCx won't re-discover the card after RF is killed (even with
        fresh SCardConnect), we mirror ArmouryCrate's model: card stays
        "present" until the WMI listener detects a physical removal event.

        Physical re-insertion (remove then re-insert) is handled naturally:
        removal → WMI fires on_removed, re-insert → PRESENT → on_inserted fires
        again with fresh card data.

        Startup probe: before entering the poll loop, we attempt a direct
        SCardConnect.  This serves two purposes:
          1. If the card is present and RF is on → we get it immediately.
          2. If RF is off (ArmouryCrate killed it) → the connect attempt itself
             signals NfcCx to resume RF polling.  We retry a few times with a
             short delay to let NfcCx re-discover the card.
        """
        rs = SCARD_READERSTATE()
        rs.szReader = _str_arg(self.reader)
        rs.dwCurrentState = SCARD_STATE_UNAWARE

        card_present = False
        self.inserted_fired = False

        # ── Startup probe ─────────────────────────────────────────────────────
        # Try direct connect before entering the polling loop.  Each attempt
        # may trigger NfcCx to restart RF; allow up to 3 × 800 ms = 2.4 s.
        log.debug('Startup probe: checking for card already in reader...')
        for attempt in range(3):
            if self._stop_event.is_set():
                return
            startup_card = self._read_card()
            if startup_card:
                log.info('Startup probe found card: %s', startup_card.uid_hex)
                card_present = True
                self.inserted_fired = True
                if self.on_inserted:
                    try:
                        self.on_inserted(startup_card)
                    except Exception as e:
                        log.exception('on_inserted callback raised: %s', e)
                break
            log.debug('Startup probe attempt %d/3 — no card yet', attempt + 1)
            self._stop_event.wait(0.8)
        else:
            log.debug('Startup probe: no card found — entering poll loop')

        while not self._stop_event.is_set():
            try:
                rv = SCardGetStatusChange(self._hCtx, _POLL_MS, byref(rs), 1)
                code = rv & 0xFFFFFFFF

                if code == SCARD_E_TIMEOUT & 0xFFFFFFFF:
                    # No state change — update current state and loop
                    rs.dwCurrentState = rs.dwEventState
                    continue

                if code != SCARD_S_SUCCESS:
                    log.warning('SCardGetStatusChange error: 0x%08X', code)
                    rs.dwCurrentState = SCARD_STATE_UNAWARE
                    continue

                event = rs.dwEventState

                if (event & SCARD_STATE_PRESENT) and not card_present:
                    card_present = True
                    log.debug('Card inserted')
                    card = self._read_card()
                    if card and self.on_inserted:
                        try:
                            self.on_inserted(card)
                            self.inserted_fired = True
                            log.debug('on_inserted fired — EMPTY events will '
                                      'be suppressed until next PRESENT cycle')
                        except Exception as e:
                            log.exception('on_inserted callback raised: %s', e)

                elif (event & SCARD_STATE_EMPTY) and card_present:
                    card_present = False
                    if self.inserted_fired:
                        # ArmouryCrate killed RF → SCARD_STATE_EMPTY while card
                        # is still physically present.  Suppress on_removed.
                        # Genuine removal is now handled by _wmi_listener_run!
                        log.info('EMPTY after successful insert — suppressed '
                                 '(ArmouryCrate RF kill, card still present)')
                    else:
                        log.debug('Suppressed phantom card-removed event '
                                  '(on_inserted never fired)')

                rs.dwCurrentState = event

            except Exception as e:
                log.error('Monitor loop error: %s', e)
                if self.on_error:
                    try:
                        self.on_error(e)
                    except Exception:
                        pass
                self._stop_event.wait(1.0)  # back off before retry

        # Monitor stopping — fire on_removed if card was considered present
        if self.inserted_fired and self.on_removed:
            log.debug('Monitor stopping with card present — firing on_removed')
            try:
                self.on_removed()
                self.inserted_fired = False
            except Exception as e:
                log.exception('on_removed callback raised during stop: %s', e)

    def _wmi_listener_run(self) -> None:
        """Background thread that listens for AsusAtkWmiEvent (EventID=180).
        
        Because WMI Event 180 fires on BOTH physical insertion and removal,
        we use our PC/SC state (self.inserted_fired) to disambiguate:
        If we receive an event and inserted_fired is True, it MUST be a removal.
        """
        try:
            # win32com requires CoInitialize per-thread
            import pythoncom
            pythoncom.CoInitialize()
            
            wmi = win32com.client.GetObject("winmgmts:root\\wmi")
            watcher = wmi.ExecNotificationQuery("SELECT * FROM AsusAtkWmiEvent")
            log.debug("WMI listener registered for AsusAtkWmiEvent")
            
            while not self._stop_event.is_set():
                try:
                    # Timeout after 1 second so we can check the _stop_event flag
                    event = watcher.NextEvent(1000)
                    
                    # Check if it's EventID 180 (Keystone insert/remove)
                    event_id = getattr(event, "EventID", None)
                    if event_id == 180:
                        log.debug("WMI listener caught EventID 180")
                        
                        if self.inserted_fired:
                            log.info("Physical Keystone removal detected via WMI!")
                            self.inserted_fired = False
                            if self.on_removed:
                                try:
                                    self.on_removed()
                                except Exception as e:
                                    log.exception('on_removed callback raised: %s', e)
                        else:
                            log.debug("WMI Event 180 ignored (likely physical insertion)")
                            
                except pywintypes.com_error as ce:
                    # Timeout exception is expected (WMI waiting for event)
                    if "timed out" not in str(ce) and "0x80043001" not in str(ce) and "Timeout" not in str(ce):
                        log.error("WMI listener COM error: %s", ce)
                        time.sleep(1.0)
                except Exception as e:
                    # Normal exception from timeout wrapped possibly?
                    if "timed out" not in str(e) and "0x80043001" not in str(e) and "Timeout" not in str(e):
                        log.error("WMI listener error: %s", e)
                        time.sleep(1.0)
                    
        except Exception as e:
            log.error("Failed to initialize WMI listener: %s", e)
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _read_card(self) -> Optional[CardInfo]:
        """Connect to the card, read UID and block 0, disconnect cleanly.

        ArmouryCrate mitigation #1: ASUS holds an exclusive session for ~100 ms
        after card insertion.  We retry SCardConnect up to _CONNECT_RETRIES
        times with a short sleep between attempts.
        """
        hCard = SCARDHANDLE()
        dwProto = DWORD()

        # Retry loop — ArmouryCrate briefly holds an exclusive lock
        for attempt in range(_CONNECT_RETRIES):
            rv = SCardConnect(
                self._hCtx, _str_arg(self.reader),
                SCARD_SHARE_SHARED, SCARD_PROTOCOL_ANY,
                byref(hCard), byref(dwProto),
            )
            if rv == 0:
                break
            log.debug('SCardConnect attempt %d/%d failed: 0x%08X',
                      attempt + 1, _CONNECT_RETRIES, rv & 0xFFFFFFFF)
            if attempt < _CONNECT_RETRIES - 1:
                time.sleep(_CONNECT_RETRY_DELAY)
        else:
            log.warning('SCardConnect failed after %d retries: 0x%08X',
                        _CONNECT_RETRIES, rv & 0xFFFFFFFF)
            return None

        proto = dwProto.value
        uid_raw = None
        block0  = None

        try:
            SCardBeginTransaction(hCard)
            try:
                uid_raw = _apdu_get_uid(hCard, proto)
                block0  = _apdu_read_block0(hCard, proto)
            finally:
                SCardEndTransaction(hCard, SCARD_LEAVE_CARD)

        except CardRemovedError:
            log.debug('Card removed during read — returning partial data')
        except PCSCError as e:
            log.warning('PC/SC error during card read: %s', e)
        except Exception as e:
            log.error('Unexpected error reading card: %s', e)
        finally:
            SCardDisconnect(hCard, SCARD_LEAVE_CARD)  # always LEAVE — never UNPOWER

        if uid_raw is None:
            return None

        return CardInfo.from_raw(uid_raw, self.reader, proto, block0)


def _apdu_get_uid(hCard, proto: int) -> Optional[bytes]:
    """Send FF CA 00 00 00, return UID bytes or None on failure."""
    try:
        data, sw1, sw2 = transmit(hCard, proto, _GET_UID)
        if sw1 == 0x90:
            log.debug('UID: %s', ' '.join(f'{b:02X}' for b in data))
            return bytes(data)
        log.debug('GET_UID SW=%02X%02X', sw1, sw2)
    except Exception as e:
        log.debug('GET_UID error: %s', e)
    return None


def _apdu_read_block0(hCard, proto: int) -> Optional[bytes]:
    """Send FF B0 00 00 04 to read block 0.

    On NfcCx: block 0 returns 01 01 01 01 (SW=9000).
    Any other block → SW=6981 → session killed. We only ever read block 0.
    """
    try:
        data, sw1, sw2 = transmit(hCard, proto, _READ_BLK0)
        if sw1 == 0x90:
            log.debug('Block 0: %s', ' '.join(f'{b:02X}' for b in data))
            return bytes(data)
        log.debug('READ_BLK0 SW=%02X%02X (not fatal — UID already read)', sw1, sw2)
    except Exception as e:
        log.debug('READ_BLK0 error (not fatal): %s', e)
    return None
