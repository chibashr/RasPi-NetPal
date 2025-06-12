from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import eventlet
import subprocess
import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import threading
import re

# Patch standard library for eventlet
eventlet.monkey_patch()

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1024 * 1024 * 10, backupCount=5)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

# Create app instance
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# Initialize SocketIO with cors_allowed_origins set to "*" to allow connections from any origin
socketio = SocketIO(
    app, 
    async_mode='eventlet',
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    path='/socket.io'
)

# Worker function to process console commands
# Remove old console worker - now using SSH sessions

@app.route('/')
def index():
    # Check if there's a pending connection sharing confirmation
    try:
        from modules.connection_sharing import get_sharing_status, CONFIRMATION_TIMEOUT
        status = get_sharing_status()
        
        if status.get('pending_confirmation', False):
            # Calculate remaining time
            import time
            timestamp = status.get('timestamp', time.time())
            elapsed = time.time() - timestamp
            remaining = max(0, int(CONFIRMATION_TIMEOUT - elapsed))
            
            # Render the confirmation page with the current config and timeout
            return render_template('connection_confirm.html', 
                                  config=status, 
                                  timeout=remaining)
    except Exception as e:
        app.logger.error(f"Error checking connection sharing status: {str(e)}")
    
    # If no pending confirmation or error, show the normal index page
    return render_template('index.html')

# Import and register blueprint routes
from routes.control import bp as control_bp
app.register_blueprint(control_bp)

# Import other route blueprints
try:
    from routes.capture import bp as capture_bp
    app.register_blueprint(capture_bp)
except ImportError:
    app.logger.warning("Capture routes not found")

try:
    from routes.tools import bp as tools_bp
    app.register_blueprint(tools_bp)
except ImportError:
    app.logger.warning("Tools routes not found")

try:
    from routes.system import bp as system_bp
    app.register_blueprint(system_bp)
except ImportError:
    app.logger.warning("System routes not found")

try:
    from routes.network import bp as network_bp
    app.register_blueprint(network_bp)
except ImportError:
    app.logger.warning("Network routes not found")

try:
    from routes.tftp import bp as tftp_bp
    app.register_blueprint(tftp_bp)
except ImportError:
    app.logger.warning("TFTP routes not found")

try:
    from routes.connection_sharing import bp as connection_sharing_bp
    app.register_blueprint(connection_sharing_bp)
except ImportError:
    app.logger.warning("Connection sharing routes not found")

try:
    from routes.scan import bp as scan_bp
    app.register_blueprint(scan_bp)
except ImportError:
    app.logger.warning("Network scan routes not found")

# Register logs blueprint
try:
    from routes.logs import bp as logs_bp
    app.register_blueprint(logs_bp)
except ImportError:
    app.logger.warning("Logs routes not found")

# Register docs blueprint
try:
    from routes.docs import bp as docs_bp
    app.register_blueprint(docs_bp)
except ImportError:
    app.logger.warning("Documentation routes not found")

# Register issues API blueprint
try:
    from routes.issues import bp as issues_bp
    app.register_blueprint(issues_bp)
except ImportError:
    app.logger.warning("Issue API routes not found")

# Register AnyDesk management blueprint
try:
    from routes.anydesk import bp as anydesk_bp
    app.register_blueprint(anydesk_bp)
except ImportError:
    app.logger.warning("AnyDesk routes not found")

# Register serial communication blueprint
try:
    from routes.serial import bp as serial_bp
    app.register_blueprint(serial_bp)
except ImportError:
    app.logger.warning("Serial communication routes not found")

# Remove old cd helper function - not needed for SSH sessions

# Import SSH communication functions for console
try:
    from modules.ssh_comm import send_ssh_data, get_ssh_output
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False
    def send_ssh_data(session_id, data):
        return False, "SSH module not available"
    def get_ssh_output(session_id):
        return []

