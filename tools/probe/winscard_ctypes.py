"""
WinSCard ctypes bindings — direct WinSCard API without pyscard dependency.
Exposes all PC/SC functions needed for card probing and interception.
"""

import ctypes
import ctypes.wintypes
from ctypes import POINTER, byref, c_ubyte, c_ulong, c_wchar_p, c_void_p, Structure

# ─── Load library ────────────────────────────────────────────────────────────

_wsc = ctypes.WinDLL('winscard')

# ─── Types ───────────────────────────────────────────────────────────────────

LONG      = ctypes.c_long
DWORD     = ctypes.c_ulong
LPDWORD   = POINTER(DWORD)
LPBYTE    = POINTER(c_ubyte)
HANDLE    = ctypes.c_void_p
SCARDCONTEXT = HANDLE
SCARDHANDLE  = HANDLE
LPSCARDCONTEXT = POINTER(SCARDCONTEXT)
LPSCARDHANDLE  = POINTER(SCARDHANDLE)

# ─── SCARD_IO_REQUEST ────────────────────────────────────────────────────────

class SCARD_IO_REQUEST(Structure):
    _fields_ = [('dwProtocol',  DWORD),
                ('cbPciLength', DWORD)]

LPSCARD_IO_REQUEST = POINTER(SCARD_IO_REQUEST)

# ─── SCARD_READERSTATE ───────────────────────────────────────────────────────

class SCARD_READERSTATE(Structure):
    _fields_ = [
        ('szReader',       c_wchar_p),
        ('pvUserData',     c_void_p),
        ('dwCurrentState', DWORD),
        ('dwEventState',   DWORD),
        ('cbAtr',          DWORD),
        ('rgbAtr',         c_ubyte * 36),
    ]

LPSCARD_READERSTATE = POINTER(SCARD_READERSTATE)

# ─── Constants ───────────────────────────────────────────────────────────────

SCARD_SCOPE_USER      = 0
SCARD_SCOPE_SYSTEM    = 2

SCARD_SHARE_EXCLUSIVE = 1
SCARD_SHARE_SHARED    = 2
SCARD_SHARE_DIRECT    = 3

SCARD_PROTOCOL_UNDEFINED = 0
SCARD_PROTOCOL_T0        = 0x00000001
SCARD_PROTOCOL_T1        = 0x00000002
SCARD_PROTOCOL_RAW       = 0x00010000
SCARD_PROTOCOL_ANY       = SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1

SCARD_LEAVE_CARD   = 0
SCARD_RESET_CARD   = 1
SCARD_UNPOWER_CARD = 2
SCARD_EJECT_CARD   = 3

SCARD_S_SUCCESS           = 0x00000000
SCARD_E_NO_READERS_AVAILABLE = 0x8010002E
SCARD_E_NO_SMARTCARD      = 0x8010000C
SCARD_W_REMOVED_CARD      = 0x80100069
SCARD_E_TIMEOUT           = 0x8010000A
SCARD_E_NOT_TRANSACTED    = 0x80100016
SCARD_E_SHARING_VIOLATION = 0x8010000B

SCARD_STATE_UNAWARE    = 0x00000000
SCARD_STATE_IGNORE     = 0x00000001
SCARD_STATE_CHANGED    = 0x00000002
SCARD_STATE_UNKNOWN    = 0x00000004
SCARD_STATE_UNAVAILABLE= 0x00000008
SCARD_STATE_EMPTY      = 0x00000010
SCARD_STATE_PRESENT    = 0x00000020
SCARD_STATE_EXCLUSIVE  = 0x00000080
SCARD_STATE_INUSE      = 0x00000100
SCARD_STATE_MUTE       = 0x00000200

INFINITE = 0xFFFFFFFF

# ACR122U escape IOCTL
IOCTL_CCID_ESCAPE_WINDOWS = 0x00312000   # SCARD_CTL_CODE(3136)
IOCTL_CCID_ESCAPE_LINUX   = 0x42000001

IOCTL_CCID_ESCAPE = IOCTL_CCID_ESCAPE_WINDOWS  # change for Linux

# ─── Function bindings ───────────────────────────────────────────────────────

def _bind(name, argtypes, restype=LONG):
    fn = getattr(_wsc, name)
    fn.argtypes = argtypes
    fn.restype = restype
    return fn

