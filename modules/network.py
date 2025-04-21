import subprocess
import re
import os
from .logging import add_log_entry
import time
import threading
from pathlib import Path

def get_usb_serial_devices():
    """
    Detect and identify USB serial devices
    Returns a list of detected USB serial devices with their details
    """
    serial_devices = []
    try:
        # Check for USB serial devices using ls command
        # Common patterns for USB serial devices are /dev/ttyUSB*, /dev/ttyACM*, etc.
        devices_cmd = "ls -l /dev/ttyUSB* /dev/ttyACM* /dev/ttyS* 2>/dev/null || true"
        devices_output = subprocess.check_output(devices_cmd, shell=True).decode().strip().splitlines()
        
        for line in devices_output:
            parts = line.split()
            if len(parts) >= 10:  # ls -l output format has at least 10 parts for a valid entry
                device_path = parts[-1]
                device_name = os.path.basename(device_path)
                
                # Get more details if possible
                details = {}
                
                # Try to get USB device details
                try:
                    # Get the device information using udevadm
                    udev_cmd = f"udevadm info --name={device_path} --query=property"
                    udev_output = subprocess.check_output(udev_cmd, shell=True).decode().strip().splitlines()
                    
                    for prop_line in udev_output:
                        if '=' in prop_line:
                            key, value = prop_line.split('=', 1)
                            if key in ['ID_VENDOR', 'ID_MODEL', 'ID_VENDOR_ID', 'ID_MODEL_ID', 'ID_USB_DRIVER']:
                                details[key] = value
                    
                    # Create a friendly name from vendor and model if available
                    if 'ID_VENDOR' in details and 'ID_MODEL' in details:
                        details['friendly_name'] = f"{details['ID_VENDOR']} {details['ID_MODEL']}"
                    elif 'ID_VENDOR' in details:
                        details['friendly_name'] = details['ID_VENDOR']
                    elif 'ID_MODEL' in details:
                        details['friendly_name'] = details['ID_MODEL']
                    else:
                        details['friendly_name'] = device_name
                except Exception as e:
                    add_log_entry(f"Error getting details for {device_path}: {str(e)}", is_error=True)
                    details['friendly_name'] = device_name
                
                serial_devices.append({
                    'device': device_path,
                    'name': device_name,
                    'details': details
                })
                
                add_log_entry(f"Found USB serial device: {device_path}")
        
        return serial_devices
    except Exception as e:
        add_log_entry(f"Error detecting USB serial devices: {str(e)}", is_error=True)
        return []

def get_usb_network_interfaces():
    """
    Detect and identify USB network interfaces, including tethered phones
    Returns a list of interface names that are connected via USB
    """
    usb_interfaces = []
    try:
        # Check USB devices
        usb_devices = subprocess.check_output("lsusb", shell=True).decode().strip().splitlines()
        
        # List all network interfaces
        interfaces = subprocess.check_output("ls -la /sys/class/net/", shell=True).decode().strip().splitlines()
        for interface_line in interfaces:
            parts = interface_line.split()
            if len(parts) < 9:
                continue
            
            interface_name = parts[-1]
            # Skip loopback and virtual interfaces
            if interface_name == "lo" or interface_name.startswith("."):
                continue
                
            # Check if this is a USB interface by looking for usb in the path
            device_path = subprocess.check_output(f"readlink -f /sys/class/net/{interface_name}", 
                                                shell=True).decode().strip()
            
            if "usb" in device_path:
                usb_interfaces.append(interface_name)
                add_log_entry(f"Found USB network interface: {interface_name}")
                
        return usb_interfaces
    except Exception as e:
        add_log_entry(f"Error detecting USB network interfaces: {str(e)}", is_error=True)
        return []

def check_internet_connectivity(interface):
    """
    Test if an interface has internet connectivity
    Returns True if the interface can reach the internet, False otherwise
    """
    try:
        # Try to ping a reliable host through the specific interface
        # Using Google's DNS (8.8.8.8) as it's generally reliable
        cmd = f"ping -I {interface} -c 1 -W 2 8.8.8.8"
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Return True if ping was successful
        return result.returncode == 0
    except Exception as e:
        add_log_entry(f"Error checking internet connectivity for {interface}: {str(e)}", is_error=True)
        return False

