from flask import Blueprint, render_template, request, jsonify, send_file, abort
import os
import subprocess
import json
import traceback
import time
import sys
from modules.logging import add_log_entry
import re

bp = Blueprint('tftp', __name__, url_prefix='/tftp')

# Base directory for file transfers
TRANSFER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'transfers')
# Create the directory if it doesn't exist
if not os.path.exists(TRANSFER_DIR):
    os.makedirs(TRANSFER_DIR)

@bp.route('/')
def index():
    """Render the TFTP interface."""
    add_log_entry(f"TFTP interface accessed")
    return render_template('tftp.html')

@bp.route('/list', methods=['GET'])
def list_files():
    """List files in the transfer directory or specified subdirectory."""
    subdir = request.args.get('dir', '')
    target_dir = os.path.join(TRANSFER_DIR, subdir.lstrip('/'))
    
    add_log_entry(f"TFTP file list requested for subdirectory: '{subdir}'")
    add_log_entry(f"Full target path: {target_dir}")
    
    # Ensure the requested path is within TRANSFER_DIR or is a parent of TRANSFER_DIR
    abs_target = os.path.abspath(target_dir)
    abs_transfer = os.path.abspath(TRANSFER_DIR)
    
    # Allow navigation to parent directories (up to root)
    if not (abs_target.startswith(abs_transfer) or abs_transfer.startswith(abs_target)):
        add_log_entry(f"Security error: Attempted directory traversal to {target_dir}", is_error=True)
        return jsonify({"error": "Invalid directory path"}), 403
    
    if not os.path.exists(target_dir):
        add_log_entry(f"Directory not found: {target_dir}", is_error=True)
        return jsonify({"error": "Directory not found"}), 404
    
    try:
        # Always ensure TFTP directory has the right permissions
        try:
            # Ensure the directory has correct permissions
            if subdir == '':  # Only for the root TFTP directory
                # Set 777 permissions for the transfer directory
                os.chmod(TRANSFER_DIR, 0o777)
                add_log_entry(f"Set permissions for TFTP root directory: {TRANSFER_DIR}")
        except Exception as e:
            add_log_entry(f"Warning: Failed to set permissions on TFTP directory: {str(e)}", is_error=True)
        
        files = []
        
        # Add parent directory if we're in a subdirectory
        if subdir:
            parent_path = os.path.dirname(subdir.rstrip('/'))
            files.append({
                "name": "..",
                "path": parent_path,
                "type": "directory",
                "size": 0
            })
        
        for item in os.listdir(target_dir):
            if item == "." or item == "..":
                continue  # Skip . and .. entries
                
            item_path = os.path.join(target_dir, item)
            item_type = "directory" if os.path.isdir(item_path) else "file"
            item_size = os.path.getsize(item_path) if os.path.isfile(item_path) else 0
            item_rel_path = os.path.join(subdir, item).lstrip('/')
            
            files.append({
                "name": item,
                "path": item_rel_path,
                "type": item_type,
                "size": item_size
            })
        
        add_log_entry(f"Found {len(files)} files/directories in {target_dir}")
        return jsonify({"files": files, "current_dir": subdir})
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Error listing files in {target_dir}: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Error listing files: {str(e)}"}), 500

@bp.route('/download', methods=['GET'])
def download_file():
    """Download a file from the transfer directory."""
    file_path = request.args.get('path', '')
    full_path = os.path.join(TRANSFER_DIR, file_path.lstrip('/'))
    
    add_log_entry(f"File download requested: {file_path}")
    add_log_entry(f"Full file path: {full_path}")
    
    # Ensure the requested path is within TRANSFER_DIR
    if not os.path.abspath(full_path).startswith(os.path.abspath(TRANSFER_DIR)):
        add_log_entry(f"Security error: Attempted file access outside TRANSFER_DIR: {full_path}", is_error=True)
        return jsonify({"error": "Invalid file path"}), 403
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        add_log_entry(f"File not found: {full_path}", is_error=True)
        return jsonify({"error": "File not found"}), 404
    
    try:
        add_log_entry(f"Sending file: {full_path}, size: {os.path.getsize(full_path)} bytes")
        return send_file(full_path, as_attachment=True)
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Error downloading file {full_path}: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Error downloading file: {str(e)}"}), 500

