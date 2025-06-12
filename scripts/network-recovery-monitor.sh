#!/bin/bash

# Network Recovery Monitor
# Monitors for IP address loss on active interfaces and automatically recovers
# Designed to handle random IP address loss on eth0 and other interfaces
# Retries every 10 seconds when IP loss is detected

# Configuration
RETRY_INTERVAL=10
STATE_FILE="/tmp/network-recovery-state"
LOG_FILE="/var/log/captive/network-recovery.log"
RECOVERY_TIMEOUT=300  # 5 minutes before giving up on recovery

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Log function with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [RECOVERY] $1" | tee -a "$LOG_FILE"
    logger -t "network-recovery" "$1"
}

# Function to notify the web interface
notify_ui() {
    if [ -S "/tmp/captive.sock" ]; then
        echo '{"action":"refresh_interfaces"}' | nc -U /tmp/captive.sock 2>/dev/null
    fi
}

# Function to get interface IP address
get_interface_ip() {
    local interface="$1"
    ip -4 addr show dev "$interface" 2>/dev/null | grep -oP 'inet \K[0-9.]+' | head -1
}

# Function to check if interface has carrier
has_carrier() {
    local interface="$1"
    [ -e "/sys/class/net/$interface/carrier" ] && [ "$(cat /sys/class/net/$interface/carrier 2>/dev/null)" = "1" ]
}

# Function to get interface operational state
get_interface_state() {
    local interface="$1"
    cat "/sys/class/net/$interface/operstate" 2>/dev/null || echo "unknown"
}

# Function to test connectivity
test_connectivity() {
    local interface="$1"
    local timeout="${2:-3}"
    
    # Try multiple test targets
    local test_targets=("8.8.8.8" "1.1.1.1" "208.67.222.222")
    
    for target in "${test_targets[@]}"; do
        if ping -I "$interface" -c 1 -W "$timeout" "$target" >/dev/null 2>&1; then
            return 0
        fi
    done
    return 1
}

# Function to attempt DHCP recovery
attempt_dhcp_recovery() {
    local interface="$1"
    
    log "Attempting DHCP recovery for $interface"
    
    # Release current lease if any
    if command -v dhclient >/dev/null 2>&1; then
        dhclient -r "$interface" 2>/dev/null || true
        sleep 1
        log "Requesting new DHCP lease for $interface using dhclient"
        dhclient -v "$interface" 2>&1 | tee -a "$LOG_FILE" &
    elif command -v dhcpcd >/dev/null 2>&1; then
        dhcpcd -k "$interface" 2>/dev/null || true
        sleep 1
        log "Requesting new DHCP lease for $interface using dhcpcd"
        dhcpcd -n "$interface" &
    else
        log "ERROR: No DHCP client available"
        return 1
    fi
    
    # Wait for IP assignment
    local wait_time=0
    while [ $wait_time -lt 15 ]; do
        sleep 1
        local new_ip=$(get_interface_ip "$interface")
        if [ -n "$new_ip" ]; then
            log "Successfully recovered IP $new_ip for $interface"
            return 0
        fi
        wait_time=$((wait_time + 1))
    done
    
    log "DHCP recovery failed for $interface after 15 seconds"
    return 1
}

# Function to attempt interface recovery
attempt_interface_recovery() {
    local interface="$1"
    
    log "Attempting full interface recovery for $interface"
    
    # Bring interface down and up
    ip link set "$interface" down
    sleep 2
    ip link set "$interface" up
    sleep 3
    
    # Check if we now have carrier
    if has_carrier "$interface"; then
        log "Carrier restored for $interface, attempting DHCP"
        attempt_dhcp_recovery "$interface"
        return $?
    else
        log "No carrier signal on $interface after interface reset"
        return 1
    fi
}

# Function to load previous state
load_state() {
    if [ -f "$STATE_FILE" ]; then
        source "$STATE_FILE"
    fi
}

# Function to save current state
save_state() {
    cat > "$STATE_FILE" << EOF
# Network Recovery Monitor State
# Last updated: $(date)
EOF
    
    for interface in $(ls /sys/class/net/ | grep -E '^(eth|enp|wlan|usb)'); do
        if [ -e "/sys/class/net/$interface" ]; then
            local ip=$(get_interface_ip "$interface")
            local state=$(get_interface_state "$interface")
            local carrier=$(has_carrier "$interface" && echo "1" || echo "0")
            
            echo "INTERFACE_${interface}_IP=\"$ip\"" >> "$STATE_FILE"
            echo "INTERFACE_${interface}_STATE=\"$state\"" >> "$STATE_FILE"
            echo "INTERFACE_${interface}_CARRIER=\"$carrier\"" >> "$STATE_FILE"
        fi
    done
}

