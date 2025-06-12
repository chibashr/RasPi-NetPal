#!/usr/bin/env python3
"""
Serial Bridge Server - TCP to Serial Bridge
Allows external programs to connect to serial devices via TCP sockets.

Usage:
    python3 serial_bridge.py --device /dev/ttyUSB0 --baudrate 9600 --port 9000
    
This creates a TCP server on port 9000 that bridges to /dev/ttyUSB0.
Multiple clients can connect and all will see the same serial data.
"""

import argparse
import socket
import threading
import time
import select
import sys
import os
import signal
import json
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import serial
    from modules.serial_comm import SerialDevice
    from modules.logging import add_log_entry
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please ensure pyserial is installed: pip install pyserial")
    sys.exit(1)

class SerialBridge:
    """TCP to Serial bridge server"""
    
    def __init__(self, device_path, baudrate=9600, tcp_port=9000, max_clients=10):
        self.device_path = device_path
        self.baudrate = baudrate
        self.tcp_port = tcp_port
        self.max_clients = max_clients
        
        self.serial_device = None
        self.tcp_server = None
        self.clients = []
        self.running = False
        
        # Threading
        self.serial_thread = None
        self.server_thread = None
        self.client_threads = []
        
        # Statistics
        self.stats = {
            'start_time': None,
            'bytes_sent': 0,
            'bytes_received': 0,
            'clients_connected': 0,
            'clients_total': 0
        }
    
    def start(self):
        """Start the bridge server"""
        try:
            # Connect to serial device
            self.serial_device = SerialDevice(self.device_path, self.baudrate)
            success, message = self.serial_device.connect()
            
            if not success:
                print(f"Failed to connect to serial device: {message}")
                return False
            
            print(f"Connected to serial device: {self.device_path} at {self.baudrate} baud")
            
            # Start TCP server
            self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_server.bind(('0.0.0.0', self.tcp_port))
            self.tcp_server.listen(self.max_clients)
            
            print(f"TCP server listening on port {self.tcp_port}")
            print(f"Bridge: {self.device_path} <-> TCP:{self.tcp_port}")
            print(f"External programs can connect to: telnet localhost {self.tcp_port}")
            
            self.running = True
            self.stats['start_time'] = datetime.now()
            
            # Start threads
            self.serial_thread = threading.Thread(target=self._serial_reader, daemon=True)
            self.server_thread = threading.Thread(target=self._tcp_server, daemon=True)
            
            self.serial_thread.start()
            self.server_thread.start()
            
            return True
            
        except Exception as e:
            print(f"Error starting bridge: {e}")
            return False
    
    def stop(self):
        """Stop the bridge server"""
        print("Stopping serial bridge...")
        self.running = False
        
        # Close all client connections
        for client in self.clients[:]:
            self._disconnect_client(client)
        
        # Close TCP server
        if self.tcp_server:
            self.tcp_server.close()
        
        # Disconnect serial device
        if self.serial_device:
            self.serial_device.disconnect()
        
        print("Serial bridge stopped")
    
    def _tcp_server(self):
        """TCP server thread - accepts new connections"""
        while self.running:
            try:
                # Use select to make accept non-blocking
                ready, _, _ = select.select([self.tcp_server], [], [], 1.0)
                
                if ready:
                    client_socket, address = self.tcp_server.accept()
                    print(f"New client connected from {address}")
                    
                    # Create client info
                    client = {
                        'socket': client_socket,
                        'address': address,
                        'connected_time': datetime.now(),
                        'bytes_sent': 0,
                        'bytes_received': 0
                    }
                    
                    self.clients.append(client)
                    self.stats['clients_connected'] += 1
                    self.stats['clients_total'] += 1
                    
                    # Send welcome message
                    welcome_msg = f"Connected to serial bridge: {self.device_path} @ {self.baudrate} baud\r\n"
                    self._send_to_client(client, welcome_msg.encode())
                    
                    # Start client handler thread
                    client_thread = threading.Thread(
                        target=self._client_handler, 
                        args=(client,), 
                        daemon=True
                    )
                    client_thread.start()
                    self.client_threads.append(client_thread)
                    
            except Exception as e:
                if self.running:
                    print(f"Error in TCP server: {e}")
                break
    
    def _client_handler(self, client):
        """Handle individual client connection"""
        client_socket = client['socket']
        
        try:
            while self.running:
                # Use select to make recv non-blocking
                ready, _, error = select.select([client_socket], [], [client_socket], 1.0)
                
                if error:
                    break
                
                if ready:
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    
                    # Send data to serial device
                    if self.serial_device and self.serial_device.is_connected:
                        success, message = self.serial_device.write(data)
                        if success:
                            client['bytes_received'] += len(data)
                            self.stats['bytes_received'] += len(data)
                        
        except Exception as e:
            print(f"Error handling client {client['address']}: {e}")
        finally:
            self._disconnect_client(client)
    
    def _serial_reader(self):
        """Serial reader thread - broadcasts data to all clients"""
        while self.running:
            try:
                if self.serial_device and self.serial_device.is_connected:
                    # Get any available output
                    output_lines = self.serial_device.read_output()
                    
                    for line in output_lines:
                        data = line.encode()
                        self._broadcast_to_clients(data)
                        self.stats['bytes_sent'] += len(data)
                
                time.sleep(0.01)  # Small delay to prevent excessive CPU usage
                
            except Exception as e:
                if self.running:
                    print(f"Error reading from serial: {e}")
                time.sleep(1)
    
    def _broadcast_to_clients(self, data):
        """Send data to all connected clients"""
        disconnected_clients = []
        
        for client in self.clients:
            if not self._send_to_client(client, data):
                disconnected_clients.append(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            self._disconnect_client(client)
    
    def _send_to_client(self, client, data):
        """Send data to a specific client"""
        try:
            client['socket'].send(data)
            client['bytes_sent'] += len(data)
            return True
        except:
            return False
    
    def _disconnect_client(self, client):
        """Disconnect a client"""
        try:
            if client in self.clients:
                self.clients.remove(client)
                self.stats['clients_connected'] -= 1
                
                print(f"Client {client['address']} disconnected")
                print(f"  Connection time: {datetime.now() - client['connected_time']}")
                print(f"  Bytes sent: {client['bytes_sent']}, received: {client['bytes_received']}")
                
            client['socket'].close()
        except:
            pass
    
    def print_status(self):
        """Print current status"""
        if not self.running:
            print("Bridge is not running")
            return
        
        uptime = datetime.now() - self.stats['start_time'] if self.stats['start_time'] else "Unknown"
        
        print(f"\n=== Serial Bridge Status ===")
        print(f"Device: {self.device_path} @ {self.baudrate} baud")
        print(f"TCP Port: {self.tcp_port}")
        print(f"Uptime: {uptime}")
        print(f"Connected Clients: {self.stats['clients_connected']}")
        print(f"Total Clients: {self.stats['clients_total']}")
        print(f"Bytes Sent: {self.stats['bytes_sent']}")
        print(f"Bytes Received: {self.stats['bytes_received']}")
        
        if self.clients:
            print(f"\nActive Clients:")
            for i, client in enumerate(self.clients):
                duration = datetime.now() - client['connected_time']
                print(f"  {i+1}. {client['address']} (connected: {duration})")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\nReceived shutdown signal")
    if 'bridge' in globals():
        bridge.stop()
    sys.exit(0)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Serial Bridge Server - TCP to Serial Bridge')
    parser.add_argument('--device', '-d', required=True, help='Serial device path (e.g., /dev/ttyUSB0)')
    parser.add_argument('--baudrate', '-b', type=int, default=9600, help='Baud rate (default: 9600)')
    parser.add_argument('--port', '-p', type=int, default=9000, help='TCP port (default: 9000)')
    parser.add_argument('--max-clients', '-m', type=int, default=10, help='Maximum clients (default: 10)')
    parser.add_argument('--status-interval', '-s', type=int, default=30, help='Status print interval in seconds (0 to disable)')
    
    args = parser.parse_args()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(f"Starting Serial Bridge Server")
    print(f"Device: {args.device}")
    print(f"Baud Rate: {args.baudrate}")
    print(f"TCP Port: {args.port}")
    print(f"Max Clients: {args.max_clients}")
    print()
    
    # Create and start bridge
    global bridge
    bridge = SerialBridge(args.device, args.baudrate, args.port, args.max_clients)
    
    if not bridge.start():
        print("Failed to start bridge")
        sys.exit(1)
    
    print("Bridge started successfully!")
    print("Press Ctrl+C to stop")
    print()
    
    # Status reporting loop
    last_status = time.time()
    
    try:
        while bridge.running:
            time.sleep(1)
            
            # Print status periodically
            if args.status_interval > 0:
                now = time.time()
                if now - last_status >= args.status_interval:
                    bridge.print_status()
                    last_status = now
                    
    except KeyboardInterrupt:
        print("\nShutdown requested")
    finally:
        bridge.stop()

if __name__ == '__main__':
    main() 