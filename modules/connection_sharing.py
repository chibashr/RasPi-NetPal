import os
import subprocess
import json
import time
import threading
from pathlib import Path
from modules.logging import add_log_entry
from modules.network import get_usb_network_interfaces

CONFIG_FILE = '/etc/captive/connection_sharing.json'
TEMP_CONFIG_FILE = '/etc/captive/connection_sharing.temp.json'
# Timeout in seconds before reverting changes if not confirmed
CONFIRMATION_TIMEOUT = 60  # 1 minute

# Global variable to track the revert timer thread
revert_timer = None

def get_sharing_status():
    """Get the current connection sharing status"""
    # Check if we're in confirmation mode
    if os.path.exists(TEMP_CONFIG_FILE):
        try:
            with open(TEMP_CONFIG_FILE, 'r') as f:
                temp_config = json.load(f)
            temp_config['pending_confirmation'] = True
            return temp_config
        except Exception as e:
            add_log_entry(f"Error reading temporary configuration: {str(e)}", is_error=True)
    
    # Regular check if configuration file exists
    if not os.path.exists(CONFIG_FILE):
        return {
            'active': False,
            'source': None,
            'target': None,
            'nat_enabled': False,
            'pending_confirmation': False
        }
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
        # Verify that connection sharing is actually active by checking iptables
        check_cmd = f"sudo iptables -t nat -C POSTROUTING -o {config.get('source', '')} -j MASQUERADE"
        result = subprocess.run(check_cmd, shell=True, capture_output=True)
        
        # If the rule exists, connection sharing is active
        config['active'] = result.returncode == 0
        config['pending_confirmation'] = False
        return config
    except Exception as e:
        add_log_entry(f"Error checking connection sharing status: {str(e)}", is_error=True)
        return {
            'active': False,
            'source': None,
            'target': None,
            'nat_enabled': False,
            'pending_confirmation': False
        }

