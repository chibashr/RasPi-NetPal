import os
import subprocess
import json
import sys
import traceback
import re
from .logging import add_log_entry

class TFTPManager:
    """Manages TFTP server and client operations."""
    
    def __init__(self, transfer_dir):
        """Initialize with the transfer directory."""
        self.transfer_dir = transfer_dir
        add_log_entry(f"TFTPManager initialized with transfer_dir: {transfer_dir}")
        
    def get_server_status(self):
        """Check if the TFTP server is running."""
        try:
            # Check systemd service status
            add_log_entry(f"Checking TFTP server status...")
            cmd = ['systemctl', 'is-active', 'tftpd-hpa']
            add_log_entry(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            status = result.stdout.strip()
            
            add_log_entry(f"TFTP service status: {status}")
            return status == "active"
        except Exception as e:
            error_trace = traceback.format_exc()
            add_log_entry(f"Error checking TFTP server status: {str(e)}\n{error_trace}", is_error=True)
            return False
    
    def start_server(self):
        """Start the TFTP server."""
        try:
            # Ensure the transfer directory exists and has correct permissions
            add_log_entry(f"Starting TFTP server with transfer_dir: {self.transfer_dir}")
            os.makedirs(self.transfer_dir, exist_ok=True)
            
            # Log the action being attempted
            add_log_entry(f"Attempting to start TFTP server")
            
            try:
                # Set permissions to allow tftpd to read/write
                chmod_cmd = ['sudo', 'chmod', '777', self.transfer_dir]
                add_log_entry(f"Setting permissions with command: {' '.join(chmod_cmd)}")
                subprocess.run(chmod_cmd, check=True)
                add_log_entry(f"Set permissions for {self.transfer_dir}")
            except subprocess.CalledProcessError as e:
                # Safe error logging that handles different exception types
                stdout = e.stdout.decode() if hasattr(e, 'stdout') and e.stdout else "N/A"
                stderr = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else "N/A"
                add_log_entry(f"Failed to set permissions: {str(e)}, stdout: {stdout}, stderr: {stderr}", is_error=True)
                raise Exception(f"Permission error: {str(e)}. Please ensure the web service user has sudo permission.")
            
            # Configure the TFTP server to use the transfer directory
            # This is typically done by editing /etc/default/tftpd-hpa
            config_path = '/etc/default/tftpd-hpa'
            add_log_entry(f"Checking for TFTP config at: {config_path}")
            if os.path.exists(config_path):
                try:
                    add_log_entry(f"Reading existing TFTP config")
                    with open(config_path, 'r') as f:
                        config = f.read()
                    
                    add_log_entry(f"Original config:\n{config}")
                    
                    # Update the TFTP directory and options
                    config = self._update_tftp_config(config, self.transfer_dir)
                    add_log_entry(f"Updated config:\n{config}")
                    
                    # Write the updated config to a temporary file
                    temp_config_path = '/tmp/tftpd-hpa'
                    add_log_entry(f"Writing updated config to {temp_config_path}")
                    with open(temp_config_path, 'w') as f:
                        f.write(config)
                    
                    # Copy the config using sudo
                    try:
                        cp_cmd = ['sudo', 'cp', temp_config_path, config_path]
                        add_log_entry(f"Copying config with command: {' '.join(cp_cmd)}")
                        subprocess.run(cp_cmd, check=True)
                        add_log_entry("Updated TFTP configuration")
                    except subprocess.CalledProcessError as e:
                        # Safe error logging that handles different exception types
                        stdout = e.stdout.decode() if hasattr(e, 'stdout') and e.stdout else "N/A"
                        stderr = e.stderr.decode() if hasattr(e, 'stderr') and e.stderr else "N/A"
                        add_log_entry(f"Failed to update TFTP config: {str(e)}, stdout: {stdout}, stderr: {stderr}", is_error=True)
                        raise Exception(f"Configuration error: {str(e)}. Please ensure the web service user has sudo permission to copy files.")
                except Exception as e:
                    error_trace = traceback.format_exc()
                    add_log_entry(f"Error updating config: {str(e)}\n{error_trace}", is_error=True)
                    raise Exception(f"Config file handling error: {str(e)}")
            else:
                add_log_entry(f"TFTP config file not found: {config_path}", is_error=True)
                raise Exception(f"TFTP config file not found: {config_path}. Please ensure tftpd-hpa is installed.")
            
            # Start the TFTP server
            try:
                # Try systemctl first, then service if that fails
                try:
                    restart_cmd = ['sudo', 'systemctl', 'restart', 'tftpd-hpa']
                    add_log_entry(f"Restarting TFTP with systemctl: {' '.join(restart_cmd)}")
                    restart_result = subprocess.run(restart_cmd, capture_output=True, check=True, text=True)
                    add_log_entry(f"systemctl restart output - stdout: {restart_result.stdout}, stderr: {restart_result.stderr}")
                    add_log_entry("TFTP server started via systemctl")
                except subprocess.CalledProcessError as e:
                    # Try using service command as fallback
                    # Safe error logging that handles different exception types
                    stdout = e.stdout if hasattr(e, 'stdout') else "N/A"
                    stderr = e.stderr if hasattr(e, 'stderr') else "N/A"
                    add_log_entry(f"systemctl restart failed: {str(e)}, stdout: {stdout}, stderr: {stderr}", is_error=True)
                    try:
                        service_cmd = ['sudo', 'service', 'tftpd-hpa', 'restart']
                        add_log_entry(f"Trying service command: {' '.join(service_cmd)}")
                        service_result = subprocess.run(service_cmd, capture_output=True, check=True, text=True)
                        add_log_entry(f"service restart output - stdout: {service_result.stdout}, stderr: {service_result.stderr}")
                        add_log_entry("TFTP server started via service command")
                    except subprocess.CalledProcessError as inner_e:
                        # Safe error handling for string or bytes objects
                        error_output = stdout
                        inner_error = inner_e.stderr if hasattr(inner_e, 'stderr') else str(inner_e)
                        if hasattr(inner_error, 'decode'):
                            inner_error = inner_error.decode()
                        add_log_entry(f"Failed to start TFTP server with both systemctl and service: {error_output}, {inner_error}", is_error=True)
                        raise Exception(f"Service error: Could not start tftpd-hpa. systemctl error: {error_output}, service error: {inner_error}")
            except Exception as e:
                error_trace = traceback.format_exc()
                add_log_entry(f"Unexpected error starting TFTP service: {str(e)}\n{error_trace}", is_error=True)
                raise Exception(f"Service control error: {str(e)}")
            
            # Verify the service is actually running
            add_log_entry("Verifying TFTP service is running...")
            is_active = self.get_server_status()
            add_log_entry(f"TFTP service active status: {is_active}")
            
            if is_active:
                add_log_entry(f"TFTP server started successfully")
                return True
            else:
                add_log_entry("TFTP service start command succeeded but service is not active", is_error=True)
                return False
                
        except Exception as e:
            error_trace = traceback.format_exc()
            add_log_entry(f"Failed to start TFTP server: {str(e)}\n{error_trace}", is_error=True)
            return False

    def _update_tftp_config(self, config, directory):
        """Update the TFTP server configuration with the new directory.
        
        Args:
            config: TFTP config file content
            directory: Directory to serve files from
        
        Returns:
            Updated config file content
        """
        add_log_entry(f"Updating TFTP config with directory={directory}")
        lines = config.splitlines()
        updated_lines = []
        
        for line in lines:
            if line.startswith('TFTP_DIRECTORY='):
                updated_lines.append(f'TFTP_DIRECTORY="{directory}"')
                add_log_entry(f"Updated TFTP_DIRECTORY to {directory}")
            elif line.startswith('TFTP_OPTIONS='):
                # Base options - enable file creation and set permissions
                options = '"--secure --create"'
                updated_lines.append(f'TFTP_OPTIONS={options}')
                add_log_entry(f"Updated TFTP_OPTIONS to {options}")
            elif line.startswith('TFTP_ADDRESS='):
                # Always use 0.0.0.0 to listen on all interfaces
                updated_lines.append('TFTP_ADDRESS="0.0.0.0:69"')
                add_log_entry(f"Updated TFTP_ADDRESS to 0.0.0.0:69")
            elif line.startswith('TFTP_USERNAME='):
                # Use default tftp user
                updated_lines.append('TFTP_USERNAME="tftp"')
                add_log_entry(f"Keeping TFTP_USERNAME as tftp")
            else:
                updated_lines.append(line)
        
        # Check if we need to add missing config lines
        if not any(line.startswith('TFTP_OPTIONS=') for line in lines):
            options = '"--secure --create"'
            updated_lines.append(f'TFTP_OPTIONS={options}')
            add_log_entry(f"Added missing TFTP_OPTIONS={options}")
            
        if not any(line.startswith('TFTP_ADDRESS=') for line in lines):
            updated_lines.append('TFTP_ADDRESS="0.0.0.0:69"')
            add_log_entry(f"Added missing TFTP_ADDRESS=0.0.0.0:69")
        
        if not any(line.startswith('TFTP_USERNAME=') for line in lines):
            updated_lines.append('TFTP_USERNAME="tftp"')
            add_log_entry(f"Added missing TFTP_USERNAME=tftp")
        
        return '\n'.join(updated_lines)

    def stop_server(self):
        """Stop the TFTP server."""
        try:
            # Stop the TFTP server
            add_log_entry("Stopping TFTP server...")
            stop_cmd = ['sudo', 'systemctl', 'stop', 'tftpd-hpa']
            add_log_entry(f"Running command: {' '.join(stop_cmd)}")
            stop_result = subprocess.run(stop_cmd, capture_output=True, check=True, text=True)
            add_log_entry(f"Stop command output - stdout: {stop_result.stdout}, stderr: {stop_result.stderr}")
            
            # Verify the service is actually stopped
            is_active = self.get_server_status()
            add_log_entry(f"TFTP service active status after stop: {is_active}")
            
            if not is_active:
                add_log_entry("TFTP server stopped successfully")
                return True
            else:
                add_log_entry("TFTP service stop command succeeded but service is still active", is_error=True)
                return False
                
        except Exception as e:
            error_trace = traceback.format_exc()
            add_log_entry(f"Failed to stop TFTP server: {str(e)}\n{error_trace}", is_error=True)
            return False
    
    def download_file(self, server, filename, target_dir=''):
        """Download a file from a remote TFTP server."""
        target_path = os.path.join(self.transfer_dir, target_dir.lstrip('/'))
        
        add_log_entry(f"TFTP download: server={server}, filename={filename}, target_dir={target_dir}")
        add_log_entry(f"Full target path: {target_path}")
        
        # Ensure target directory exists
        os.makedirs(target_path, exist_ok=True)
        add_log_entry(f"Ensured target directory exists")
        
        try:
            # Save current directory
            current_dir = os.getcwd()
            add_log_entry(f"Current working directory: {current_dir}")
            
            # Change to target directory
            add_log_entry(f"Changing to target directory: {target_path}")
            os.chdir(target_path)
            
            # Run TFTP client command
            cmd = ['tftp', server, '-c', 'get', filename]
            add_log_entry(f"Running TFTP download command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            add_log_entry(f"TFTP download result - stdout: {result.stdout}, stderr: {result.stderr}")
            
            # Check if file was downloaded
            expected_file = os.path.join(target_path, filename)
            if os.path.exists(expected_file):
                add_log_entry(f"Downloaded file exists at {expected_file}, size: {os.path.getsize(expected_file)} bytes")
            else:
                add_log_entry(f"Warning: Command succeeded but file not found at {expected_file}", is_error=True)
            
            # Return to original directory
            add_log_entry(f"Changing back to original directory: {current_dir}")
            os.chdir(current_dir)
            
            add_log_entry(f"Downloaded {filename} from {server} via TFTP")
            return True
        except subprocess.CalledProcessError as e:
            add_log_entry(f"TFTP download failed: stdout: {e.stdout}, stderr: {e.stderr}", is_error=True)
            # Return to original directory
            os.chdir(current_dir)
            return False
        except Exception as e:
            error_trace = traceback.format_exc()
            add_log_entry(f"TFTP error: {str(e)}\n{error_trace}", is_error=True)
            # Return to original directory in case of any error
            if 'current_dir' in locals():
                os.chdir(current_dir)
            return False
    
    def upload_file(self, server, filename, source_dir=''):
        """Upload a file to a remote TFTP server."""
        source_path = os.path.join(self.transfer_dir, source_dir.lstrip('/'))
        file_path = os.path.join(source_path, filename)
        
        add_log_entry(f"TFTP upload: server={server}, filename={filename}, source_dir={source_dir}")
        add_log_entry(f"Full source file path: {file_path}")
        
        if not os.path.exists(file_path):
            add_log_entry(f"File not found: {file_path}", is_error=True)
            return False
        
        add_log_entry(f"File exists, size: {os.path.getsize(file_path)} bytes")
        
        try:
            # Save current directory
            current_dir = os.getcwd()
            add_log_entry(f"Current working directory: {current_dir}")
            
            # Change to source directory
            add_log_entry(f"Changing to source directory: {source_path}")
            os.chdir(source_path)
            
            # Run TFTP client command
            cmd = ['tftp', server, '-c', 'put', filename]
            add_log_entry(f"Running TFTP upload command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            add_log_entry(f"TFTP upload result - stdout: {result.stdout}, stderr: {result.stderr}")
            
            # Return to original directory
            add_log_entry(f"Changing back to original directory: {current_dir}")
            os.chdir(current_dir)
            
            add_log_entry(f"Uploaded {filename} to {server} via TFTP")
            return True
        except subprocess.CalledProcessError as e:
            add_log_entry(f"TFTP upload failed: stdout: {e.stdout}, stderr: {e.stderr}", is_error=True)
            # Return to original directory
            os.chdir(current_dir)
            return False
        except Exception as e:
            error_trace = traceback.format_exc()
            add_log_entry(f"TFTP error: {str(e)}\n{error_trace}", is_error=True)
            # Return to original directory in case of any error
            if 'current_dir' in locals():
                os.chdir(current_dir)
            return False 