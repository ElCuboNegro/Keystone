import ctypes
from ctypes import wintypes
import sys

user32 = getattr(ctypes, "windll").user32  # type: ignore[attr-defined]
kernel32 = getattr(ctypes, "windll").kernel32  # type: ignore[attr-defined]

WM_INPUT = 0x00FF
RIDEV_INPUTSINK = 0x00000100

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]

# Need proper pointer types for 64-bit Windows
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)  # type: ignore

class WNDCLASSEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]

# Make wndproc global to prevent garbage collection
@WNDPROC
def wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_INPUT:
        print(f"WM_INPUT received! wparam: {hex(wparam)}, lparam: {hex(lparam)}", flush=True)
        return user32.DefWindowProcW(hwnd, msg, wintypes.WPARAM(wparam), wintypes.LPARAM(lparam))
    elif msg == 0x0010: # WM_CLOSE
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wintypes.WPARAM(wparam), wintypes.LPARAM(lparam))

def main():
    hinst = kernel32.GetModuleHandleW(None)
    
    wndclass = WNDCLASSEX()
    wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)  # type: ignore
    wndclass.lpfnWndProc = wndproc  # type: ignore
    wndclass.hInstance = hinst  # type: ignore
    wndclass.lpszClassName = "RawInputMonitor"  # type: ignore
    
    if not user32.RegisterClassExW(ctypes.byref(wndclass)):
        print("Failed to register window class")
        return

    hwnd = user32.CreateWindowExW(
        0,
        wndclass.lpszClassName,
        "Raw Input Monitor",
        0, 0, 0, 0, 0,
        None, None, hinst, None
    )
    
    if not hwnd:
        print("Failed to create window")
        return

    # Try just capturing top level collections for ASUS custom pages or Generic Desktop
    pages_to_monitor = [
        (0x01, 0x00), # Generic Desktop, All
        (0xFF31, 0x00), # ASUS Aura?
    ]
    
    rid_array = (RAWINPUTDEVICE * len(pages_to_monitor))()  # type: ignore
    for i, (page, usage) in enumerate(pages_to_monitor):
        rid_array[i].usUsagePage = wintypes.USHORT(page)
        rid_array[i].usUsage = wintypes.USHORT(usage)
        rid_array[i].dwFlags = wintypes.DWORD(RIDEV_INPUTSINK)
        rid_array[i].hwndTarget = hwnd

    ctypes.set_last_error(0)  # type: ignore
    success = user32.RegisterRawInputDevices(rid_array, len(pages_to_monitor), ctypes.sizeof(RAWINPUTDEVICE))
    if not success:
        err = ctypes.get_last_error()  # type: ignore
        print(f"Failed to register raw input devices. Error: {err}")
        return
        
    print("Monitoring raw input. Insert/remove card...")
    
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

if __name__ == "__main__":
    main()
