from flask import Blueprint, jsonify, request, render_template
from flask_socketio import emit, join_room, leave_room
import json
import threading
import time

# Import serial communication functions
try:
    from modules.serial_comm import (
        get_serial_devices, connect_serial_device, disconnect_serial_device,
        send_serial_command, send_serial_break, send_serial_raw_data, get_serial_output, get_connected_serial_devices,
        disconnect_all_serial_devices, get_common_baudrates,
        test_serial_device_connection, serial_manager
    )
except ImportError as e:
    print(f"Error importing serial communication module: {e}")
    # Fallback functions for when module is not available
    def get_serial_devices():
        return []
    def connect_serial_device(device_path, baudrate=9600):
        return False, "Serial module not available"
    def disconnect_serial_device(device_path):
        return False, "Serial module not available"
    def send_serial_command(device_path, command):
        return False, "Serial module not available"
    def send_serial_break(device_path, duration=0.25):
        return False, "Serial module not available"
    def send_serial_raw_data(device_path, data):
        return False, "Serial module not available"
    def get_serial_output(device_path):
        return []
    def get_connected_serial_devices():
        return []
    def disconnect_all_serial_devices():
        return []
    def get_common_baudrates():
        return [9600, 115200]
    def test_serial_device_connection(device_path, baudrate=9600):
        return False, "Serial module not available"
    
    class DummySerialManager:
        def __init__(self):
            pass
    serial_manager = DummySerialManager()

try:
    from modules.logging import add_log_entry
except ImportError:
    def add_log_entry(message, is_error=False):
        print(f"Log: {'ERROR' if is_error else 'INFO'} - {message}")

bp = Blueprint('serial', __name__, url_prefix='/serial')

# Thread for broadcasting serial output to connected clients
output_broadcast_thread = None
output_broadcast_stop = threading.Event()

def start_output_broadcast():
    """Start the background thread that broadcasts serial output to connected clients"""
    global output_broadcast_thread
    
    if output_broadcast_thread and output_broadcast_thread.is_alive():
        return
    
    output_broadcast_stop.clear()
    output_broadcast_thread = threading.Thread(target=broadcast_serial_output, daemon=True)
    output_broadcast_thread.start()

def stop_output_broadcast():
    """Stop the background thread that broadcasts serial output"""
    output_broadcast_stop.set()

def broadcast_serial_output():
    """Background thread function to broadcast serial output to all connected clients"""
    from app import socketio
    
    while not output_broadcast_stop.is_set():
        try:
            connected_devices = get_connected_serial_devices()
            
            for device_info in connected_devices:
                device_path = device_info['path']
                output_lines = get_serial_output(device_path)
                
                if output_lines:
                    # Broadcast to all clients listening to this device
                    for line in output_lines:
                        socketio.emit('serial_output', {
                            'device': device_path,
                            'data': line
                        }, namespace='/serial')
            
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            
        except Exception as e:
            add_log_entry(f"Error broadcasting serial output: {str(e)}", is_error=True)
            time.sleep(1)

@bp.route('/')
def index():
    """Main serial communication interface"""
    return render_template('serial.html')

@bp.route('/devices', methods=['GET'])
def get_devices():
    """Get list of available serial devices"""
    try:
        devices = get_serial_devices()
        connected_devices = {dev['path']: dev for dev in get_connected_serial_devices()}
        
        # Mark connected devices
        for device in devices:
            if device['path'] in connected_devices:
                device['connected'] = True
                device['baudrate'] = connected_devices[device['path']]['baudrate']
            else:
                device['connected'] = False
        
        return jsonify({
            'success': True,
            'devices': devices,
            'connected_count': len(connected_devices)
        })
    except Exception as e:
        add_log_entry(f"Error getting serial devices: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'devices': []
        }), 500

@bp.route('/baudrates', methods=['GET'])
def get_baudrates():
    """Get list of common baud rates"""
    try:
        return jsonify({
            'success': True,
            'baudrates': get_common_baudrates()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'baudrates': [9600, 115200]
        }), 500