@bp.route('/upload', methods=['POST'])
def upload_file():
    """Upload a file to the transfer directory."""
    start_time = time.time()
    add_log_entry(f"File upload initiated")
    
    # Check if file part exists in request
    if 'file' not in request.files:
        add_log_entry(f"No file part in request", is_error=True)
        return jsonify({"error": "No file part"}), 400
    
    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        add_log_entry(f"No file selected", is_error=True)
        return jsonify({"error": "No file selected"}), 400
    
    # Get target directory
    target_dir = request.form.get('dir', '')
    upload_dir = os.path.join(TRANSFER_DIR, target_dir.lstrip('/'))
    
    add_log_entry(f"Upload request details: filename={uploaded_file.filename}, target_dir={target_dir}")
    add_log_entry(f"Full upload directory path: {upload_dir}")
    
    # Ensure the requested path is within TRANSFER_DIR or is a parent of TRANSFER_DIR
    abs_upload = os.path.abspath(upload_dir)
    abs_transfer = os.path.abspath(TRANSFER_DIR)
    
    if not (abs_upload.startswith(abs_transfer) or abs_transfer.startswith(abs_upload)):
        add_log_entry(f"Security error: Attempted upload outside TRANSFER_DIR: {upload_dir}", is_error=True)
        return jsonify({"error": "Invalid directory path"}), 403
    
    try:
        # Create directory if it doesn't exist
        if not os.path.exists(upload_dir):
            add_log_entry(f"Creating upload directory: {upload_dir}")
            os.makedirs(upload_dir)
            
            # Set directory permissions
            try:
                os.chmod(upload_dir, 0o777)
                add_log_entry(f"Set permissions 777 for directory: {upload_dir}")
            except Exception as e:
                add_log_entry(f"Warning: Could not set directory permissions: {str(e)}", is_error=True)
        
        # Save the file
        file_path = os.path.join(upload_dir, uploaded_file.filename)
        add_log_entry(f"Saving file to: {file_path}")
        uploaded_file.save(file_path)
        
        # Make sure file has the correct permissions for TFTP access
        try:
            # Set file permissions to read/write for everyone
            os.chmod(file_path, 0o666)
            add_log_entry(f"Set file permissions to 666 for {file_path}")
        except Exception as e:
            add_log_entry(f"Warning: Failed to set permissions for file: {str(e)}", is_error=True)
        
        # Verify the file was saved correctly and return file info
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            elapsed_time = time.time() - start_time
            add_log_entry(f"File uploaded successfully: {file_path}, size: {file_size} bytes, time: {elapsed_time:.2f}s")
            
            # Return detailed file info
            return jsonify({
                "success": True, 
                "filename": uploaded_file.filename,
                "size": file_size,
                "path": os.path.join(target_dir, uploaded_file.filename),
                "upload_time": elapsed_time
            })
        else:
            add_log_entry(f"File save operation completed but file not found: {file_path}", is_error=True)
            return jsonify({"error": "File save operation failed"}), 500
            
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Error uploading file: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Error uploading file: {str(e)}"}), 500

@bp.route('/create_dir', methods=['POST'])
def create_directory():
    """Create a new directory."""
    data = request.get_json()
    parent_dir = data.get('parent_dir', '')
    new_dir = data.get('name', '')
    
    add_log_entry(f"Directory creation requested: parent_dir={parent_dir}, new_dir={new_dir}")
    
    if not new_dir:
        add_log_entry(f"Directory name is required", is_error=True)
        return jsonify({"error": "Directory name is required"}), 400
    
    target_dir = os.path.join(TRANSFER_DIR, parent_dir.lstrip('/'), new_dir)
    add_log_entry(f"Full target directory path: {target_dir}")
    
    # Ensure the target directory is within TRANSFER_DIR
    if not os.path.abspath(target_dir).startswith(os.path.abspath(TRANSFER_DIR)):
        add_log_entry(f"Security error: Attempted directory creation outside TRANSFER_DIR: {target_dir}", is_error=True)
        return jsonify({"error": "Invalid directory path"}), 403
    
    if os.path.exists(target_dir):
        add_log_entry(f"Directory already exists: {target_dir}", is_error=True)
        return jsonify({"error": "Directory already exists"}), 400
    
    try:
        os.makedirs(target_dir)
        add_log_entry(f"Directory created: {target_dir}")
        return jsonify({"success": True})
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Error creating directory {target_dir}: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Error creating directory: {str(e)}"}), 500

