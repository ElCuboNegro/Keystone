# DLL Analysis Report
Generated: 2026-03-11 01:50

## ArmouryCrate.SoulKeyServicePlugin.dll

- **Type:** native
- **Size:** 280,168 bytes
- **Architecture:** x86-64 (64-bit)
- **Compiled:** 2026-01-06T09:42:02

### Hardware/NFC API Imports (14)

| DLL | Function | IAT Address |
|-----|----------|------------|
| `winscard.dll` | `SCardEstablishContext` | `0x18002e5a0` |
| `winscard.dll` | `SCardGetStatusChangeW` | `0x18002e5a8` |
| `winscard.dll` | `SCardDisconnect` | `0x18002e5b8` |
| `winscard.dll` | `SCardTransmit` | `0x18002e5c8` |
| `winscard.dll` | `SCardReleaseContext` | `0x18002e5d0` |
| `winscard.dll` | `SCardGetAttrib` | `0x18002e5d8` |
| `winscard.dll` | `SCardListReadersW` | `0x18002e5e8` |
| `winscard.dll` | `SCardConnectW` | `0x18002e5f0` |
| `kernel32.dll` | `DeviceIoControl` | `0x18002e0d0` |
| `kernel32.dll` | `CreateFileA` | `0x18002e0f0` |
| `kernel32.dll` | `CreateFileW` | `0x18002e148` |
| `setupapi.dll` | `SetupDiGetClassDevsW` | `0x18002e3e0` |
| `setupapi.dll` | `SetupDiEnumDeviceInterfaces` | `0x18002e3f8` |
| `setupapi.dll` | `SetupDiGetClassDevsA` | `0x18002e400` |

### Exports (22)

- `OnUninstall` @ `0x6050`
- `QueryService` @ `0x6010`
- `SetCrashLogger` @ `0x20820`
- `SetLogger` @ `0x20830`
- `hid_close` @ `0x6f80`
- `hid_enumerate` @ `0x6380`
- `hid_error` @ `0x7110`
- `hid_exit` @ `0x6350`
- `hid_free_enumeration` @ `0x68d0`
- `hid_get_feature_report` @ `0x6ec0`
- `hid_get_indexed_string` @ `0x70c0`
- `hid_get_manufacturer_string` @ `0x6fd0`
- `hid_get_product_string` @ `0x7020`
- `hid_get_serial_number_string` @ `0x7070`
- `hid_init` @ `0x6120`
- `hid_open` @ `0x6930`
- `hid_open_path` @ `0x6a30`
- `hid_read` @ `0x6e50`
- `hid_read_timeout` @ `0x6d00`
- `hid_send_feature_report` @ `0x6e70`
- `hid_set_nonblocking` @ `0x6e60`
- `hid_write` @ `0x6c00`

### Hardcoded APDU/Protocol Sequences (50)

