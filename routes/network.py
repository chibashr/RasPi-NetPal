from flask import Blueprint, jsonify, request, render_template
from modules.network import get_interfaces, get_listening_ports, get_interface_config, update_interface_config, release_renew_dhcp, cycle_interface, get_usb_network_interfaces, get_usb_serial_devices
from modules.logging import add_log_entry

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
    
    success, message = update_interface_config(iface, ip, netmask, gateway, static)
    
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