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
    interfaces = []
    try:
        # Get all network interfaces
        output = subprocess.check_output("ip -o link show", shell=True).decode().strip().splitlines()
        
        # Get USB interfaces
        usb_interfaces = get_usb_network_interfaces()
        
        # Find default route
        default_route_output = subprocess.check_output("ip route show default", shell=True, stderr=subprocess.STDOUT).decode().strip()
        default_interface = None
        if default_route_output:
            default_match = re.search(r'dev\s+(\w+)', default_route_output)
            if default_match:
                default_interface = default_match.group(1)
        
        # Parse interface information
        for line in output:
            parts = line.split(': ')
            if len(parts) < 2:
                continue
                
            name = parts[1].split('@')[0]
            
            # Get state (UP/DOWN)
            state_match = re.search(r'state\s+(\w+)', line)
            state = state_match.group(1) if state_match else "UNKNOWN"
            
            # Get IP address
            ip_output = subprocess.check_output(f"ip -o addr show {name}", shell=True).decode().strip().splitlines()
            addr = "N/A"
            for ip_line in ip_output:
                if 'inet ' in ip_line:
                    addr_match = re.search(r'inet\s+([0-9.]+)', ip_line)
                    if addr_match:
                        addr = addr_match.group(1)
                        break
            
            # Get gateway for this interface
            gateway = "N/A"
            all_routes = []
            try:
                route_output = subprocess.check_output(f"ip route show dev {name}", shell=True).decode().strip().splitlines()
                for route_line in route_output:
                    if 'default via ' in route_line:
                        gateway_match = re.search(r'default via\s+([0-9.]+)', route_line)
                        if gateway_match:
                            gateway = gateway_match.group(1)
                            all_routes.append(gateway)
            except:
                pass
                
            # Get detailed information
            details = None
            try:
                details_output = subprocess.check_output(f"ip -s link show {name}", shell=True).decode().strip()
                details = details_output
            except:
                pass
            
            # Check if this is a USB interface
            is_usb = name in usb_interfaces
            interface_type = "usb" if is_usb else "built-in"
            
            # Check for carrier signal, especially important for USB interfaces
            has_carrier = False
            try:
                carrier = subprocess.check_output(f"cat /sys/class/net/{name}/carrier 2>/dev/null || echo 0", 
                                               shell=True).decode().strip()
                has_carrier = carrier == "1"
                
                # Enhanced status detection for USB interfaces
                if is_usb and state == "DOWN" and has_carrier:
                    # Interface has carrier signal but is administratively down
                    state = "DOWN (connected)"
            except:
                pass
            
            # Check if this interface has internet connectivity
            has_internet = False
            if state == "UP" and addr != "N/A":
                has_internet = check_internet_connectivity(name)
                
            # Check if this is the default route
            has_default_route = name == default_interface
            
            interfaces.append({
                'name': name, 
                'state': state, 
                'addr': addr,
                'gateway': gateway,
                'all_routes': all_routes,
                'details': details,
                'type': interface_type,
                'has_internet': has_internet,
                'has_default_route': has_default_route,
                'has_carrier': has_carrier
            })
    except Exception as e:
        log_message = f"Error in get_interfaces: {str(e)}"
        print(log_message)
        add_log_entry(log_message, is_error=True)
        
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
        'dns': '',
        'static': False,
        'has_custom_dns': False,
        'has_custom_gateway': False
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
                    # If we have a gateway setting but no static IP, it's a custom gateway override
                    if not config['static']:
                        config['has_custom_gateway'] = True
                        
                if match_dns:
                    config['dns'] = match_dns.group(1)
                    # If we have DNS settings but no static IP, it's a custom DNS override
                    if not config['static']:
                        config['has_custom_dns'] = True
                
                # For debugging
                add_log_entry(f"Debug: Interface {iface} config - static: {config['static']}, ip: {config['ip']}, netmask: {config['netmask']}, gateway: {config['gateway']}, dns: {config['dns']}")
    except Exception as e:
        add_log_entry(f"Error in get_interface_config for {iface}: {str(e)}", is_error=True)
    return config