def enable_connection_sharing(source, target, enable_nat=True, require_confirmation=True):
    """Enable connection sharing between interfaces"""
    global revert_timer
    
    try:
        add_log_entry(f"Enabling connection sharing from {source} to {target} with NAT={enable_nat}")
        
        # Check if source is a USB interface
        usb_interfaces = get_usb_network_interfaces()
        is_usb_source = source in usb_interfaces
        
        if is_usb_source:
            add_log_entry(f"USB interface {source} detected as source, ensuring it's active")
            # Make sure USB interface is up
            subprocess.run(f"sudo ip link set {source} up", shell=True, check=False)
            time.sleep(1)  # Brief delay to allow interface to come up
        
        # Save current configuration for potential rollback
        current_config = get_sharing_status()
        
        # First disable any existing sharing
        disable_connection_sharing(restart_services=False)
        
        # Enable IP forwarding in kernel
        subprocess.run("echo 1 > /proc/sys/net/ipv4/ip_forward", shell=True, check=True)
        
        # Make IP forwarding persistent across reboots
        with open('/etc/sysctl.conf', 'r') as f:
            sysctl_content = f.read()
        
        if 'net.ipv4.ip_forward=1' not in sysctl_content:
            add_log_entry("Adding persistent IP forwarding to sysctl.conf")
            with open('/etc/sysctl.conf', 'a') as f:
                f.write("\n# Enable IP forwarding for connection sharing\nnet.ipv4.ip_forward=1\n")
        
        # Get DNS servers from source interface
        dns_servers = []
        try:
            # First try to get DNS servers from systemd-resolved
            try:
                resolved_output = subprocess.check_output("systemd-resolve --status", shell=True, text=True)
                # Parse DNS servers from systemd-resolved output
                for line in resolved_output.splitlines():
                    if 'DNS Servers:' in line:
                        servers = line.split(':')[1].strip().split()
                        if servers:
                            dns_servers.extend(servers)
                            add_log_entry(f"Found DNS servers from systemd-resolved: {', '.join(dns_servers)}")
            except Exception as e:
                add_log_entry(f"Could not get DNS servers from systemd-resolved: {str(e)}", is_error=False)
            
            # If no DNS servers found, try resolv.conf
            if not dns_servers:
                with open('/etc/resolv.conf', 'r') as f:
                    for line in f:
                        if line.startswith('nameserver'):
                            dns_servers.append(line.split()[1])
                
                if dns_servers:
                    add_log_entry(f"Found DNS servers from resolv.conf: {', '.join(dns_servers)}")
            
            # If still no DNS servers, try using network interface-specific config
            if not dns_servers:
                # Try to get DNS from the source interface using nmcli (if available)
                try:
                    nmcli_output = subprocess.check_output(f"nmcli device show {source} | grep DNS", shell=True, text=True)
                    for line in nmcli_output.splitlines():
                        if 'DNS' in line and ':' in line:
                            server = line.split(':')[1].strip()
                            if server and server not in dns_servers:
                                dns_servers.append(server)
                    
                    if dns_servers:
                        add_log_entry(f"Found DNS servers from nmcli: {', '.join(dns_servers)}")
                except Exception as e:
                    add_log_entry(f"Could not get DNS servers from nmcli: {str(e)}", is_error=False)
            
            if not dns_servers:
                # Fallback to some common DNS servers
                dns_servers = ['8.8.8.8', '1.1.1.1']
                add_log_entry(f"No DNS servers found, using default public DNS: {', '.join(dns_servers)}")
            else:
                add_log_entry(f"Using DNS servers: {', '.join(dns_servers)}")
        except Exception as e:
            add_log_entry(f"Error getting DNS servers: {str(e)}", is_error=True)
            # Use default DNS servers
            dns_servers = ['8.8.8.8', '1.1.1.1']
        
        # Set up NAT if enabled
        if enable_nat:
            # Configure iptables for NAT
            subprocess.run(f"sudo iptables -t nat -A POSTROUTING -o {source} -j MASQUERADE", shell=True, check=True)
            subprocess.run(f"sudo iptables -A FORWARD -i {source} -o {target} -m state --state RELATED,ESTABLISHED -j ACCEPT", shell=True, check=True)
            subprocess.run(f"sudo iptables -A FORWARD -i {target} -o {source} -j ACCEPT", shell=True, check=True)
            
            # Allow DNS traffic (port 53) specifically
            subprocess.run(f"sudo iptables -A FORWARD -i {target} -o {source} -p udp --dport 53 -j ACCEPT", shell=True, check=True)
            subprocess.run(f"sudo iptables -A FORWARD -i {target} -o {source} -p tcp --dport 53 -j ACCEPT", shell=True, check=True)
            
            # Save iptables rules for persistence
            subprocess.run("sudo sh -c 'iptables-save > /etc/iptables.ipv4.nat'", shell=True, check=True)
            
            # Ensure iptables rules are loaded on boot
            if not os.path.exists('/etc/network/if-pre-up.d/iptables'):
                with open('/etc/network/if-pre-up.d/iptables', 'w') as f:
                    f.write("#!/bin/sh\niptables-restore < /etc/iptables.ipv4.nat\nexit 0\n")
                os.chmod('/etc/network/if-pre-up.d/iptables', 0o755)
        
        # Create new configuration
        new_config = {
            'active': True,
            'source': source,
            'target': target,
            'nat_enabled': enable_nat,
            'dns_servers': dns_servers,
            'previous_config': current_config,
            'timestamp': time.time()
        }
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        # If confirmation is required, store as temporary config
        if require_confirmation and target == 'wlan0':
            # Save to temporary file
            with open(TEMP_CONFIG_FILE, 'w') as f:
                json.dump(new_config, f)
            
            # Cancel any existing revert timer
            if revert_timer and revert_timer.is_alive():
                revert_timer.cancel()
            
            # Start a new revert timer
            revert_timer = threading.Timer(CONFIRMATION_TIMEOUT, revert_connection_sharing)
            revert_timer.daemon = True
            revert_timer.start()
            
            add_log_entry(f"Connection sharing enabled temporarily, waiting for confirmation within {CONFIRMATION_TIMEOUT} seconds")
        else:
            # Save directly to config file (no confirmation needed)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(new_config, f)
        
        # Restart the hostapd service if target is wlan0 (it's an AP)
        if target == 'wlan0':
            add_log_entry("Restarting hostapd service to apply changes to AP")
            try:
                # Configure dnsmasq to use the source DNS servers
                if os.path.exists('/etc/dnsmasq.conf'):
                    # Backup original config
                    subprocess.run("sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.bak", shell=True)
                    
                    # Check if systemd-resolved is running and potentially conflicting with dnsmasq
                    try:
                        resolved_status = subprocess.run("systemctl is-active systemd-resolved", 
                                                         shell=True, capture_output=True, text=True).stdout.strip()
                        
                        if resolved_status == "active":
                            add_log_entry("systemd-resolved is active, checking for port conflicts")
                            # Check if something is listening on port 53
                            port_check = subprocess.run("sudo netstat -tulpn | grep ':53 '", 
                                                      shell=True, capture_output=True, text=True).stdout
                            
                            if "systemd-resolve" in port_check:
                                add_log_entry("systemd-resolved is using port 53, configuring it to not interfere with dnsmasq")
                                # Edit resolved.conf to disable stub listener
                                resolved_conf = "/etc/systemd/resolved.conf"
                                if os.path.exists(resolved_conf):
                                    # Backup resolved.conf
                                    subprocess.run(f"sudo cp {resolved_conf} {resolved_conf}.bak", shell=True)
                                    
                                    # Read existing config
                                    with open(resolved_conf, 'r') as f:
                                        resolved_config = f.readlines()
                                    
                                    # Update or add DNSStubListener=no 
                                    found = False
                                    for i, line in enumerate(resolved_config):
                                        if line.strip().startswith("DNSStubListener="):
                                            resolved_config[i] = "DNSStubListener=no\n"
                                            found = True
                                            break
                                    
                                    if not found:
                                        resolved_config.append("\n# Disable DNS stub listener to avoid conflicts with dnsmasq\n")
                                        resolved_config.append("DNSStubListener=no\n")
                                    
                                    # Write updated config
                                    with open(resolved_conf, 'w') as f:
                                        f.writelines(resolved_config)
                                    
                                    # Restart systemd-resolved
                                    add_log_entry("Restarting systemd-resolved with updated configuration")
                                    subprocess.run("sudo systemctl restart systemd-resolved", shell=True)
                    except Exception as e:
                        add_log_entry(f"Error checking systemd-resolved: {str(e)}", is_error=False)
                    
                    # Update dnsmasq configuration
                    dnsmasq_config = []
                    with open('/etc/dnsmasq.conf', 'r') as f:
                        dnsmasq_config = f.readlines()
                    
                    # Remove existing DNS server entries
                    dnsmasq_config = [line for line in dnsmasq_config if not line.startswith('server=')]
                    
                    # Add our DNS servers
                    for dns in dns_servers:
                        dnsmasq_config.append(f"server={dns}\n")
                    
                    # Ensure local DNS queries are forwarded
                    if not any(line.startswith('domain-needed') for line in dnsmasq_config):
                        dnsmasq_config.append("domain-needed\n")
                    
                    if not any(line.startswith('bogus-priv') for line in dnsmasq_config):
                        dnsmasq_config.append("bogus-priv\n")
                    
                    # Make dnsmasq listen on the target interface
                    # Remove existing interface bindings first
                    dnsmasq_config = [line for line in dnsmasq_config if not line.startswith('interface=')]
                    dnsmasq_config.append(f"interface={target}\n")
                    
                    # Explicitly set the DHCP range for the AP network (assuming 192.168.4.x is the AP network)
                    # Remove existing dhcp-range settings first
                    dnsmasq_config = [line for line in dnsmasq_config if not line.startswith('dhcp-range=')]
                    dnsmasq_config.append("dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h\n")
                    
                    # Set the local DNS server (dnsmasq) to be advertised to DHCP clients
                    dnsmasq_config = [line for line in dnsmasq_config if not line.startswith('dhcp-option=')]
                    # Use the Pi as the DNS server; it will forward DNS requests to the upstream servers
                    dnsmasq_config.append("dhcp-option=6,192.168.4.1\n")
                    
                    # Ensure dnsmasq doesn't use /etc/resolv.conf
                    dnsmasq_config = [line for line in dnsmasq_config if not line.startswith('no-resolv')]
                    dnsmasq_config.append("no-resolv\n")
                    
                    # Add explicit DNS forwarding settings
                    dnsmasq_config.append("# Forward all DNS queries from AP clients to specified DNS servers\n")
                    dnsmasq_config.append("bind-interfaces\n")
                    dnsmasq_config.append("listen-address=127.0.0.1,192.168.4.1\n")
                    
                    # Make dnsmasq log DNS queries for troubleshooting
                    dnsmasq_config.append("log-queries\n")
                    dnsmasq_config.append("log-facility=/var/log/dnsmasq.log\n")
                    
                    # Ensure DNS traffic is allowed on loopback interface
                    subprocess.run("sudo iptables -I INPUT -i lo -j ACCEPT", shell=True)
                    subprocess.run("sudo iptables -I OUTPUT -o lo -j ACCEPT", shell=True)
                    
                    # Explicitly allow DNS traffic on UDP and TCP
                    subprocess.run(f"sudo iptables -I INPUT -i {target} -p udp --dport 53 -j ACCEPT", shell=True)
                    subprocess.run(f"sudo iptables -I INPUT -i {target} -p tcp --dport 53 -j ACCEPT", shell=True)
                    
                    # Add a specific rule to forward DNS traffic to the gateway
                    for dns in dns_servers:
                        subprocess.run(f"sudo iptables -t nat -A PREROUTING -i {target} -p udp --dport 53 -j DNAT --to {dns}:53", shell=True)
                        subprocess.run(f"sudo iptables -t nat -A PREROUTING -i {target} -p tcp --dport 53 -j DNAT --to {dns}:53", shell=True)
                    
                    # Enable DNS caching to improve performance
                    dnsmasq_config.append("cache-size=1000\n")
                    
                    # Ensure DHCP server is explicitly enabled
                    dnsmasq_config.append("dhcp-authoritative\n")
                    
                    # Add DHCP lease file location
                    dnsmasq_config = [line for line in dnsmasq_config if not line.startswith('dhcp-leasefile=')]
                    dnsmasq_config.append("dhcp-leasefile=/var/lib/misc/dnsmasq.leases\n")
                    
                    # Set gateway for DHCP clients to be the Raspberry Pi
                    dnsmasq_config.append("dhcp-option=3,192.168.4.1\n")
                    
                    # Write updated config
                    with open('/etc/dnsmasq.conf', 'w') as f:
                        f.writelines(dnsmasq_config)
                    
                    add_log_entry(f"Updated dnsmasq.conf to forward DNS queries to: {', '.join(dns_servers)}")
                    
                    # Try to restart dnsmasq
                    try:
                        add_log_entry("Restarting dnsmasq to apply DNS forwarding settings")
                        subprocess.run("sudo systemctl restart dnsmasq", shell=True, check=True)
                    except Exception as e:
                        add_log_entry(f"Error restarting dnsmasq, trying to start it: {str(e)}", is_error=True)
                        # Try to start it if it's not running
                        subprocess.run("sudo systemctl start dnsmasq", shell=True)
                else:
                    add_log_entry("dnsmasq.conf not found, DNS forwarding may not work properly", is_error=True)
                
                # Verify DNS server configuration
                add_log_entry("DNS forwarding configuration (dnsmasq to upstream DNS servers) complete")
                add_log_entry(f"Clients on 192.168.4.x network will receive DNS server: 192.168.4.1")
                add_log_entry(f"Queries to 192.168.4.1 will be forwarded to: {', '.join(dns_servers)}")
                
                # Restart network services
                subprocess.run("sudo systemctl restart hostapd", shell=True, check=True)
                # Also restart dhcpcd to ensure proper network configuration
                subprocess.run("sudo systemctl restart dhcpcd", shell=True, check=True)
                
                # Ensure wlan0 has the correct static IP
                try:
                    # Check if wlan0 has the correct IP address
                    ip_cmd = "ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1"
                    current_ip = subprocess.check_output(ip_cmd, shell=True, text=True).strip()
                    
                    if current_ip != "192.168.4.1":
                        add_log_entry(f"Setting static IP 192.168.4.1 on wlan0 (current: {current_ip})")
                        # Set the correct IP address
                        subprocess.run("sudo ip addr flush dev wlan0", shell=True)
                        subprocess.run("sudo ip addr add 192.168.4.1/24 dev wlan0", shell=True)
                        
                        # Update dhcpcd.conf to ensure persistent IP
                        dhcpcd_path = '/etc/dhcpcd.conf'
                        if os.path.exists(dhcpcd_path):
                            # Read current config
                            with open(dhcpcd_path, 'r') as f:
                                dhcpcd_content = f.readlines()
                            
                            # Remove existing wlan0 static config
                            new_content = []
                            skip = False
                            for line in dhcpcd_content:
                                if line.strip() == "interface wlan0":
                                    skip = True
                                    continue
                                elif skip and line.strip().startswith("interface "):
                                    skip = False
                                
                                if not skip:
                                    new_content.append(line)
                            
                            # Add proper static IP config
                            new_content.append("\n# Static IP configuration for wlan0 (AP mode)\n")
                            new_content.append("interface wlan0\n")
                            new_content.append("    static ip_address=192.168.4.1/24\n")
                            new_content.append("    nohook wpa_supplicant\n")
                            
                            # Write updated config
                            with open(dhcpcd_path, 'w') as f:
                                f.writelines(new_content)
                            
                            add_log_entry("Updated dhcpcd.conf with static IP for wlan0")
                except Exception as e:
                    add_log_entry(f"Error configuring static IP for wlan0: {str(e)}", is_error=True)
                
                # Flush DNS caches to ensure fresh DNS resolution
                try:
                    # Try systemd-resolved cache flush first
                    subprocess.run("sudo systemd-resolve --flush-caches", shell=True)
                except:
                    pass  # Ignore if not available
                
                # Try nscd cache flush if available
                try:
                    subprocess.run("sudo service nscd restart", shell=True)
                except:
                    pass  # Ignore if not available
                
                # Clear local DNS cache on the Raspberry Pi
                try:
                    subprocess.run("sudo killall -HUP dnsmasq", shell=True)
                except:
                    pass  # Ignore if not running
                
            except Exception as e:
                add_log_entry(f"Warning: Error restarting network services: {str(e)}", is_error=True)
        
        add_log_entry(f"Connection sharing enabled successfully from {source} to {target}")
        return True, "Connection sharing enabled successfully"
    except Exception as e:
        add_log_entry(f"Error enabling connection sharing: {str(e)}", is_error=True)
        return False, f"Error enabling connection sharing: {str(e)}"