# WebSocket for SSH console access
@socketio.on('connect', namespace='/console')
def console_connect():
    """Handle client connection to the SSH console."""
    session_id = request.sid
    app.logger.info(f'WebSocket: Client connected to SSH console: {session_id}')
    
    # Send connection ready message
    socketio.emit('connection_ready', {'session_id': session_id}, namespace='/console')

@socketio.on('disconnect', namespace='/console')
def console_disconnect():
    """Handle client disconnection from the SSH console."""
    session_id = request.sid
    app.logger.info(f'WebSocket: Client disconnected from SSH console: {session_id}')

@socketio.on('join_session', namespace='/console')
def join_session_room(data):
    """Join a specific SSH session room for output broadcasting"""
    session_id = data.get('session_id')
    if session_id:
        join_room(f"ssh_session_{session_id}")
        app.logger.info(f'Client joined SSH session room: {session_id}')

@socketio.on('leave_session', namespace='/console')
def leave_session_room(data):
    """Leave a specific SSH session room"""
    session_id = data.get('session_id')
    if session_id:
        leave_room(f"ssh_session_{session_id}")
        app.logger.info(f'Client left SSH session room: {session_id}')

@socketio.on('send_data', namespace='/console')
def handle_send_data(data):
    """Send data to SSH session"""
    try:
        session_id = data.get('session_id')
        raw_data = data.get('data', '')
        
        if not session_id:
            socketio.emit('error', {'message': 'Session ID required'}, namespace='/console')
            return
        
        if SSH_AVAILABLE:
            success, message = send_ssh_data(session_id, raw_data)
            if not success:
                socketio.emit('error', {'message': f'Failed to send data: {message}'}, namespace='/console')
        else:
            socketio.emit('error', {'message': 'SSH module not available'}, namespace='/console')
            
    except Exception as e:
        app.logger.error(f"Error sending SSH data: {str(e)}")
        socketio.emit('error', {'message': f'Error: {str(e)}'}, namespace='/console')

@socketio.on('refresh_sessions', namespace='/console')
def handle_refresh_sessions():
    """Refresh and send list of connected SSH sessions"""
    try:
        if SSH_AVAILABLE:
            from modules.ssh_comm import get_connected_ssh_sessions
            sessions = get_connected_ssh_sessions()
            socketio.emit('session_list', {'sessions': sessions}, namespace='/console')
        else:
            socketio.emit('session_list', {'sessions': []}, namespace='/console')
    except Exception as e:
        app.logger.error(f"Error refreshing SSH sessions: {str(e)}")
        socketio.emit('session_list', {'sessions': []}, namespace='/console')

