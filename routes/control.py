from flask import Blueprint, render_template, request, jsonify
import subprocess
import os
import time
from modules.logging import add_log_entry

# Create blueprint
bp = Blueprint('control', __name__)

@bp.route('/control')
def control_page():
    """Render the Raspberry Pi control page."""
    add_log_entry("Accessed Pi Control page")
    return render_template('control.html')

# The WebSocket route will be registered in app.py 

@bp.route('/start_vnc', methods=['POST'])
def start_vnc():
    """Start a VNC server on the Raspberry Pi."""
    try:
        # Check if VNC is already running
        check_process = subprocess.run(['pgrep', 'wayvnc'], 
                                      capture_output=True, text=True)
        
        if check_process.returncode == 0:
            # VNC is already running
            return jsonify({
                'success': True,
                'message': 'VNC server is already running',
                'port': 5900  # Default VNC port
            })
        
        # For Raspberry Pi, try using the system's existing VNC capabilities
        # Try wayvnc first (for Wayland)
        try:
            # Start with wayvnc
            process = subprocess.run(['wayvnc', '0.0.0.0', '5900'],
                                    capture_output=True, text=True,
                                    start_new_session=True)
            
            # Check if wayvnc is now running
            check = subprocess.run(['pgrep', 'wayvnc'], 
                                  capture_output=True, text=True)
            
            if check.returncode == 0:
                add_log_entry("Started wayvnc server")
                return jsonify({
                    'success': True,
                    'message': 'wayvnc server started successfully',
                    'port': 5900
                })
        except:
            # wayvnc failed, try x11vnc (for X11)
            try:
                process = subprocess.run(['x11vnc', '-display', ':0', '-forever', '-nopw', '-quiet'],
                                        capture_output=True, text=True,
                                        start_new_session=True)
                
                # Check if x11vnc is now running
                check = subprocess.run(['pgrep', 'x11vnc'], 
                                      capture_output=True, text=True)
                
                if check.returncode == 0:
                    add_log_entry("Started x11vnc server")
                    return jsonify({
                        'success': True,
                        'message': 'x11vnc server started successfully',
                        'port': 5900
                    })
            except:
                # Fallback to tigervnc/vncserver
                process = subprocess.run(['vncserver', ':0', '-geometry', '1024x768', '-depth', '24'],
                                        capture_output=True, text=True)
                
                if process.returncode == 0:
                    add_log_entry("Started TigerVNC server")
                    return jsonify({
                        'success': True,
                        'message': 'VNC server started successfully',
                        'port': 5900
                    })
        
        # If all attempts failed
        add_log_entry("Failed to start any VNC server", is_error=True)
        return jsonify({
            'success': False,
            'message': 'Failed to start any VNC server'
        }), 500
    
    except Exception as e:
        add_log_entry(f"VNC server error: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@bp.route('/stop_vnc', methods=['POST'])
def stop_vnc():
    """Stop the VNC server."""
    try:
        # Try stopping different types of VNC servers
        vnc_servers = ['wayvnc', 'x11vnc', 'vncserver']
        stopped = False
        
        for server in vnc_servers:
            if server == 'vncserver':
                # TigerVNC needs special handling
                process = subprocess.run(['vncserver', '-kill', ':0'],
                                       capture_output=True, text=True)
                if process.returncode == 0:
                    stopped = True
            else:
                # For wayvnc and x11vnc, just find and kill the process
                check = subprocess.run(['pgrep', server], 
                                      capture_output=True, text=True)
                if check.returncode == 0:
                    # Get the PIDs
                    pids = check.stdout.strip().split('\n')
                    for pid in pids:
                        if pid:
                            subprocess.run(['kill', pid.strip()], 
                                          capture_output=True, text=True)
                    stopped = True
        
        if stopped:
            add_log_entry("Stopped VNC server")
            return jsonify({
                'success': True,
                'message': 'VNC server stopped successfully'
            })
        else:
            add_log_entry("No running VNC server found to stop", is_error=True)
            return jsonify({
                'success': False,
                'message': 'No running VNC server found to stop'
            }), 404
    
    except Exception as e:
        add_log_entry(f"VNC server stop error: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500 