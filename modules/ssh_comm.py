import subprocess
import os
import threading
import time
import queue
import select
import paramiko
import socket
from .logging import add_log_entry
import json
import pty
import fcntl
import termios
import struct

class SSHSession:
    """Represents a single SSH session connection"""
    
    def __init__(self, host='localhost', port=22, username=None, password=None, timeout=10):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.client = None
        self.channel = None
        self.is_connected = False
        self.output_queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.read_thread = None
        self.lock = threading.Lock()
        
    def connect(self):
        """Connect to the SSH server"""
        try:
            with self.lock:
                if self.is_connected:
                    return True, "Already connected"
                
                # Create SSH client
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Connect to SSH server
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                    allow_agent=False,
                    look_for_keys=False
                )
                
                # Create interactive shell channel
                self.channel = self.client.invoke_shell()
                self.channel.settimeout(0.1)  # Non-blocking
                
                self.is_connected = True
                self.stop_flag.clear()
                
                # Start reading thread
                self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
                self.read_thread.start()
                
                add_log_entry(f"Connected to SSH session {self.username}@{self.host}:{self.port}")
                return True, f"Successfully connected to {self.username}@{self.host}:{self.port}"
                
        except paramiko.AuthenticationException:
            return False, "Authentication failed - invalid username or password"
        except paramiko.SSHException as e:
            return False, f"SSH connection error: {str(e)}"
        except socket.timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def disconnect(self):
        """Disconnect from the SSH server"""
        try:
            with self.lock:
                if not self.is_connected:
                    return True, "Already disconnected"
                
                self.stop_flag.set()
                self.is_connected = False
                
                # Close channel and client
                if self.channel:
                    self.channel.close()
                    self.channel = None
                
                if self.client:
                    self.client.close()
                    self.client = None
                
                # Wait for read thread to finish
                if self.read_thread and self.read_thread.is_alive():
                    self.read_thread.join(timeout=2)
                
                add_log_entry(f"Disconnected from SSH session {self.username}@{self.host}:{self.port}")
                return True, "Successfully disconnected"
                
        except Exception as e:
            add_log_entry(f"Error disconnecting SSH session: {str(e)}", is_error=True)
            return False, f"Disconnect error: {str(e)}"
    
    def write(self, data):
        """Send data to the SSH session"""
        try:
            with self.lock:
                if not self.is_connected or not self.channel:
                    return False, "Not connected"
                
                # Send data to SSH channel
                self.channel.send(data)
                return True, "Data sent successfully"
                
        except Exception as e:
            add_log_entry(f"Error sending data to SSH session: {str(e)}", is_error=True)
            return False, f"Send error: {str(e)}"
    
    def read_output(self):
        """Get available output from the SSH session"""
        output = []
        try:
            while not self.output_queue.empty():
                output.append(self.output_queue.get_nowait())
        except:
            pass
        return output
    
    def _read_loop(self):
        """Background thread to read from SSH session"""
        while not self.stop_flag.is_set() and self.is_connected:
            try:
                with self.lock:
                    if not self.channel or self.channel.closed:
                        break
                    
                    # Check if data is available to read
                    if self.channel.recv_ready():
                        data = self.channel.recv(4096)
                        if data:
                            try:
                                # Decode data as UTF-8
                                decoded_data = data.decode('utf-8', errors='replace')
                                self.output_queue.put(decoded_data)
                            except Exception:
                                # If decoding fails, put raw bytes as hex
                                hex_data = ' '.join(f'{b:02x}' for b in data)
                                self.output_queue.put(f"[HEX] {hex_data}")
                
                time.sleep(0.01)  # Small delay to prevent excessive CPU usage
                
            except Exception as e:
                if self.is_connected:  # Only log if we're supposed to be connected
                    add_log_entry(f"Error reading from SSH session: {str(e)}", is_error=True)
                break

