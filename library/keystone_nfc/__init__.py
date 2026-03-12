"""
keystone_nfc — Python package for Keystone NFC card event monitoring and UID reading.

Supports:
- Windows: NfcCx built-in reader ("Microsoft IFD 0") and any PC/SC compatible reader
- Linux:   ACR122U / SCL3711 via pcsc-lite (pcscd must be running)

Quick start:

    from keystone_nfc import KeystoneReader

    reader = KeystoneReader()

    @reader.on_card_inserted
    def handle(card):
        print(f'UID: {card.uid_hex}')
        if card.block0:
            print(f'Block 0: {card.block0.hex()}')

    @reader.on_card_removed
    def removed():
        print('Card removed')

    with reader:
        input('Watching for cards — press Enter to stop...')

One-shot synchronous read:

    card = KeystoneReader().read_once(timeout=30.0)
    print(card)

List available readers:

    print(KeystoneReader().available_readers())
"""

from .reader import KeystoneReader
from .card import CardInfo
from .exceptions import (
    KeystoneError,
    NoReaderError,
    NoCardError,
    CardRemovedError,
    PCSCError,
)

__all__ = [
    'KeystoneReader',
    'CardInfo',
    'KeystoneError',
    'NoReaderError',
    'NoCardError',
    'CardRemovedError',
    'PCSCError',
]

__version__ = '0.2.0'
