import subprocess
import os
from .logging import add_log_entry

def get_usb_info():
    try:
        return subprocess.check_output("lsusb", shell=True).decode().strip().splitlines()
    except:
        return ["Error fetching USB info"]

def test_serial_device(device_path, baudrate=9600):
    """
    Test if a serial device is accessible
    Parameters:
        device_path: Path to the serial device (e.g., /dev/ttyUSB0)
        baudrate: Baud rate to test with (default: 9600)
    Returns:
        (success, message) tuple
    """
    try:
        add_log_entry(f"Testing serial device {device_path} at {baudrate} baud")
        
        # Check if device exists
        if not os.path.exists(device_path):
            return False, f"Device {device_path} not found"
        
        # Check device permissions
        permissions = subprocess.check_output(f"ls -l {device_path}", shell=True).decode().strip()
        add_log_entry(f"Device permissions: {permissions}")
        
        # Try to open the device using stty
        try:
            # Set the baud rate and other basic parameters
            subprocess.check_output(f"stty -F {device_path} {baudrate} cs8 -cstopb -parenb", 
                                   shell=True, stderr=subprocess.STDOUT, timeout=2)
            
            # If we got here, the device is accessible
            return True, f"Successfully opened {device_path} at {baudrate} baud"
        except subprocess.CalledProcessError as e:
            return False, f"Error opening device: {e.output.decode()}"
        
    except Exception as e:
        error_msg = f"Error testing serial device {device_path}: {str(e)}"
        add_log_entry(error_msg, is_error=True)
        return False, error_msg

def get_available_services():
    # List of potential services to check
    potential_services = [
        'ssh', 
        'vncserver-x11-serviced', 
        'realvnc-vnc-server', 
        'xrdp', 
        'dhcpcd', 
        'dnsmasq', 
        'hostapd',
        'nginx',
        'apache2',
        'anydesk',
        'webpage'  # Our own service
    ]
    
    available_services = []
    
    for service in potential_services:
        try:
            # Check if the service exists in systemd
            output = subprocess.check_output(f"systemctl list-unit-files {service}.service", shell=True, stderr=subprocess.DEVNULL).decode().strip()
            if service in output:
                available_services.append(service)
        except subprocess.CalledProcessError:
            # Service might not exist, skip it
            continue
            
    return available_services

def get_service_status():
    available_services = get_available_services()
    
    result = []
    for service_name in available_services:
        try:
            status = subprocess.check_output(f"systemctl is-active {service_name}", shell=True).decode().strip()
            details = subprocess.check_output(f"systemctl status {service_name}", shell=True).decode().strip()
            
            # Get additional service information
            try:
                # Get service enabled status
                enabled_status = subprocess.check_output(f"systemctl is-enabled {service_name}", shell=True).decode().strip()
            except:
                enabled_status = "unknown"
                
            # Get service uptime/memory info from status
            memory_usage = "N/A"
            pid = "N/A"
            try:
                # Extract PID and memory from status output
                for line in details.split('\n'):
                    if 'Main PID:' in line:
                        pid = line.split('Main PID:')[1].split('(')[0].strip()
                    elif 'Memory:' in line:
                        memory_usage = line.split('Memory:')[1].strip()
            except:
                pass
                
        except:
            status = "unknown"
            details = "Could not fetch details"
            enabled_status = "unknown"
            memory_usage = "N/A"
            pid = "N/A"
            
        result.append({
            'name': service_name,
            'status': status,
            'details': details,
            'enabled': enabled_status,
            'memory': memory_usage,
            'pid': pid
        })
        
    return result

def get_service_details(service_name):
    """Get detailed information about a specific service"""
    try:
        # Get basic status information
        status = subprocess.check_output(f"systemctl is-active {service_name}", shell=True).decode().strip()
        enabled = subprocess.check_output(f"systemctl is-enabled {service_name}", shell=True).decode().strip()
        full_status = subprocess.check_output(f"systemctl status {service_name}", shell=True).decode().strip()
        
        # Get service unit file information
        try:
            unit_info = subprocess.check_output(f"systemctl show {service_name} --no-page", shell=True).decode().strip()
        except:
            unit_info = "Unit information unavailable"
        
        # Get recent logs
        try:
            logs = subprocess.check_output(f"journalctl -u {service_name} -n 20 --no-pager", shell=True).decode().strip()
        except:
            logs = "Logs unavailable"
            
        # Parse unit info for useful details
        parsed_info = {}
        for line in unit_info.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                if key in ['ExecStart', 'ExecReload', 'ExecStop', 'User', 'Group', 'WorkingDirectory', 'Environment']:
                    parsed_info[key] = value
        
        return {
            'name': service_name,
            'status': status,
            'enabled': enabled,
            'full_status': full_status,
            'unit_info': parsed_info,
            'logs': logs
        }
    except Exception as e:
        return {
            'name': service_name,
            'status': 'unknown',
            'enabled': 'unknown', 
            'full_status': f'Error: {str(e)}',
            'unit_info': {},
            'logs': 'Error retrieving logs'
        }

def restart_service(service_name):
    try:
        # Validate if the service exists first
        available_services = get_available_services()
        if service_name not in available_services:
            add_log_entry(f"Service {service_name} does not exist", is_error=True)
            return False, f"Service {service_name} does not exist on this system."
            
        # Execute the restart command
        add_log_entry(f"Restarting service {service_name}")
        output = subprocess.check_output(f"sudo systemctl restart {service_name}", shell=True, stderr=subprocess.STDOUT).decode().strip()
        return True, f"Service {service_name} restarted successfully."
    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to restart {service_name}: {e.output.decode()}"
        add_log_entry(error_msg, is_error=True)
        return False, error_msg
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        add_log_entry(error_msg, is_error=True)
        return False, error_msg 