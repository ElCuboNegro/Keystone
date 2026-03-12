"""
keystone_nfc._pcsc — Cross-platform PC/SC bindings.

Loads winscard.dll on Windows, libpcsclite on Linux/macOS.
Function names are identical across platforms — only the library and
a few constants differ.
"""

import sys
import ctypes
from ctypes import POINTER, byref, c_ubyte, c_ulong, c_void_p, Structure
from typing import Any, List, Tuple

from .exceptions import PCSCError, NoReaderError

_IS_WINDOWS = sys.platform == 'win32'

# ── Load library ──────────────────────────────────────────────────────────────

if _IS_WINDOWS:
    _lib = ctypes.WinDLL('winscard')
else:
    # pcsc-lite: try common library names
    for _name in ('libpcsclite.so.1', 'libpcsclite.so', 'PCSC'):
        try:
            _lib = ctypes.CDLL(_name)
            break
        except OSError:
            continue
    else:
        raise ImportError(
            'libpcsclite not found. Install it with: sudo apt install libpcsclite1'
        )

# ── Types ─────────────────────────────────────────────────────────────────────

LONG          = ctypes.c_long
DWORD         = ctypes.c_ulong
LPDWORD       = POINTER(DWORD)
LPBYTE        = POINTER(c_ubyte)
HANDLE        = ctypes.c_void_p
SCARDCONTEXT  = HANDLE
SCARDHANDLE   = HANDLE
LPSCARDCONTEXT = POINTER(SCARDCONTEXT)
LPSCARDHANDLE  = POINTER(SCARDHANDLE)


class SCARD_IO_REQUEST(Structure):
    _fields_ = [('dwProtocol',  DWORD),
                ('cbPciLength', DWORD)]

LPSCARD_IO_REQUEST = POINTER(SCARD_IO_REQUEST)


class SCARD_READERSTATE(Structure):
    _fields_ = [
        ('szReader',       ctypes.c_wchar_p if _IS_WINDOWS else ctypes.c_char_p),
        ('pvUserData',     c_void_p),
        ('dwCurrentState', DWORD),
        ('dwEventState',   DWORD),
        ('cbAtr',          DWORD),
        ('rgbAtr',         c_ubyte * 36),
    ]

LPSCARD_READERSTATE = POINTER(SCARD_READERSTATE)

# ── Constants ─────────────────────────────────────────────────────────────────

SCARD_SCOPE_USER      = 0
SCARD_SCOPE_SYSTEM    = 2

SCARD_SHARE_SHARED    = 2
SCARD_SHARE_EXCLUSIVE = 1
SCARD_SHARE_DIRECT    = 3

SCARD_PROTOCOL_UNDEFINED = 0
SCARD_PROTOCOL_T0        = 0x00000001
SCARD_PROTOCOL_T1        = 0x00000002
SCARD_PROTOCOL_ANY       = SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1

SCARD_LEAVE_CARD   = 0
SCARD_RESET_CARD   = 1
SCARD_UNPOWER_CARD = 2  # DO NOT USE on NfcCx — kills RF field

SCARD_S_SUCCESS              = 0x00000000
SCARD_E_TIMEOUT              = 0x8010000A
SCARD_E_NO_SMARTCARD         = 0x8010000C
SCARD_W_REMOVED_CARD         = 0x80100069
SCARD_E_NO_READERS_AVAILABLE = 0x8010002E
SCARD_E_NO_SERVICE           = 0x8010001D

SCARD_STATE_UNAWARE    = 0x0000
SCARD_STATE_IGNORE     = 0x0001
SCARD_STATE_CHANGED    = 0x0002
SCARD_STATE_UNKNOWN    = 0x0004
SCARD_STATE_UNAVAILABLE= 0x0008
SCARD_STATE_EMPTY      = 0x0010
SCARD_STATE_PRESENT    = 0x0020
SCARD_STATE_EXCLUSIVE  = 0x0080
SCARD_STATE_INUSE      = 0x0100
SCARD_STATE_MUTE       = 0x0200

