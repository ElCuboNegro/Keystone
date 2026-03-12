import os
import time
import configparser

STATUS_FILE = r"C:\ProgramData\ASUS\SoulKey\SoulKeyPlugin_Status.ini"

def get_status():
    if not os.path.exists(STATUS_FILE):
        return None
    
    config = configparser.ConfigParser()
    try:
        config.read(STATUS_FILE)
        
        # Check if any section has CardExist=1
        for section in config.sections():
            if section not in ("KeyStone", "NoKeyStone"):
                exist = config[section].get("CardExist", "0")
                if exist == "1":
                    return f"INSERTED ({section})"
                    
        return "REMOVED"
    except Exception as e:
        return f"ERROR ({e})"

def main():
    print(f"Monitoring {STATUS_FILE} for changes...")
    print("Please insert and remove the Keystone card.")
    
    last_status = None
    last_mtime = 0
    
    try:
        while True:
            if os.path.exists(STATUS_FILE):
                mtime = os.stat(STATUS_FILE).st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    status = get_status()
                    if status != last_status:
                        print(f"[{time.strftime('%H:%M:%S')}] Status changed: {status}")
                        last_status = status
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    main()
