#!/bin/bash
# wlan0_dhcp_fix.sh
# This script ensures the DHCP server on wlan0 always works correctly
# It should be run on system boot

# Log function
log() {
    echo "$(date): $1"
    logger -t "wlan0_dhcp_fix" "$1"
}

# Set static IP for wlan0 (this is critical for DHCP server)
set_static_ip() {
    log "Setting static IP 192.168.4.1 for wlan0"
    sudo ip addr flush dev wlan0
    sudo ip addr add 192.168.4.1/24 dev wlan0
    sudo ip link set wlan0 up
}

# Update dhcpcd.conf
update_dhcpcd_conf() {
    # Check if dhcpcd is being used
    if [ -f /etc/dhcpcd.conf ]; then
        log "Updating dhcpcd.conf for wlan0"
        # Create backup if not exists
        if [ ! -f /etc/dhcpcd.conf.original ]; then
            sudo cp /etc/dhcpcd.conf /etc/dhcpcd.conf.original
        fi
        
        # Remove existing wlan0 configuration
        sudo sed -i '/interface wlan0/,/^[^[:space:]]/!b;//d' /etc/dhcpcd.conf
        
        # Add correct configuration
        echo '
# Static IP configuration for wlan0 (AP mode)
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
' | sudo tee -a /etc/dhcpcd.conf > /dev/null
    else
        log "dhcpcd.conf not found, dhcpcd not in use"
    fi
}

# Configure dnsmasq
configure_dnsmasq() {
    log "Configuring dnsmasq for wlan0"
    # Create backup if not exists
    if [ ! -f /etc/dnsmasq.conf.original ]; then
        sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.original
    fi
    
    # Create custom dnsmasq configuration
    echo '# dnsmasq configuration for wlan0 AP mode
# Interface to listen on
interface=wlan0
# Do not use /etc/resolv.conf
no-resolv
# Set domain needed to stop forwarding short names
domain-needed
# Do not forward non-routed addresses
bogus-priv
# DHCP range
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
# DHCP options
dhcp-option=option:dns-server,192.168.4.1
# Set gateway (router) for clients
dhcp-option=option:router,192.168.4.1
# Set DNS servers to forward to
server=8.8.8.8
server=8.8.4.4
server=1.1.1.1
# Bind only to needed interfaces
bind-interfaces
# Listen addresses
listen-address=127.0.0.1,192.168.4.1
# Enable DHCP server
dhcp-authoritative
# DHCP lease file
dhcp-leasefile=/var/lib/misc/dnsmasq.leases
# DNS cache size
cache-size=1000
' | sudo tee /etc/dnsmasq.conf > /dev/null
}

# Configure IP forwarding
configure_ip_forwarding() {
    log "Enabling IP forwarding"
    echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward > /dev/null
    # Make permanent
    sudo sed -i '/net.ipv4.ip_forward/d' /etc/sysctl.conf
    echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf > /dev/null
    sudo sysctl -p
}

# Configure iptables for NAT
configure_nat() {
    log "Configuring NAT for wlan0"
    
    # Get the internet-facing interface
    # Assuming it's the default route interface
    INTERNET_IFACE=$(ip route | grep default | awk '{print $5}')
    
    if [ -z "$INTERNET_IFACE" ]; then
        log "Warning: Could not determine internet interface, using eth0 as fallback"
        INTERNET_IFACE="eth0"
    fi
    
    log "Using $INTERNET_IFACE as internet-facing interface"
    
    # Clear existing rules
    sudo iptables -t nat -F POSTROUTING
    
    # Add NAT rule
    sudo iptables -t nat -A POSTROUTING -o $INTERNET_IFACE -j MASQUERADE
    sudo iptables -A FORWARD -i $INTERNET_IFACE -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    sudo iptables -A FORWARD -i wlan0 -o $INTERNET_IFACE -j ACCEPT
    
    # Save rules
    sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"
    
    # Ensure rules are loaded on boot
    if [ ! -f /etc/network/if-pre-up.d/iptables ]; then
        echo '#!/bin/sh
iptables-restore < /etc/iptables.ipv4.nat
exit 0
' | sudo tee /etc/network/if-pre-up.d/iptables > /dev/null
        sudo chmod +x /etc/network/if-pre-up.d/iptables
    fi
}

# Restart services
restart_services() {
    log "Restarting network services"
    sudo systemctl restart dnsmasq
    
    # Check if dhcpcd is available and restart it
    if systemctl list-unit-files | grep -q dhcpcd; then
        log "Restarting dhcpcd service"
        sudo systemctl restart dhcpcd || log "Failed to restart dhcpcd, may not be installed"
    else
        log "dhcpcd service not available"
    fi
    
    # Check if hostapd is active, restart if needed
    if sudo systemctl is-active --quiet hostapd; then
        log "Restarting hostapd service"
        sudo systemctl restart hostapd
    fi
}

# Handle systemd-resolved conflicts
handle_resolved() {
    if sudo systemctl is-active --quiet systemd-resolved; then
        log "Configuring systemd-resolved to not conflict with dnsmasq"
        # Backup original config if not exists
        if [ ! -f /etc/systemd/resolved.conf.original ]; then
            sudo cp /etc/systemd/resolved.conf /etc/systemd/resolved.conf.original
        fi
        
        # Disable stub listener
        sudo sed -i 's/^#DNSStubListener=yes/DNSStubListener=no/' /etc/systemd/resolved.conf
        if ! grep -q "DNSStubListener=no" /etc/systemd/resolved.conf; then
            echo "DNSStubListener=no" | sudo tee -a /etc/systemd/resolved.conf > /dev/null
        fi
        
        # Restart systemd-resolved
        sudo systemctl restart systemd-resolved
    fi
}

# Main execution
log "Starting wlan0 DHCP fix script"

# Run all steps
set_static_ip
update_dhcpcd_conf
configure_dnsmasq
configure_ip_forwarding
configure_nat
handle_resolved
restart_services

log "wlan0 DHCP fix script completed" 