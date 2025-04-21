import os
import subprocess
import time
import threading
import re
from datetime import datetime
from .logging import add_log_entry

# Directory for storing captures
CAPTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'captures')
if not os.path.exists(CAPTURES_DIR):
    os.makedirs(CAPTURES_DIR, exist_ok=True)

# Capture status tracking
active_captures = {}

def ensure_capture_dir():
    """Ensure the captures directory exists and is writable"""
    if not os.path.exists(CAPTURES_DIR):
        try:
            os.makedirs(CAPTURES_DIR, exist_ok=True)
            add_log_entry(f"Created captures directory: {CAPTURES_DIR}")
        except Exception as e:
            add_log_entry(f"Error creating captures directory: {str(e)}", is_error=True)
            return False
    
    # Check if directory is writable
    try:
        test_file = os.path.join(CAPTURES_DIR, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except Exception as e:
        add_log_entry(f"Captures directory is not writable: {str(e)}", is_error=True)
        return False

def list_captures():
    """List all available captures"""
    ensure_capture_dir()
    captures = []
    
    try:
        # Look for .pcap files in the captures directory
        for filename in os.listdir(CAPTURES_DIR):
            if filename.endswith('.pcap'):
                file_path = os.path.join(CAPTURES_DIR, filename)
                capture_id = filename.split('.')[0]
                
                # Extract interface from filename if possible (format: timestamp_interface)
                parts = capture_id.split('_')
                interface = "unknown"
                if len(parts) >= 3:  # At least timestamp (2 parts) + interface
                    interface = parts[2]  # Third part should be interface
                
                # Try to extract capture details
                capture_info = {
                    "id": capture_id,
                    "name": capture_id.replace('_', ' '),
                    "interface": interface,
                    "filter": "",
                    "promiscuous": True,  # Default to promiscuous mode for old captures
                    "start_time": datetime.fromtimestamp(os.path.getctime(file_path)).strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S"),
                    "file_path": file_path,
                    "file_size": os.path.getsize(file_path),
                    "packet_count": get_packet_count(file_path),
                    "status": "completed"
                }
                
                # If this is currently capturing, update status
                if capture_id in active_captures:
                    capture_info["status"] = "running"
                    # Update with more accurate info from active capture
                    for key in ["name", "interface", "filter", "promiscuous", "start_time", "packet_count"]:
                        if key in active_captures[capture_id]:
                            capture_info[key] = active_captures[capture_id][key]
                
                captures.append(capture_info)
    except Exception as e:
        add_log_entry(f"Error listing captures: {str(e)}", is_error=True)
    
    # Sort by start time (newest first)
    captures.sort(key=lambda x: x["start_time"], reverse=True)
    return captures

def get_packet_count(capture_file):
    """Get the number of packets in a capture file"""
    try:
        # First try using tcpdump stats
        output = subprocess.check_output(
            ["sudo", "tcpdump", "-r", capture_file, "-qn"],
            stderr=subprocess.STDOUT
        ).decode().strip()
        
        # Look for the packet count in the output
        count_match = re.search(r'(\d+) packets', output)
        if count_match:
            return int(count_match.group(1))
            
        # Alternative approach: count line by line
        output = subprocess.check_output(
            ["sudo", "tcpdump", "-r", capture_file, "-qn"],
            stderr=subprocess.PIPE
        ).decode().strip()
        
        # Count non-empty lines
        packet_lines = [line for line in output.split("\n") if line.strip() and not line.startswith("reading")]
        return len(packet_lines)
    except Exception as e:
        add_log_entry(f"Error getting packet count: {str(e)}", is_error=True)
        
    return 0

def start_capture(interface, filter_expr="", capture_name=None, promiscuous=True):
    """Start a packet capture
    
    Args:
        interface: Network interface to capture on
        filter_expr: Optional tcpdump filter expression
        capture_name: Optional name for the capture
        promiscuous: Whether to use promiscuous mode (True) or normal mode (False)
    """
    if not ensure_capture_dir():
        return False, "Capture directory is not available or writable", None
    
    # Generate a default name if none provided
    if not capture_name:
        capture_name = f"Capture_{interface}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    capture_id = f"{timestamp}_{interface.replace(':', '_')}"
    
    # Add filter to filename if provided (abbreviated)
    if filter_expr:
        filter_short = filter_expr.replace(' ', '_')[:20]
        capture_id += f"_{filter_short}"
    
    capture_file = os.path.join(CAPTURES_DIR, f"{capture_id}.pcap")
    
    try:
        # Build tcpdump command for capture
        cmd = ["sudo", "tcpdump", "-i", interface, "-w", capture_file]
        
        # Add -p flag to disable promiscuous mode if requested
        if not promiscuous:
            cmd.append("-p")
        
        # Add filter if provided (must split into separate arguments)
        if filter_expr:
            filter_args = filter_expr.split()
            cmd.extend(filter_args)
        
        # Log the command
        add_log_entry(f"Starting capture: {' '.join(cmd)}")
        
        # Start capture process
        capture_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Check if process started correctly
        time.sleep(0.5)
        if capture_proc.poll() is not None:
            error_output = capture_proc.stderr.read().decode() if capture_proc.stderr else "Unknown error"
            add_log_entry(f"Capture process failed to start: {error_output}", is_error=True)
            return False, f"Failed to start capture: {error_output}", None
        
        # Store capture info
        capture_info = {
            "id": capture_id,
            "name": capture_name,
            "interface": interface,
            "filter": filter_expr,
            "promiscuous": promiscuous,
            "process": capture_proc,
            "output": [],
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_path": capture_file,
            "packet_count": 0,
            "file_size": 0
        }
        
        # Track active capture
        active_captures[capture_id] = capture_info
        
        # Start a separate display process for live output
        display_cmd = ["sudo", "tcpdump", "-i", interface, "-l", "-n"]
        
        # Add -p flag to disable promiscuous mode if requested
        if not promiscuous:
            display_cmd.append("-p")
            
        if filter_expr:
            filter_args = filter_expr.split()
            display_cmd.extend(filter_args)
        
        display_proc = subprocess.Popen(
            display_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=False
        )
        
        # Store the display process
        capture_info["display_process"] = display_proc
        
        # Start thread to read output
        def read_output():
            while display_proc.poll() is None:
                line = display_proc.stdout.readline().decode().strip()
                if line:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    formatted_line = f"{timestamp} - {line}"
                    capture_info["output"].append(formatted_line)
                    # Keep only the last 1000 lines
                    if len(capture_info["output"]) > 1000:
                        capture_info["output"].pop(0)
                time.sleep(0.1)
        
        threading.Thread(target=read_output, daemon=True).start()
        
        add_log_entry(f"Started packet capture {capture_id} on {interface}")
        return True, f"Capture started on {interface}", capture_id
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        add_log_entry(f"Error starting capture: {str(e)}\n{error_details}", is_error=True)
        return False, f"Error starting capture: {str(e)}", None

def stop_capture(capture_id=None):
    """Stop a running capture"""
    # If no ID specified, stop the most recent capture
    if capture_id is None and active_captures:
        capture_id = list(active_captures.keys())[-1]
    
    if not capture_id or capture_id not in active_captures:
        return False, "No active capture found to stop"
    
    try:
        capture_info = active_captures[capture_id]
        
        # Stop the capture process
        if "process" in capture_info and capture_info["process"]:
            try:
                capture_info["process"].terminate()
                time.sleep(0.5)
                if capture_info["process"].poll() is None:
                    capture_info["process"].kill()
            except:
                pass
        
        # Stop the display process
        if "display_process" in capture_info and capture_info["display_process"]:
            try:
                capture_info["display_process"].terminate()
                time.sleep(0.5)
                if capture_info["display_process"].poll() is None:
                    capture_info["display_process"].kill()
            except:
                pass
        
        # Record end time
        capture_info["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update file size and packet count for the stopped capture
        if os.path.exists(capture_info["file_path"]):
            capture_info["file_size"] = os.path.getsize(capture_info["file_path"])
            capture_info["packet_count"] = get_packet_count(capture_info["file_path"])
        
        # Remove from active captures
        del active_captures[capture_id]
        
        add_log_entry(f"Stopped packet capture {capture_id}")
        return True, "Capture stopped successfully"
    
    except Exception as e:
        add_log_entry(f"Error stopping capture {capture_id}: {str(e)}", is_error=True)
        return False, f"Error stopping capture: {str(e)}"

def get_capture_output(capture_id=None):
    """Get the current output of a running capture"""
    # If no ID specified, get the most recent capture
    if capture_id is None and active_captures:
        capture_id = list(active_captures.keys())[-1]
    
    if not capture_id or capture_id not in active_captures:
        return [], False
    
    capture_info = active_captures[capture_id]
    return capture_info["output"], True

def delete_capture(capture_id):
    """Delete a capture file"""
    captures = list_captures()
    for capture in captures:
        if capture["id"] == capture_id:
            # Check if capture is running
            if capture_id in active_captures:
                stop_capture(capture_id)
            
            # Delete the file
            try:
                if os.path.exists(capture["file_path"]):
                    os.remove(capture["file_path"])
                    add_log_entry(f"Deleted capture file: {capture['file_path']}")
                    return True, f"Capture '{capture['name']}' deleted"
                else:
                    return False, "Capture file not found"
            except Exception as e:
                add_log_entry(f"Error deleting capture {capture_id}: {str(e)}", is_error=True)
                return False, f"Error deleting capture: {str(e)}"
    
    return False, "Capture not found"

def view_capture(capture_id):
    """Read the contents of a capture file"""
    captures = list_captures()
    for capture in captures:
        if capture["id"] == capture_id:
            if not os.path.exists(capture["file_path"]):
                return None, "Capture file not found"
            
            try:
                # Read the capture file using tcpdump
                output = subprocess.check_output(
                    ["sudo", "tcpdump", "-r", capture["file_path"], "-n", "-v"],
                    stderr=subprocess.STDOUT
                ).decode()
                
                return output.splitlines(), capture["name"]
            except Exception as e:
                add_log_entry(f"Error reading capture {capture_id}: {str(e)}", is_error=True)
                return None, f"Error reading capture: {str(e)}"
    
    return None, "Capture not found"

def rename_capture(capture_id, new_name):
    """Rename a capture file
    
    Args:
        capture_id: ID of the capture to rename
        new_name: New name for the capture
        
    Returns:
        Tuple of (success, message)
    """
    captures = list_captures()
    
    for capture in captures:
        if capture["id"] == capture_id:
            # Cannot rename currently running captures
            if capture["status"] == "running":
                return False, "Cannot rename a currently running capture"
            
            try:
                # Update the name in any storage/db if needed
                # For this simple implementation, we just track in memory
                capture["name"] = new_name
                
                add_log_entry(f"Renamed capture {capture_id} to '{new_name}'")
                return True, f"Capture renamed to '{new_name}'"
            except Exception as e:
                add_log_entry(f"Error renaming capture {capture_id}: {str(e)}", is_error=True)
                return False, f"Error renaming capture: {str(e)}"
    
    return False, "Capture not found" 