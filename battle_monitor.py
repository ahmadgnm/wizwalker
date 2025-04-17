import time
import os

def tail_log(filename):
    print("Battle Monitor Log Viewer")
    print(f"Watching: {filename}\n")
    if not os.path.exists(filename):
        open(filename, "w").close()
    with open(filename, "r", encoding="utf-8") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            print(line, end="", flush=True)

if __name__ == "__main__":
    tail_log("battle_monitor.log")