import subprocess
import os
import threading
import time
import queue
import select
import glob
import serial
import serial.tools.list_ports
from .logging import add_log_entry
import json
import pty
import fcntl
import termios
import struct

class SerialDevice:
    """Represents a single serial device connection"""
    
    def __init__(self, device_path, baudrate=9600, timeout=1):
        self.device_path = device_path
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection = None
        self.is_connected = False
        self.read_thread = None
        self.output_queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.lock = threading.Lock()
        
    def connect(self):
        """Connect to the serial device"""
        try:
            with self.lock:
                if self.is_connected:
                    return True, "Already connected"
                
                self.connection = serial.Serial(
                    port=self.device_path,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False
                )
                
                self.is_connected = True
                self.stop_flag.clear()
                
                # Start reading thread
                self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
                self.read_thread.start()
                
                add_log_entry(f"Connected to serial device {self.device_path} at {self.baudrate} baud")
                return True, f"Successfully connected to {self.device_path}"
                
        except serial.SerialException as e:
            error_msg = f"Failed to connect to {self.device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error connecting to {self.device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def disconnect(self):
        """Disconnect from the serial device"""
        try:
            with self.lock:
                if not self.is_connected:
                    return True, "Already disconnected"
                
                self.stop_flag.set()
                
                if self.connection and self.connection.is_open:
                    self.connection.close()
                
                self.is_connected = False
                
                if self.read_thread and self.read_thread.is_alive():
                    self.read_thread.join(timeout=2)
                
                add_log_entry(f"Disconnected from serial device {self.device_path}")
                return True, f"Successfully disconnected from {self.device_path}"
                
        except Exception as e:
            error_msg = f"Error disconnecting from {self.device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def write(self, data):
        """Write data to the serial device"""
        try:
            with self.lock:
                if not self.is_connected or not self.connection:
                    return False, "Device not connected"
                
                if isinstance(data, str):
                    data = data.encode('utf-8')
                
                self.connection.write(data)
                self.connection.flush()
                
                return True, f"Sent {len(data)} bytes"
                
        except Exception as e:
            error_msg = f"Error writing to {self.device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def send_break(self, duration=0.25):
        """Send a break signal to the serial device"""
        try:
            with self.lock:
                if not self.is_connected or not self.connection:
                    return False, "Device not connected"
                
                self.connection.send_break(duration)
                add_log_entry(f"Sent break signal to {self.device_path}")
                return True, "Break signal sent"
                
        except Exception as e:
            error_msg = f"Error sending break to {self.device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def read_output(self):
        """Get any available output from the device"""
        output = []
        try:
            while not self.output_queue.empty():
                output.append(self.output_queue.get_nowait())
        except queue.Empty:
            pass
        return output
    
    def _read_loop(self):
        """Background thread to read from serial device"""
        buffer = b""
        
        while not self.stop_flag.is_set() and self.is_connected:
            try:
                with self.lock:
                    if not self.connection or not self.connection.is_open:
                        break
                    
                    # Check if data is available to read
                    if self.connection.in_waiting > 0:
                        data = self.connection.read(self.connection.in_waiting)
                        if data:
                            buffer += data
                            
                            # Process complete lines
                            while b'\n' in buffer:
                                line, buffer = buffer.split(b'\n', 1)
                                try:
                                    decoded_line = line.decode('utf-8', errors='replace').rstrip('\r')
                                    self.output_queue.put(decoded_line + '\n')
                                except Exception:
                                    # If decoding fails, put raw bytes as hex
                                    hex_line = ' '.join(f'{b:02x}' for b in line)
                                    self.output_queue.put(f"[HEX] {hex_line}\n")
                
                time.sleep(0.01)  # Small delay to prevent excessive CPU usage
                
            except Exception as e:
                if self.is_connected:  # Only log if we're supposed to be connected
                    add_log_entry(f"Error reading from {self.device_path}: {str(e)}", is_error=True)
                break
        
        # If there's remaining data in buffer, add it
        if buffer:
            try:
                decoded_buffer = buffer.decode('utf-8', errors='replace')
                self.output_queue.put(decoded_buffer)
            except Exception:
                hex_buffer = ' '.join(f'{b:02x}' for b in buffer)
                self.output_queue.put(f"[HEX] {hex_buffer}")

