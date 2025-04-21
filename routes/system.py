from flask import Blueprint, jsonify, request, render_template
import subprocess
import platform
import os
import re

# Import modules with try-except to catch import errors
try:
    from modules.system import get_usb_info, get_service_status, restart_service, test_serial_device
except ImportError as e:
    print(f"Error importing system module: {e}")
    # Fallback functions
    def get_usb_info():
        return ["USB info unavailable"]
    
    def get_service_status():
        # Define common services to check when module is not available
        common_services = [
            'ssh', 'sshd', 'dhcpcd', 'dnsmasq', 'hostapd', 'networking',
            'nginx', 'apache2', 'lighttpd', 'avahi-daemon', 'bluetooth',
            'ntp', 'systemd-timesyncd', 'rsyslog', 'cron', 'tftpd-hpa',
            'smbd', 'nmbd', 'openvpn', 'pihole-FTL', 'ufw', 'firewalld'
        ]
        
        services = []
        for service in common_services:
            try:
                # Check if service exists and get status
                result = subprocess.run(
                    f"systemctl is-active {service}",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 or "inactive" in result.stdout:
                    status = result.stdout.strip()
                    services.append({
                        "name": service,
                        "status": status,
                        "details": f"Service: {service}"
                    })
            except:
                pass
        
        # Add a system service as fallback if nothing found
        if not services:
            services = [{"name": "system", "status": "unknown", "details": "Service details unavailable"}]
        
        return services
    
    def restart_service(service):
        return False, f"Unable to restart {service}, service module not available"

try:
    from modules.network import get_interfaces, get_listening_ports, check_internet_connectivity
except ImportError as e:
    print(f"Error importing network module: {e}")
    # Fallback functions
    def get_interfaces():
        return [{"name": "eth0", "addr": "Not available", "gateway": "Not available", "state": "UNKNOWN", "details": "Interface details unavailable"}]
    def get_listening_ports():
        return []

try:
    from modules.logging import log_entries, add_log_entry
except ImportError as e:
    print(f"Error importing logging module: {e}")
    # Fallback functions
    log_entries = []
    def add_log_entry(message, is_error=False):
        print(f"Log: {'ERROR' if is_error else 'INFO'} - {message}")

bp = Blueprint('system', __name__)

def get_system_info():
    """Get basic system information like OS, uptime, load, CPU, memory, temperature"""
    system_info = {}
    
    # Helper function to safely run commands with a timeout
    def run_command(cmd, default="Unknown"):
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=2  # 2 second timeout
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return default
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            print(f"Command failed: {cmd} - {str(e)}")
            return default
    
    # Get OS information - simpler approach
    try:
        # Use a simpler command that's less likely to fail
        os_info = run_command("cat /etc/os-release | grep PRETTY_NAME")
        if os_info and '=' in os_info:
            os_info = os_info.split('=')[1].replace('"', '')
            system_info['os'] = os_info
        else:
            system_info['os'] = platform.platform()
    except Exception as e:
        print(f"OS info error: {str(e)}")
        system_info['os'] = "Raspberry Pi OS"
    
    # Get uptime - simplified
    try:
        uptime_output = run_command("uptime -p")
        if uptime_output and uptime_output != "Unknown":
            system_info['uptime'] = uptime_output.replace("up ", "")
        else:
            # Fallback to proc
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                days = int(uptime_seconds / 86400)
                hours = int((uptime_seconds % 86400) / 3600)
                minutes = int((uptime_seconds % 3600) / 60)
                system_info['uptime'] = f"{days}d {hours}h {minutes}m"
    except Exception as e:
        print(f"Uptime error: {str(e)}")
        system_info['uptime'] = "Unknown"
    
    # Get load average - simplified
    try:
        load_avg = run_command("uptime")
        if "load average:" in load_avg:
            load_avg = load_avg.split("load average:")[1].strip()
            system_info['load_avg'] = load_avg
        else:
            # Try to read directly from proc
            with open('/proc/loadavg', 'r') as f:
                load = f.readline().split()[:3]
                system_info['load_avg'] = f"{load[0]} {load[1]} {load[2]}"
    except Exception as e:
        print(f"Load average error: {str(e)}")
        system_info['load_avg'] = "Unknown"
    
    # Get CPU usage - more compatible approach
    try:
        # Try simpler command first
        cpu_usage = run_command("top -bn1 | grep '%Cpu' | awk '{print $2}'")
        if cpu_usage and cpu_usage != "Unknown":
            system_info['cpu'] = f"{cpu_usage}%"
        else:
            # Alternative method
            cpu_usage = run_command("vmstat 1 2 | tail -1 | awk '{print 100-$15}'")
            if cpu_usage and cpu_usage != "Unknown":
                system_info['cpu'] = f"{cpu_usage}%"
            else:
                system_info['cpu'] = "Unknown"
    except Exception as e:
        print(f"CPU error: {str(e)}")
        system_info['cpu'] = "Unknown"
    
    # Get memory usage - more compatible
    try:
        # Try to get memory info directly from proc
        with open('/proc/meminfo', 'r') as f:
            mem_info = f.readlines()
            total_mem = None
            free_mem = None
            
            for line in mem_info:
                if "MemTotal" in line:
                    total_mem = int(line.split()[1]) // 1024  # Convert to MB
                elif "MemAvailable" in line:
                    free_mem = int(line.split()[1]) // 1024   # Convert to MB
            
            if total_mem and free_mem:
                used_mem = total_mem - free_mem
                percent = round((used_mem / total_mem) * 100)
                system_info['memory'] = f"{used_mem}MB / {total_mem}MB ({percent}%)"
            else:
                raise Exception("Could not parse memory info")
    except Exception as e:
        try:
            # Fallback to free command
            memory_info = run_command("free -m | grep Mem:")
            if memory_info and memory_info != "Unknown":
                parts = memory_info.split()
                if len(parts) >= 3:  # Make sure we have enough parts
                    total = int(parts[1])
                    used = int(parts[2])
                    if total > 0:  # Avoid division by zero
                        percent = round((used / total) * 100)
                        system_info['memory'] = f"{used}MB / {total}MB ({percent}%)"
                    else:
                        system_info['memory'] = "Unknown"
                else:
                    system_info['memory'] = "Unknown"
            else:
                system_info['memory'] = "Unknown"
        except Exception as ex:
            print(f"Memory error: {str(ex)}")
            system_info['memory'] = "Unknown"
    
    # Get temperature - multiple methods for Raspberry Pi
    try:
        # Method 1: vcgencmd (Raspberry Pi specific)
        temp = run_command("vcgencmd measure_temp")
        if temp and temp != "Unknown" and "temp=" in temp:
            system_info['temperature'] = temp.replace("temp=", "")
        else:
            # Method 2: Check thermal zone
            if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = float(f.read().strip()) / 1000
                    system_info['temperature'] = f"{temp}°C"
            else:
                # Method 3: Try sensors command
                temp_output = run_command("sensors | grep temp1 | awk '{print $2}'")
                if temp_output and temp_output != "Unknown":
                    system_info['temperature'] = temp_output
                else:
                    system_info['temperature'] = "N/A"
    except Exception as e:
        print(f"Temperature error: {str(e)}")
        system_info['temperature'] = "N/A"
    
    print(f"Collected system info: {system_info}")  # Debug log
    return system_info

def get_storage_details():
    """Get storage information from the df command"""
    storage_info = []
    
    # Define the run_command helper if it's not already defined in this scope
    def run_command(cmd, default=""):
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=2  # 2 second timeout
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return default
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            print(f"Command failed: {cmd} - {str(e)}")
            return default
    
    try:
        # Run df command to get disk usage information - skip tmpfs and other virtual filesystems
        output = run_command("df -h -x tmpfs -x devtmpfs")
        if not output:
            raise Exception("df command returned empty output")
            
        lines = output.splitlines()
        
        # Skip the header
        for line in lines[1:]:
            # Handle wrapped lines by checking if line starts with a device path
            if not line.startswith('/'):
                continue
                
            parts = line.split()
            if len(parts) >= 6:
                # Only include real filesystems
                if parts[0].startswith('/dev/') or parts[0].startswith('/'):
                    storage_info.append({
                        'filesystem': parts[0],
                        'size': parts[1],
                        'used': parts[2],
                        'avail': parts[3],
                        'use': parts[4],
                        'mount': parts[5]
                    })
    except Exception as e:
        print(f"Error in first storage method: {str(e)}")
        # Fallback to more basic command if the first one fails
        try:
            # Try a simpler version of df
            output = run_command("df -h | grep '/dev/'")
            if not output:
                raise Exception("grep for /dev/ returned empty")
                
            lines = output.splitlines()
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 6:
                    storage_info.append({
                        'filesystem': parts[0],
                        'size': parts[1],
                        'used': parts[2],
                        'avail': parts[3],
                        'use': parts[4],
                        'mount': parts[5]
                    })
        except Exception as ex:
            print(f"Error in fallback storage method: {str(ex)}")
            # Fallback to very basic approach
            try:
                output = run_command("mount | grep '/dev/'")
                if output:
                    # Try to extract just the mount points
                    filesystems = []
                    for line in output.splitlines():
                        parts = line.split()
                        if len(parts) >= 3:
                            filesystems.append({
                                'filesystem': parts[0],
                                'size': 'N/A',
                                'used': 'N/A',
                                'avail': 'N/A',
                                'use': 'N/A',
                                'mount': parts[2]
                            })
                    
                    if filesystems:
                        storage_info = filesystems
                    else:
                        # No filesystems found, use placeholder
                        add_log_entry("Could not get any filesystem information", is_error=True)
                        storage_info = [{
                            'filesystem': 'root',
                            'size': 'Unknown',
                            'used': 'Unknown',
                            'avail': 'Unknown',
                            'use': 'Unknown',
                            'mount': '/'
                        }]
                else:
                    # No mount info, use placeholder
                    storage_info = [{
                        'filesystem': 'rootfs',
                        'size': 'Unknown',
                        'used': 'Unknown',
                        'avail': 'Unknown',
                        'use': 'Unknown',
                        'mount': '/'
                    }]
            except Exception as e:
                print(f"Final storage fallback error: {str(e)}")
                storage_info = [{
                    'filesystem': 'Error retrieving storage info',
                    'size': 'N/A',
                    'used': 'N/A',
                    'avail': 'N/A',
                    'use': 'N/A', 
                    'mount': 'N/A'
                }]
    
    # If we still have no storage info, add a placeholder
    if not storage_info:
        storage_info = [{
            'filesystem': 'No storage information available',
            'size': 'N/A',
            'used': 'N/A',
            'avail': 'N/A',
            'use': 'N/A', 
            'mount': 'N/A'
        }]
    
    print(f"Collected storage info: {storage_info}")  # Debug log
    return storage_info

def get_serial_devices():
    """Get information about connected serial devices"""
    serial_devices = []
    
    # Define the run_command helper if it's not already defined in this scope
    def run_command(cmd, default=""):
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=2  # 2 second timeout
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return default
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            print(f"Command failed: {cmd} - {str(e)}")
            return default
    
    try:
        # Check /dev for serial devices
        output = run_command("ls -l /dev/tty*")
        if output:
            # Look for common serial devices
            for line in output.splitlines():
                if any(device in line for device in ["ttyUSB", "ttyACM", "ttyS", "ttyAMA"]):
                    parts = line.split()
                    if len(parts) >= 10:
                        device_path = parts[-1]  # Last part is the device path
                        
                        # Get additional device info if available
                        device_info = run_command(f"udevadm info --name={device_path} --attribute-walk | grep -i 'manufacturer\\|product\\|serial'")
                        
                        manufacturer = "Unknown"
                        product = "Serial Device"
                        serial = "Unknown"
                        
                        # Parse the udevadm output
                        if device_info:
                            for info_line in device_info.splitlines():
                                if "manufacturer" in info_line.lower():
                                    manufacturer_match = info_line.split("==")
                                    if len(manufacturer_match) > 1:
                                        manufacturer = manufacturer_match[1].strip().strip('"')
                                elif "product" in info_line.lower():
                                    product_match = info_line.split("==")
                                    if len(product_match) > 1:
                                        product = product_match[1].strip().strip('"')
                                elif "serial" in info_line.lower():
                                    serial_match = info_line.split("==")
                                    if len(serial_match) > 1:
                                        serial = serial_match[1].strip().strip('"')
                        
                        # Add device to the list
                        serial_devices.append({
                            "path": device_path,
                            "manufacturer": manufacturer,
                            "product": product,
                            "serial": serial
                        })
    except Exception as e:
        print(f"Error detecting serial devices: {str(e)}")
        # Add a placeholder in case of error
        serial_devices = [{
            "path": "Error detecting devices",
            "manufacturer": "Unknown",
            "product": "Error",
            "serial": "Unknown"
        }]
    
    # If no devices were found, add a message
    if not serial_devices:
        serial_devices = [{
            "path": "No serial devices found",
            "manufacturer": "N/A",
            "product": "N/A",
            "serial": "N/A"
        }]
    
    print(f"Detected serial devices: {serial_devices}")  # Debug log
    return serial_devices

def get_available_services():
    """Improved function to detect available services on Raspberry Pi"""
    # Helper function to safely run commands
    def run_command(cmd, default=""):
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return default
        except Exception as e:
            print(f"Command failed: {cmd} - {str(e)}")
            return default

    # List of potential services commonly found on Raspberry Pi
    potential_services = [
        # System services
        'ssh', 'sshd', 'systemd-journald', 'systemd-logind', 'systemd-timesyncd',
        'dbus', 'dhcpcd', 'rsyslog', 'cron', 'networking', 'ntp',
        
        # Network services
        'dnsmasq', 'hostapd', 'avahi-daemon', 'bluetooth', 'wpa_supplicant',
        
        # Web services
        'nginx', 'apache2', 'lighttpd', 
        
        # File sharing
        'smbd', 'nmbd', 'proftpd', 'vsftpd', 'tftpd-hpa',
        
        # VPN and network tools
        'openvpn', 'wireguard', 'pihole-FTL', 'unbound',
        
        # Firewalls and security
        'ufw', 'firewalld', 'fail2ban',
        
        # Databases
        'mariadb', 'postgresql', 'influxdb', 'mongodb',
        
        # Containers and virtualization
        'docker', 'containerd', 'kubelet', 'libvirtd',
        
        # IoT and home automation
        'mosquitto', 'zigbee2mqtt', 'homeassistant', 'homebridge',
        'node-red'
    ]
    
    available_services = []
    
    # First, try to get a list of active services
    active_services = run_command("systemctl list-units --type=service --state=active,running | grep '\.service' | awk '{print $1}'")
    if active_services:
        for line in active_services.splitlines():
            service_name = line.replace('.service', '')
            if service_name and service_name not in available_services:
                available_services.append(service_name)
    
    # Then check specific services of interest that might not be active
    for service in potential_services:
        if service not in available_services:
            # Check if the service exists in systemd
            exists = run_command(f"systemctl list-unit-files {service}.service 2>/dev/null | grep {service}.service")
            if exists:
                available_services.append(service)
    
    # Ensure we have at least one service
    if not available_services:
        print("No services detected, adding system as a fallback")
        available_services.append('system')
    
    return available_services

def get_service_status():
    """Get the status of system services"""
    services = []
    available_services = get_available_services()
    
    # Helper function to safely run commands
    def run_command(cmd, default=""):
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=2
            )
            return result.stdout.strip(), result.returncode
        except Exception as e:
            print(f"Command failed: {cmd} - {str(e)}")
            return default, -1
    
    for service_name in available_services:
        try:
            # Get service status
            status_output, status_code = run_command(f"systemctl is-active {service_name}")
            status = status_output if status_output else "unknown"
            
            # Get service details
            details_output, _ = run_command(f"systemctl status {service_name} | head -3")
            details = details_output if details_output else f"Service: {service_name}"
            
            services.append({
                'name': service_name,
                'status': status,
                'details': details
            })
        except Exception as e:
            print(f"Error getting status for {service_name}: {str(e)}")
            
    # Sort services by status (active first) then by name
    services.sort(key=lambda x: (x['status'] != 'active', x['name']))
    
    return services

