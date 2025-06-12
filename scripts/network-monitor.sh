#!/bin/bash

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> /var/log/captive/network-monitor.log
    logger -t "network-monitor" "$1"
}

log "Network monitor starting"

# Check USB network interfaces
check_usb_interfaces() {
    # Get list of USB interfaces
    USB_INTERFACES=$(find /sys/class/net/*/device -lname "*usb*" | awk -F/ '{print $4}')
    
    if [ -z "$USB_INTERFACES" ]; then
        log "No USB network interfaces detected"
        return
    fi
    
    for IFACE in $USB_INTERFACES; do
        log "Checking USB interface $IFACE"
        
        # Skip if interface doesn't exist
        if [ ! -e "/sys/class/net/$IFACE" ]; then
            continue
        fi
        
        # Check interface state
        STATE=$(cat /sys/class/net/$IFACE/operstate 2>/dev/null)
        
        # Check if interface has carrier but is DOWN
        if [ "$STATE" = "down" ]; then
            CARRIER=$(cat /sys/class/net/$IFACE/carrier 2>/dev/null || echo "0")
            if [ "$CARRIER" = "1" ]; then
                log "Interface $IFACE is DOWN but has carrier signal, attempting recovery"
                
                # Try to bring the interface up
                ip link set $IFACE up
                sleep 2
                
                # Check if it has an IP address
                IP=$(ip -4 addr show dev $IFACE 2>/dev/null | grep -oP 'inet \K[0-9.]+')
                if [ -z "$IP" ]; then
                    log "No IP address on $IFACE, requesting DHCP lease"
                    if command -v dhclient >/dev/null 2>&1; then
                        dhclient -v $IFACE
                    else
                        dhcpcd -n $IFACE
                    fi
                    sleep 3
                    
                    # Verify IP assignment
                    IP=$(ip -4 addr show dev $IFACE 2>/dev/null | grep -oP 'inet \K[0-9.]+')
                    if [ -n "$IP" ]; then
                        log "Successfully assigned IP $IP to $IFACE"
                    else
                        log "Failed to assign IP to $IFACE"
                    fi
                else
                    log "Interface $IFACE already has IP $IP"
                fi
            else
                log "Interface $IFACE is DOWN and has no carrier signal"
                
                # Try to reset USB device
                log "Attempting USB device reset for $IFACE"
                USB_PATH=$(readlink -f /sys/class/net/$IFACE/device | grep -o 'usb[0-9]*/[0-9-\.]*')
                if [ -n "$USB_PATH" ]; then
                    log "Found USB path: /sys/bus/$USB_PATH for $IFACE"
                    if [ -e "/sys/bus/$USB_PATH/authorized" ]; then
                        echo 0 > /sys/bus/$USB_PATH/authorized
                        sleep 2
                        echo 1 > /sys/bus/$USB_PATH/authorized
                        log "Reset USB device for $IFACE"
                        sleep 5
                        
                        # Check if interface is up after reset
                        if [ -e "/sys/class/net/$IFACE" ]; then
                            ip link set $IFACE up
                            log "Brought $IFACE up after USB reset"
                        else
                            log "Interface $IFACE no longer exists after USB reset"
                        fi
                    else
                        log "Could not find authorized file for USB reset"
                    fi
                else
                    log "Could not determine USB path for $IFACE"
                fi
            fi
        elif [ "$STATE" = "up" ]; then
            # Check if interface has an IP but no connectivity
            IP=$(ip -4 addr show dev $IFACE 2>/dev/null | grep -oP 'inet \K[0-9.]+')
            if [ -n "$IP" ]; then
                # Test connectivity
                ping -I $IFACE -c 1 -W 2 8.8.8.8 >/dev/null 2>&1
                if [ $? -ne 0 ]; then
                    log "Interface $IFACE has IP $IP but no connectivity, attempting recovery"
                    
                    # Try cycling the interface
                    ip link set $IFACE down
                    sleep 2
                    ip link set $IFACE up
                    sleep 2
                    
                    # Refresh DHCP lease
                    if command -v dhclient >/dev/null 2>&1; then
                        dhclient -v $IFACE
                    else
                        dhcpcd -n $IFACE
                    fi
                else
                    log "Interface $IFACE has IP $IP and connectivity, working correctly"
                fi
            else
                log "Interface $IFACE is UP but has no IP address, requesting DHCP lease"
                if command -v dhclient >/dev/null 2>&1; then
                    dhclient -v $IFACE
                else
                    dhcpcd -n $IFACE
                fi
            fi
        fi
    done
    
    # Notify the UI to refresh
    if [ -S "/tmp/captive.sock" ]; then
        echo '{"action":"refresh_interfaces"}' | nc -U /tmp/captive.sock
    fi
}

# Check all interfaces
check_usb_interfaces

log "Network monitor completed" 