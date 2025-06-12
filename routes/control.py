from flask import Blueprint, render_template, request, jsonify
from flask_socketio import emit, join_room, leave_room
import subprocess
import os
import time
import socket
import threading
try:
    import netifaces
    NETIFACES_AVAILABLE = True
except ImportError:
    NETIFACES_AVAILABLE = False
from modules.logging import add_log_entry

# Import SSH communication functions
try:
    from modules.ssh_comm import (
        create_ssh_session, disconnect_ssh_session, send_ssh_data, 
        get_ssh_output, get_connected_ssh_sessions, disconnect_all_ssh_sessions,
        test_ssh_connection, ssh_manager
    )
    SSH_AVAILABLE = True
except ImportError as e:
    print(f"Error importing SSH communication module: {e}")
    # Fallback functions for when module is not available
    def create_ssh_session(session_id, host='localhost', port=22, username=None, password=None):
        return False, "SSH module not available"
    def disconnect_ssh_session(session_id):
        return False, "SSH module not available"
    def send_ssh_data(session_id, data):
        return False, "SSH module not available"
    def get_ssh_output(session_id):
        return []
    def get_connected_ssh_sessions():
        return []
    def disconnect_all_ssh_sessions():
        return []
    def test_ssh_connection(host='localhost', port=22, username=None, password=None):
        return False, "SSH module not available"
    
    class DummySSHManager:
        def __init__(self):
            pass
    ssh_manager = DummySSHManager()
    SSH_AVAILABLE = False

# Create blueprint
bp = Blueprint('control', __name__)

# Thread for broadcasting SSH output to connected clients
output_broadcast_thread = None
output_broadcast_stop = threading.Event()

def start_output_broadcast():
    """Start the background thread that broadcasts SSH output to connected clients"""
    global output_broadcast_thread
    
    if output_broadcast_thread and output_broadcast_thread.is_alive():
        return
    
    output_broadcast_stop.clear()
    output_broadcast_thread = threading.Thread(target=broadcast_ssh_output, daemon=True)
    output_broadcast_thread.start()

def stop_output_broadcast():
    """Stop the background thread that broadcasts SSH output"""
    output_broadcast_stop.set()

def broadcast_ssh_output():
    """Background thread function to broadcast SSH output to all connected clients"""
    from app import socketio
    
    while not output_broadcast_stop.is_set():
        try:
            connected_sessions = get_connected_ssh_sessions()
            
            for session_info in connected_sessions:
                session_id = session_info['session_id']
                output_lines = get_ssh_output(session_id)
                
                if output_lines:
                    # Broadcast to all clients listening to this session
                    for line in output_lines:
                        socketio.emit('ssh_output', {
                            'session_id': session_id,
                            'data': line
                        }, namespace='/console')
            
            time.sleep(0.05)  # Small delay to prevent excessive CPU usage
            
        except Exception as e:
            add_log_entry(f"Error broadcasting SSH output: {str(e)}", is_error=True)
            time.sleep(1)

@bp.route('/control')
def control_page():
    """Render the Raspberry Pi control page."""
    add_log_entry("Accessed Pi Control page")
    return render_template('control.html')

