#!/bin/bash

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> /var/log/captive/usb-network.log
    logger -t "usb-network" "$1"
}

# Get interface name from environment variable
INTERFACE=$1
if [ -z "$INTERFACE" ]; then
    log "No interface specified, exiting"
    exit 1
fi

log "USB network interface $INTERFACE detected"

# Wait to ensure device is fully initialized
sleep 2

# Check if interface exists
if [ ! -e "/sys/class/net/$INTERFACE" ]; then
    log "Interface $INTERFACE does not exist, exiting"
    exit 1
fi

# Force bring interface down first
log "Bringing down $INTERFACE to reset state"
ip link set $INTERFACE down
sleep 1

# Bring interface up
log "Bringing up $INTERFACE"
ip link set $INTERFACE up
sleep 2

# Check carrier signal
CARRIER=$(cat /sys/class/net/$INTERFACE/carrier 2>/dev/null || echo "0")
if [ "$CARRIER" = "1" ]; then
    log "Carrier detected on $INTERFACE"
    
    # Check if dhclient is available
    if command -v dhclient >/dev/null 2>&1; then
        log "Running dhclient on $INTERFACE"
        dhclient -v $INTERFACE
    else
        # Fallback to dhcpcd
        log "Running dhcpcd on $INTERFACE"
        dhcpcd -n $INTERFACE
    fi
    
    # Wait for IP address assignment
    sleep 3
    
    # Check if IP was assigned
    IP=$(ip -4 addr show dev $INTERFACE | grep -oP 'inet \K[0-9.]+')
    if [ -n "$IP" ]; then
        log "IP address $IP assigned to $INTERFACE"
        
        # Test connectivity
        ping -I $INTERFACE -c 1 -W 2 8.8.8.8 >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            log "Internet connectivity confirmed on $INTERFACE"
        else
            log "No internet connectivity on $INTERFACE"
        fi
    else
        log "No IP address assigned to $INTERFACE"
    fi
else
    log "No carrier detected on $INTERFACE"
fi

# Update the UI via a socket if available
if [ -S "/tmp/captive.sock" ]; then
    echo '{"action":"refresh_interfaces"}' | nc -U /tmp/captive.sock
fi

exit 0 