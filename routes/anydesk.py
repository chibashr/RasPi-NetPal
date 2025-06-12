from flask import Blueprint, jsonify, request
import subprocess

try:
    from modules.anydesk import (
        is_anydesk_installed, get_anydesk_status, get_anydesk_id,
        set_anydesk_password, install_anydesk, restart_anydesk,
        enable_anydesk_autostart, get_anydesk_logs
    )
except ImportError as e:
    print(f"Error importing anydesk module: {e}")
    # Fallback functions
    def is_anydesk_installed():
        return False
    
    def get_anydesk_status():
        return {
            'installed': False,
            'service_status': 'unknown',
            'service_enabled': False,
            'anydesk_id': None,
            'version': 'Unknown',
            'connection_status': 'Unknown',
            'dependencies_ok': False,
            'dependency_issues': ['AnyDesk module not available']
        }
    
    def get_anydesk_id():
        return None
    
    def set_anydesk_password(password):
        return False, "AnyDesk module not available"
    
    def install_anydesk():
        return False, "AnyDesk module not available"
    
    def restart_anydesk():
        return False, "AnyDesk module not available"
    
    def enable_anydesk_autostart():
        return False, "AnyDesk module not available"
    
    def get_anydesk_logs():
        return "AnyDesk module not available"

bp = Blueprint('anydesk', __name__)

@bp.route("/get_anydesk_status", methods=["GET"])
def anydesk_status():
    """Get comprehensive AnyDesk status"""
    try:
        status = get_anydesk_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'status': {
                'installed': False,
                'service_status': 'error',
                'service_enabled': False,
                'anydesk_id': None,
                'version': 'Unknown',
                'connection_status': 'Error',
                'dependencies_ok': False,
                'dependency_issues': [str(e)]
            }
        })

@bp.route("/set_anydesk_password", methods=["POST"])
def set_password():
    """Set AnyDesk unattended access password"""
    try:
        password = request.form.get("password")
        if not password:
            return jsonify({
                'success': False,
                'message': 'Password is required'
            })
        
        success, message = set_anydesk_password(password)
        
        # Get updated status
        status = get_anydesk_status()
        
        return jsonify({
            'success': success,
            'message': message,
            'status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error setting password: {str(e)}'
        })

@bp.route("/install_anydesk", methods=["POST"])
def install():
    """Install AnyDesk"""
    try:
        success, message = install_anydesk()
        
        # Get updated status after installation
        status = get_anydesk_status()
        
        return jsonify({
            'success': success,
            'message': message,
            'status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Installation error: {str(e)}'
        })

@bp.route("/restart_anydesk", methods=["POST"])
def restart():
    """Restart AnyDesk service"""
    try:
        success, message = restart_anydesk()
        
        # Get updated status
        status = get_anydesk_status()
        
        return jsonify({
            'success': success,
            'message': message,
            'status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Restart error: {str(e)}'
        })

@bp.route("/enable_anydesk_autostart", methods=["POST"])
def enable_autostart():
    """Enable AnyDesk auto-start"""
    try:
        success, message = enable_anydesk_autostart()
        
        # Get updated status
        status = get_anydesk_status()
        
        return jsonify({
            'success': success,
            'message': message,
            'status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error enabling auto-start: {str(e)}'
        })

@bp.route("/get_anydesk_logs", methods=["GET"])
def logs():
    """Get AnyDesk logs"""
    try:
        logs = get_anydesk_logs()
        return jsonify({
            'success': True,
            'logs': logs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'logs': f'Error retrieving logs: {str(e)}'
        }) 