class SerialManager:
    """Manages multiple serial device connections"""
    
    def __init__(self):
        self.devices = {}  # device_path -> SerialDevice
        self.device_info = {}  # device_path -> device info dict
        self.lock = threading.Lock()
        
    def scan_devices(self):
        """Scan for available serial devices"""
        devices = []
        
        try:
            # Use pyserial's built-in device listing
            ports = serial.tools.list_ports.comports()
            for port in ports:
                device_info = {
                    'path': port.device,
                    'name': port.name,
                    'description': port.description or 'Unknown device',
                    'manufacturer': port.manufacturer or 'Unknown',
                    'product': port.product or 'Unknown',
                    'serial_number': port.serial_number or 'Unknown',
                    'vid': hex(port.vid) if port.vid else 'Unknown',
                    'pid': hex(port.pid) if port.pid else 'Unknown',
                    'connected': port.device in self.devices and self.devices[port.device].is_connected
                }
                devices.append(device_info)
                self.device_info[port.device] = device_info
            
            # Also check common serial device paths manually
            common_paths = [
                '/dev/ttyUSB*',
                '/dev/ttyACM*', 
                '/dev/ttyS*',
                '/dev/ttyAMA*',
                '/dev/serial/by-id/*',
                '/dev/serial/by-path/*'
            ]
            
            for pattern in common_paths:
                for device_path in glob.glob(pattern):
                    if not any(d['path'] == device_path for d in devices):
                        # Check if device exists and is accessible
                        if os.path.exists(device_path):
                            try:
                                # Try to get device info
                                device_info = {
                                    'path': device_path,
                                    'name': os.path.basename(device_path),
                                    'description': f'Serial device at {device_path}',
                                    'manufacturer': 'Unknown',
                                    'product': 'Unknown',
                                    'serial_number': 'Unknown',
                                    'vid': 'Unknown',
                                    'pid': 'Unknown',
                                    'connected': device_path in self.devices and self.devices[device_path].is_connected
                                }
                                devices.append(device_info)
                                self.device_info[device_path] = device_info
                            except Exception:
                                pass
            
            add_log_entry(f"Found {len(devices)} serial devices")
            return devices
            
        except Exception as e:
            add_log_entry(f"Error scanning serial devices: {str(e)}", is_error=True)
            return []
    
    def connect_device(self, device_path, baudrate=9600):
        """Connect to a specific serial device"""
        try:
            with self.lock:
                if device_path in self.devices:
                    device = self.devices[device_path]
                    if device.is_connected:
                        return True, "Already connected"
                    else:
                        # Remove old disconnected device
                        del self.devices[device_path]
                
                # Create new device connection
                device = SerialDevice(device_path, baudrate)
                success, message = device.connect()
                
                if success:
                    self.devices[device_path] = device
                    
                return success, message
                
        except Exception as e:
            error_msg = f"Error connecting to device {device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def disconnect_device(self, device_path):
        """Disconnect from a specific serial device"""
        try:
            with self.lock:
                if device_path not in self.devices:
                    return True, "Device not connected"
                
                device = self.devices[device_path]
                success, message = device.disconnect()
                
                if success:
                    del self.devices[device_path]
                
                return success, message
                
        except Exception as e:
            error_msg = f"Error disconnecting from device {device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def send_command(self, device_path, command):
        """Send a command to a specific device"""
        try:
            with self.lock:
                if device_path not in self.devices:
                    return False, "Device not connected"
                
                device = self.devices[device_path]
                
                # Handle empty commands by sending just newline
                if not command:
                    command = '\n'
                elif not command.endswith('\n'):
                    command += '\n'
                
                return device.write(command)
                
        except Exception as e:
            error_msg = f"Error sending command to {device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def send_raw_data(self, device_path, data):
        """Send raw data to a specific device (no automatic newlines)"""
        try:
            with self.lock:
                if device_path not in self.devices:
                    return False, "Device not connected"
                
                device = self.devices[device_path]
                
                # Send data exactly as provided (raw mode like PuTTY)
                return device.write(data)
                
        except Exception as e:
            error_msg = f"Error sending raw data to {device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def send_break(self, device_path, duration=0.25):
        """Send a break signal to a specific device"""
        try:
            with self.lock:
                if device_path not in self.devices:
                    return False, "Device not connected"
                
                device = self.devices[device_path]
                return device.send_break(duration)
                
        except Exception as e:
            error_msg = f"Error sending break to {device_path}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def get_device_output(self, device_path):
        """Get output from a specific device"""
        try:
            with self.lock:
                if device_path not in self.devices:
                    return []
                
                device = self.devices[device_path]
                return device.read_output()
                
        except Exception as e:
            add_log_entry(f"Error getting output from {device_path}: {str(e)}", is_error=True)
            return []
    
    def get_connected_devices(self):
        """Get list of currently connected devices"""
        try:
            with self.lock:
                connected = []
                for device_path, device in self.devices.items():
                    if device.is_connected:
                        info = self.device_info.get(device_path, {
                            'path': device_path,
                            'name': os.path.basename(device_path),
                            'description': 'Connected serial device',
                            'baudrate': device.baudrate
                        })
                        info['baudrate'] = device.baudrate
                        info['connected'] = True
                        connected.append(info)
                return connected
                
        except Exception as e:
            add_log_entry(f"Error getting connected devices: {str(e)}", is_error=True)
            return []
    
    def disconnect_all(self):
        """Disconnect from all devices"""
        disconnected = []
        try:
            with self.lock:
                for device_path, device in list(self.devices.items()):
                    try:
                        device.disconnect()
                        disconnected.append(device_path)
                    except Exception as e:
                        add_log_entry(f"Error disconnecting {device_path}: {str(e)}", is_error=True)
                
                self.devices.clear()
                
        except Exception as e:
            add_log_entry(f"Error disconnecting all devices: {str(e)}", is_error=True)
        
        return disconnected

