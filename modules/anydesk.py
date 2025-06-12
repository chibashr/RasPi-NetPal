import subprocess
import os
import re
from .logging import add_log_entry

def is_anydesk_installed():
    """Check if AnyDesk is installed on the system"""
    try:
        # Check if anydesk command exists
        result = subprocess.run("which anydesk", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        
        # Also check if it's installed as a service
        result = subprocess.run("systemctl list-unit-files anydesk.service", shell=True, capture_output=True, text=True)
        return "anydesk.service" in result.stdout
    except:
        return False

def get_anydesk_id():
    """Get the AnyDesk ID"""
    try:
        if not is_anydesk_installed():
            return None
        
        # Try getting ID from service
        result = subprocess.run("anydesk --get-id", shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        
        # Try alternative method - look in config files
        config_paths = [
            "/etc/anydesk/service.conf",
            "/var/lib/anydesk/service.conf",
            "~/.anydesk/service.conf"
        ]
        
        for config_path in config_paths:
            expanded_path = os.path.expanduser(config_path)
            if os.path.exists(expanded_path):
                try:
                    with open(expanded_path, 'r') as f:
                        content = f.read()
                        # Look for ID in config
                        id_match = re.search(r'ad\.anynet\.id=(\d+)', content)
                        if id_match:
                            return id_match.group(1)
                except:
                    continue
        
        return "Unable to retrieve"
    except Exception as e:
        add_log_entry(f"Error getting AnyDesk ID: {str(e)}", is_error=True)
        return "Error retrieving ID"

def get_anydesk_status():
    """Get comprehensive AnyDesk status information"""
    status = {
        'installed': is_anydesk_installed(),
        'service_status': 'unknown',
        'service_enabled': False,
        'anydesk_id': None,
        'version': 'Unknown',
        'connection_status': 'Unknown',
        'last_connection': 'Never',
        'dependencies_ok': True,
        'dependency_issues': []
    }
    
    if not status['installed']:
        return status
    
    try:
        # Get service status
        result = subprocess.run("systemctl is-active anydesk", shell=True, capture_output=True, text=True)
        status['service_status'] = result.stdout.strip()
        
        # Get enabled status
        result = subprocess.run("systemctl is-enabled anydesk", shell=True, capture_output=True, text=True)
        status['service_enabled'] = result.stdout.strip() == 'enabled'
        
        # Get AnyDesk ID
        status['anydesk_id'] = get_anydesk_id()
        
        # Get version
        result = subprocess.run("anydesk --version", shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_match = re.search(r'anydesk\s+(\S+)', result.stdout, re.IGNORECASE)
            if version_match:
                status['version'] = version_match.group(1)
        
        # Check dependencies
        status['dependencies_ok'], status['dependency_issues'] = check_anydesk_dependencies()
        
        # Get connection info (if available)
        try:
            # Check if AnyDesk is accessible
            result = subprocess.run("anydesk --get-status", shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                status['connection_status'] = 'Ready' if 'ready' in result.stdout.lower() else 'Unknown'
        except:
            pass
            
    except Exception as e:
        add_log_entry(f"Error getting AnyDesk status: {str(e)}", is_error=True)
    
    return status

def check_anydesk_dependencies():
    """Check if all AnyDesk dependencies are met"""
    issues = []
    
    # Check internet connectivity
    try:
        result = subprocess.run("ping -c 1 -W 3 8.8.8.8", shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            issues.append("No internet connectivity")
    except:
        issues.append("Cannot test internet connectivity")
    
    # Check if X11 is available (for GUI)
    if not os.environ.get('DISPLAY') and not os.path.exists('/tmp/.X11-unix'):
        # Check if X11 service is running
        try:
            result = subprocess.run("systemctl is-active lightdm", shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                result = subprocess.run("systemctl is-active gdm", shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    issues.append("Display manager not running")
        except:
            issues.append("Cannot check display manager status")
    
    # Check required ports (if firewall is active)
    try:
        result = subprocess.run("systemctl is-active ufw", shell=True, capture_output=True, text=True)
        if result.returncode == 0:  # UFW is active
            # AnyDesk uses dynamic ports, but suggest checking firewall
            issues.append("Firewall is active - ensure AnyDesk ports are allowed")
    except:
        pass
    
    return len(issues) == 0, issues

def set_anydesk_password(password):
    """Set AnyDesk unattended access password"""
    try:
        if not is_anydesk_installed():
            return False, "AnyDesk is not installed"
        
        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters long"
        
        add_log_entry(f"Setting AnyDesk password")
        
        # Set the password
        result = subprocess.run(
            f"echo '{password}' | anydesk --set-password",
            shell=True, 
            capture_output=True, 
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            add_log_entry("AnyDesk password set successfully")
            return True, "Password set successfully"
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            add_log_entry(f"Failed to set AnyDesk password: {error_msg}", is_error=True)
            return False, f"Failed to set password: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, "Timeout setting password"
    except Exception as e:
        error_msg = f"Error setting password: {str(e)}"
        add_log_entry(error_msg, is_error=True)
        return False, error_msg

def install_anydesk():
    """Install AnyDesk on Raspberry Pi"""
    try:
        add_log_entry("Starting AnyDesk installation")
        
        # Download and install AnyDesk for Raspberry Pi
        commands = [
            # Update package list
            "apt-get update",
            # Download AnyDesk GPG key
            "wget -qO - https://keys.anydesk.com/repos/DEB-GPG-KEY | apt-key add -",
            # Add AnyDesk repository
            "echo 'deb http://deb.anydesk.com/ all main' > /etc/apt/sources.list.d/anydesk-stable.list",
            # Update package list again
            "apt-get update",
            # Install AnyDesk
            "apt-get install -y anydesk"
        ]
        
        for i, command in enumerate(commands):
            add_log_entry(f"Installation step {i+1}/{len(commands)}: {command}")
            result = subprocess.run(
                f"sudo {command}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                error_msg = f"Installation failed at step {i+1}: {result.stderr}"
                add_log_entry(error_msg, is_error=True)
                return False, error_msg
        
        # Enable AnyDesk service
        try:
            subprocess.run("sudo systemctl enable anydesk", shell=True, timeout=30)
            subprocess.run("sudo systemctl start anydesk", shell=True, timeout=30)
        except:
            pass  # Service might not exist yet
        
        add_log_entry("AnyDesk installation completed successfully")
        return True, "AnyDesk installed successfully"
        
    except subprocess.TimeoutExpired:
        return False, "Installation timeout - please try again"
    except Exception as e:
        error_msg = f"Installation error: {str(e)}"
        add_log_entry(error_msg, is_error=True)
        return False, error_msg

def restart_anydesk():
    """Restart AnyDesk service"""
    try:
        add_log_entry("Restarting AnyDesk service")
        
        result = subprocess.run(
            "sudo systemctl restart anydesk",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            add_log_entry("AnyDesk service restarted successfully")
            return True, "AnyDesk restarted successfully"
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            add_log_entry(f"Failed to restart AnyDesk: {error_msg}", is_error=True)
            return False, f"Failed to restart: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, "Timeout restarting AnyDesk"
    except Exception as e:
        error_msg = f"Error restarting AnyDesk: {str(e)}"
        add_log_entry(error_msg, is_error=True)
        return False, error_msg

def enable_anydesk_autostart():
    """Enable AnyDesk to start automatically"""
    try:
        result = subprocess.run(
            "sudo systemctl enable anydesk",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            add_log_entry("AnyDesk auto-start enabled")
            return True, "Auto-start enabled"
        else:
            return False, "Failed to enable auto-start"
            
    except Exception as e:
        return False, f"Error enabling auto-start: {str(e)}"

def get_anydesk_logs():
    """Get recent AnyDesk logs"""
    try:
        # Get systemd logs for AnyDesk
        result = subprocess.run(
            "journalctl -u anydesk -n 20 --no-pager",
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return result.stdout
        else:
            return "No logs available"
            
    except:
        return "Error retrieving logs" 