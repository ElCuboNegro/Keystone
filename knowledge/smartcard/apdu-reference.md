# APDU Reference — Application Protocol Data Units
## Technical Reference for Smart Card Agent

---

## APDU Structure

An APDU (Application Protocol Data Unit) is the communication unit between a card reader and a smart card.

### Command APDU (C-APDU)
```
┌─────┬─────┬────┬────┬──────────┬──────────────┬──────────┐
│ CLA │ INS │ P1 │ P2 │ Lc (opt) │ Data (opt)   │ Le (opt) │
└─────┴─────┴────┴────┴──────────┴──────────────┴──────────┘
  1B    1B    1B   1B    0-3B        0-65535B       0-3B
```

| Field | Size | Description |
|-------|------|-------------|
| CLA | 1 | Class byte — identifies command class |
| INS | 1 | Instruction byte — identifies the command |
| P1 | 1 | Parameter 1 |
| P2 | 1 | Parameter 2 |
| Lc | 0-3 | Length of command data (0 if no data) |
| Data | 0-n | Command data |
| Le | 0-3 | Expected response length (0 = no response data, absent = don't care) |

### Response APDU (R-APDU)
```
┌──────────────┬──────┬──────┐
│ Data (opt)   │  SW1 │  SW2 │
└──────────────┴──────┴──────┘
  0-65535B        1B     1B
```

- SW1/SW2 are the **status words** — always present
- `SW1=0x90, SW2=0x00` = success

---

## CLA Byte Values

| Value | Meaning |
|-------|---------|
| `0x00` | ISO 7816 command, first interindustry |
| `0x01-0x0F` | ISO 7816 command, further interindustry |
| `0x80-0x8F` | Proprietary, no SM |
| `0x90-0x9F` | Proprietary, SM possible |
| `0xA0-0xAF` | ISO 7816 with logical channel |
| `0xFF` | **PC/SC pseudo-APDU** (reader command, not sent to card) |

The `0xFF` CLA is intercepted by the PC/SC middleware and handled by the reader driver — it never reaches the smart card.

---

## Standard ISO 7816 Commands (CLA=0x00)

| INS | Name | Description |
|-----|------|-------------|
| 0x0E | ERASE_BINARY | Erase part of EF |
| 0x10 | PERFORM_SCQL_OPERATION | SCQL |
| 0x12 | PERFORM_TRANSACTION_OPERATION | Transaction |
| 0x14 | PERFORM_USER_OPERATION | User op |
| 0x20 | VERIFY | PIN verification |
| 0x21 | VERIFY (even) | |
| 0x22 | MANAGE_SECURITY_ENVIRONMENT | Select key for crypto |
| 0x24 | CHANGE_REFERENCE_DATA | Change PIN |
| 0x26 | DISABLE_VERIFICATION | Disable PIN |
| 0x28 | ENABLE_VERIFICATION | Enable PIN |
| 0x2A | PERFORM_SECURITY_OPERATION | Crypto operation (sign/verify/encrypt) |
| 0x2C | RESET_RETRY_COUNTER | Reset PIN attempts |
| 0x44 | ACTIVATE_FILE | |
| 0x46 | GENERATE_ASYMMETRIC_KEY_PAIR | Generate RSA/ECC key |
| 0x04 | DEACTIVATE_FILE | |
| 0x70 | MANAGE_CHANNEL | Open/close logical channel |
| 0x82 | EXTERNAL_AUTHENTICATE | Mutual auth step 2 |
| 0x84 | GET_CHALLENGE | Get random nonce |
| 0x86 | GENERAL_AUTHENTICATE | |
| 0x88 | INTERNAL_AUTHENTICATE | Auth card with key |
| 0xA0 | SEARCH_BINARY | Search EF binary |
| 0xA2 | SEARCH_RECORD | Search EF record |
| 0xA4 | SELECT_FILE | Select AID / DF / EF |
| 0xB0 | READ_BINARY | Read EF binary |
| 0xB1 | READ_BINARY (odd) | |
| 0xB2 | READ_RECORD | Read EF record |
| 0xC0 | GET_RESPONSE | Get pending response data |
| 0xC2 | ENVELOPE | Encapsulate APDU |
| 0xCA | GET_DATA | Get card data object |
| 0xCB | GET_DATA (odd) | |
| 0xD0 | WRITE_BINARY | Write EF binary |
| 0xD2 | WRITE_RECORD | Write EF record |
| 0xD6 | UPDATE_BINARY | Update EF binary |
| 0xD7 | UPDATE_BINARY (odd) | |
| 0xDA | PUT_DATA | Put data object |
| 0xDB | PUT_DATA (odd) | |
| 0xDC | UPDATE_RECORD | Update EF record |
| 0xE0 | CREATE_FILE | Create DF or EF |
| 0xE2 | APPEND_RECORD | Append to EF |
| 0xE4 | DELETE_FILE | Delete DF or EF |
| 0xFE | TERMINATE_CARD_USAGE | |

---

## PC/SC Pseudo-APDUs (CLA=0xFF)

These are handled by the reader driver, NOT the card.

### FF CA 00 00 00 — Get UID
```
Command:  FF CA 00 00 00
Response: <UID bytes> 90 00
```

### FF CA 01 00 00 — Get ATS (ISO 14443A only)
```
Command:  FF CA 01 00 00
Response: <ATS> 90 00
```

### FF B0 00 <blk> <len> — Read Binary Block
```
Command:  FF B0 00 <block_number> <length>
Response: <data> 90 00
```

### FF D6 00 <blk> <len> <data> — Update Binary Block
```
Command:  FF D6 00 <block_number> <length> <data...>
Response: 90 00
```

### FF 82 <P1> <key> 06 <k[6]> — Load Authentication Key (Mifare)
```
P1: 00=Key A, 01=Key B
key: 00 or 01 (key slot in reader)
```

### FF 86 00 00 05 01 00 <blk> <kt> <kn> — Authenticate (Mifare)
```
block: block number to authenticate
kt: 60=Key A, 61=Key B
kn: key slot (00 or 01)
```

### FF 00 40 <led> 04 <t1> <t2> <rep> <buz> — LED/Buzzer Control
```
led: bit0=red_final, bit1=green_final, bit2=red_blink, bit3=green_blink
t1, t2: blink durations (100ms units)
rep: repetitions
buz: 00=off, 01=on_t1, 02=on_t2, 03=on_both
```

### FF 00 00 00 <Lc> <PN532_cmd> — Direct Transmit (Escape)
Passes bytes directly to the PN532 chip. See acr122u-commands.md.

---

## Status Word Reference (SW1 SW2)

### Success
| SW1 SW2 | Meaning |
|---------|---------|
| 90 00 | Success |
| 61 XX | Success, XX more bytes available (use GET_RESPONSE) |

### Warning
| SW1 SW2 | Meaning |
|---------|---------|
| 62 00 | No info, state unchanged |
| 62 81 | Returned data may be corrupted |
| 62 82 | End of file/record reached |
| 62 83 | Selected file deactivated |
| 62 84 | FCI not formatted per 7816-4 |
| 63 00 | No info, state changed |
| 63 CX | Counter = X (PIN verification, X tries left) |

### Execution Errors
| SW1 SW2 | Meaning |
|---------|---------|
| 64 00 | Execution error, state unchanged |
| 65 00 | Execution error, state changed |
| 65 81 | Memory failure |
| 66 XX | Security issue |
| 67 00 | Wrong length (Lc/Le mismatch) |

### Function Not Supported
| SW1 SW2 | Meaning |
|---------|---------|
| 68 00 | No info |
| 68 81 | Logical channel not supported |
| 68 82 | Secure messaging not supported |
| 69 00 | No info |
| 69 81 | Command incompatible with file structure |
| 69 82 | Security status not satisfied |
| 69 83 | Authentication method blocked |
| 69 84 | Referenced data invalidated |
| 69 85 | Conditions not satisfied |
| 69 86 | Command not allowed (no EF selected) |
| 69 87 | Expected SM data objects missing |
| 69 88 | SM data objects incorrect |

### Wrong Parameters
| SW1 SW2 | Meaning |
|---------|---------|
| 6A 00 | No info |
| 6A 80 | Incorrect data in command |
| 6A 81 | Function not supported |
| 6A 82 | File not found |
| 6A 83 | Record not found |
| 6A 84 | Not enough space in file |
| 6A 85 | Lc inconsistent with TLV |
| 6A 86 | Incorrect P1/P2 |
| 6A 87 | Lc inconsistent with P1/P2 |
| 6A 88 | Reference data not found |
| 6B 00 | Wrong P1/P2 |
| 6C XX | Wrong Le, correct Le is XX |
| 6D 00 | Instruction code not supported |
| 6E 00 | Class not supported |
| 6F 00 | No precise diagnosis |

### ACR122U Specific
| SW1 SW2 | Meaning |
|---------|---------|
| 63 00 | Operation failed (e.g., no card for Get UID) |
| 6A 81 | Function not supported |

---

## SELECT FILE Command Detail

```
FF A4 <P1> <P2> <Lc> <AID/FID>
P1: 00=select MF/DF/EF by FID, 04=select DF by AID
P2: 00=first match, 02=last match
```

Example — Select by AID:
```
00 A4 04 00 07 A0 00 00 00 03 10 10
                   └── AID (7 bytes): Visa credit card AID
```

---

## Common APDU Sequences

### Read NDEF from NFC Type 4 Tag (ISO 14443-4)
```
1. Select NDEF app:    00 A4 04 00 07 D2 76 00 00 85 01 01
2. Select CC file:     00 A4 00 0C 02 E1 03
3. Read CC:            00 B0 00 00 0F
4. Parse CC, get NDEF file ID
5. Select NDEF file:   00 A4 00 0C 02 <NDEF_FILE_ID>
6. Read NDEF length:   00 B0 00 00 02
7. Read NDEF data:     00 B0 00 02 <length>
```

### Verify PIN
```
00 20 00 <PIN_ref> <len> <PIN_data>
PIN_ref: 01 = PIN 1
```

### Get Card Serial Number (ISO 7816)
```
00 CA 9F 7F 00   (returns CPLC data including serial number)
```
