"""
keystone_nfc.exceptions — All custom exceptions for the package.
"""

__all__ = [
    'KeystoneError',
    'NoReaderError',
    'NoCardError',
    'CardRemovedError',
    'PCSCError',
]


class KeystoneError(Exception):
    """Base exception for all keystone_nfc errors."""


class NoReaderError(KeystoneError):
    """Raised when no PC/SC reader is available."""


class NoCardError(KeystoneError):
    """Raised when an operation requires a card but none is present."""


class CardRemovedError(KeystoneError):
    """Raised when the card is removed during an active operation."""


class PCSCError(KeystoneError):
    """Raised when a PC/SC API call fails."""

    _CODE_NAMES = {
        0x8010000A: 'SCARD_E_TIMEOUT',
        0x8010000B: 'SCARD_E_SHARING_VIOLATION',
        0x8010000C: 'SCARD_E_NO_SMARTCARD',
        0x8010000F: 'SCARD_E_PROTO_MISMATCH',
        0x80100016: 'SCARD_E_NOT_TRANSACTED',
        0x8010001D: 'SCARD_E_NO_SERVICE',
        0x8010002E: 'SCARD_E_NO_READERS_AVAILABLE',
        0x80100069: 'SCARD_W_REMOVED_CARD',
    }

    def __init__(self, operation: str, code: int) -> None:
        """Create a PCSCError.

        Args:
            operation: Name of the PC/SC function that failed (e.g. 'SCardConnect').
            code:      Raw return value from the PC/SC call (signed or unsigned).
        """
        self.operation = operation
        self.code = code & 0xFFFFFFFF
        name = self._CODE_NAMES.get(self.code, f'0x{self.code:08X}')
        super().__init__(f'{operation} failed: {name}')
