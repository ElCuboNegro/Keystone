/**
 * keystone_reader.cpp
 * =====================
 * Cross-platform C++ port of the ASUS Keystone card reader.
 *
 * Confirmed card protocol (from experiments 01-05):
 *   UID:    FF CA 00 00 00  →  54 D4 4C 4F 08 01 04 E0  (8 bytes, LSB-first)
 *   Block0: FF B0 00 00 04  →  01 01 01 01              (4 bytes, card type marker)
 *   All other blocks → SW=6981 → kills session (do NOT attempt)
 *
 * Build:
 *   Windows:  cl keystone_reader.cpp /link winscard.lib
 *   Linux:    g++ keystone_reader.cpp -lpcsclite -I/usr/include/PCSC -o keystone_reader
 *   macOS:    g++ keystone_reader.cpp -framework PCSC -o keystone_reader
 *
 * Linux prerequisites:
 *   sudo apt install libpcsclite-dev pcscd pcsc-tools
 *   (if using built-in NXP chip) sudo apt install libnfc-bin nfc-tools
 *   Verify reader appears: pcsc_scan
 *
 * NOTE ON LINUX BUILT-IN NXP CHIP:
 *   If the chip appears as /dev/nfc0 but NOT as a PC/SC reader:
 *   Install ifdnfc-nci (PC/SC bridge) or use libnfc directly.
 *   See: https://github.com/StarGate01/ifdnfc-nci
 *   Alternative: any USB NFC reader (ACR122U, SCL3711) works with this code as-is.
 */

#ifdef _WIN32
  #include <winscard.h>
  #pragma comment(lib, "winscard.lib")
#else
  #include <PCSC/winscard.h>
  #include <PCSC/reader.h>
#endif

#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>
#include <string>

// ─── APDU constants ──────────────────────────────────────────────────────────

static const BYTE CMD_GET_UID[]   = { 0xFF, 0xCA, 0x00, 0x00, 0x00 };
static const BYTE CMD_READ_BLK0[] = { 0xFF, 0xB0, 0x00, 0x00, 0x04 };

// ─── Result types ─────────────────────────────────────────────────────────────

