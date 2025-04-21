from flask import Blueprint, jsonify, request, render_template, send_file
from modules.capture import list_captures, start_capture, stop_capture, get_capture_output, delete_capture, view_capture, rename_capture
from modules.network import get_interfaces
from modules.logging import add_log_entry
import os

bp = Blueprint('capture', __name__)

@bp.route("/capture", methods=["GET"])
def capture():
    """Capture page with packet capture tool"""
    return render_template(
        "capture.html",
        interfaces=get_interfaces(),
        capture_running=bool(get_capture_output()[1]),
        capture_history=list_captures()
    )

@bp.route("/start_capture", methods=["POST"])
def handle_start_capture():
    """Start packet capture on selected interface"""
    interface = request.form.get("interface")
    filter_expr = request.form.get("filter", "")
    capture_name = request.form.get("name", "")
    promiscuous = request.form.get("promiscuous", "true").lower() == "true"
    
    add_log_entry(f"Request to start capture on {interface} with filter: '{filter_expr}', promiscuous: {promiscuous}")
    success, message, capture_id = start_capture(interface, filter_expr, capture_name, promiscuous)
    
    return jsonify({
        "success": success,
        "message": message,
        "capture_running": success,
        "capture_id": capture_id
    })

@bp.route("/stop_capture", methods=["POST"])
def handle_stop_capture():
    """Stop the packet capture"""
    capture_id = request.form.get("capture_id")
    
    success, message = stop_capture(capture_id)
    
    return jsonify({
        "success": success,
        "message": message,
        "capture_running": False
    })

@bp.route("/get_capture_output", methods=["GET"])
def handle_get_capture_output():
    """Get the current capture output"""
    capture_id = request.args.get("id")
    
    output, is_running = get_capture_output(capture_id)
    
    return jsonify({
        "success": True,
        "capture_running": is_running,
        "output": output
    })

@bp.route("/download_capture/<capture_id>", methods=["GET"])
def download_capture(capture_id):
    """Download a capture file"""
    captures = list_captures()
    
    for capture in captures:
        if capture["id"] == capture_id:
            if os.path.exists(capture["file_path"]):
                download_name = f"{capture['name']}.pcap"
                return send_file(
                    capture["file_path"],
                    as_attachment=True,
                    download_name=download_name,
                    mimetype="application/vnd.tcpdump.pcap"
                )
    
    return jsonify({
        "success": False,
        "message": "Capture file not found"
    }), 404

@bp.route("/delete_capture/<capture_id>", methods=["POST"])
def handle_delete_capture(capture_id):
    """Delete a capture file"""
    success, message = delete_capture(capture_id)
    
    return jsonify({
        "success": success,
        "message": message
    })

@bp.route("/view_capture/<capture_id>", methods=["GET"])
def handle_view_capture(capture_id):
    """View a specific capture file"""
    output, name_or_error = view_capture(capture_id)
    
    if output is None:
        return jsonify({
            "success": False,
            "message": name_or_error
        }), 404
    
    return jsonify({
        "success": True,
        "name": name_or_error,
        "output": output
    })

@bp.route("/rename_capture/<capture_id>", methods=["POST"])
def handle_rename_capture(capture_id):
    """Rename a capture file"""
    new_name = request.form.get("new_name", "")
    
    if not new_name:
        return jsonify({
            "success": False,
            "message": "New name is required"
        }), 400
    
    success, message = rename_capture(capture_id, new_name)
    
    return jsonify({
        "success": success,
        "message": message
    }) 