"""Configuration and global state management"""
import json
import os
import threading

# Load configuration from JSON file
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
with open(config_path) as f:
    config = json.load(f)

GOOGLE_SHEET_URL = config["GOOGLE_SHEET_URL"]
GOOGLE_CREDENTIALS_PATH = config.get("GOOGLE_CREDENTIALS_PATH", None)
SAVE_TO_EXCEL = config.get("SAVE_TO_EXCEL", False)
MAX_THREADS = config["MAX_THREADS"]
CONCURRENT_PAGES = config.get("CONCURRENT_PAGES", 1)
USE_PROXIES = config.get("USE_PROXIES", False)
HEADLESS = config.get("HEADLESS", False)

# Global data storage with thread locks
shutdown_flag = threading.Event()
progress_lock = threading.Lock()
completed_lock = threading.Lock()
proxy_lock = threading.Lock()
proxy_index = 0

# Track active pages per URL (normalized URL -> set of active page numbers)
active_pages_lock = threading.Lock()
active_pages = {}  # normalized_url -> set of active page numbers

# Track all executors for graceful shutdown
active_executors = []
executors_lock = threading.Lock()

# Track all active futures to cancel them on shutdown
active_futures = []
futures_lock = threading.Lock()

# Global flag to prevent new thread creation
NO_NEW_THREADS = False
no_new_threads_lock = threading.Lock()

def can_create_new_threads():
    """Atomically check if new threads can be created"""
    with no_new_threads_lock:
        no_new = NO_NEW_THREADS
        shutdown = shutdown_flag.is_set()
        can_create = not (no_new or shutdown)
        return can_create

# Progress tracking files
PROGRESS_FILE = "url_progress.csv"
COMPLETED_URLS_FILE = "completed_urls.csv"

# Load proxies once at startup
PROXIES_LIST = []
if USE_PROXIES:
    try:
        proxies_path = os.path.join(os.path.dirname(__file__), "proxies.txt")
        if os.path.exists(proxies_path):
            with open(proxies_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and ":" in line:
                        # Store proxy as string format (host:port:username:password or host:port)
                        # This format is compatible with undetected Chrome driver proxy extension
                        PROXIES_LIST.append(line)
            if PROXIES_LIST:
                print(f"Loaded {len(PROXIES_LIST)} proxies from proxies.txt")
            else:
                print("Warning: No valid proxies found in proxies.txt")
        else:
            print("Warning: proxies.txt not found, running without proxies")
    except Exception as e:
        print(f"Warning: Could not load proxies: {e}")