def get_interfaces():
    raw = subprocess.check_output("ip -br addr", shell=True).decode().strip().splitlines()
    interfaces = []
    
    # Get USB interfaces for identification
    usb_interfaces = get_usb_network_interfaces()
    
    for line in raw:
        parts = line.split()
        name = parts[0]
        state = parts[1]
        addr = parts[2] if len(parts) > 2 else "N/A"
        
        # Get detailed info
        try:
            details = subprocess.check_output(f"ip addr show {name}", shell=True).decode().strip()
        except:
            details = "Could not fetch details"
        
        # Get the interface gateway
        gateway = "N/A"
        try:
            routes = subprocess.check_output(f"ip route show dev {name}", shell=True).decode().strip()
            gw_match = re.search(r'default via (\S+)', routes)
            if gw_match:
                gateway = gw_match.group(1)
        except:
            pass
        
        # Check if this is a USB interface
        is_usb = name in usb_interfaces
        interface_type = "usb" if is_usb else "built-in"
        
        # Check if this interface has internet connectivity
        has_internet = False
        if state == "UP" and addr != "N/A":
            has_internet = check_internet_connectivity(name)
            
        interfaces.append({
            'name': name, 
            'state': state, 
            'addr': addr,
            'gateway': gateway,
            'details': details,
            'type': interface_type,
            'has_internet': has_internet
        })
    return interfaces

def get_listening_ports():
    try:
        # Using ss command to get listening ports with process names
        output = subprocess.check_output("ss -tulnp", shell=True).decode().strip().splitlines()
        ports = []
        
        # Skip the header line
        for line in output[1:]:
            parts = line.split()
            if len(parts) >= 5:
                protocol = parts[0].lower()
                addr_port = parts[4].split(':')
                
                # The last part may contain process info
                process = "Unknown"
                if len(parts) > 5:
                    process_info = ' '.join(parts[5:])
                    process_match = re.search(r'users:\(\("([^"]+)"', process_info)
                    if process_match:
                        process = process_match.group(1)
                
                # Handle IPv6 addresses
                if '[' in parts[4]:
                    # IPv6 format
                    addr_match = re.search(r'\[([^\]]+)\]:(\d+)', parts[4])
                    if addr_match:
                        address = addr_match.group(1)
                        port = addr_match.group(2)
                else:
                    # IPv4 format
                    if ':' in parts[4]:
                        address, port = parts[4].rsplit(':', 1)
                    else:
                        address = '*'
                        port = parts[4]
                
                ports.append({
                    'protocol': protocol,
                    'address': address,
                    'port': port,
                    'process': process
                })
        
        return ports
    except Exception as e:
        print(f"Error getting listening ports: {e}")
        return [{'protocol': 'Error', 'address': 'Error', 'port': 'Error', 'process': str(e)}]

def get_interface_config(iface):
    config = {
        'ip': '',
        'netmask': '',
        'gateway': '',
        'static': False
    }
    try:
        if os.path.exists("/etc/dhcpcd.conf"):
            with open("/etc/dhcpcd.conf") as f:
                content = f.read()
                match_ip = re.search(rf"interface {iface}\n\s*static ip_address=(\S+)", content)
                match_gw = re.search(rf"interface {iface}(?:\n[^\n]*)*\n\s*static routers=(\S+)", content)
                match_dns = re.search(rf"interface {iface}(?:\n[^\n]*)*\n\s*static domain_name_servers=(\S+)", content)
                
                # This is a static configuration if we found an ip_address entry
                if match_ip:
                    config['ip'] = match_ip.group(1).split('/')[0]
                    config['netmask'] = match_ip.group(1).split('/')[1]
                    config['static'] = True
                if match_gw:
                    config['gateway'] = match_gw.group(1)
                
                # For debugging
                add_log_entry(f"Debug: Interface {iface} config - static: {config['static']}, ip: {config['ip']}, netmask: {config['netmask']}, gateway: {config['gateway']}")
    except Exception as e:
        add_log_entry(f"Error in get_interface_config for {iface}: {str(e)}", is_error=True)
    return config