@bp.route('/create_folder', methods=['POST'])
def create_folder():
    """Create a new folder - alias for create_dir for JS compatibility."""
    data = request.get_json()
    add_log_entry(f"Create folder request: {data}")
    
    # Convert parameters to match create_dir endpoint
    if 'path' in data and 'name' in data:
        # Create a new data structure with the expected parameters
        new_data = {
            'parent_dir': data.get('path', ''),
            'name': data.get('name', '')
        }
        request._cached_json = (new_data, request._cached_json[1]) if hasattr(request, '_cached_json') else (new_data, None)
        
    # Delegate to the original function
    return create_directory()

@bp.route('/delete', methods=['POST'])
def delete_item():
    """Delete a file or directory."""
    data = request.get_json()
    item_path = data.get('path', '')
    full_path = os.path.join(TRANSFER_DIR, item_path.lstrip('/'))
    
    add_log_entry(f"Delete request for: {item_path}")
    add_log_entry(f"Full path to delete: {full_path}")
    
    # Ensure the requested path is within TRANSFER_DIR
    if not os.path.abspath(full_path).startswith(os.path.abspath(TRANSFER_DIR)):
        add_log_entry(f"Security error: Attempted deletion outside TRANSFER_DIR: {full_path}", is_error=True)
        return jsonify({"error": "Invalid path"}), 403
    
    if not os.path.exists(full_path):
        add_log_entry(f"Path not found: {full_path}", is_error=True)
        return jsonify({"error": "Path not found"}), 404
    
    try:
        if os.path.isdir(full_path):
            import shutil
            add_log_entry(f"Deleting directory: {full_path}")
            shutil.rmtree(full_path)
            add_log_entry(f"Directory deleted: {full_path}")
        else:
            add_log_entry(f"Deleting file: {full_path}")
            os.remove(full_path)
            add_log_entry(f"File deleted: {full_path}")
        
        return jsonify({"success": True})
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Error deleting {full_path}: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Error deleting path: {str(e)}"}), 500

@bp.route('/status', methods=['GET'])
def status():
    """Get TFTP server status."""
    try:
        add_log_entry(f"TFTP status check requested")
        # Import the TFTPManager
        from modules.tftp import TFTPManager
        manager = TFTPManager(TRANSFER_DIR)
        
        # Check if the server is running
        add_log_entry(f"Checking TFTP server status")
        is_active = manager.get_server_status()
        add_log_entry(f"TFTP server is {'active' if is_active else 'inactive'}")
        
        return jsonify({"running": is_active})
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Failed to get TFTP server status: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Failed to get TFTP server status: {str(e)}"}), 500

@bp.route('/start', methods=['POST'])
def start_server():
    """Start the TFTP server."""
    start_time = time.time()
    add_log_entry(f"TFTP server start requested")
    
    try:
        # Create a temporary transfers directory to serve files from
        if not os.path.exists(TRANSFER_DIR):
            add_log_entry(f"Creating transfers directory: {TRANSFER_DIR}")
            os.makedirs(TRANSFER_DIR)
        
        # Set permissive permissions on transfer directory
        try:
            os.chmod(TRANSFER_DIR, 0o777)
            add_log_entry(f"Set permissions for TFTP directory: {TRANSFER_DIR}")
        except Exception as e:
            add_log_entry(f"Warning: Failed to set permissions: {str(e)}", is_error=True)
        
        # Import TFTPManager to properly configure and start the server
        add_log_entry(f"Importing TFTPManager and initializing")
        from modules.tftp import TFTPManager
        manager = TFTPManager(TRANSFER_DIR)
        
        # Start the TFTP server
        add_log_entry(f"Calling manager.start_server")
        if manager.start_server():
            elapsed_time = time.time() - start_time
            add_log_entry(f"TFTP server started successfully in {elapsed_time:.2f}s")
            return jsonify({"success": True, "status": "running"})
        else:
            error_msg = "Failed to start TFTP server through manager (returned False)"
            add_log_entry(error_msg, is_error=True)
            return jsonify({"error": error_msg}), 500
    except Exception as e:
        error_trace = traceback.format_exc()
        error_msg = f"Unexpected error starting TFTP server: {str(e)}"
        add_log_entry(f"{error_msg}\n{error_trace}", is_error=True)
        return jsonify({"error": error_msg}), 500

