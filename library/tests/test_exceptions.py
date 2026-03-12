"""Tests for keystone_nfc.exceptions."""
import pytest
from keystone_nfc.exceptions import (
    CardRemovedError,
    KeystoneError,
    NoCardError,
    NoReaderError,
    PCSCError,
)


# ── Exception hierarchy ───────────────────────────────────────────────────────

def test_all_are_keystone_errors() -> None:
    assert issubclass(NoReaderError,    KeystoneError)
    assert issubclass(NoCardError,      KeystoneError)
    assert issubclass(CardRemovedError, KeystoneError)
    assert issubclass(PCSCError,        KeystoneError)


def test_keystone_error_is_exception() -> None:
    assert issubclass(KeystoneError, Exception)


# ── PCSCError ─────────────────────────────────────────────────────────────────

def test_pcsc_error_known_code() -> None:
    e = PCSCError('SCardConnect', 0x8010000C)
    assert 'SCARD_E_NO_SMARTCARD' in str(e)
    assert e.operation == 'SCardConnect'
    assert e.code == 0x8010000C


def test_pcsc_error_unknown_code() -> None:
    e = PCSCError('op', 0x12345678)
    assert '0x12345678' in str(e).lower() or '12345678' in str(e).lower()


def test_pcsc_error_masks_negative_long() -> None:
    """WinSCard returns signed LONG values that must be masked to uint32."""
    signed = -2146435060   # 0x8010000C as two's complement
    e = PCSCError('op', signed)
    assert e.code == 0x8010000C


def test_pcsc_error_timeout_code() -> None:
    e = PCSCError('SCardGetStatusChange', 0x8010000A)
    assert 'SCARD_E_TIMEOUT' in str(e)


def test_pcsc_error_no_service() -> None:
    e = PCSCError('SCardEstablishContext', 0x8010001D)
    assert 'SCARD_E_NO_SERVICE' in str(e)


def test_pcsc_error_removed_card() -> None:
    e = PCSCError('SCardTransmit', 0x80100069)
    assert 'SCARD_W_REMOVED_CARD' in str(e)


# ── Simple exception messages ─────────────────────────────────────────────────

def test_no_reader_error_message() -> None:
    e = NoReaderError('no reader connected')
    assert 'no reader connected' in str(e)


def test_no_card_error_message() -> None:
    e = NoCardError('timed out after 30s')
    assert '30s' in str(e)


def test_card_removed_error_message() -> None:
    e = CardRemovedError('card removed during read')
    assert 'removed' in str(e)


# ── raise / catch ─────────────────────────────────────────────────────────────

def test_catch_as_keystone_error() -> None:
    with pytest.raises(KeystoneError):
        raise NoReaderError('test')


def test_catch_as_base_exception() -> None:
    with pytest.raises(Exception):
        raise PCSCError('op', 0x8010000C)