def update_interface_config(iface, ip, netmask, gateway, use_static):
    try:
        config_lines = []
        with open("/etc/dhcpcd.conf", "r") as f:
            config_lines = f.readlines()

        # Remove old interface config
        config_lines = [line for line in config_lines if not line.strip().startswith(f"interface {iface}")]
        # Remove static settings that might belong to the interface
        i = 0
        while i < len(config_lines):
            if config_lines[i].strip().startswith("static") and i > 0 and config_lines[i-1].strip().startswith(f"interface {iface}"):
                config_lines.pop(i)
            else:
                i += 1

        if use_static == "yes":
            config_lines += [
                f"\ninterface {iface}\n",
                f"static ip_address={ip}/{netmask}\n",
                f"static routers={gateway}\n",
                f"static domain_name_servers=8.8.8.8 1.1.1.1\n"
            ]

        with open("/etc/dhcpcd.conf", "w") as f:
            f.writelines(config_lines)

        # Log the changes
        log_entry = f"Updated {iface}: {'Static IP ' + ip + '/' + netmask if use_static == 'yes' else 'DHCP'}"
        add_log_entry(log_entry)

        # First, stop dhcpcd to release DHCP leases
        add_log_entry(f"Reconfiguring network for {iface}")
        subprocess.call("sudo systemctl stop dhcpcd", shell=True)
        
        # Directly configure the interface IP if static is requested
        if use_static == "yes":
            # Clear any existing IP addresses
            subprocess.call(f"sudo ip addr flush dev {iface}", shell=True)
            # Set the new IP address
            subprocess.call(f"sudo ip addr add {ip}/{netmask} dev {iface}", shell=True)
            # Set the default gateway if provided
            if gateway:
                subprocess.call(f"sudo ip route add default via {gateway} dev {iface}", shell=True)
        
        # Restart dhcpcd to apply configuration from dhcpcd.conf
        subprocess.call("sudo systemctl start dhcpcd", shell=True)
        import time
        time.sleep(2)
        
        return True, f"Successfully updated {iface} configuration. Changes have been applied."
    except Exception as e:
        add_log_entry(f"Error updating {iface}: {str(e)}", is_error=True)
        return False, f"Error updating interface: {str(e)}"

def release_renew_dhcp(iface):
    """Release and renew DHCP lease for the specified interface"""
    try:
        add_log_entry(f"Releasing and renewing DHCP for {iface}")
        
        # Release DHCP lease
        subprocess.call(f"sudo dhclient -r {iface}", shell=True)
        
        # Bring the interface down and up
        subprocess.call(f"sudo ip link set {iface} down", shell=True)
        import time
        time.sleep(1)
        subprocess.call(f"sudo ip link set {iface} up", shell=True)
        
        # Request new DHCP lease
        subprocess.call(f"sudo dhclient {iface}", shell=True)
        
        time.sleep(2)
        return True, f"Successfully released and renewed DHCP lease for {iface}"
    except Exception as e:
        add_log_entry(f"Error releasing/renewing DHCP for {iface}: {str(e)}", is_error=True)
        return False, f"Error renewing DHCP: {str(e)}"

def cycle_interface(iface):
    """Cycle (down/up) a network interface"""
    try:
        add_log_entry(f"Cycling interface {iface} down and up")
        
        # Check current state
        current_state = subprocess.check_output(f"ip link show {iface}", shell=True).decode().strip()
        was_up = "state UP" in current_state
        
        # Bring interface down
        add_log_entry(f"Setting {iface} down")
        subprocess.call(f"sudo ip link set {iface} down", shell=True)
        
        # Small delay to ensure it's processed
        import time
        time.sleep(1)
        
        # Bring interface back up
        add_log_entry(f"Setting {iface} up")
        subprocess.call(f"sudo ip link set {iface} up", shell=True)
        
        # If this was a DHCP interface, renew lease
        interface_config = get_interface_config(iface)
        if not interface_config['static'] and was_up:
            add_log_entry(f"Renewing DHCP lease for {iface}")
            subprocess.call(f"sudo dhclient {iface}", shell=True)
        
        # Wait for the interface to stabilize
        time.sleep(2)
        
        return True, f"Successfully cycled {iface} interface"
    except Exception as e:
        add_log_entry(f"Error cycling interface {iface}: {str(e)}", is_error=True)
        return False, f"Error cycling interface: {str(e)}" 