| Description | Pattern | Offset | Context |
|-------------|---------|--------|---------|
| Get UID (pseudo-APDU) | `FFCA0000` | `0xd679` | `FFCA0000C68424EC00000000C78424F0` |
| Read Binary Block | `FFB000` | `0xd68c` | `FFB00000C68424F40000000433D241B8` |
| PN532 InListPassiveTarget | `D44A` | `0x408b8` | `D44A020088B30300D44A0200E54A0200` |
| PN532 InListPassiveTarget | `D44A` | `0x408c0` | `D44A0200E54A02009CB30300E54A0200` |
| READ BINARY | `00B0` | `0x4982` | `00B001488B7C2478488B4C24584833CC` |
| READ BINARY | `00B0` | `0x10c0e` | `00B001488B8C24A00400004833CCE85F` |
| READ BINARY | `00B0` | `0x27a70` | `00B0014883C428C34883EC2833C9E82D` |
| READ BINARY | `00B0` | `0x27ac5` | `00B0014883C428C3CCCCCC48895C2408` |
| READ BINARY | `00B0` | `0x27d18` | `00B0014883C4205BC3CCCCCC40534883` |
| READ BINARY | `00B0` | `0x292f3` | `00B001C3CCCCCCCCCCCCCCCCCCCCCCCC` |
| READ BINARY | `00B0` | `0x2ce7f` | `00B0E50300000000007AD00300000000` |
| READ BINARY | `00B0` | `0x2d07f` | `00B0D3030000000000C6D30300000000` |
| READ BINARY | `00B0` | `0x2d32f` | `00B0E003000000000000000000000000` |
| READ BINARY | `00B0` | `0x2d66f` | `00B0A100000070A8000000B0B5000000` |
| READ BINARY | `00B0` | `0x2d679` | `00B0B5000000E0D80000007023010000` |
| READ BINARY | `00B0` | `0x2d6ab` | `00B031010000A0320100003035010000` |
| READ BINARY | `00B0` | `0x2d6e7` | `00B04001000090410100007042010000` |
| READ BINARY | `00B0` | `0x2d72d` | `00B093010000D0930100001096010000` |
| READ BINARY | `00B0` | `0x2d75a` | `00B09B010000F09B010000009C010000` |
| READ BINARY | `00B0` | `0x2d7be` | `00B0E501000090E601000000EA010000` |
| READ BINARY | `00B0` | `0x2d8b8` | `00B039020000D039020000403A020000` |
| READ BINARY | `00B0` | `0x2d8e0` | `00B084020000B089020000008B020000` |
| READ BINARY | `00B0` | `0x2d8e5` | `00B089020000008B020000208E020000` |
| READ BINARY | `00B0` | `0x2d917` | `00B0D5020000E0D5020000F0D5020000` |
| READ BINARY | `00B0` | `0x2da3f` | `00B0E501800100000090E60180010000` |
| READ BINARY | `00B0` | `0x2e707` | `00B039028001000000D0390280010000` |
| READ BINARY | `00B0` | `0x2e747` | `00B039028001000000D0390280010000` |
| READ BINARY | `00B0` | `0x2e85f` | `00B08402800100000000000000000000` |
| READ BINARY | `00B0` | `0x33b17` | `00B09B018001000000B09B0180010000` |
| READ BINARY | `00B0` | `0x33b1f` | `00B09B018001000000909B0180010000` |
| READ BINARY | `00B0` | `0x33baf` | `00B09301800100000030930180010000` |
| READ BINARY | `00B0` | `0x33bfb` | `00B0000000287103800100000090A301` |
| READ BINARY | `00B0` | `0x33c97` | `00B07003800100000020DD0180010000` |
| READ BINARY | `00B0` | `0x33cdf` | `00B0E501800100000090E60180010000` |
| READ BINARY | `00B0` | `0x33d1f` | `00B0A1008001000000107F0080010000` |
| READ BINARY | `00B0` | `0x3402f` | `00B000000008720300085E0300000000` |
| READ BINARY | `00B0` | `0x341c3` | `00B05503000000000000000000000000` |
| READ BINARY | `00B0` | `0x344a3` | `00B0FC0300C058030098580300000000` |
| READ BINARY | `00B0` | `0x344ef` | `00B0FC03000100000000000000FFFFFF` |
| READ BINARY | `00B0` | `0x3499f` | `00B05D03000000000000000000000000` |
| READ BINARY | `00B0` | `0x34b33` | `00B05D03000000000000000000000000` |
| READ BINARY | `00B0` | `0x34ba3` | `00B05F03000000000000000000C85F03` |
| READ BINARY | `00B0` | `0x34bb3` | `00B05D03000000000000000000000000` |
| READ BINARY | `00B0` | `0x34c97` | `00B06003008860030000000000000000` |
| READ BINARY | `00B0` | `0x34cef` | `00B06003000000000000000000000000` |
| READ BINARY | `00B0` | `0x34f27` | `00B0F703000100000000000000FFFFFF` |
| READ BINARY | `00B0` | `0x34fd3` | `00B0040400A8620300C8630300000000` |
| READ BINARY | `00B0` | `0x3500f` | `00B00404000100000000000000FFFFFF` |
| READ BINARY | `00B0` | `0x35143` | `00B0F70300A065030038650300000000` |
| READ BINARY | `00B0` | `0x35193` | `00B06103000000000000000000000000` |

### Interesting Strings

**reader_name:**
- `HidD_GetAttributes`
- `HidD_GetSerialNumberString`
- `HidD_GetManufacturerString`
- `HidD_GetProductString`
- `HidD_SetFeature`
- `HidD_GetFeature`
- `HidD_GetIndexedString`
- `HidD_GetPreparsedData`
- `HidD_FreePreparsedData`
- `HidP_GetCaps`
**apdu_comment:**
- `SCardListReadersW`
- `g_rgSCardT1Pci`
- `SCardGetStatusChangeW`
- `SCardTransmit`
- `SCardReleaseContext`
- `SCardEstablishContext`
- `SCardDisconnect`
- `g_rgSCardRawPci`
- `SCardGetAttrib`
- `SCardFreeMemory`
**timeout_value:**
- `hid_read_timeout`
- `Sleep`
- `SleepConditionVariableSRW`
- `SendMessageTimeoutW`

### PE Sections

| Name | Virtual Addr | Size | Entropy |
|------|-------------|------|---------|
| `.text` | `0x1000` | 182,272 | 6.246 |
| `.rdata` | `0x2e000` | 67,584 | 4.84 |
| `.data` | `0x3f000` | 7,168 | 4.77 |
| `.pdata` | `0x42000` | 9,728 | 5.406 |
| `.rsrc` | `0x45000` | 1,536 | 3.17 |
| `.reloc` | `0x46000` | 1,024 | 4.684 |

---
