import hid  # type: ignore[import-untyped]
import time

print("Current HID devices:")
for device in hid.enumerate():
    print(f"VID: {device['vendor_id']:04x} PID: {device['product_id']:04x} - {device.get('product_string', 'Unknown')}")

print("\nPlease physically insert and remove the Keystone while this script runs.")
print("Monitoring for changes...")

known_devices = set((d['vendor_id'], d['product_id'], d['path']) for d in hid.enumerate())

try:
    while True:
        current_devices = set((d['vendor_id'], d['product_id'], d['path']) for d in hid.enumerate())
        
        added = current_devices - known_devices
        removed = known_devices - current_devices
        
        if added:
            for d in added:
                print(f"[+] Device Added: VID {d[0]:04x} PID {d[1]:04x}")
        if removed:
            for d in removed:
                print(f"[-] Device Removed: VID {d[0]:04x} PID {d[1]:04x}")
                
        known_devices = current_devices
        time.sleep(0.5)
except KeyboardInterrupt:
    print("Stopped.")