@bp.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        interfaces=get_interfaces(),
        listening_ports=get_listening_ports(),
        usb_info=get_usb_info(),
        services=get_service_status(),
        logs=log_entries
    )

@bp.route("/restart_service/<service>", methods=["POST"])
def service_restart(service):
    success, message = restart_service(service)
    
    # Return the updated service data along with the status
    updated_data = {
        'services': get_service_status(),
        'success': success, 
        'message': message
    }
    
    return jsonify(updated_data)

@bp.route("/get_storage_info", methods=["GET"])
def storage_info():
    """Endpoint for getting storage information"""
    return jsonify({
        'storage': get_storage_details()
    })

@bp.route("/get_serial_devices", methods=["GET"])
def serial_devices():
    """Endpoint for getting serial device information"""
    return jsonify({
        'devices': get_serial_devices()
    })

@bp.route("/get_updates", methods=["GET"])
def get_updates():
    """Endpoint for polling updated data"""
    return jsonify({
        'system_info': get_system_info(),
        'interfaces': get_interfaces(),
        'services': get_service_status(),
        'serial_devices': get_serial_devices(),
        'logs': log_entries
    })

@bp.route("/get_interface_details/<iface>", methods=["GET"])
def interface_details(iface):
    """Endpoint for getting detailed information about a specific network interface"""
    try:
        # Define the run_command helper
        def run_command(cmd, default=""):
            try:
                result = subprocess.run(
                    cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=5  # Longer timeout for detailed info
                )
                if result.returncode == 0:
                    return result.stdout.strip()
                return default
            except Exception as e:
                print(f"Command failed: {cmd} - {str(e)}")
                return default
        
        details = {}
        
        # Get interface name and ensure it exists
        if not iface or iface.strip() == "":
            return jsonify({"success": False, "message": "No interface specified"})
        
        details["name"] = iface
        
        # Get MAC address
        mac_address = run_command(f"cat /sys/class/net/{iface}/address 2>/dev/null")
        details["mac_address"] = mac_address if mac_address else "Unknown"
        
        # Check internet connectivity
        try:
            details["has_internet"] = check_internet_connectivity(iface)
        except ImportError:
            # Fallback if function not available
            ping_result = run_command(f"ping -I {iface} -c 1 -W 2 8.8.8.8 > /dev/null 2>&1 && echo success || echo failed")
            details["has_internet"] = ping_result == "success"
        
        # Get current IP, netmask and gateway
        try:
            # Get IP and netmask
            ip_info = run_command(f"ip addr show {iface}")
            ip_match = None
            netmask = None
            
            if ip_info:
                # Look for inet line with IP address
                inet_match = re.search(r"inet\s+([0-9\.]+)\/([0-9]+)", ip_info)
                if inet_match:
                    ip_match = inet_match.group(1)
                    # Convert CIDR to netmask
                    cidr = int(inet_match.group(2))
                    netmask = '.'.join([str((0xFFFFFFFF << (32 - cidr) >> i) & 0xFF) for i in [24, 16, 8, 0]])
            
            details["ip"] = ip_match if ip_match else "Not assigned"
            details["netmask"] = netmask if netmask else "Unknown"
            
            # Get gateway
            gateway = run_command(f"ip route show default | grep {iface} | awk '{{print $3}}'")
            details["gateway"] = gateway if gateway else "Not configured"
            
            # Get DNS servers from resolv.conf
            dns_servers = run_command("cat /etc/resolv.conf | grep nameserver | awk '{print $2}' | tr '\n' ' '")
            details["dns"] = dns_servers.strip() if dns_servers else "Not configured"
            
            # Get MTU
            mtu = run_command(f"cat /sys/class/net/{iface}/mtu 2>/dev/null")
            details["mtu"] = mtu if mtu else "Unknown"
            
            # Get interface statistics
            rx_bytes = run_command(f"cat /sys/class/net/{iface}/statistics/rx_bytes 2>/dev/null")
            tx_bytes = run_command(f"cat /sys/class/net/{iface}/statistics/tx_bytes 2>/dev/null")
            rx_packets = run_command(f"cat /sys/class/net/{iface}/statistics/rx_packets 2>/dev/null")
            tx_packets = run_command(f"cat /sys/class/net/{iface}/statistics/tx_packets 2>/dev/null")
            rx_errors = run_command(f"cat /sys/class/net/{iface}/statistics/rx_errors 2>/dev/null")
            tx_errors = run_command(f"cat /sys/class/net/{iface}/statistics/tx_errors 2>/dev/null")
            
            # Format byte values to human-readable
            if rx_bytes and rx_bytes.isdigit():
                rx_bytes = format_bytes(int(rx_bytes))
            if tx_bytes and tx_bytes.isdigit():
                tx_bytes = format_bytes(int(tx_bytes))
                
            details["stats"] = {
                "rx_bytes": rx_bytes if rx_bytes else "0",
                "tx_bytes": tx_bytes if tx_bytes else "0",
                "rx_packets": rx_packets if rx_packets else "0",
                "tx_packets": tx_packets if tx_packets else "0",
                "errors": f"{rx_errors if rx_errors else '0'} RX / {tx_errors if tx_errors else '0'} TX"
            }
            
            # Get raw interface information from ifconfig and ip commands
            ifconfig_output = run_command(f"ifconfig {iface} 2>/dev/null")
            ip_output = run_command(f"ip addr show {iface} 2>/dev/null")
            
            raw_info = ""
            if ifconfig_output:
                raw_info += f"ifconfig output:\n{ifconfig_output}\n\n"
            if ip_output:
                raw_info += f"ip addr output:\n{ip_output}\n\n"
                
            details["raw_info"] = raw_info if raw_info else "No raw information available"
            
            # Check if interface is using DHCP
            dhcp_check = run_command(f"grep -l {iface} /var/lib/dhcp/dhclient.* 2>/dev/null || grep -l {iface} /var/lib/dhcpcd/* 2>/dev/null")
            details["is_dhcp"] = True if dhcp_check else False
            
        except Exception as e:
            print(f"Error getting interface details: {str(e)}")
            details["error"] = str(e)
        
        return jsonify({"success": True, "details": details})
    except Exception as e:
        print(f"Exception in interface_details: {str(e)}")
        return jsonify({"success": False, "message": str(e)})

def format_bytes(bytes):
    """Format bytes into a human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} PB"

@bp.route("/test_serial_device", methods=["POST"])
def test_serial():
    """Test if a serial device is accessible and working"""
    try:
        data = request.json
        device_path = data.get('device')
        baudrate = data.get('baudrate', 9600)
        
        if not device_path:
            return jsonify({"success": False, "message": "Device path is required"}), 400
        
        success, message = test_serial_device(device_path, baudrate)
        return jsonify({"success": success, "message": message})
    except Exception as e:
        error_msg = f"Error testing serial device: {str(e)}"
        add_log_entry(error_msg, is_error=True)
        return jsonify({"success": False, "message": error_msg}), 500 