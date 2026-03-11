"""
keystone_nfc.card — CardInfo dataclass representing a single card read.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ISO 15693 manufacturer codes (byte 7 of UID, LSB-first = index 6)
_MANUFACTURERS = {
    0x01: 'Motorola',
    0x02: 'STMicroelectronics',
    0x03: 'Hitachi',
    0x04: 'NXP (Philips)',
    0x05: 'Infineon',
    0x07: 'Texas Instruments',
    0x08: 'Fujitsu',
    0x16: 'EM Microelectronic',
}


@dataclass
class CardInfo:
    """All data extracted from a single card read.

    uid_bytes:   raw UID as bytes (ISO 15693 = 8 bytes, LSB-first as returned by FF CA)
    uid_hex:     UID formatted as "E0 04 01 02 03 04 05 06"
    block0:      raw bytes of memory block 0, or None if unreadable
    reader:      name of the PC/SC reader that read this card
    protocol:    PC/SC protocol used (1=T0, 2=T1)
    timestamp:   when the card was read
    """
    uid_bytes:    bytes
    uid_hex:      str
    reader:       str
    protocol:     int
    timestamp:    datetime = field(default_factory=datetime.now)
    block0:       Optional[bytes] = None
    manufacturer: Optional[str]  = None

    @classmethod
    def from_raw(cls, uid_raw: bytes, reader: str, protocol: int,
                 block0: Optional[bytes] = None) -> 'CardInfo':
        """Build CardInfo from the raw bytes returned by FF CA 00 00 00."""
        uid_hex = ' '.join(f'{b:02X}' for b in uid_raw)

        # ISO 15693 UID: 8 bytes, byte[7] == 0xE0 (ISO 15693 prefix), byte[6] = mfr code
        # FF CA returns bytes LSB-first, so uid_raw[7] is the MSB (0xE0)
        manufacturer = None
        if len(uid_raw) == 8 and uid_raw[7] == 0xE0:
            mfr_code = uid_raw[6]
            manufacturer = _MANUFACTURERS.get(mfr_code, f'Unknown (0x{mfr_code:02X})')

        return cls(
            uid_bytes=uid_raw,
            uid_hex=uid_hex,
            reader=reader,
            protocol=protocol,
            block0=block0,
            manufacturer=manufacturer,
        )

    @property
    def uid_compact(self) -> str:
        """UID without spaces: 'E004010203040506'."""
        return self.uid_hex.replace(' ', '')

    def __str__(self) -> str:
        lines = [
            f'UID:          {self.uid_hex}',
            f'Reader:       {self.reader}',
            f'Manufacturer: {self.manufacturer or "unknown"}',
        ]
        if self.block0 is not None:
            lines.append(f'Block 0:      {" ".join(f"{b:02X}" for b in self.block0)}')
        lines.append(f'Timestamp:    {self.timestamp.isoformat()}')
        return '\n'.join(lines)