# Function to check for IP address loss
check_ip_loss() {
    local interface="$1"
    local previous_ip_var="INTERFACE_${interface}_IP"
    local previous_state_var="INTERFACE_${interface}_STATE"
    local recovery_start_var="INTERFACE_${interface}_RECOVERY_START"
    
    local current_ip=$(get_interface_ip "$interface")
    local current_state=$(get_interface_state "$interface")
    local previous_ip="${!previous_ip_var}"
    local previous_state="${!previous_state_var}"
    local recovery_start="${!recovery_start_var}"
    
    # Check if interface was previously working and now lost IP
    if [ -n "$previous_ip" ] && [ "$previous_state" = "up" ] && [ -z "$current_ip" ] && has_carrier "$interface"; then
        log "ALERT: Interface $interface lost IP address (was $previous_ip, now none)"
        
        # Start recovery if not already in progress
        if [ -z "$recovery_start" ]; then
            log "Starting recovery process for $interface"
            export "INTERFACE_${interface}_RECOVERY_START=$(date +%s)"
            notify_ui
        fi
        
        # Check if we've been trying to recover for too long
        local now=$(date +%s)
        local recovery_duration=$((now - ${recovery_start:-$now}))
        
        if [ $recovery_duration -gt $RECOVERY_TIMEOUT ]; then
            log "Recovery timeout reached for $interface ($recovery_duration seconds), resetting recovery"
            unset "INTERFACE_${interface}_RECOVERY_START"
            return 1
        fi
        
        # Attempt recovery
        log "Attempting recovery for $interface (attempt duration: ${recovery_duration}s)"
        if attempt_dhcp_recovery "$interface"; then
            log "Successfully recovered $interface"
            unset "INTERFACE_${interface}_RECOVERY_START"
            notify_ui
            return 0
        else
            log "DHCP recovery failed for $interface, will retry in $RETRY_INTERVAL seconds"
            return 1
        fi
    fi
    
    # Check for connectivity loss on interfaces with IP
    if [ -n "$current_ip" ] && [ "$current_state" = "up" ] && has_carrier "$interface"; then
        if ! test_connectivity "$interface" 2; then
            log "ALERT: Interface $interface ($current_ip) has no connectivity"
            
            # Start recovery if not already in progress
            if [ -z "$recovery_start" ]; then
                log "Starting connectivity recovery for $interface"
                export "INTERFACE_${interface}_RECOVERY_START=$(date +%s)"
                notify_ui
            fi
            
            # Try DHCP renewal
            if attempt_dhcp_recovery "$interface"; then
                log "Successfully restored connectivity for $interface"
                unset "INTERFACE_${interface}_RECOVERY_START"
                notify_ui
                return 0
            else
                return 1
            fi
        else
            # Interface is working, clear any recovery state
            if [ -n "$recovery_start" ]; then
                log "Interface $interface connectivity restored"
                unset "INTERFACE_${interface}_RECOVERY_START"
                notify_ui
            fi
        fi
    fi
    
    return 0
}

# Main monitoring function
monitor_interfaces() {
    load_state
    
    # Priority check for eth0 (most common issue)
    if [ -e "/sys/class/net/eth0" ]; then
        check_ip_loss "eth0"
    fi
    
    # Check other network interfaces
    for interface in $(ls /sys/class/net/ | grep -E '^(enp|ens|wlan|usb)' | head -5); do
        if [ -e "/sys/class/net/$interface" ] && [ "$interface" != "eth0" ]; then
            check_ip_loss "$interface"
        fi
    done
    
    save_state
}

# Main execution
case "${1:-monitor}" in
    "monitor")
        log "Network recovery monitor starting (PID: $$)"
        monitor_interfaces
        log "Network recovery monitor completed"
        ;;
    "daemon")
        log "Network recovery daemon starting (PID: $$)"
        while true; do
            monitor_interfaces
            sleep $RETRY_INTERVAL
        done
        ;;
    "status")
        echo "Network Recovery Monitor Status"
        echo "==============================="
        if [ -f "$STATE_FILE" ]; then
            echo "State file: $STATE_FILE"
            cat "$STATE_FILE"
        else
            echo "No state file found"
        fi
        echo ""
        echo "Recent log entries:"
        tail -10 "$LOG_FILE" 2>/dev/null || echo "No log file found"
        ;;
    *)
        echo "Usage: $0 [monitor|daemon|status]"
        echo "  monitor - Run once and exit"
        echo "  daemon  - Run continuously with $RETRY_INTERVAL second intervals"
        echo "  status  - Show current status and recent logs"
        exit 1
        ;;
esac 