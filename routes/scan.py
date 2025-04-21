from flask import Blueprint, jsonify, request, render_template, send_file
from modules.scanner import (NetworkScanner, get_saved_scans, get_scan_results, 
                            rename_scan, delete_scan, get_active_scans)
from modules.network import get_interfaces
from modules.logging import add_log_entry
import json
import tempfile
import os
from datetime import datetime

bp = Blueprint('scan', __name__)

@bp.route("/scan")
def scan_page():
    """Render the network scanning page"""
    return render_template('scan.html')

@bp.route("/api/scan/interfaces")
def get_network_interfaces():
    """Get network interfaces for scanning"""
    interfaces = get_interfaces()
    return jsonify(interfaces)

@bp.route("/api/scan/start", methods=["POST"])
def start_scan():
    """Start a new network scan"""
    data = request.json
    target_range = data.get('target_range')
    name = data.get('name')
    options = data.get('options', {})
    
    if not target_range:
        return jsonify({"success": False, "message": "No target range specified"})
    
    scanner = NetworkScanner(name=name)
    success = scanner.start_scan(target_range, options)
    
    if success:
        return jsonify({
            "success": True, 
            "message": f"Scan started with ID {scanner.scan_id}",
            "scan_id": scanner.scan_id,
            "name": scanner.name
        })
    else:
        return jsonify({
            "success": False, 
            "message": "Failed to start scan. Check the target range and try again."
        })

@bp.route("/api/scan/cancel/<scan_id>", methods=["POST"])
def cancel_scan(scan_id):
    """Cancel an ongoing scan"""
    from modules.scanner import active_scans
    
    if scan_id in active_scans:
        scanner = active_scans[scan_id]
        if scanner.cancel_scan():
            return jsonify({"success": True, "message": f"Scan {scan_id} cancelled"})
        else:
            return jsonify({"success": False, "message": "Could not cancel scan"})
    else:
        return jsonify({"success": False, "message": "Scan not found or already completed"})

@bp.route("/api/scan/status/<scan_id>")
def get_scan_status(scan_id):
    """Get the status of a scan"""
    from modules.scanner import active_scans
    
    # Check active scans first
    if scan_id in active_scans:
        scanner = active_scans[scan_id]
        return jsonify({
            "success": True,
            "active": True,
            "status": scanner.status,
            "progress": scanner.progress,
            "scanned_hosts": scanner.scanned_hosts,
            "total_hosts": scanner.total_hosts,
            "result_count": len([r for r in scanner.results if r is not None])
        })
    
    # Check saved scans
    results = get_scan_results(scan_id)
    if results:
        return jsonify({
            "success": True,
            "active": False,
            "status": results.get("status", "unknown"),
            "progress": 100 if results.get("status") == "completed" else 0,
            "scanned_hosts": results.get("scanned_hosts", 0),
            "total_hosts": results.get("total_hosts", 0),
            "result_count": len(results.get("results", []))
        })
    
    return jsonify({"success": False, "message": "Scan not found"})

@bp.route("/api/scan/list")
def list_scans():
    """List all saved scans"""
    saved_scans = get_saved_scans()
    active = get_active_scans()
    
    # Add active scans to the list
    active_scan_list = [scan for scan in active.values()]
    
    # Combine active and saved scans
    all_scans = active_scan_list + saved_scans
    
    # Sort by start time (newest first)
    all_scans.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    
    return jsonify({"success": True, "scans": all_scans})

@bp.route("/api/scan/results/<scan_id>")
def get_results(scan_id):
    """Get results for a specific scan"""
    results = get_scan_results(scan_id)
    if results:
        return jsonify({"success": True, "results": results})
    else:
        return jsonify({"success": False, "message": "Scan not found"})

@bp.route("/api/scan/rename/<scan_id>", methods=["POST"])
def rename_scan_route(scan_id):
    """Rename a saved scan"""
    data = request.json
    new_name = data.get('name')
    
    if not new_name:
        return jsonify({"success": False, "message": "No new name provided"})
    
    if rename_scan(scan_id, new_name):
        return jsonify({"success": True, "message": f"Scan renamed to {new_name}"})
    else:
        return jsonify({"success": False, "message": "Failed to rename scan"})

@bp.route("/api/scan/delete/<scan_id>", methods=["POST"])
def delete_scan_route(scan_id):
    """Delete a saved scan"""
    if delete_scan(scan_id):
        return jsonify({"success": True, "message": "Scan deleted"})
    else:
        return jsonify({"success": False, "message": "Failed to delete scan"})

@bp.route("/api/scan/export/<scan_id>")
def export_scan(scan_id):
    """Export scan results as a downloadable JSON file"""
    format_type = request.args.get('format', 'json')
    results = get_scan_results(scan_id)
    
    if not results:
        return jsonify({"success": False, "message": "Scan not found"})
    
    scan_name = results.get("name", "scan_results")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        if format_type == 'json':
            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='.json')
            with os.fdopen(fd, 'w') as tmp:
                json.dump(results, tmp, indent=2)
            
            filename = f"{scan_name}_{timestamp}.json"
            return send_file(temp_path, as_attachment=True, download_name=filename, mimetype='application/json')
        
        elif format_type == 'csv':
            # Create a temporary CSV file
            fd, temp_path = tempfile.mkstemp(suffix='.csv')
            with os.fdopen(fd, 'w') as tmp:
                # Write header
                tmp.write("IP,Status,MAC,Hostname,Host Type,Response Time\n")
                
                # Write data
                for host in results.get("results", []):
                    if host and host.get("status") == "up":
                        tmp.write(f"{host.get('ip', '')},{host.get('status', '')},{host.get('mac', '')}," + 
                                 f"{host.get('hostname', '')},{host.get('host_type', '')}," + 
                                 f"{host.get('response_time', '')}\n")
            
            filename = f"{scan_name}_{timestamp}.csv"
            return send_file(temp_path, as_attachment=True, download_name=filename, mimetype='text/csv')
            
        else:
            return jsonify({"success": False, "message": "Unsupported export format"})
    
    except Exception as e:
        add_log_entry(f"Error exporting scan {scan_id}: {str(e)}", is_error=True)
        return jsonify({"success": False, "message": f"Error exporting scan: {str(e)}"}) 