INFINITE = 0xFFFFFFFF

# ── Function bindings ─────────────────────────────────────────────────────────

def _fn(name: str, argtypes: list, restype: Any = LONG, wide: bool = False) -> Any:
    """Bind a PC/SC function. Use wide=True for functions that take reader name strings
    (they have a W suffix on Windows; plain name on Linux)."""
    actual_name = (name + 'W') if (_IS_WINDOWS and wide) else name
    f = getattr(_lib, actual_name)
    f.argtypes = argtypes
    f.restype   = restype
    return f


_str_t = ctypes.c_wchar_p if _IS_WINDOWS else ctypes.c_char_p

# Functions with NO string parameters — no W suffix on Windows
SCardEstablishContext = _fn('SCardEstablishContext',
    [DWORD, c_void_p, c_void_p, LPSCARDCONTEXT])
SCardReleaseContext   = _fn('SCardReleaseContext', [SCARDCONTEXT])
SCardDisconnect       = _fn('SCardDisconnect',    [SCARDHANDLE, DWORD])
SCardBeginTransaction = _fn('SCardBeginTransaction', [SCARDHANDLE])
SCardEndTransaction   = _fn('SCardEndTransaction', [SCARDHANDLE, DWORD])
SCardTransmit         = _fn('SCardTransmit',
    [SCARDHANDLE, LPSCARD_IO_REQUEST, LPBYTE, DWORD,
     LPSCARD_IO_REQUEST, LPBYTE, LPDWORD])

# Functions WITH string parameters — W suffix on Windows
SCardListReaders      = _fn('SCardListReaders',
    [SCARDCONTEXT, _str_t, _str_t, LPDWORD], wide=True)
SCardConnect          = _fn('SCardConnect',
    [SCARDCONTEXT, _str_t, DWORD, DWORD, LPSCARDHANDLE, LPDWORD], wide=True)
SCardGetStatusChange  = _fn('SCardGetStatusChange',
    [SCARDCONTEXT, DWORD, LPSCARD_READERSTATE, DWORD], wide=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _check(rv: int, op: str) -> None:
    if rv != 0:
        code = rv & 0xFFFFFFFF
        if code == (SCARD_W_REMOVED_CARD & 0xFFFFFFFF):
            from .exceptions import CardRemovedError
            raise CardRemovedError(f'{op}: card removed')
        raise PCSCError(op, rv)


def list_readers(hCtx: SCARDCONTEXT) -> List[str]:
    needed = DWORD(0)
    rv = SCardListReaders(hCtx, None, None, byref(needed))
    if rv & 0xFFFFFFFF == SCARD_E_NO_READERS_AVAILABLE & 0xFFFFFFFF or needed.value == 0:
        return []
    if _IS_WINDOWS:
        buf = ctypes.create_unicode_buffer(needed.value)
    else:
        buf = ctypes.create_string_buffer(needed.value)
    _check(SCardListReaders(hCtx, None, buf, byref(needed)), 'SCardListReaders')
    raw = buf.value if _IS_WINDOWS else buf.value.decode('utf-8', errors='replace')
    return [s for s in raw.split('\x00') if s]


def _str_arg(name: str):
    """Encode reader name appropriately for the platform."""
    if _IS_WINDOWS:
        return name
    return name.encode('utf-8')


def transmit(hCard: SCARDHANDLE, proto: int, cmd: List[int]) -> Tuple[bytes, int, int]:
    """Send APDU bytes, return (data: bytes, sw1: int, sw2: int)."""
    pci = SCARD_IO_REQUEST(proto, ctypes.sizeof(SCARD_IO_REQUEST))
    send = (c_ubyte * len(cmd))(*cmd)
    recv = (c_ubyte * 258)()
    rlen = DWORD(258)
    _check(SCardTransmit(hCard, byref(pci), send, len(cmd), None, recv, byref(rlen)),
           'SCardTransmit')
    raw = bytes(recv[:rlen.value])
    if len(raw) >= 2:
        return raw[:-2], raw[-2], raw[-1]
    return raw, 0, 0
