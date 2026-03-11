import time
import win32com.client

def monitor_wmi():
    print("Connecting to WMI namespace root\\wmi...")
    wmi = win32com.client.GetObject("winmgmts:root\\wmi")
    
    print("Watching for AsusAtkWmiEvent...")
    watcher = wmi.ExecNotificationQuery("SELECT * FROM AsusAtkWmiEvent")
    
    print("Please insert and remove the Keystone card.")
    while True:
        try:
            event = watcher.NextEvent(1000) # Wait 1 second
            
            # Print all properties of the event
            print(f"[{time.strftime('%H:%M:%S')}] WMI Event Received!")
            for prop in event.Properties_:
                print(f"  {prop.Name}: {prop.Value}")
                
        except Exception as e:
            # NextEvent throws an exception if it times out, which is expected
            error_str = str(e)
            if "WMI" not in error_str and "timed out" not in error_str and "Timeout" not in error_str and "0x80043001" not in error_str:
                pass
                # print(f"Error: {e}")

if __name__ == "__main__":
    try:
        monitor_wmi()
    except KeyboardInterrupt:
        print("Stopped.")