def confirm_connection_sharing():
    """Confirm the temporary connection sharing configuration"""
    global revert_timer
    
    try:
        # Check if we have a temporary configuration
        if not os.path.exists(TEMP_CONFIG_FILE):
            return False, "No pending connection sharing configuration to confirm"
        
        # Load the temporary configuration
        with open(TEMP_CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Cancel the revert timer
        if revert_timer and revert_timer.is_alive():
            revert_timer.cancel()
            revert_timer = None
        
        # Move the temporary configuration to the permanent one
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        
        # Delete the temporary configuration
        os.remove(TEMP_CONFIG_FILE)
        
        add_log_entry("Connection sharing configuration confirmed")
        return True, "Connection sharing configuration confirmed"
    except Exception as e:
        add_log_entry(f"Error confirming connection sharing: {str(e)}", is_error=True)
        return False, f"Error confirming connection sharing: {str(e)}"

def revert_connection_sharing():
    """Revert to previous connection sharing configuration after timeout"""
    try:
        add_log_entry("Reverting connection sharing configuration due to timeout")
        
        # Check if we have a temporary configuration
        if not os.path.exists(TEMP_CONFIG_FILE):
            return
        
        # Load the temporary configuration to get previous settings
        with open(TEMP_CONFIG_FILE, 'r') as f:
            temp_config = json.load(f)
        
        previous_config = temp_config.get('previous_config', {})
        
        # First disable current sharing
        disable_connection_sharing(restart_services=False)
        
        # If previous config was active, restore it
        if previous_config.get('active', False):
            source = previous_config.get('source')
            target = previous_config.get('target')
            nat_enabled = previous_config.get('nat_enabled', True)
            
            if source and target:
                # Re-enable with the previous settings but don't require confirmation
                enable_connection_sharing(source, target, nat_enabled, require_confirmation=False)
        
        # Remove temporary configuration
        if os.path.exists(TEMP_CONFIG_FILE):
            os.remove(TEMP_CONFIG_FILE)
        
        # Restart services if target was wlan0
        if temp_config.get('target') == 'wlan0':
            add_log_entry("Restarting hostapd service after reverting changes")
            try:
                subprocess.run("sudo systemctl restart hostapd", shell=True, check=True)
                subprocess.run("sudo systemctl restart dhcpcd", shell=True, check=True)
            except Exception as e:
                add_log_entry(f"Warning: Error restarting services: {str(e)}", is_error=True)
        
        add_log_entry("Connection sharing configuration reverted successfully")
    except Exception as e:
        add_log_entry(f"Error reverting connection sharing: {str(e)}", is_error=True)

def disable_connection_sharing(restart_services=True):
    """Disable connection sharing and clean up rules"""
    try:
        add_log_entry("Disabling connection sharing")
        
        # Check if configuration file exists to get interfaces
        target_was_wlan0 = False
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
            source = config.get('source')
            target = config.get('target')
            target_was_wlan0 = (target == 'wlan0')
            
            # Remove specific rules if source and target are known
            if source and target:
                try:
                    subprocess.run(f"sudo iptables -t nat -D POSTROUTING -o {source} -j MASQUERADE", shell=True)
                    subprocess.run(f"sudo iptables -D FORWARD -i {source} -o {target} -m state --state RELATED,ESTABLISHED -j ACCEPT", shell=True)
                    subprocess.run(f"sudo iptables -D FORWARD -i {target} -o {source} -j ACCEPT", shell=True)
                except Exception as e:
                    add_log_entry(f"Error removing specific iptables rules: {str(e)}", is_error=True)
        
        # Also check temporary configuration file
        if os.path.exists(TEMP_CONFIG_FILE):
            try:
                with open(TEMP_CONFIG_FILE, 'r') as f:
                    temp_config = json.load(f)
                source = temp_config.get('source')
                target = temp_config.get('target')
                target_was_wlan0 = target_was_wlan0 or (target == 'wlan0')
                
                # Remove specific rules if source and target are known
                if source and target:
                    try:
                        subprocess.run(f"sudo iptables -t nat -D POSTROUTING -o {source} -j MASQUERADE", shell=True)
                        subprocess.run(f"sudo iptables -D FORWARD -i {source} -o {target} -m state --state RELATED,ESTABLISHED -j ACCEPT", shell=True)
                        subprocess.run(f"sudo iptables -D FORWARD -i {target} -o {source} -j ACCEPT", shell=True)
                    except Exception as e:
                        add_log_entry(f"Error removing specific temporary iptables rules: {str(e)}", is_error=True)
                
                # Remove temporary configuration file
                os.remove(TEMP_CONFIG_FILE)
            except Exception as e:
                add_log_entry(f"Error removing temporary configuration: {str(e)}", is_error=True)
        
        # Flush all iptables NAT and FORWARD rules to be sure
        subprocess.run("sudo iptables -t nat -F POSTROUTING", shell=True)
        subprocess.run("sudo iptables -F FORWARD", shell=True)
        
        # Disable IP forwarding
        subprocess.run("echo 0 > /proc/sys/net/ipv4/ip_forward", shell=True)
        
        # Update configuration file
        config = {
            'active': False,
            'source': None,
            'target': None,
            'nat_enabled': False
        }
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        
        # Restart the hostapd service if target was wlan0 (it's an AP)
        if restart_services and target_was_wlan0:
            add_log_entry("Restarting hostapd service to apply changes to AP")
            try:
                subprocess.run("sudo systemctl restart hostapd", shell=True, check=True)
                # Also restart dhcpcd to ensure proper network configuration
                subprocess.run("sudo systemctl restart dhcpcd", shell=True, check=True)
            except Exception as e:
                add_log_entry(f"Warning: Error restarting hostapd or dhcpcd: {str(e)}", is_error=True)
            
        add_log_entry("Connection sharing disabled successfully")
        return True, "Connection sharing disabled successfully"
    except Exception as e:
        add_log_entry(f"Error disabling connection sharing: {str(e)}", is_error=True)
        return False, f"Error disabling connection sharing: {str(e)}" 