@bp.route('/stop', methods=['POST'])
def stop_server():
    """Stop the TFTP server."""
    try:
        # Import TFTPManager to properly stop the server
        add_log_entry(f"Importing TFTPManager for stop operation")
        from modules.tftp import TFTPManager
        manager = TFTPManager(TRANSFER_DIR)
        
        # Stop the TFTP server
        add_log_entry(f"Calling manager.stop_server")
        if manager.stop_server():
            add_log_entry(f"TFTP server stopped successfully")
            return jsonify({"success": True, "status": "stopped"})
        else:
            error_msg = "Failed to stop TFTP server through manager (returned False)"
            add_log_entry(error_msg, is_error=True)
            return jsonify({"error": error_msg}), 500
    except Exception as e:
        error_trace = traceback.format_exc()
        error_msg = f"Unexpected error stopping TFTP server: {str(e)}"
        add_log_entry(f"{error_msg}\n{error_trace}", is_error=True)
        return jsonify({"error": error_msg}), 500

@bp.route('/tftp_download', methods=['POST'])
def tftp_download():
    """Download file from remote TFTP server."""
    start_time = time.time()
    data = request.get_json()
    server = data.get('server')
    filename = data.get('filename')
    target_dir = data.get('target_dir', '')
    
    add_log_entry(f"TFTP download requested: server={server}, filename={filename}, target_dir={target_dir}")
    
    if not server or not filename:
        add_log_entry(f"TFTP download missing required parameters", is_error=True)
        return jsonify({"error": "Server address and filename are required"}), 400
    
    target_path = os.path.join(TRANSFER_DIR, target_dir.lstrip('/'))
    add_log_entry(f"Full target path: {target_path}")
    
    # Ensure the target directory is within TRANSFER_DIR
    if not os.path.abspath(target_path).startswith(os.path.abspath(TRANSFER_DIR)):
        add_log_entry(f"Security error: Invalid target directory: {target_path}", is_error=True)
        return jsonify({"error": "Invalid target directory"}), 403
    
    if not os.path.exists(target_path):
        add_log_entry(f"Creating target directory: {target_path}")
        os.makedirs(target_path)
    
    try:
        # Use TFTPManager to download the file
        add_log_entry(f"Initializing TFTPManager for download")
        from modules.tftp import TFTPManager
        manager = TFTPManager(TRANSFER_DIR)
        
        add_log_entry(f"Starting TFTP download from {server} of file {filename}")
        if manager.download_file(server, filename, target_dir):
            elapsed_time = time.time() - start_time
            add_log_entry(f"TFTP download successful, time: {elapsed_time:.2f}s")
            
            # Verify the file was downloaded
            expected_file = os.path.join(target_path, filename)
            if os.path.exists(expected_file):
                file_size = os.path.getsize(expected_file)
                add_log_entry(f"Downloaded file exists: {expected_file}, size: {file_size} bytes")
            else:
                add_log_entry(f"Warning: Download reported success but file not found at {expected_file}", is_error=True)
            
            return jsonify({"success": True})
        else:
            add_log_entry(f"TFTP download failed (manager returned False)", is_error=True)
            return jsonify({"error": "TFTP download failed"}), 500
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"TFTP download error: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"TFTP download error: {str(e)}"}), 500