class SSHManager:
    """Manages SSH session connections"""
    
    def __init__(self):
        self.sessions = {}  # session_id -> SSHSession
        self.session_info = {}  # session_id -> session info dict
        self.lock = threading.Lock()
        
    def create_session(self, session_id, host='localhost', port=22, username=None, password=None):
        """Create a new SSH session"""
        try:
            with self.lock:
                if session_id in self.sessions:
                    session = self.sessions[session_id]
                    if session.is_connected:
                        return True, "Session already exists and connected"
                    else:
                        # Remove old disconnected session
                        del self.sessions[session_id]
                
                # Create new SSH session
                session = SSHSession(host, port, username, password)
                success, message = session.connect()
                
                if success:
                    self.sessions[session_id] = session
                    self.session_info[session_id] = {
                        'host': host,
                        'port': port,
                        'username': username,
                        'connected': True,
                        'session_id': session_id
                    }
                    
                return success, message
                
        except Exception as e:
            error_msg = f"Error creating SSH session: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def disconnect_session(self, session_id):
        """Disconnect a specific SSH session"""
        try:
            with self.lock:
                if session_id not in self.sessions:
                    return True, "Session not found"
                
                session = self.sessions[session_id]
                success, message = session.disconnect()
                
                if success:
                    del self.sessions[session_id]
                    if session_id in self.session_info:
                        del self.session_info[session_id]
                
                return success, message
                
        except Exception as e:
            error_msg = f"Error disconnecting SSH session: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def send_data(self, session_id, data):
        """Send data to a specific SSH session"""
        try:
            with self.lock:
                if session_id not in self.sessions:
                    return False, "Session not connected"
                
                session = self.sessions[session_id]
                return session.write(data)
                
        except Exception as e:
            error_msg = f"Error sending data to SSH session {session_id}: {str(e)}"
            add_log_entry(error_msg, is_error=True)
            return False, error_msg
    
    def get_output(self, session_id):
        """Get output from a specific SSH session"""
        try:
            with self.lock:
                if session_id not in self.sessions:
                    return []
                
                session = self.sessions[session_id]
                return session.read_output()
                
        except Exception as e:
            add_log_entry(f"Error getting output from SSH session {session_id}: {str(e)}", is_error=True)
            return []
    
    def get_connected_sessions(self):
        """Get list of currently connected sessions"""
        try:
            with self.lock:
                connected = []
                for session_id, session in self.sessions.items():
                    if session.is_connected:
                        info = self.session_info.get(session_id, {
                            'session_id': session_id,
                            'host': session.host,
                            'port': session.port,
                            'username': session.username,
                            'connected': True
                        })
                        connected.append(info)
                return connected
                
        except Exception as e:
            add_log_entry(f"Error getting connected SSH sessions: {str(e)}", is_error=True)
            return []
    
    def disconnect_all(self):
        """Disconnect from all SSH sessions"""
        disconnected = []
        try:
            with self.lock:
                for session_id, session in list(self.sessions.items()):
                    try:
                        session.disconnect()
                        disconnected.append(session_id)
                    except Exception as e:
                        add_log_entry(f"Error disconnecting SSH session {session_id}: {str(e)}", is_error=True)
                
                self.sessions.clear()
                self.session_info.clear()
                
        except Exception as e:
            add_log_entry(f"Error disconnecting all SSH sessions: {str(e)}", is_error=True)
        
        return disconnected

# Global SSH manager instance
ssh_manager = SSHManager()

def create_ssh_session(session_id, host='localhost', port=22, username=None, password=None):
    """Create a new SSH session"""
    return ssh_manager.create_session(session_id, host, port, username, password)

def disconnect_ssh_session(session_id):
    """Disconnect an SSH session"""
    return ssh_manager.disconnect_session(session_id)

def send_ssh_data(session_id, data):
    """Send data to an SSH session"""
    return ssh_manager.send_data(session_id, data)

def get_ssh_output(session_id):
    """Get output from an SSH session"""
    return ssh_manager.get_output(session_id)

def get_connected_ssh_sessions():
    """Get list of connected SSH sessions"""
    return ssh_manager.get_connected_sessions()

def disconnect_all_ssh_sessions():
    """Disconnect all SSH sessions"""
    return ssh_manager.disconnect_all()

def test_ssh_connection(host='localhost', port=22, username=None, password=None, timeout=5):
    """Test if SSH connection can be established"""
    try:
        # Test SSH connection
        test_session = SSHSession(host, port, username, password, timeout)
        success, message = test_session.connect()
        
        if success:
            test_session.disconnect()
            return True, f"Successfully tested SSH connection to {username}@{host}:{port}"
        else:
            return False, message
            
    except Exception as e:
        return False, f"Test failed for {username}@{host}:{port}: {str(e)}" 