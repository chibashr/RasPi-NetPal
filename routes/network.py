from flask import Blueprint, jsonify, request, render_template
from modules.network import get_interfaces, get_listening_ports, get_interface_config, update_interface_config, release_renew_dhcp, cycle_interface, get_usb_network_interfaces, get_usb_serial_devices, switch_gateway
from modules.logging import add_log_entry
import subprocess
import re

bp = Blueprint('network', __name__)

@bp.route("/get_interfaces", methods=["GET"])
def get_network_interfaces():
    """Endpoint to get all network interfaces"""
    return jsonify(get_interfaces())

@bp.route("/get_usb_interfaces", methods=["GET"])
def get_usb_interfaces():
    """Endpoint to get USB network interfaces"""
    usb_interfaces = get_usb_network_interfaces()
    return jsonify({"usb_interfaces": usb_interfaces})

@bp.route("/get_usb_serial_devices", methods=["GET"])
def get_serial_devices():
    """Endpoint to get USB serial devices"""
    serial_devices = get_usb_serial_devices()
    return jsonify({"serial_devices": serial_devices})

@bp.route("/get_interface_config/<iface>", methods=["GET"])
def get_iface_config(iface):
    return jsonify(get_interface_config(iface))

@bp.route("/update_interface", methods=["POST"])
def update_interface():
    iface = request.form.get("iface")
    ip = request.form.get("ip")
    netmask = request.form.get("netmask")
    gateway = request.form.get("gateway")
    static = request.form.get("static")
    dns = request.form.get("dns")
    
    success, message = update_interface_config(iface, ip, netmask, gateway, static, dns)
    
    # Return the updated interface data along with the status
    updated_interface_data = {
        'interfaces': get_interfaces(),
        'success': success, 
        'message': message
    }
    
    return jsonify(updated_interface_data)

@bp.route("/renew_dhcp/<iface>", methods=["POST"])
def renew_dhcp(iface):
    """Endpoint for releasing and renewing DHCP lease"""
    success, message = release_renew_dhcp(iface)
    
    # Return the updated interface data along with the status
    updated_interface_data = {
        'interfaces': get_interfaces(),
        'success': success, 
        'message': message
    }
    
    return jsonify(updated_interface_data)

@bp.route("/cycle_interface/<iface>", methods=["POST"])
def interface_cycle(iface):
    """Endpoint for cycling (down/up) an interface"""
    # Safety check - don't allow cycling wlan0 or lo
    if iface in ['wlan0', 'lo']:
        return jsonify({
            'interfaces': get_interfaces(),
            'success': False, 
            'message': f"Cycling interface {iface} is not allowed for safety reasons"
        })
    
    success, message = cycle_interface(iface)
    
    # Return the updated interface data along with the status
    updated_interface_data = {
        'interfaces': get_interfaces(),
        'success': success, 
        'message': message
    }
    
    return jsonify(updated_interface_data)

@bp.route("/switch_gateway", methods=["POST"])
def switch_gateway_route():
    iface = request.form.get("iface")
    gateway = request.form.get("gateway")
    
    if not iface or not gateway:
        return jsonify({
            'success': False, 
            'message': 'Missing interface or gateway'
        })
    
    success, message = switch_gateway(iface, gateway)
    
    # Return the updated interface data along with the status
    updated_interface_data = {
        'interfaces': get_interfaces(),
        'success': success, 
        'message': message
    }
    
    return jsonify(updated_interface_data)

@bp.route('/get_updates', methods=['GET'])
def get_updates():
    """Get various system updates for the dashboard."""
    try:
        data = {}
        
        # Get interface information
        interfaces = []
        
        # Get list of interfaces
        cmd = "ls -1 /sys/class/net"
        result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            iface_names = result.stdout.strip().split('\n')
            
            # Get default route information
            default_route_cmd = "ip -4 route show default"
            default_route_result = subprocess.run(default_route_cmd, shell=True, check=False, capture_output=True, text=True)
            default_iface = None
            default_gateway = None
            
            if default_route_result.returncode == 0 and default_route_result.stdout.strip():
                # Parse the default route output
                match = re.search(r'default via ([0-9.]+) dev (\w+)', default_route_result.stdout)
                if match:
                    default_gateway = match.group(1)
                    default_iface = match.group(2)
            
            for iface in iface_names:
                # Get interface details
                ip_cmd = f"ip addr show {iface}"
                ip_result = subprocess.run(ip_cmd, shell=True, check=False, capture_output=True, text=True)
                
                if ip_result.returncode == 0:
                    ip_info = ip_result.stdout
                    
                    # Parse state (UP/DOWN)
                    state_match = re.search(r'state (\w+)', ip_info)
                    state = state_match.group(1) if state_match else "UNKNOWN"
                    
                    # Parse IP address
                    ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_info)
                    ip_addr = ip_match.group(1) if ip_match else None
                    
                    # If interface is down but has a carrier (physical link), it's "connected but down"
                    if state.upper() == "DOWN":
                        carrier_cmd = f"cat /sys/class/net/{iface}/carrier 2>/dev/null || echo 0"
                        carrier_result = subprocess.run(carrier_cmd, shell=True, check=False, capture_output=True, text=True)
                        if carrier_result.returncode == 0 and carrier_result.stdout.strip() == "1":
                            state = "DOWN (connected)"
                    
                    # Check if it's a USB device
                    is_usb = False
                    usb_cmd = f"readlink -f /sys/class/net/{iface} | grep -i usb"
                    usb_result = subprocess.run(usb_cmd, shell=True, check=False, capture_output=True, text=True)
                    if usb_result.returncode == 0 and usb_result.stdout.strip():
                        is_usb = True
                    
                    # Check for internet connectivity
                    has_internet = False
                    if state.upper() == "UP" and ip_addr:
                        ping_cmd = f"ping -c 1 -W 2 -I {iface} 8.8.8.8"
                        ping_result = subprocess.run(ping_cmd, shell=True, check=False, capture_output=True)
                        if ping_result.returncode == 0:
                            has_internet = True
                    
                    # Get gateway for this interface
                    gateway = None
                    if state.upper() == "UP":
                        gw_cmd = f"ip route show dev {iface} | grep default | awk '{{print $3}}'"
                        gw_result = subprocess.run(gw_cmd, shell=True, check=False, capture_output=True, text=True)
                        if gw_result.returncode == 0 and gw_result.stdout.strip():
                            gateway = gw_result.stdout.strip()
                    
                    # Get all available gateways for this interface
                    all_routes = []
                    routes_cmd = f"ip route show dev {iface} | grep via | awk '{{print $3}}'"
                    routes_result = subprocess.run(routes_cmd, shell=True, check=False, capture_output=True, text=True)
                    if routes_result.returncode == 0 and routes_result.stdout.strip():
                        all_routes = list(set(routes_result.stdout.strip().split('\n')))
                    
                    # Add interface to list
                    iface_data = {
                        'name': iface,
                        'addr': ip_addr,
                        'state': state,
                        'type': 'usb' if is_usb else 'ethernet',
                        'has_internet': has_internet,
                        'gateway': gateway or default_gateway if iface == default_iface else gateway,
                        'all_routes': all_routes,
                        'has_default_route': iface == default_iface
                    }
                    
                    interfaces.append(iface_data)
        
        data['interfaces'] = interfaces
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
    return jsonify(data) 