@bp.route('/tftp_upload', methods=['POST'])
def tftp_upload():
    """Upload file to remote TFTP server."""
    start_time = time.time()
    data = request.get_json()
    server = data.get('server')
    filename = data.get('filename')
    source_dir = data.get('source_dir', '')
    
    add_log_entry(f"TFTP upload requested: server={server}, filename={filename}, source_dir={source_dir}")
    
    if not server or not filename:
        add_log_entry(f"TFTP upload missing required parameters", is_error=True)
        return jsonify({"error": "Server address and filename are required"}), 400
    
    source_path = os.path.join(TRANSFER_DIR, source_dir.lstrip('/'))
    file_path = os.path.join(source_path, filename)
    add_log_entry(f"Full source file path: {file_path}")
    
    # Ensure the source file exists
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        add_log_entry(f"Source file not found: {file_path}", is_error=True)
        return jsonify({"error": "Source file not found"}), 404
    
    file_size = os.path.getsize(file_path)
    add_log_entry(f"Source file exists, size: {file_size} bytes")
    
    try:
        # Use TFTPManager to upload the file
        add_log_entry(f"Initializing TFTPManager for upload")
        from modules.tftp import TFTPManager
        manager = TFTPManager(TRANSFER_DIR)
        
        add_log_entry(f"Starting TFTP upload to {server} of file {filename}")
        if manager.upload_file(server, filename, source_dir):
            elapsed_time = time.time() - start_time
            add_log_entry(f"TFTP upload successful, time: {elapsed_time:.2f}s")
            return jsonify({"success": True})
        else:
            add_log_entry(f"TFTP upload failed (manager returned False)", is_error=True)
            return jsonify({"error": "TFTP upload failed"}), 500
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"TFTP upload error: {str(e)}\n{error_trace}", is_error=True)
        if 'current_dir' in locals():
            os.chdir(current_dir)
        return jsonify({"error": f"TFTP upload error: {str(e)}"}), 500

@bp.route('/debug_logs', methods=['GET'])
def debug_logs():
    """View the most recent debug logs to troubleshoot TFTP issues."""
    try:
        log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "debug_log.txt")
        add_log_entry(f"Debug logs requested, log file: {log_file}")
        
        # Check if file exists
        if not os.path.exists(log_file):
            return jsonify({"error": "Log file not found"}), 404
            
        # Get the number of lines to show (default 100)
        lines = request.args.get('lines', 100, type=int)
        
        # Read the last N lines of the log file
        with open(log_file, 'r') as f:
            log_lines = f.readlines()
        
        # Get last N lines and reverse to show newest first
        log_lines = log_lines[-lines:]
        
        add_log_entry(f"Returning {len(log_lines)} log lines")
        return jsonify({
            "log_file": log_file,
            "lines_requested": lines,
            "lines_returned": len(log_lines),
            "logs": log_lines
        })
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Error retrieving debug logs: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Error retrieving logs: {str(e)}"}), 500

@bp.route('/current_path', methods=['GET'])
def get_current_path():
    """Return the current path for file browsing."""
    add_log_entry(f"Current path requested")
    # Default to transfers root directory
    return jsonify({"path": "/"})

@bp.route('/files', methods=['GET'])
def get_files():
    """List files in a directory for file browser."""
    path = request.args.get('path', '/')
    add_log_entry(f"File listing requested for path: {path}")
    
    # Convert web path to actual file system path
    target_dir = os.path.join(TRANSFER_DIR, path.lstrip('/'))
    add_log_entry(f"Target directory: {target_dir}")
    
    try:
        # Ensure the directory exists
        if not os.path.exists(target_dir):
            add_log_entry(f"Creating directory: {target_dir}")
            os.makedirs(target_dir)
        
        files = []
        
        # Add parent directory entry if not at root
        if path != '/' and path != '':
            parent_path = os.path.dirname(path.rstrip('/'))
            if parent_path == '':
                parent_path = '/'
                
            files.append({
                "name": "..",
                "path": parent_path,
                "type": "directory",
                "size": 0
            })
        
        # List files in directory
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            item_type = "directory" if os.path.isdir(item_path) else "file"
            item_size = os.path.getsize(item_path) if item_type == "file" else 0
            
            # Create relative path for the item
            rel_path = os.path.join(path, item)
            if rel_path.startswith('//'):
                rel_path = rel_path[1:]
                
            files.append({
                "name": item,
                "path": rel_path,
                "type": item_type,
                "size": item_size
            })
            
        add_log_entry(f"Found {len(files)} items in {target_dir}")
        return jsonify({
            "files": files,
            "current_dir": path
        })
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Error listing files: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Error listing files: {str(e)}"}), 500