@app.route('/get_routes/<iface>', methods=['GET'])
def get_routes(iface):
    """Get detailed routing information for a specific interface."""
    try:
        routes = []
        # Get route information using ip route show
        cmd = f"ip route show dev {iface}"
        result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            route_lines = result.stdout.strip().split('\n')
            for line in route_lines:
                parts = line.split()
                route = {
                    'destination': parts[0] if parts else '',
                    'gateway': '',
                    'mask': '',
                    'flags': '',
                    'metric': '',
                    'interface': iface
                }
                
                # Parse ip route output
                for i, part in enumerate(parts):
                    if part == 'via' and i+1 < len(parts):
                        route['gateway'] = parts[i+1]
                    elif part == 'proto' and i+1 < len(parts):
                        route['flags'] = parts[i+1]
                    elif part == 'metric' and i+1 < len(parts):
                        route['metric'] = parts[i+1]
                
                routes.append(route)
        
        return jsonify({'success': True, 'routes': routes})
    except Exception as e:
        logging.error(f"Error getting route information for {iface}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/test_gateway/<iface>', methods=['GET'])
def test_gateway(iface):
    """Test connectivity to the gateway for a specific interface."""
    try:
        # Get gateway for the interface
        gateway = None
        cmd = f"ip route show dev {iface} | grep default | awk '{{print $3}}'"
        result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            gateway = result.stdout.strip()
        
        # If no default gateway found, check for any gateway
        if not gateway:
            cmd = f"ip route show dev {iface} | grep via | head -1 | awk '{{print $3}}'"
            result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout:
                gateway = result.stdout.strip()
        
        # If still no gateway found, check interface configuration
        if not gateway:
            # Get interface details to check for gateway_override
            interface_data = get_interface_details_data(iface)
            if interface_data and 'dhcp_info' in interface_data:
                if interface_data['dhcp_info'].get('gateway_override'):
                    gateway = interface_data['dhcp_info']['gateway_override']
                elif interface_data['dhcp_info'].get('gateway'):
                    gateway = interface_data['dhcp_info']['gateway']
        
        if not gateway:
            return jsonify({'success': False, 'message': 'No gateway found for this interface'})
        
        # Test connectivity using ping
        cmd = f"ping -c 1 -W 2 -I {iface} {gateway}"
        result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Extract ping time if available
            ping_time = None
            match = re.search(r'time=(\d+\.\d+) ms', result.stdout)
            if match:
                ping_time = float(match.group(1))
            
            return jsonify({
                'success': True, 
                'message': 'Gateway is reachable',
                'ping_time': ping_time
            })
        else:
            return jsonify({'success': False, 'message': 'Gateway is unreachable'})
    except Exception as e:
        logging.error(f"Error testing gateway for {iface}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

def get_interface_details_data(iface):
    """Get detailed information for a specific interface."""
    try:
        # Basic info
        basic_info = {}
        # Get IP address, netmask, etc.
        result = subprocess.run(f"ip addr show {iface}", shell=True, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout
            # Parse state (UP/DOWN)
            state_match = re.search(r'state (\S+)', output)
            if state_match:
                basic_info['state'] = state_match.group(1)
            
            # Parse IP address and netmask
            ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)/(\d+)', output)
            if ip_match:
                basic_info['ip'] = ip_match.group(1)
                basic_info['netmask'] = ip_match.group(2)  # CIDR notation
            
            # Parse MAC address
            mac_match = re.search(r'link/ether (\S+)', output)
            if mac_match:
                basic_info['mac'] = mac_match.group(1)
        
        # Get gateway
        result = subprocess.run(f"ip route show dev {iface} | grep default", shell=True, check=False, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout:
            gateway_match = re.search(r'default via (\S+)', result.stdout)
            if gateway_match:
                basic_info['gateway'] = gateway_match.group(1)
        
        # Get DHCP information
        dhcp_info = {}
        dhcp_conf_path = f"/etc/dhcpcd.conf"
        if os.path.exists(dhcp_conf_path):
            with open(dhcp_conf_path, 'r') as f:
                lines = f.readlines()
                in_interface_block = False
                for line in lines:
                    line = line.strip()
                    if line.startswith(f"interface {iface}"):
                        in_interface_block = True
                    elif in_interface_block and line.startswith("interface "):
                        in_interface_block = False
                    elif in_interface_block:
                        if line.startswith("static ip_address="):
                            dhcp_info['static_ip'] = line.split('=')[1]
                        elif line.startswith("static routers="):
                            dhcp_info['gateway_override'] = line.split('=')[1]
                        elif line.startswith("static domain_name_servers="):
                            dhcp_info['dns_override'] = line.split('=')[1]
        
        return {
            'basic_info': basic_info,
            'dhcp_info': dhcp_info
        }
    except Exception as e:
        logging.error(f"Error getting interface details for {iface}: {str(e)}")
        return None

@app.route('/api/interface/<iface>/routes', methods=['GET'])
def get_interface_routes(iface):
    """Get routes for a specific interface for UI display."""
    try:
        routes = []
        result = subprocess.run(f"ip route show dev {iface}", shell=True, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                route_data = {}
                # Parse destination
                if line.startswith("default"):
                    route_data['destination'] = "default"
                    via_match = re.search(r'via (\S+)', line)
                    if via_match:
                        route_data['gateway'] = via_match.group(1)
                else:
                    # Non-default route
                    dest_match = re.search(r'^(\S+)', line)
                    if dest_match:
                        route_data['destination'] = dest_match.group(1)
                
                # Parse metric if available
                metric_match = re.search(r'metric (\d+)', line)
                if metric_match:
                    route_data['metric'] = metric_match.group(1)
                
                # Parse scope if available
                scope_match = re.search(r'scope (\S+)', line)
                if scope_match:
                    route_data['scope'] = scope_match.group(1)
                
                # Parse protocol if available
                proto_match = re.search(r'proto (\S+)', line)
                if proto_match:
                    route_data['protocol'] = proto_match.group(1)
                
                routes.append(route_data)
                
        return jsonify({'success': True, 'routes': routes})
    except Exception as e:
        logging.error(f"Error getting routes for interface {iface}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/set_default_route', methods=['POST'])
def set_default_route():
    """Set an interface as the default route."""
    try:
        # Get interface name from form data
        iface = request.form.get('iface')
        if not iface:
            return jsonify({
                'success': False,
                'message': 'No interface specified'
            })
        
        # Get gateway for the interface
        gateway = None
        
        # First try to get the gateway assigned to this interface
        cmd = f"ip -4 route show dev {iface} | grep via | head -1 | awk '{{print $3}}'"
        result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            gateway = result.stdout.strip()
            
        # If no gateway found, check for IP in the same subnet
        if not gateway:
            cmd = f"ip -4 addr show dev {iface} | grep inet | awk '{{print $2}}' | cut -d/ -f1"
            result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip()
                
                # Generate a gateway from the IP (use first 3 octets + .1)
                ip_parts = ip.split('.')
                if len(ip_parts) == 4:
                    gateway = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.1"
                    
                    # Test if this gateway is reachable
                    ping_cmd = f"ping -c 1 -W 1 {gateway}"
                    ping_result = subprocess.run(ping_cmd, shell=True, check=False, capture_output=True)
                    if ping_result.returncode != 0:
                        # Try .254 as gateway if .1 didn't work
                        gateway = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.254"
                        
        if not gateway:
            return jsonify({
                'success': False,
                'message': f'Could not determine gateway for interface {iface}'
            })
            
        # Remove existing default routes
        # First check if there's an existing default route
        check_cmd = "ip -4 route show default"
        check_result = subprocess.run(check_cmd, shell=True, check=False, capture_output=True, text=True)
        if check_result.returncode == 0 and check_result.stdout.strip():
            # Remove all existing default routes
            del_cmd = "ip route del default"
            del_result = subprocess.run(del_cmd, shell=True, check=False, capture_output=True, text=True)
            if del_result.returncode != 0:
                app.logger.warning(f"Error removing existing default routes: {del_result.stderr}")
        
        # Add the new default route
        add_cmd = f"ip route add default via {gateway} dev {iface}"
        add_result = subprocess.run(add_cmd, shell=True, check=False, capture_output=True, text=True)
        
        if add_result.returncode != 0:
            return jsonify({
                'success': False,
                'message': f'Error setting default route: {add_result.stderr}'
            })
        
        # Test internet connectivity through the new default route
        internet_test_cmd = f"ping -c 1 -W 3 -I {iface} 8.8.8.8"
        internet_result = subprocess.run(internet_test_cmd, shell=True, check=False, capture_output=True)
        has_internet = internet_result.returncode == 0
        
        internet_message = ""
        if has_internet:
            internet_message = " Internet connectivity confirmed."
        else:
            internet_message = " Note: No internet connectivity detected on this interface."
        
        # Get updated interface information
        interfaces = get_interfaces_data()
        
        # Update has_internet status for the interface with default route
        for i, interface in enumerate(interfaces):
            if interface['name'] == iface:
                interfaces[i]['has_internet'] = has_internet
                interfaces[i]['has_default_route'] = True
            else:
                interfaces[i]['has_default_route'] = False
        
        # Return success response
        return jsonify({
            'success': True,
            'message': f'Default route set to interface {iface} via {gateway}.{internet_message}',
            'interfaces': interfaces
        })
        
    except Exception as e:
        app.logger.error(f"Error setting default route: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })

def get_interfaces_data():
    """Get information about all network interfaces."""
    try:
        interfaces = []
        
        # Get list of interfaces
        cmd = "ls -1 /sys/class/net"
        result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            app.logger.error(f"Error getting network interfaces: {result.stderr}")
            return interfaces
            
        interface_names = result.stdout.strip().split('\n')
        
        # Get default route information
        default_route_cmd = "ip -4 route show default"
        default_route_result = subprocess.run(default_route_cmd, shell=True, check=False, capture_output=True, text=True)
        default_iface = None
        default_gateway = None
        
        if default_route_result.returncode == 0 and default_route_result.stdout.strip():
            # Parse the default route output
            match = re.search(r'default via ([0-9.]+) dev (\w+)', default_route_result.stdout)
            if match:
                default_gateway = match.group(1)
                default_iface = match.group(2)
                
        # Gather information for each interface
        for iface_name in interface_names:
            iface_data = {
                'name': iface_name,
                'state': 'UNKNOWN',
                'addr': None,
                'has_internet': False,
                'has_default_route': iface_name == default_iface,
                'gateway': default_gateway if iface_name == default_iface else None,
                'type': 'ethernet'  # Default type
            }
            
            # Get interface state
            state_cmd = f"cat /sys/class/net/{iface_name}/operstate"
            state_result = subprocess.run(state_cmd, shell=True, check=False, capture_output=True, text=True)
            if state_result.returncode == 0:
                state = state_result.stdout.strip().upper()
                iface_data['state'] = state
                
                # Check if DOWN but carrier is present (connected but admin down)
                if state == 'DOWN':
                    carrier_cmd = f"cat /sys/class/net/{iface_name}/carrier"
                    carrier_result = subprocess.run(carrier_cmd, shell=True, check=False, capture_output=True, text=True)
                    if carrier_result.returncode == 0 and carrier_result.stdout.strip() == '1':
                        iface_data['state'] = 'DOWN (connected)'
            
            # Get IP address
            addr_cmd = f"ip -4 addr show dev {iface_name} | grep inet | awk '{{print $2}}' | cut -d/ -f1"
            addr_result = subprocess.run(addr_cmd, shell=True, check=False, capture_output=True, text=True)
            if addr_result.returncode == 0 and addr_result.stdout.strip():
                iface_data['addr'] = addr_result.stdout.strip()
                
            # Check if it's a USB interface
            # USB interfaces often have "usb" in their sysfs path
            usb_check_cmd = f"readlink -f /sys/class/net/{iface_name} | grep -i usb"
            usb_check_result = subprocess.run(usb_check_cmd, shell=True, check=False, capture_output=True, text=True)
            if usb_check_result.returncode == 0 and usb_check_result.stdout.strip():
                iface_data['type'] = 'usb'
                
            # Check for internet connectivity if the interface is UP
            if iface_data['state'] == 'UP' and iface_data['addr']:
                # Simple internet check - ping a reliable IP
                internet_check_cmd = f"ping -c 1 -W 2 -I {iface_name} 8.8.8.8"
                internet_check_result = subprocess.run(internet_check_cmd, shell=True, check=False, capture_output=True)
                if internet_check_result.returncode == 0:
                    iface_data['has_internet'] = True
            
            # Get all available gateways for this interface
            all_routes_cmd = f"ip -4 route show dev {iface_name} | grep via | awk '{{print $3}}'"
            all_routes_result = subprocess.run(all_routes_cmd, shell=True, check=False, capture_output=True, text=True)
            if all_routes_result.returncode == 0 and all_routes_result.stdout.strip():
                all_routes = all_routes_result.stdout.strip().split('\n')
                # Filter out duplicates
                all_routes = list(set(all_routes))
                iface_data['all_routes'] = all_routes
            
            interfaces.append(iface_data)
        
        return interfaces
    except Exception as e:
        app.logger.error(f"Error getting interface data: {str(e)}")
        return []

# Main entry point for running the app directly
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) # Console implementation updated