@bp.route('/connect', methods=['POST'])
def connect_device():
    """Connect to a serial device"""
    try:
        data = request.get_json()
        device_path = data.get('device_path')
        baudrate = data.get('baudrate', 9600)
        
        if not device_path:
            return jsonify({
                'success': False,
                'error': 'Device path is required'
            }), 400
        
        success, message = connect_serial_device(device_path, baudrate)
        
        if success:
            # Start output broadcasting if not already started
            start_output_broadcast()
            add_log_entry(f"Connected to serial device {device_path} at {baudrate} baud")
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        add_log_entry(f"Error connecting to serial device: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/disconnect', methods=['POST'])
def disconnect_device():
    """Disconnect from a serial device"""
    try:
        data = request.get_json()
        device_path = data.get('device_path')
        
        if not device_path:
            return jsonify({
                'success': False,
                'error': 'Device path is required'
            }), 400
        
        success, message = disconnect_serial_device(device_path)
        
        if success:
            add_log_entry(f"Disconnected from serial device {device_path}")
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        add_log_entry(f"Error disconnecting from serial device: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/disconnect_all', methods=['POST'])
def disconnect_all():
    """Disconnect from all serial devices"""
    try:
        disconnected_devices = disconnect_all_serial_devices()
        
        if disconnected_devices:
            add_log_entry(f"Disconnected from {len(disconnected_devices)} serial devices")
        
        return jsonify({
            'success': True,
            'message': f'Disconnected from {len(disconnected_devices)} devices',
            'disconnected_devices': disconnected_devices
        })
        
    except Exception as e:
        add_log_entry(f"Error disconnecting from all serial devices: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/send_command', methods=['POST'])
def send_command():
    """Send command to a serial device"""
    try:
        data = request.get_json()
        device_path = data.get('device_path')
        command = data.get('command')
        
        if not device_path:
            return jsonify({
                'success': False,
                'error': 'Device path is required'
            }), 400
        
        if not command:
            return jsonify({
                'success': False,
                'error': 'Command is required'
            }), 400
        
        success, message = send_serial_command(device_path, command)
        
        if success:
            add_log_entry(f"Sent command to {device_path}: {command.strip()}")
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        add_log_entry(f"Error sending command: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/test_device', methods=['POST'])
def test_device():
    """Test connection to a serial device"""
    try:
        data = request.get_json()
        device_path = data.get('device_path')
        baudrate = data.get('baudrate', 9600)
        
        if not device_path:
            return jsonify({
                'success': False,
                'error': 'Device path is required'
            }), 400
        
        success, message = test_serial_device_connection(device_path, baudrate)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        add_log_entry(f"Error testing serial device: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/connected_devices', methods=['GET'])
def get_connected():
    """Get list of currently connected devices"""
    try:
        connected_devices = get_connected_serial_devices()
        
        return jsonify({
            'success': True,
            'devices': connected_devices
        })
        
    except Exception as e:
        add_log_entry(f"Error getting connected devices: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'devices': []
        }), 500

@bp.route('/device_output/<path:device_path>', methods=['GET'])
def get_device_output(device_path):
    """Get recent output from a specific device"""
    try:
        # Decode the device path (in case it contains slashes)
        device_path = '/' + device_path
        
        output_lines = get_serial_output(device_path)
        
        return jsonify({
            'success': True,
            'device': device_path,
            'output': output_lines
        })
        
    except Exception as e:
        add_log_entry(f"Error getting device output: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'output': []
        }), 500

@bp.route('/download_output/<path:device_path>', methods=['GET'])
def download_output(device_path):
    """Download output log from a specific device"""
    try:
        from flask import make_response
        import datetime
        
        # Decode the device path
        device_path = '/' + device_path
        
        # Get all available output (this would need to be extended to store full logs)
        output_lines = get_serial_output(device_path)
        
        # Create log content
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        device_name = device_path.replace('/', '_').replace(' ', '_')
        filename = f"serial_log_{device_name}_{timestamp}.txt"
        
        log_content = f"Serial Log for {device_path}\n"
        log_content += f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        log_content += "-" * 50 + "\n\n"
        
        for line in output_lines:
            log_content += line
        
        # Create response
        response = make_response(log_content)
        response.headers['Content-Type'] = 'text/plain'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        add_log_entry(f"Error downloading device output: {str(e)}", is_error=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# WebSocket Events
from app import socketio

@socketio.on('connect', namespace='/serial')
def serial_connect():
    """Handle client connection to serial namespace"""
    try:
        add_log_entry("Client connected to serial interface")
        emit('connection_status', {'connected': True})
        
        # Send current device list
        devices = get_serial_devices()
        connected_devices = {dev['path']: dev for dev in get_connected_serial_devices()}
        
        for device in devices:
            if device['path'] in connected_devices:
                device['connected'] = True
                device['baudrate'] = connected_devices[device['path']]['baudrate']
            else:
                device['connected'] = False
        
        emit('device_list', {
            'devices': devices,
            'connected_count': len(connected_devices)
        })
        
        # Start output broadcasting if there are connected devices
        if connected_devices:
            start_output_broadcast()
            
    except Exception as e:
        add_log_entry(f"Error in serial connect: {str(e)}", is_error=True)
        emit('error', {'message': str(e)})

@socketio.on('disconnect', namespace='/serial')
def serial_disconnect():
    """Handle client disconnection from serial namespace"""
    try:
        add_log_entry("Client disconnected from serial interface")
    except Exception as e:
        add_log_entry(f"Error in serial disconnect: {str(e)}", is_error=True)

@socketio.on('join_device', namespace='/serial')
def join_device_room(data):
    """Join room for a specific device to receive its output"""
    try:
        device_path = data.get('device_path')
        if device_path:
            join_room(f"device:{device_path}")
            emit('joined_device', {'device': device_path})
            add_log_entry(f"Client joined device room: {device_path}")
    except Exception as e:
        add_log_entry(f"Error joining device room: {str(e)}", is_error=True)
        emit('error', {'message': str(e)})

@socketio.on('leave_device', namespace='/serial')
def leave_device_room(data):
    """Leave room for a specific device"""
    try:
        device_path = data.get('device_path')
        if device_path:
            leave_room(f"device:{device_path}")
            emit('left_device', {'device': device_path})
            add_log_entry(f"Client left device room: {device_path}")
    except Exception as e:
        add_log_entry(f"Error leaving device room: {str(e)}", is_error=True)
        emit('error', {'message': str(e)})

@socketio.on('send_command', namespace='/serial')
def handle_send_command(data):
    """Handle command sending via WebSocket"""
    try:
        device_path = data.get('device_path')
        command = data.get('command', '')  # Allow empty commands
        
        if not device_path:
            emit('error', {'message': 'Device path is required'})
            return
        
        success, message = send_serial_command(device_path, command)
        
        emit('command_result', {
            'success': success,
            'message': message,
            'device': device_path,
            'command': command
        })
        
        if success:
            cmd_display = command.strip() if command.strip() else '[ENTER]'
            add_log_entry(f"Command sent via WebSocket to {device_path}: {cmd_display}")
        
    except Exception as e:
        add_log_entry(f"Error handling WebSocket command: {str(e)}", is_error=True)
        emit('error', {'message': str(e)})

@socketio.on('send_break', namespace='/serial')
def handle_send_break(data):
    """Handle break signal sending via WebSocket"""
    try:
        device_path = data.get('device_path')
        duration = data.get('duration', 0.25)
        
        if not device_path:
            emit('error', {'message': 'Device path is required'})
            return
        
        success, message = send_serial_break(device_path, duration)
        
        emit('break_result', {
            'success': success,
            'message': message,
            'device': device_path
        })
        
        if success:
            add_log_entry(f"Break signal sent via WebSocket to {device_path}")
        
    except Exception as e:
        add_log_entry(f"Error handling WebSocket break: {str(e)}", is_error=True)
        emit('error', {'message': str(e)})

@socketio.on('send_raw_data', namespace='/serial')
def handle_send_raw_data(data):
    """Handle raw data sending via WebSocket (like PuTTY)"""
    try:
        device_path = data.get('device_path')
        raw_data = data.get('data', '')
        
        if not device_path:
            emit('error', {'message': 'Device path is required'})
            return
        
        # Send raw data without adding newlines (pure pass-through)
        success, message = send_serial_raw_data(device_path, raw_data)
        
        # Don't emit response for raw data - let device output speak for itself
        if not success:
            emit('error', {'message': f'Failed to send data: {message}'})
        
    except Exception as e:
        add_log_entry(f"Error handling raw data: {str(e)}", is_error=True)
        emit('error', {'message': str(e)})

@socketio.on('refresh_devices', namespace='/serial')
def handle_refresh_devices():
    """Handle device list refresh request"""
    try:
        devices = get_serial_devices()
        connected_devices = {dev['path']: dev for dev in get_connected_serial_devices()}
        
        for device in devices:
            if device['path'] in connected_devices:
                device['connected'] = True
                device['baudrate'] = connected_devices[device['path']]['baudrate']
            else:
                device['connected'] = False
        
        emit('device_list', {
            'devices': devices,
            'connected_count': len(connected_devices)
        })
        
    except Exception as e:
        add_log_entry(f"Error refreshing devices: {str(e)}", is_error=True)
        emit('error', {'message': str(e)})

# Initialize the output broadcasting when the module is loaded
# This will be started when the first device connects 