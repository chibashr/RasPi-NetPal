#!/bin/bash

# Network interface hotplug handler
# Called by udev rules when network interfaces are connected/disconnected
# Parameters: $1 = interface name, $2 = action (up/down/add)

INTERFACE="$1"
ACTION="$2"

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [HOTPLUG] $1" >> /var/log/captive/network-hotplug.log
    logger -t "network-hotplug" "$1"
}

# Function to notify the web interface
notify_ui() {
    if [ -S "/tmp/captive.sock" ]; then
        echo '{"action":"refresh_interfaces"}' | nc -U /tmp/captive.sock 2>/dev/null
    fi
}

log "Network hotplug event: interface=$INTERFACE, action=$ACTION"

case "$ACTION" in
    "up"|"add")
        log "Interface $INTERFACE carrier detected - attempting automatic configuration"
        
        # Wait a moment for the interface to stabilize
        sleep 1
        
        # Check if interface exists
        if [ ! -e "/sys/class/net/$INTERFACE" ]; then
            log "Interface $INTERFACE does not exist, exiting"
            exit 1
        fi
        
        # Bring interface up if it's down
        CURRENT_STATE=$(cat /sys/class/net/$INTERFACE/operstate 2>/dev/null || echo "unknown")
        if [ "$CURRENT_STATE" = "down" ]; then
            log "Bringing interface $INTERFACE up"
            ip link set "$INTERFACE" up
            sleep 2
        fi
        
        # Check if interface already has an IP address
        CURRENT_IP=$(ip -4 addr show dev "$INTERFACE" 2>/dev/null | grep -oP 'inet \K[0-9.]+' | head -1)
        
        if [ -z "$CURRENT_IP" ]; then
            log "No IP address on $INTERFACE, requesting DHCP lease"
            
            # Try dhclient first, fallback to dhcpcd
            if command -v dhclient >/dev/null 2>&1; then
                log "Using dhclient for $INTERFACE"
                dhclient -v "$INTERFACE" &
            elif command -v dhcpcd >/dev/null 2>&1; then
                log "Using dhcpcd for $INTERFACE"
                dhcpcd -n "$INTERFACE" &
            else
                log "No DHCP client available"
            fi
            
            # Wait for IP assignment
            sleep 5
            
            # Check if IP was assigned
            NEW_IP=$(ip -4 addr show dev "$INTERFACE" 2>/dev/null | grep -oP 'inet \K[0-9.]+' | head -1)
            if [ -n "$NEW_IP" ]; then
                log "Successfully assigned IP $NEW_IP to $INTERFACE"
                
                # Test connectivity
                if ping -I "$INTERFACE" -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
                    log "Internet connectivity confirmed on $INTERFACE"
                else
                    log "No internet connectivity on $INTERFACE (this may be normal)"
                fi
            else
                log "Failed to assign IP to $INTERFACE"
            fi
        else
            log "Interface $INTERFACE already has IP $CURRENT_IP"
            
            # Test existing connectivity
            if ping -I "$INTERFACE" -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
                log "Existing connectivity on $INTERFACE working correctly"
            else
                log "Existing connection on $INTERFACE has no internet (may be normal)"
            fi
        fi
        ;;
        
    "down")
        log "Interface $INTERFACE carrier lost (cable unplugged)"
        ;;
        
    *)
        log "Unknown action: $ACTION"
        ;;
esac

# Always notify the UI to refresh interface status
notify_ui

log "Network hotplug handler completed for $INTERFACE ($ACTION)" 