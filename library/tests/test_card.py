"""Tests for keystone_nfc.card — CardInfo construction and UID parsing."""
from datetime import datetime

import pytest

from keystone_nfc.card import CardInfo

# ISO 15693 UID: 8 bytes, LSB-first
# Format: [serial 6B][manufacturer][0xE0]
# uid_raw[7] = 0xE0 (ISO 15693 prefix, MSB in the physical UID)
# uid_raw[6] = manufacturer code
_NXP_UID = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0x04, 0xE0])  # NXP = 0x04
_ST_UID  = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0x02, 0xE0])  # STMicro = 0x02
_UNK_UID = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xFF, 0xE0])  # unknown mfr
_SHORT_UID = bytes([0xAA, 0xBB, 0xCC, 0xDD])                          # 4-byte (non-ISO 15693)


# ── from_raw construction ─────────────────────────────────────────────────────

def test_from_raw_stores_uid_bytes() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2)
    assert card.uid_bytes == _NXP_UID


def test_from_raw_uid_hex_format() -> None:
    """uid_hex is space-separated upper-case hex."""
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2)
    expected = ' '.join(f'{b:02X}' for b in _NXP_UID)
    assert card.uid_hex == expected


def test_uid_compact_no_spaces() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2)
    assert ' ' not in card.uid_compact
    assert card.uid_compact == card.uid_hex.replace(' ', '')


def test_from_raw_reader_stored() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='Microsoft IFD 0', protocol=2)
    assert card.reader == 'Microsoft IFD 0'


def test_from_raw_protocol_stored() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=1)
    assert card.protocol == 1


def test_timestamp_set_on_construction() -> None:
    before = datetime.now()
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2)
    after = datetime.now()
    assert before <= card.timestamp <= after


def test_block0_none_by_default() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2)
    assert card.block0 is None


def test_block0_stored() -> None:
    b0 = bytes([0x01, 0x02, 0x03, 0x04])
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2, block0=b0)
    assert card.block0 == b0


# ── Manufacturer detection ────────────────────────────────────────────────────

def test_manufacturer_nxp() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2)
    assert card.manufacturer is not None
    assert 'NXP' in card.manufacturer


def test_manufacturer_stmicro() -> None:
    card = CardInfo.from_raw(_ST_UID, reader='R', protocol=2)
    assert card.manufacturer is not None
    assert 'ST' in card.manufacturer or 'Micro' in card.manufacturer


def test_manufacturer_unknown_code_returns_hex() -> None:
    """Unknown manufacturer code is formatted as 'Unknown (0xFF)'."""
    card = CardInfo.from_raw(_UNK_UID, reader='R', protocol=2)
    assert card.manufacturer is not None
    assert '0xFF' in card.manufacturer or 'Unknown' in card.manufacturer


def test_manufacturer_short_uid_is_none() -> None:
    """Non-ISO-15693 UIDs (not 8 bytes with 0xE0 prefix) have no manufacturer."""
    card = CardInfo.from_raw(_SHORT_UID, reader='R', protocol=2)
    assert card.manufacturer is None


def test_manufacturer_8byte_non_iso15693() -> None:
    """8 bytes but uid_raw[7] != 0xE0 — not ISO 15693."""
    uid = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x04, 0x00])  # MSB = 0x00
    card = CardInfo.from_raw(uid, reader='R', protocol=2)
    assert card.manufacturer is None


# ── __str__ ───────────────────────────────────────────────────────────────────

def test_str_contains_uid() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2)
    s = str(card)
    assert card.uid_hex in s


def test_str_contains_reader() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='ACR122U', protocol=2)
    assert 'ACR122U' in str(card)


def test_str_contains_manufacturer() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2)
    assert 'NXP' in str(card)


def test_str_contains_block0_when_present() -> None:
    b0 = bytes([0xDE, 0xAD, 0xBE, 0xEF])
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2, block0=b0)
    assert 'DE' in str(card)


def test_str_no_block0_when_absent() -> None:
    card = CardInfo.from_raw(_NXP_UID, reader='R', protocol=2, block0=None)
    assert 'Block 0' not in str(card)