@bp.route('/rename', methods=['POST'])
def rename_file():
    """Rename a file or directory."""
    data = request.get_json()
    old_path = data.get('old_path', '')
    new_name = data.get('new_name', '')
    
    if not old_path or not new_name:
        add_log_entry(f"Missing required parameters for rename", is_error=True)
        return jsonify({"error": "Missing required parameters"}), 400
    
    # Full path of the source file
    full_old_path = os.path.join(TRANSFER_DIR, old_path.lstrip('/'))
    
    # Get directory and filename components
    old_dir = os.path.dirname(full_old_path)
    full_new_path = os.path.join(old_dir, new_name)
    
    add_log_entry(f"Rename request: from {full_old_path} to {full_new_path}")
    
    # Ensure the source path exists
    if not os.path.exists(full_old_path):
        add_log_entry(f"Source path not found: {full_old_path}", is_error=True)
        return jsonify({"error": "Source path not found"}), 404
    
    # Ensure the target path is within TRANSFER_DIR
    if not os.path.abspath(full_new_path).startswith(os.path.abspath(TRANSFER_DIR)):
        add_log_entry(f"Security error: Target path outside TRANSFER_DIR: {full_new_path}", is_error=True)
        return jsonify({"error": "Invalid target path"}), 403
    
    # Ensure target doesn't already exist
    if os.path.exists(full_new_path):
        add_log_entry(f"Target path already exists: {full_new_path}", is_error=True)
        return jsonify({"error": "Target already exists"}), 400
    
    try:
        # Perform the rename operation
        os.rename(full_old_path, full_new_path)
        add_log_entry(f"Successfully renamed {full_old_path} to {full_new_path}")
        return jsonify({"success": True})
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Error renaming file: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Error renaming file: {str(e)}"}), 500

@bp.route('/view', methods=['GET'])
def view_file():
    """View the content of a text file."""
    file_path = request.args.get('path', '')
    full_path = os.path.join(TRANSFER_DIR, file_path.lstrip('/'))
    
    add_log_entry(f"File view requested: {file_path}")
    add_log_entry(f"Full file path: {full_path}")
    
    # Ensure the requested path is within TRANSFER_DIR
    if not os.path.abspath(full_path).startswith(os.path.abspath(TRANSFER_DIR)):
        add_log_entry(f"Security error: Attempted file access outside TRANSFER_DIR: {full_path}", is_error=True)
        return jsonify({"error": "Invalid file path"}), 403
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        add_log_entry(f"File not found: {full_path}", is_error=True)
        return jsonify({"error": "File not found"}), 404
    
    try:
        # Check file size to prevent loading large files
        file_size = os.path.getsize(full_path)
        if file_size > 5 * 1024 * 1024:  # 5MB limit
            add_log_entry(f"File too large for viewing: {full_path}, size: {file_size} bytes", is_error=True)
            return jsonify({"error": "File too large for viewing"}), 400
        
        # Read file content
        with open(full_path, 'r', errors='replace') as f:
            content = f.read()
        
        add_log_entry(f"File viewed: {full_path}, size: {file_size} bytes")
        return jsonify({"content": content})
    except UnicodeDecodeError:
        add_log_entry(f"File is not a text file: {full_path}", is_error=True)
        return jsonify({"error": "File is not a text file"}), 400
    except Exception as e:
        error_trace = traceback.format_exc()
        add_log_entry(f"Error viewing file {full_path}: {str(e)}\n{error_trace}", is_error=True)
        return jsonify({"error": f"Error viewing file: {str(e)}"}), 500 