struct CardData {
    bool        valid;
    uint8_t     uid[8];
    uint8_t     block0[4];
    char        uid_hex[32];    // "E0 04 01 08 4F 4C D4 54"
    char        block0_hex[16]; // "01 01 01 01"
    char        error[128];
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

static void bytes_to_hex(const uint8_t* data, size_t len, char* out, size_t out_size) {
    size_t pos = 0;
    for (size_t i = 0; i < len && pos + 3 < out_size; i++) {
        if (i > 0) out[pos++] = ' ';
        snprintf(out + pos, out_size - pos, "%02X", data[i]);
        pos += 2;
    }
    out[pos] = '\0';
}

static bool transmit_apdu(SCARDHANDLE hCard, DWORD proto,
                           const BYTE* cmd, DWORD cmd_len,
                           BYTE* resp, DWORD* resp_len,
                           uint8_t* sw1_out, uint8_t* sw2_out) {
    SCARD_IO_REQUEST pci;
    pci.dwProtocol  = proto;
    pci.cbPciLength = sizeof(SCARD_IO_REQUEST);

    LONG rv = SCardTransmit(hCard, &pci, cmd, cmd_len, nullptr, resp, resp_len);
    if (rv != SCARD_S_SUCCESS) {
        if (sw1_out) *sw1_out = 0;
        if (sw2_out) *sw2_out = 0;
        return false;
    }
    if (*resp_len >= 2) {
        if (sw1_out) *sw1_out = resp[*resp_len - 2];
        if (sw2_out) *sw2_out = resp[*resp_len - 1];
        *resp_len -= 2;  // strip SW bytes from data length
    }
    return true;
}

// ─── Core reader ─────────────────────────────────────────────────────────────

/**
 * read_keystone_card
 *
 * Connects to the first available PC/SC reader, reads the Keystone card UID
 * and block 0, then disconnects with SCARD_LEAVE_CARD.
 *
 * IMPORTANT: Do NOT attempt to read block 1 or beyond — SW=6981 on any
 * non-zero block kills the NfcCx/NFC session immediately.
 *
 * Returns CardData with valid=true on success, valid=false with error message.
 */
CardData read_keystone_card() {
    CardData result = {};
    result.valid = false;

    SCARDCONTEXT hCtx = 0;
    LONG rv = SCardEstablishContext(SCARD_SCOPE_USER, nullptr, nullptr, &hCtx);
    if (rv != SCARD_S_SUCCESS) {
        snprintf(result.error, sizeof(result.error),
                 "SCardEstablishContext failed: 0x%08lX", (unsigned long)rv);
        return result;
    }

    // List readers
#ifdef _WIN32
    DWORD needed = SCARD_AUTOALLOCATE;
    LPWSTR mszReaders = nullptr;
    rv = SCardListReadersW(hCtx, nullptr, (LPWSTR)&mszReaders, &needed);
#else
    DWORD needed = 0;
    SCardListReaders(hCtx, nullptr, nullptr, &needed);
    std::vector<char> buf(needed);
    char* mszReaders_a = buf.data();
    rv = SCardListReaders(hCtx, nullptr, mszReaders_a, &needed);
#endif

    if (rv != SCARD_S_SUCCESS || needed == 0) {
        snprintf(result.error, sizeof(result.error), "No PC/SC readers found");
        SCardReleaseContext(hCtx);
        return result;
    }

    // Use first reader
#ifdef _WIN32
    LPCWSTR reader = mszReaders;
#else
    const char* reader = mszReaders_a;
    printf("Using reader: %s\n", reader);
#endif

    SCARDHANDLE hCard = 0;
    DWORD dwProto = 0;

#ifdef _WIN32
    rv = SCardConnectW(hCtx, reader,
                       SCARD_SHARE_SHARED, SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1,
                       &hCard, &dwProto);
#else
    rv = SCardConnect(hCtx, reader,
                      SCARD_SHARE_SHARED, SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1,
                      &hCard, &dwProto);
#endif

    if (rv != SCARD_S_SUCCESS) {
        snprintf(result.error, sizeof(result.error),
                 "SCardConnect failed: 0x%08lX — is card on reader?", (unsigned long)rv);
#ifdef _WIN32
        SCardFreeMemory(hCtx, mszReaders);
#endif
        SCardReleaseContext(hCtx);
        return result;
    }

    rv = SCardBeginTransaction(hCard);
    if (rv != SCARD_S_SUCCESS) {
        snprintf(result.error, sizeof(result.error),
                 "SCardBeginTransaction failed: 0x%08lX", (unsigned long)rv);
        SCardDisconnect(hCard, SCARD_LEAVE_CARD);
        SCardReleaseContext(hCtx);
        return result;
    }

    // ── Step 1: GET UID ──────────────────────────────────────────────────────
    BYTE  resp[64] = {};
    DWORD resp_len = sizeof(resp);
    uint8_t sw1, sw2;

    if (!transmit_apdu(hCard, dwProto, CMD_GET_UID, sizeof(CMD_GET_UID),
                       resp, &resp_len, &sw1, &sw2)) {
        snprintf(result.error, sizeof(result.error), "GET UID transmit failed");
        goto cleanup;
    }
    if (sw1 != 0x90 || resp_len != 8) {
        snprintf(result.error, sizeof(result.error),
                 "GET UID failed: SW=%02X%02X, len=%lu", sw1, sw2, (unsigned long)resp_len);
        goto cleanup;
    }

    // UID returned LSB-first; store as-is, display MSB-first
    memcpy(result.uid, resp, 8);
    {
        uint8_t uid_msb[8];
        for (int i = 0; i < 8; i++) uid_msb[i] = resp[7 - i];
        bytes_to_hex(uid_msb, 8, result.uid_hex, sizeof(result.uid_hex));
    }

    // ── Step 2: READ BLOCK 0 ─────────────────────────────────────────────────
    // CRITICAL: Do NOT read block 1 or beyond — SW=6981 kills session
    resp_len = sizeof(resp);
    if (!transmit_apdu(hCard, dwProto, CMD_READ_BLK0, sizeof(CMD_READ_BLK0),
                       resp, &resp_len, &sw1, &sw2)) {
        snprintf(result.error, sizeof(result.error), "READ BLOCK 0 transmit failed");
        goto cleanup;
    }
    if (sw1 != 0x90 || resp_len != 4) {
        snprintf(result.error, sizeof(result.error),
                 "READ BLOCK 0 failed: SW=%02X%02X", sw1, sw2);
        goto cleanup;
    }
    memcpy(result.block0, resp, 4);
    bytes_to_hex(resp, 4, result.block0_hex, sizeof(result.block0_hex));

    result.valid = true;

cleanup:
    SCardEndTransaction(hCard, SCARD_LEAVE_CARD);
    SCardDisconnect(hCard, SCARD_LEAVE_CARD);  // LEAVE_CARD, not UNPOWER_CARD
#ifdef _WIN32
    SCardFreeMemory(hCtx, mszReaders);
#endif
    SCardReleaseContext(hCtx);
    return result;
}

// ─── Wait for card insertion ──────────────────────────────────────────────────

/**
 * wait_for_card
 *
 * Blocks until a card is inserted in the first available reader.
 * Uses SCardGetStatusChange (works on Windows NfcCx, Linux pcsclite, macOS).
 * Returns the reader name, or empty string on error.
 *
 * This replaces the ASUS-specific ATKHotkey / WM_INPUT trigger.
 * On Windows: ATKHotkey fires first, then this confirms card presence.
 * On Linux: this IS the detection mechanism (polling every 500ms).
 */
std::string wait_for_card(SCARDCONTEXT hCtx, unsigned int timeout_ms = INFINITE) {
    DWORD needed = 0;

#ifdef _WIN32
    SCardListReadersW(hCtx, nullptr, nullptr, &needed);
    if (needed == 0) return "";
    std::vector<wchar_t> buf(needed);
    SCardListReadersW(hCtx, nullptr, buf.data(), &needed);
    std::wstring wreader(buf.data());
    // For SCARD_READERSTATE we need the wide name
    SCARD_READERSTATEW rs = {};
    rs.szReader = wreader.c_str();
    rs.dwCurrentState = SCARD_STATE_UNAWARE;
    LONG rv = SCardGetStatusChangeW(hCtx, timeout_ms, &rs, 1);
    if (rv != SCARD_S_SUCCESS) return "";
    if (rs.dwEventState & SCARD_STATE_PRESENT) {
        return "Microsoft IFD 0";  // confirmed reader name
    }
#else
    SCardListReaders(hCtx, nullptr, nullptr, &needed);
    if (needed == 0) return "";
    std::vector<char> buf(needed);
    SCardListReaders(hCtx, nullptr, buf.data(), &needed);
    std::string reader(buf.data());

    SCARD_READERSTATE rs = {};
    rs.szReader      = reader.c_str();
    rs.dwCurrentState = SCARD_STATE_UNAWARE;
    LONG rv = SCardGetStatusChange(hCtx, timeout_ms, &rs, 1);
    if (rv != SCARD_S_SUCCESS) return "";
    if (rs.dwEventState & SCARD_STATE_PRESENT) {
        return reader;
    }
#endif
    return "";
}

// ─── Main ─────────────────────────────────────────────────────────────────────

int main() {
    printf("Keystone Card Reader — Cross-Platform Port\n");
    printf("==========================================\n");
    printf("Place Keystone card on reader...\n\n");

    CardData card = read_keystone_card();

    if (!card.valid) {
        printf("ERROR: %s\n", card.error);
        return 1;
    }

    printf("Card found!\n");
    printf("  UID (MSB-first): %s\n", card.uid_hex);
    printf("  Block 0:         %s\n", card.block0_hex);
    printf("\n");

    // Interpret block 0
    // 01 01 01 01 = standard Keystone card (all bytes = 0x01 = active/enabled)
    if (card.block0[0] == 0x01 && card.block0[1] == 0x01 &&
        card.block0[2] == 0x01 && card.block0[3] == 0x01) {
        printf("  Card type: Standard Keystone (01 01 01 01)\n");
    } else {
        printf("  Card type: Unknown variant (%s)\n", card.block0_hex);
    }

    printf("\nSummary:\n");
    printf("  UID (for server lookup): %s\n", card.uid_hex);
    printf("  Card marker:             %s\n", card.block0_hex);
    printf("\nOn ASUS: SoulKey plugin sends UID to ASUS server to retrieve card metadata.\n");
    printf("On Linux: use this UID + block0 in the same way once server API is known.\n");

    return 0;
}
