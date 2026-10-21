import time, threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CanaryHandler(FileSystemEventHandler):
    def __init__(self, on_violation):
        self.on_violation = on_violation
    def on_any_event(self, event):
        if event.is_directory:
            return
        self.on_violation(f"canary touched: {event.event_type} {event.src_path}")

def start_canary_watch(path, on_violation):
    obs = Observer()
    obs.schedule(CanaryHandler(on_violation), path, recursive=True)
    obs.daemon = True
    obs.start()
    return obs