SCardEstablishContext = _bind('SCardEstablishContext', [DWORD, c_void_p, c_void_p, LPSCARDCONTEXT])
SCardReleaseContext   = _bind('SCardReleaseContext',   [SCARDCONTEXT])
SCardListReadersW     = _bind('SCardListReadersW',     [SCARDCONTEXT, c_wchar_p, c_wchar_p, LPDWORD])
SCardConnectW         = _bind('SCardConnectW',         [SCARDCONTEXT, c_wchar_p, DWORD, DWORD, LPSCARDHANDLE, LPDWORD])
SCardDisconnect       = _bind('SCardDisconnect',       [SCARDHANDLE, DWORD])
SCardBeginTransaction = _bind('SCardBeginTransaction', [SCARDHANDLE])
SCardEndTransaction   = _bind('SCardEndTransaction',   [SCARDHANDLE, DWORD])
SCardTransmit         = _bind('SCardTransmit',         [SCARDHANDLE, LPSCARD_IO_REQUEST, LPBYTE, DWORD, LPSCARD_IO_REQUEST, LPBYTE, LPDWORD])
SCardControl          = _bind('SCardControl',          [SCARDHANDLE, DWORD, c_void_p, DWORD, c_void_p, DWORD, LPDWORD])
SCardGetStatusChangeW = _bind('SCardGetStatusChangeW', [SCARDCONTEXT, DWORD, LPSCARD_READERSTATE, DWORD])
SCardGetAttrib        = _bind('SCardGetAttrib',        [SCARDHANDLE, DWORD, LPBYTE, LPDWORD])

# ─── Helpers ─────────────────────────────────────────────────────────────────

def check(rv: int, op: str = ''):
    if rv != 0:
        raise WinSCardError(op, rv)
    return rv


def bytes_to_hex(data) -> str:
    if isinstance(data, (bytes, bytearray)):
        return ' '.join(f'{b:02X}' for b in data)
    return ' '.join(f'{b:02X}' for b in data)


def list_readers(hCtx) -> list[str]:
    """Return list of reader name strings."""
    needed = DWORD(0)
    rv = SCardListReadersW(hCtx, None, None, byref(needed))
    if rv == SCARD_E_NO_READERS_AVAILABLE or needed.value == 0:
        return []
    buf = ctypes.create_unicode_buffer(needed.value)
    check(SCardListReadersW(hCtx, None, buf, byref(needed)), 'SCardListReadersW')
    # multi-string: split on null, drop empty
    return [s for s in buf.value.split('\x00') if s]


def transmit(hCard, proto: int, cmd: list[int]) -> tuple[bytes, int, int]:
    """Send APDU, return (data, sw1, sw2)."""
    pci = SCARD_IO_REQUEST(proto, ctypes.sizeof(SCARD_IO_REQUEST))
    send = (c_ubyte * len(cmd))(*cmd)
    recv = (c_ubyte * 258)()
    rlen = DWORD(258)
    check(SCardTransmit(hCard, byref(pci), send, len(cmd), None, recv, byref(rlen)), 'SCardTransmit')
    raw = bytes(recv[:rlen.value])
    if len(raw) >= 2:
        return raw[:-2], raw[-2], raw[-1]
    return raw, 0, 0


def control(hCard, ioctl: int, cmd: list[int]) -> bytes:
    """Send escape/control command to reader (bypass card)."""
    inp = (c_ubyte * len(cmd))(*cmd)
    out = (c_ubyte * 512)()
    rlen = DWORD(0)
    check(SCardControl(hCard, ioctl, inp, len(cmd), out, 512, byref(rlen)), 'SCardControl')
    return bytes(out[:rlen.value])


class WinSCardError(Exception):
    ERROR_NAMES = {
        0x8010000B: 'SCARD_E_SHARING_VIOLATION',
        0x8010000C: 'SCARD_E_NO_SMARTCARD',
        0x8010000A: 'SCARD_E_TIMEOUT',
        0x80100069: 'SCARD_W_REMOVED_CARD',
        0x80100016: 'SCARD_E_NOT_TRANSACTED',
        0x8010002E: 'SCARD_E_NO_READERS_AVAILABLE',
        0x8010001D: 'SCARD_E_NO_SERVICE',
        0x8010000F: 'SCARD_E_PROTO_MISMATCH',
    }
    def __init__(self, op: str, code: int):
        self.op = op
        self.code = code
        name = self.ERROR_NAMES.get(code & 0xFFFFFFFF, f'0x{code & 0xFFFFFFFF:08X}')
        super().__init__(f'{op} failed: {name}')
