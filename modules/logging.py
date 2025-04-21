import json
import os
import datetime
import traceback
import sys

# Set up the log directory and file
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "app_log.txt")
DEBUG_LOG_FILE = os.path.join(LOG_DIR, "debug_log.txt")

# Keep an in-memory log for the UI
MAX_LOG_ENTRIES = 50
log_entries = []

def add_log_entry(message, is_error=False):
    """Add a log entry to the application log."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_level = "ERROR" if is_error else "INFO"
        
        # Construct the log entry
        log_entry = {
            "timestamp": timestamp,
            "level": log_level,
            "message": message,
            "type": "error" if is_error else "info"  # For backward compatibility
        }
        
        # Add to in-memory log for UI
        log_entries.insert(0, log_entry)  # Add to beginning of list
        
        # Trim log to max size
        while len(log_entries) > MAX_LOG_ENTRIES:
            log_entries.pop()
        
        # Get calling function/file information for debugging
        caller_info = ""
        try:
            frame = sys._getframe(1)
            filename = os.path.basename(frame.f_code.co_filename)
            function_name = frame.f_code.co_name
            line_number = frame.f_lineno
            caller_info = f"[{filename}:{function_name}:{line_number}]"
        except Exception:
            caller_info = "[unknown]"
        
        # Print to console for immediate feedback
        console_message = f"[{timestamp}] {log_level} {caller_info} {message}"
        print(console_message, file=sys.stderr if is_error else sys.stdout)
        
        # Save to log file
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
        # Save detailed version to debug log
        with open(DEBUG_LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {log_level} {caller_info} {message}\n")
            
        return log_entry
    except Exception as e:
        # Last resort - print to stderr if something fails in the logging
        error_msg = f"ERROR IN LOGGING: {str(e)}, while trying to log: {message}"
        print(error_msg, file=sys.stderr)
        try:
            with open(DEBUG_LOG_FILE, "a") as f:
                f.write(f"LOGGING FAILURE: {error_msg}\n")
        except:
            pass  # Nothing more we can do 