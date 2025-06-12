from flask import Blueprint, render_template, jsonify, request
import os
import json
import re
from datetime import datetime

bp = Blueprint('logs', __name__, url_prefix='/logs')

# Path to logs directory
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

@bp.route('/')
def logs_index():
    """Render the logs page"""
    return render_template('logs.html')

@bp.route('/list')
def list_logs():
    """List all log files in the logs directory"""
    if not os.path.exists(LOGS_DIR):
        return jsonify({"error": "Logs directory not found"}), 404
    
    log_files = []
    for filename in os.listdir(LOGS_DIR):
        file_path = os.path.join(LOGS_DIR, filename)
        if os.path.isfile(file_path):
            try:
                file_size = os.path.getsize(file_path)
                size_str = f"{file_size/1024:.1f} KB" if file_size < 1024*1024 else f"{file_size/(1024*1024):.1f} MB"
                
                # Get modification time
                mtime = os.path.getmtime(file_path)
                mod_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                
                # Count number of error lines
                error_count = 0
                try:
                    with open(file_path, 'r') as f:
                        for line in f:
                            if 'error' in line.lower() or '[error]' in line.lower():
                                error_count += 1
                except:
                    pass
                
                log_files.append({
                    "name": filename,
                    "size": size_str,
                    "raw_size": file_size,
                    "modified": mod_time,
                    "modified_timestamp": mtime,
                    "error_count": error_count
                })
            except Exception as e:
                continue
    
    # Sort log files by modification time (newest first)
    log_files = sorted(log_files, key=lambda x: x["modified_timestamp"], reverse=True)
    
    return jsonify({"log_files": log_files})

@bp.route('/view/<filename>')
def view_log(filename):
    """Get contents of a log file"""
    file_path = os.path.join(LOGS_DIR, filename)
    
    # Security check to prevent directory traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(LOGS_DIR)):
        return jsonify({"error": "Invalid file path"}), 403
    
    if not os.path.exists(file_path):
        return jsonify({"error": "Log file not found"}), 404
    
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 100, type=int)
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_order = request.args.get('sort_order', 'desc')
    filter_level = request.args.get('filter_level', 'all')
    search_term = request.args.get('search', '')
    
    # Cap the limit to prevent loading too much at once
    limit = min(limit, 1000)
    
    # Handle different log formats
    if filename.endswith('.json') or filename == 'app_log.txt':
        # JSON format logs
        try:
            entries = []
            line_count = 0
            error_count = 0
            warning_count = 0
            
            with open(file_path, 'r') as f:
                for line in f:
                    line_count += 1
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            
                            # Check level for counting
                            level = entry.get('level', '').lower()
                            if level == 'error':
                                error_count += 1
                            elif level == 'warning':
                                warning_count += 1
                                
                            # Apply level filtering
                            if filter_level != 'all':
                                if filter_level == 'error' and level != 'error':
                                    continue
                                if filter_level == 'warning' and level not in ['error', 'warning']:
                                    continue
                            
                            # Apply search term filtering
                            if search_term and not (
                                search_term.lower() in entry.get('message', '').lower() or
                                search_term.lower() in entry.get('level', '').lower()
                            ):
                                continue
                            
                            entries.append(entry)
                        except:
                            # Handle non-JSON lines
                            entry = {"timestamp": "", "message": line.strip(), "level": "UNKNOWN"}
                            entries.append(entry)
            
            # Sort entries
            if sort_by == 'timestamp':
                # Try to parse timestamps for sorting
                def get_timestamp(entry):
                    ts = entry.get('timestamp', '')
                    try:
                        return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f')
                    except:
                        try:
                            return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                        except:
                            return datetime.min
                
                entries.sort(key=get_timestamp, reverse=(sort_order == 'desc'))
            elif sort_by == 'level':
                # Custom sort order for log levels
                def get_level_priority(entry):
                    level = entry.get('level', '').lower()
                    if level == 'error':
                        return 0
                    elif level == 'warning':
                        return 1
                    elif level == 'info':
                        return 2
                    elif level == 'debug':
                        return 3
                    else:
                        return 4
                
                entries.sort(key=get_level_priority, reverse=(sort_order == 'asc'))
            
            # Handle pagination after filtering and sorting
            filtered_count = len(entries)
            start = (page - 1) * limit
            end = start + limit
            
            return jsonify({
                "entries": entries[start:end],
                "total": line_count,
                "filtered_count": filtered_count,
                "error_count": error_count,
                "warning_count": warning_count,
                "page": page,
                "limit": limit,
                "format": "json"
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        # Text format logs
        try:
            lines = []
            line_count = 0
            error_count = 0
            warning_count = 0
            
            with open(file_path, 'r') as f:
                for line in f:
                    line_count += 1
                    line_text = line.strip()
                    
                    # Try to extract timestamp and level using common log patterns
                    timestamp_match = re.search(r'\[([\d\-\s:\.]+)\]', line)
                    level_match = re.search(r'\[(INFO|ERROR|WARNING|DEBUG)\]', line, re.IGNORECASE)
                    
                    timestamp = timestamp_match.group(1) if timestamp_match else ""
                    level = level_match.group(1).upper() if level_match else "INFO"
                    
                    # Count errors and warnings
                    if level == "ERROR" or "error" in line_text.lower():
                        error_count += 1
                        level = "ERROR"  # Ensure consistency
                    elif level == "WARNING" or "warning" in line_text.lower():
                        warning_count += 1
                        level = "WARNING"  # Ensure consistency
                    
                    # Apply level filtering
                    if filter_level != 'all':
                        if filter_level == 'error' and level != 'ERROR':
                            continue
                        if filter_level == 'warning' and level not in ['ERROR', 'WARNING']:
                            continue
                    
                    # Apply search term filtering
                    if search_term and search_term.lower() not in line_text.lower():
                        continue
                    
                    # Extract additional timestamp for sorting
                    try:
                        if timestamp:
                            dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f')
                        else:
                            # Try to find a timestamp in the text
                            date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', line_text)
                            if date_match:
                                dt = datetime.strptime(date_match.group(1), '%Y-%m-%d %H:%M:%S')
                            else:
                                dt = None
                    except:
                        dt = None
                    
                    entry = {
                        "line": line_text,
                        "timestamp": timestamp,
                        "level": level,
                        "dt": dt
                    }
                    lines.append(entry)
            
            # Sort entries
            if sort_by == 'timestamp' and any(entry["dt"] for entry in lines):
                lines.sort(key=lambda x: x["dt"] if x["dt"] else datetime.min, reverse=(sort_order == 'desc'))
            elif sort_by == 'level':
                # Custom sort order for log levels
                def get_level_priority(entry):
                    level = entry.get('level', '').upper()
                    if level == 'ERROR':
                        return 0
                    elif level == 'WARNING':
                        return 1
                    elif level == 'INFO':
                        return 2
                    elif level == 'DEBUG':
                        return 3
                    else:
                        return 4
                
                lines.sort(key=get_level_priority, reverse=(sort_order == 'asc'))
            
            # Handle pagination after filtering and sorting
            filtered_count = len(lines)
            start = (page - 1) * limit
            end = start + limit
            paginated_lines = lines[start:end]
            
            return jsonify({
                "lines": paginated_lines,
                "total": line_count,
                "filtered_count": filtered_count,
                "error_count": error_count, 
                "warning_count": warning_count,
                "page": page,
                "limit": limit,
                "format": "text"
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500 