@bp.route('/ssh/connect', methods=['POST'])
def ssh_connect():
    """Connect to SSH session"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        host = data.get('host', 'localhost')
        port = data.get('port', 22)
        username = data.get('username')
        password = data.get('password')
        
        if not session_id or not username or not password:
            return jsonify({
                'success': False,
                'error': 'Session ID, username and password are required'
            }), 400
        
        # Test connection first
        test_success, test_message = test_ssh_connection(host, port, username, password)
        if not test_success:
            return jsonify({
                'success': False,
                'error': test_message
            })
        
        success, message = create_ssh_session(session_id, host, port, username, password)
        
        if success:
            # Start output broadcasting if not already started
            start_output_broadcast()
            add_log_entry(f"SSH session created: {username}@{host}:{port}")
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        add_log_entry(f"Error creating SSH session: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/ssh/disconnect', methods=['POST'])
def ssh_disconnect():
    """Disconnect SSH session"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Session ID is required'
            }), 400
        
        success, message = disconnect_ssh_session(session_id)
        
        if success:
            add_log_entry(f"SSH session disconnected: {session_id}")
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        add_log_entry(f"Error disconnecting SSH session: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/ssh/test', methods=['POST'])
def ssh_test():
    """Test SSH connection"""
    try:
        data = request.get_json()
        host = data.get('host', 'localhost')
        port = data.get('port', 22)
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400
        
        success, message = test_ssh_connection(host, port, username, password)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        add_log_entry(f"Error testing SSH connection: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/ssh/sessions', methods=['GET'])
def get_ssh_sessions():
    """Get list of connected SSH sessions"""
    try:
        sessions = get_connected_ssh_sessions()
        return jsonify({
            'success': True,
            'sessions': sessions
        })
    except Exception as e:
        add_log_entry(f"Error getting SSH sessions: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'sessions': []
        }), 500

@bp.route('/get_system_ips', methods=['GET'])
def get_system_ips():
    """Get all system IP addresses for VNC connection display."""
    try:
        ip_addresses = []
        
        # Try netifaces first if available
        if NETIFACES_AVAILABLE:
            try:
                # Get all network interfaces
                interfaces = netifaces.interfaces()
                
                for interface in interfaces:
                    # Skip loopback interface
                    if interface == 'lo':
                        continue
                        
                    # Get address info for this interface
                    addresses = netifaces.ifaddresses(interface)
                    
                    # Get IPv4 addresses
                    if netifaces.AF_INET in addresses:
                        for addr_info in addresses[netifaces.AF_INET]:
                            ip = addr_info.get('addr')
                            if ip and not ip.startswith('127.'):
                                ip_addresses.append({
                                    'interface': interface,
                                    'ip': ip,
                                    'netmask': addr_info.get('netmask', '')
                                })
            except Exception:
                pass
        
        # Fallback method if netifaces doesn't work or isn't available
        if not ip_addresses:
            try:
                # Get hostname IP
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                if not local_ip.startswith('127.'):
                    ip_addresses.append({
                        'interface': 'default',
                        'ip': local_ip,
                        'netmask': ''
                    })
            except:
                pass
            
            # Try alternative method with ip command
            try:
                result = subprocess.run(['ip', 'addr', 'show'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    current_interface = None
                    for line in lines:
                        if line.strip() and not line.startswith(' '):
                            # Interface line
                            parts = line.split(':')
                            if len(parts) >= 2:
                                current_interface = parts[1].strip()
                        elif 'inet ' in line and '127.0.0.1' not in line:
                            # IP address line
                            parts = line.strip().split()
                            for part in parts:
                                if '/' in part and not part.startswith('127.'):
                                    ip = part.split('/')[0]
                                    ip_addresses.append({
                                        'interface': current_interface or 'unknown',
                                        'ip': ip,
                                        'netmask': ''
                                    })
                                    break
            except:
                pass
        
        # If still no IPs found, add localhost as fallback
        if not ip_addresses:
            ip_addresses.append({
                'interface': 'localhost',
                'ip': 'localhost',
                'netmask': ''
            })
        
        return jsonify({
            'success': True,
            'ip_addresses': ip_addresses
        })
        
    except Exception as e:
        add_log_entry(f"Error getting system IPs: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'ip_addresses': [{'interface': 'localhost', 'ip': 'localhost', 'netmask': ''}]
        })

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
        
        # Try different VNC server options
        
        # First try x11vnc (most common for headless Pi)
        try:
            process = subprocess.Popen(['x11vnc', '-display', ':0', '-forever', '-nopw', '-quiet', '-bg'],
                                      capture_output=True, text=True)
            process.wait(timeout=3)  # Wait briefly for startup
            
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
            pass
            
        # Try RealVNC (if installed)
        try:
            # Enable VNC service if available
            subprocess.run(['sudo', 'systemctl', 'enable', 'vncserver-x11-serviced'], 
                          capture_output=True, text=True)
            process = subprocess.run(['sudo', 'systemctl', 'start', 'vncserver-x11-serviced'], 
                                    capture_output=True, text=True)
            
            if process.returncode == 0:
                add_log_entry("Started RealVNC server")
                return jsonify({
                    'success': True,
                    'message': 'RealVNC server started successfully',
                    'port': 5900
                })
        except:
            pass
            
        # Try wayvnc (for Wayland environments)
        try:
            process = subprocess.Popen(['wayvnc', '0.0.0.0', '5900'],
                                      capture_output=True, text=True)
            
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
            pass
            
        # Fallback to TigerVNC/vncserver
        try:
            process = subprocess.run(['vncserver', ':1', '-geometry', '1024x768', '-depth', '24'],
                                    capture_output=True, text=True)
            
            if process.returncode == 0:
                add_log_entry("Started TigerVNC server")
                return jsonify({
                    'success': True,
                    'message': 'TigerVNC server started successfully',
                    'port': 5901  # Display :1 = port 5901
                })
        except:
            pass
        
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
        stopped = False
        
        # Try stopping RealVNC service first
        try:
            process = subprocess.run(['sudo', 'systemctl', 'stop', 'vncserver-x11-serviced'], 
                                    capture_output=True, text=True)
            if process.returncode == 0:
                stopped = True
                add_log_entry("Stopped RealVNC server")
        except:
            pass
        
        # Try stopping different types of VNC servers
        vnc_servers = ['x11vnc', 'wayvnc']
        
        for server in vnc_servers:
            # Find and kill the process
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
                add_log_entry(f"Stopped {server} server")
        
        # Try stopping TigerVNC displays
        for display in [':0', ':1', ':2']:
            try:
                process = subprocess.run(['vncserver', '-kill', display],
                                       capture_output=True, text=True)
                if process.returncode == 0:
                    stopped = True
                    add_log_entry(f"Stopped TigerVNC display {display}")
            except:
                pass
        
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

@bp.route('/vnc_status', methods=['GET'])
def vnc_status():
    """Check if VNC server is running."""
    try:
        # Check for different types of VNC servers
        vnc_processes = ['x11vnc', 'wayvnc', 'Xvnc']
        
        for process_name in vnc_processes:
            check = subprocess.run(['pgrep', process_name], 
                                  capture_output=True, text=True)
            if check.returncode == 0:
                return jsonify({
                    'success': True,
                    'running': True,
                    'server_type': process_name,
                    'port': 5900  # Default VNC port
                })
        
        # Check for RealVNC service
        try:
            service_check = subprocess.run(['systemctl', 'is-active', 'vncserver-x11-serviced'], 
                                         capture_output=True, text=True)
            if service_check.returncode == 0 and service_check.stdout.strip() == 'active':
                return jsonify({
                    'success': True,
                    'running': True,
                    'server_type': 'RealVNC',
                    'port': 5900
                })
        except:
            pass
        
        # No VNC server found running
        return jsonify({
            'success': True,
            'running': False,
            'server_type': None,
            'port': None
        })
        
    except Exception as e:
        add_log_entry(f"VNC status check error: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'running': False
        }), 500