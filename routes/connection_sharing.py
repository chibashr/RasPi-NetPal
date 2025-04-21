from flask import Blueprint, jsonify, request
from modules.connection_sharing import get_sharing_status, enable_connection_sharing, disable_connection_sharing, confirm_connection_sharing
from modules.network import get_interfaces
from modules.logging import add_log_entry

bp = Blueprint('connection_sharing', __name__)

@bp.route('/api/network/connection_sharing/status', methods=['GET'])
def sharing_status():
    """Get the current connection sharing status"""
    try:
        status = get_sharing_status()
        return jsonify(status)
    except Exception as e:
        add_log_entry(f"Error getting connection sharing status: {str(e)}", is_error=True)
        return jsonify({"error": str(e)}), 500

@bp.route('/api/network/connection_sharing/enable', methods=['POST'])
def enable_sharing():
    """Enable connection sharing between interfaces"""
    try:
        data = request.json
        source = data.get('source')
        target = data.get('target')
        enable_nat = data.get('enable_nat', True)
        
        if not source or not target:
            return jsonify({"success": False, "message": "Source and target interfaces are required"}), 400
        
        success, message = enable_connection_sharing(source, target, enable_nat)
        return jsonify({"success": success, "message": message})
    except Exception as e:
        add_log_entry(f"Error enabling connection sharing: {str(e)}", is_error=True)
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@bp.route('/api/network/connection_sharing/confirm', methods=['POST'])
def confirm_sharing():
    """Confirm the pending connection sharing configuration"""
    try:
        success, message = confirm_connection_sharing()
        return jsonify({"success": success, "message": message})
    except Exception as e:
        add_log_entry(f"Error confirming connection sharing: {str(e)}", is_error=True)
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@bp.route('/api/network/connection_sharing/disable', methods=['POST'])
def disable_sharing():
    """Disable connection sharing"""
    try:
        success, message = disable_connection_sharing()
        return jsonify({"success": success, "message": message})
    except Exception as e:
        add_log_entry(f"Error disabling connection sharing: {str(e)}", is_error=True)
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@bp.route('/api/network/interfaces', methods=['GET'])
def get_network_interfaces():
    """Get available network interfaces"""
    try:
        interfaces = get_interfaces()
        return jsonify({"interfaces": interfaces})
    except Exception as e:
        add_log_entry(f"Error getting network interfaces: {str(e)}", is_error=True)
        return jsonify({"error": str(e)}), 500 