def update_interface_config(iface, ip, netmask, gateway, use_static, dns=None):
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

        # Start with a new interface section
        interface_config = [f"\ninterface {iface}\n"]
        
        if use_static == "yes":
            # Full static configuration
            interface_config.append(f"static ip_address={ip}/{netmask}\n")
            if gateway:
                interface_config.append(f"static routers={gateway}\n")
            # Use provided DNS or default to Google and Cloudflare DNS
            dns_servers = dns if dns else "8.8.8.8 1.1.1.1"
            interface_config.append(f"static domain_name_servers={dns_servers}\n")
        else:
            # DHCP mode but with potential gateway and DNS overrides
            if gateway:
                interface_config.append(f"static routers={gateway}\n")
                add_log_entry(f"Setting custom gateway {gateway} for {iface} while using DHCP")
            
            if dns:
                interface_config.append(f"static domain_name_servers={dns}\n")
                add_log_entry(f"Setting custom DNS {dns} for {iface} while using DHCP")
        
        # Add the interface configuration if we have settings to apply
        if len(interface_config) > 1:  # More than just the interface line
            config_lines.extend(interface_config)
        
        with open("/etc/dhcpcd.conf", "w") as f:
            f.writelines(config_lines)

        # Log the changes
        config_type = "Static IP " + ip + "/" + netmask if use_static == "yes" else "DHCP"
        custom_settings = []
        if gateway and use_static != "yes":
            custom_settings.append(f"custom gateway: {gateway}")
        if dns and use_static != "yes":
            custom_settings.append(f"custom DNS: {dns}")
        
        config_desc = config_type
        if custom_settings:
            config_desc += " with " + ", ".join(custom_settings)
            
        log_entry = f"Updated {iface}: {config_desc}"
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
    """Cycle (down/up) a network interface with enhanced USB device handling"""
    try:
        add_log_entry(f"Cycling interface {iface} down and up")
        
        # Check if this is a USB interface
        usb_interfaces = get_usb_network_interfaces()
        is_usb = iface in usb_interfaces
        
        # Check current state
        current_state = subprocess.check_output(f"ip link show {iface}", shell=True).decode().strip()
        was_up = "state UP" in current_state
        has_carrier = False
        
        try:
            carrier = subprocess.check_output(f"cat /sys/class/net/{iface}/carrier 2>/dev/null || echo 0", 
                                           shell=True).decode().strip()
            has_carrier = carrier == "1"
        except:
            pass
        
        add_log_entry(f"Interface {iface} state before cycling: UP={was_up}, carrier={has_carrier}, USB={is_usb}")
        
        # For USB interfaces that aren't working correctly, try a more thorough reset
        if is_usb and (not was_up or (was_up and not has_carrier)):
            add_log_entry(f"Performing thorough reset for USB interface {iface}")
            
            # Try to reset the USB device completely first
            try:
                # Get USB bus path
                usb_info = subprocess.check_output(f"readlink -f /sys/class/net/{iface}/device", shell=True).decode().strip()
                if usb_info:
                    # Extract USB bus/device path
                    usb_path_match = re.search(r'usb\d+\/\d+-[\d\.]+', usb_info)
                    if usb_path_match:
                        usb_path = usb_path_match.group(0)
                        add_log_entry(f"Found USB path: {usb_path} for {iface}")
                        
                        # Reset USB device by removing and re-adding authorization
                        authorized_path = f"/sys/bus/{usb_path}/authorized"
                        if os.path.exists(authorized_path):
                            add_log_entry(f"Resetting USB device at {authorized_path}")
                            subprocess.call(f"echo 0 | sudo tee {authorized_path}", shell=True)
                            time.sleep(2)
                            subprocess.call(f"echo 1 | sudo tee {authorized_path}", shell=True)
                            time.sleep(3)
                            
                            # Check if interface still exists after reset
                            if not os.path.exists(f"/sys/class/net/{iface}"):
                                add_log_entry(f"Interface {iface} no longer exists after USB reset, waiting for it to reappear")
                                # Wait for the interface to reappear
                                time.sleep(5)
                                if not os.path.exists(f"/sys/class/net/{iface}"):
                                    return False, f"USB reset caused interface {iface} to disappear and not reappear"
            except Exception as usb_error:
                add_log_entry(f"Error during USB device reset: {str(usb_error)}", is_error=True)
        
        # Bring interface down
        add_log_entry(f"Setting {iface} down")
        subprocess.call(f"sudo ip link set {iface} down", shell=True)
        
        # Small delay to ensure it's processed
        time.sleep(2)
        
        # Bring interface back up
        add_log_entry(f"Setting {iface} up")
        subprocess.call(f"sudo ip link set {iface} up", shell=True)
        time.sleep(2)
        
        # Check if this was a DHCP interface
        interface_config = get_interface_config(iface)
        if not interface_config['static']:
            add_log_entry(f"Renewing DHCP lease for {iface}")
            
            # First try dhclient if available
            if subprocess.call("which dhclient >/dev/null 2>&1", shell=True) == 0:
                add_log_entry(f"Using dhclient for {iface}")
                # First release the lease
                subprocess.call(f"sudo dhclient -r {iface}", shell=True)
                time.sleep(1)
                # Then request a new lease
                subprocess.call(f"sudo dhclient -v {iface}", shell=True)
            else:
                # Fallback to dhcpcd
                add_log_entry(f"Using dhcpcd for {iface}")
                subprocess.call(f"sudo dhcpcd -n {iface}", shell=True)
        
        # Wait for the interface to stabilize
        time.sleep(3)
        
        # Final verification steps
        try:
            new_state = subprocess.check_output(f"ip link show {iface}", shell=True).decode().strip()
            is_up_now = "state UP" in new_state
            
            try:
                new_carrier = subprocess.check_output(f"cat /sys/class/net/{iface}/carrier 2>/dev/null || echo 0", 
                                                   shell=True).decode().strip()
                has_carrier_now = new_carrier == "1"
            except:
                has_carrier_now = False
            
            add_log_entry(f"Interface {iface} state after cycling: UP={is_up_now}, carrier={has_carrier_now}")
            
            if is_up_now:
                # Check if DHCP assigned an IP
                ip_output = subprocess.check_output(f"ip -o addr show {iface}", shell=True).decode().strip().splitlines()
                has_ip = False
                for ip_line in ip_output:
                    if 'inet ' in ip_line:
                        has_ip = True
                        break
                
                if not has_ip and not interface_config['static']:
                    add_log_entry(f"Interface {iface} is UP but has no IP address, forcing DHCP renewal")
                    if subprocess.call("which dhclient >/dev/null 2>&1", shell=True) == 0:
                        subprocess.call(f"sudo dhclient -v {iface}", shell=True)
                    else:
                        subprocess.call(f"sudo dhcpcd -n {iface}", shell=True)
                
                # Test connectivity if we have an IP
                if has_ip:
                    add_log_entry(f"Testing connectivity on {iface}")
                    connectivity_test = subprocess.run(f"ping -I {iface} -c 1 -W 2 8.8.8.8", 
                                                     shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if connectivity_test.returncode == 0:
                        add_log_entry(f"Interface {iface} has connectivity")
                    else:
                        add_log_entry(f"Interface {iface} is UP with IP but has no connectivity", is_error=True)
                        
            else:
                add_log_entry(f"Interface {iface} is still DOWN after cycling", is_error=True)
                
                # For USB interfaces, try one more time with a different approach
                if is_usb:
                    add_log_entry(f"Attempting alternative recovery for USB interface {iface}")
                    # Try to reload the USB module if we can determine it
                    try:
                        # Look for the driver being used
                        driver_path = f"/sys/class/net/{iface}/device/driver"
                        if os.path.exists(driver_path):
                            driver = os.path.basename(os.path.realpath(driver_path))
                            add_log_entry(f"Found driver {driver} for {iface}")
                            # Attempt to reload the module
                            subprocess.call(f"sudo modprobe -r {driver} && sudo modprobe {driver}", shell=True)
                            time.sleep(3)
                            # Try bringing the interface up again
                            subprocess.call(f"sudo ip link set {iface} up", shell=True)
                    except Exception as driver_error:
                        add_log_entry(f"Error attempting driver reload: {str(driver_error)}", is_error=True)
        except Exception as verify_error:
            add_log_entry(f"Error verifying interface state: {str(verify_error)}", is_error=True)
        
        return True, f"Completed cycling of {iface} interface"
    except Exception as e:
        add_log_entry(f"Error cycling interface {iface}: {str(e)}", is_error=True)
        return False, f"Error cycling interface: {str(e)}"

def switch_gateway(iface, new_gateway):
    """Switch the default gateway for a specific interface"""
    try:
        add_log_entry(f"Switching default gateway for {iface} to {new_gateway}")
        
        # Remove existing default route for the interface
        subprocess.call(f"sudo ip route del default dev {iface} 2>/dev/null", shell=True)
        
        # Add the new default route
        subprocess.call(f"sudo ip route add default via {new_gateway} dev {iface}", shell=True)
        
        # Update dhcpcd.conf for persistence if this is a static configuration
        interface_config = get_interface_config(iface)
        if interface_config['static']:
            config_lines = []
            with open("/etc/dhcpcd.conf", "r") as f:
                config_lines = f.readlines()
            
            # Find and update the routers line
            updated = False
            for i, line in enumerate(config_lines):
                if line.strip().startswith("static routers=") and i > 0 and config_lines[i-1].strip().startswith(f"interface {iface}"):
                    config_lines[i] = f"static routers={new_gateway}\n"
                    updated = True
                    break
            
            # Write changes back to the file
            with open("/etc/dhcpcd.conf", "w") as f:
                f.writelines(config_lines)
        
        # Log the successful gateway change
        add_log_entry(f"Successfully switched gateway for {iface} to {new_gateway}")
        return True, f"Successfully switched gateway for {iface} to {new_gateway}"
    except Exception as e:
        add_log_entry(f"Error switching gateway for {iface}: {str(e)}", is_error=True)
        return False, f"Error switching gateway: {str(e)}" 