# Global serial manager instance
serial_manager = SerialManager()

def get_serial_devices():
    """Get list of available serial devices"""
    return serial_manager.scan_devices()

def connect_serial_device(device_path, baudrate=9600):
    """Connect to a serial device"""
    return serial_manager.connect_device(device_path, baudrate)

def disconnect_serial_device(device_path):
    """Disconnect from a serial device"""
    return serial_manager.disconnect_device(device_path)

def send_serial_command(device_path, command):
    """Send command to a serial device"""
    return serial_manager.send_command(device_path, command)

def send_serial_break(device_path, duration=0.25):
    """Send break signal to a serial device"""
    return serial_manager.send_break(device_path, duration)

def send_serial_raw_data(device_path, data):
    """Send raw data to a serial device"""
    return serial_manager.send_raw_data(device_path, data)

def get_serial_output(device_path):
    """Get output from a serial device"""
    return serial_manager.get_device_output(device_path)

def get_connected_serial_devices():
    """Get list of connected serial devices"""
    return serial_manager.get_connected_devices()

def disconnect_all_serial_devices():
    """Disconnect from all serial devices"""
    return serial_manager.disconnect_all()

def get_common_baudrates():
    """Get list of common baud rates"""
    return [
        300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 28800, 
        38400, 57600, 115200, 230400, 460800, 921600
    ]

def test_serial_device_connection(device_path, baudrate=9600, test_duration=2):
    """Test if a serial device can be connected to and responds"""
    try:
        # First check if device exists
        if not os.path.exists(device_path):
            return False, f"Device {device_path} does not exist"
        
        # Check permissions
        if not os.access(device_path, os.R_OK | os.W_OK):
            return False, f"Permission denied for {device_path}"
        
        # Try to open and configure the device
        test_device = SerialDevice(device_path, baudrate, timeout=1)
        success, message = test_device.connect()
        
        if success:
            # Send a simple test command (carriage return)
            test_device.write('\r\n')
            time.sleep(0.5)
            
            # Try to read any response
            output = test_device.read_output()
            test_device.disconnect()
            
            response_info = f"Device responds with {len(output)} lines" if output else "No immediate response"
            return True, f"Successfully tested {device_path} at {baudrate} baud. {response_info}"
        else:
            return False, message
            
    except Exception as e:
        return False, f"Test failed for {device_path}: {str(e)}" 