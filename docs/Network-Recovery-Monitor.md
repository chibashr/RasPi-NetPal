# Network Recovery Monitor

## Overview

The Network Recovery Monitor is an advanced monitoring and recovery system designed to automatically detect and recover from network interface IP address loss. This system specifically addresses the common issue where Ethernet interfaces (particularly `eth0`) randomly lose their IP addresses, requiring manual intervention to restore connectivity.

## Problem Solved

- **Random IP Address Loss**: Interfaces losing their DHCP-assigned IP addresses
- **Connectivity Interruption**: Loss of network connectivity despite physical connection
- **Manual Recovery Required**: Previously required manual port cycling through web interface
- **Service Interruption**: Loss of connection to the Raspberry Pi control panel

## Features

### Core Monitoring
- **Continuous Monitoring**: Checks interface status every 10 seconds
- **Priority Interface Support**: Prioritizes `eth0` monitoring (most common issue)
- **Multi-Interface Support**: Monitors `eth0`, `enp*`, `ens*`, `wlan*`, and USB network interfaces
- **State Persistence**: Remembers previous interface states to detect changes

### Detection Capabilities
- **IP Address Loss Detection**: Detects when interfaces lose their IP addresses
- **Connectivity Loss Detection**: Identifies when interfaces have IP but no connectivity
- **Carrier Signal Monitoring**: Verifies physical connection status
- **Interface State Tracking**: Monitors operational state changes

### Recovery Mechanisms
- **Automatic DHCP Recovery**: Releases and renews DHCP leases automatically
- **Interface Reset**: Brings interfaces down/up when needed
- **Multiple DHCP Client Support**: Works with both `dhclient` and `dhcpcd`
- **Timeout Protection**: Prevents infinite recovery loops (5-minute timeout)

### Logging and Notifications
- **Comprehensive Logging**: Detailed logs of all monitoring and recovery actions
- **Web Interface Notifications**: Notifies the web UI of network changes
- **SystemD Journal Integration**: Logs to both files and systemd journal
- **Recovery Status Tracking**: Tracks recovery attempts and success rates

## Installation

### Automatic Installation
```bash
sudo /opt/captive/scripts/install-network-recovery.sh
```

### Manual Installation
1. Make the script executable:
   ```bash
   sudo chmod +x /opt/captive/scripts/network-recovery-monitor.sh
   ```

2. Create the systemd service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable network-recovery
   sudo systemctl start network-recovery
   ```

3. Verify installation:
   ```bash
   sudo systemctl status network-recovery
   ```

## Configuration

### Default Settings
- **Monitoring Interval**: 10 seconds
- **Recovery Timeout**: 5 minutes
- **Log Location**: `/var/log/captive/network-recovery.log`
- **State File**: `/tmp/network-recovery-state`

### Customization
To modify the monitoring interval, edit the script:
```bash
sudo nano /opt/captive/scripts/network-recovery-monitor.sh
```

Change the `RETRY_INTERVAL` variable:
```bash
RETRY_INTERVAL=10  # seconds between checks
```

## Usage

### Service Management
```bash
# Check service status
sudo systemctl status network-recovery

# Start the service
sudo systemctl start network-recovery

# Stop the service
sudo systemctl stop network-recovery

# Restart the service
sudo systemctl restart network-recovery

# View service logs
sudo journalctl -u network-recovery -f
```

### Manual Operations
```bash
# Run a single monitoring check
sudo /opt/captive/scripts/network-recovery-monitor.sh monitor

# Run in daemon mode (continuous monitoring)
sudo /opt/captive/scripts/network-recovery-monitor.sh daemon

# Check current status and recent activity
sudo /opt/captive/scripts/network-recovery-monitor.sh status
```

### Log Monitoring
```bash
# Watch recovery logs in real-time
sudo tail -f /var/log/captive/network-recovery.log

# View recent recovery activity
sudo tail -20 /var/log/captive/network-recovery.log

# Search for specific interface issues
sudo grep "eth0" /var/log/captive/network-recovery.log
```

## How It Works

### Monitoring Process
1. **State Loading**: Loads previous interface states from state file
2. **Interface Scanning**: Checks `eth0` first, then other network interfaces
3. **Change Detection**: Compares current state with previous state
4. **Issue Detection**: Identifies IP loss or connectivity problems
5. **Recovery Execution**: Attempts appropriate recovery actions
6. **State Saving**: Updates state file with current interface status

### Recovery Process
1. **DHCP Release**: Releases current DHCP lease if present
2. **DHCP Request**: Requests new DHCP lease from server
3. **IP Verification**: Confirms IP address assignment
4. **Connectivity Test**: Tests internet connectivity
5. **Success/Failure Logging**: Records recovery outcome
6. **UI Notification**: Notifies web interface of changes

### Detection Logic
```
IF interface had IP address previously AND
   interface is in UP state AND
   interface has carrier signal AND
   interface has no IP address now
THEN
   Start recovery process
```

## Log Analysis

### Log Format
```
2025-01-21 15:30:45 [RECOVERY] Network recovery monitor starting (PID: 1234)
2025-01-21 15:30:46 [RECOVERY] ALERT: Interface eth0 lost IP address (was 192.168.1.100, now none)
2025-01-21 15:30:46 [RECOVERY] Starting recovery process for eth0
2025-01-21 15:30:46 [RECOVERY] Attempting DHCP recovery for eth0
2025-01-21 15:30:47 [RECOVERY] Requesting new DHCP lease for eth0 using dhclient
2025-01-21 15:30:52 [RECOVERY] Successfully recovered IP 192.168.1.101 for eth0
```

### Key Log Messages
- `ALERT: Interface X lost IP address`: IP address loss detected
- `Starting recovery process`: Recovery initiated
- `Successfully recovered IP`: Recovery successful
- `DHCP recovery failed`: Recovery attempt failed
- `Recovery timeout reached`: Giving up after 5 minutes

## Troubleshooting

### Service Won't Start
1. Check service status:
   ```bash
   sudo systemctl status network-recovery
   ```

2. Check logs for errors:
   ```bash
   sudo journalctl -u network-recovery
   ```

3. Verify script permissions:
   ```bash
   ls -la /opt/captive/scripts/network-recovery-monitor.sh
   ```

### Recovery Not Working
1. Check if DHCP client is available:
   ```bash
   which dhclient || which dhcpcd
   ```

2. Test manual DHCP:
   ```bash
   sudo dhclient eth0
   ```

3. Check network configuration:
   ```bash
   ip addr show eth0
   ip route show
   ```

### Frequent Recovery Attempts
1. Check network infrastructure:
   - Router/switch stability
   - Cable quality
   - Network load

2. Review logs for patterns:
   ```bash
   sudo grep "ALERT" /var/log/captive/network-recovery.log
   ```

3. Consider adjusting monitoring interval

## Integration

### Web Interface Integration
The monitor automatically notifies the web interface when network changes occur:
```bash
echo '{"action":"refresh_interfaces"}' | nc -U /tmp/captive.sock
```

### Existing Hotplug System
Works alongside the existing network hotplug detection system:
- **Hotplug System**: Handles cable plug/unplug events
- **Recovery Monitor**: Handles IP address loss on connected interfaces

### System Requirements
- **Root Privileges**: Required for network interface management
- **DHCP Client**: `dhclient` or `dhcpcd` must be available
- **SystemD**: Service management
- **Network Tools**: `ip`, `ping`, `nc` commands

## Performance Impact

### Resource Usage
- **CPU**: Minimal (brief checks every 10 seconds)
- **Memory**: Low (small bash script)
- **Network**: Minimal (single ping per interface when testing)
- **Disk**: Low (log file growth only during recovery events)

### Optimization
- Prioritizes `eth0` interface for fastest response
- Limits to 5 interfaces maximum to prevent excessive checking
- Uses efficient bash operations for status checks
- Implements timeout protection to prevent resource waste

## Uninstallation

### Automatic Uninstallation
```bash
sudo /opt/captive/scripts/uninstall-network-recovery.sh
```

### Manual Uninstallation
```bash
# Stop and disable service
sudo systemctl stop network-recovery
sudo systemctl disable network-recovery

# Remove service files
sudo rm /etc/systemd/system/network-recovery*.service
sudo systemctl daemon-reload

# Clean up state files
sudo rm -f /tmp/network-recovery-state

# Optionally remove logs
sudo rm -f /var/log/captive/network-recovery.log
```

## Best Practices

### Monitoring
- Monitor logs regularly for recovery patterns
- Check service status after system updates
- Review connectivity issues that might indicate infrastructure problems

### Maintenance
- Restart service after network configuration changes
- Check log file size periodically
- Verify DHCP server configuration if frequent recoveries occur

### Debugging
- Use `status` command for quick health checks
- Monitor both recovery logs and systemd journal
- Test manual recovery procedures if automatic recovery fails

## Advanced Configuration

### Custom Interface Priority
Edit the script to change interface priority:
```bash
# Priority check for custom interface
if [ -e "/sys/class/net/enp0s3" ]; then
    check_ip_loss "enp0s3"
fi
```

### Extended Monitoring
To monitor additional interface types, modify the interface pattern:
```bash
for interface in $(ls /sys/class/net/ | grep -E '^(eth|enp|ens|wlan|usb|br)' | head -10); do
```

### Recovery Customization
Adjust recovery parameters:
```bash
RECOVERY_TIMEOUT=600    # 10 minutes instead of 5
RETRY_INTERVAL=5       # 5 seconds instead of 10
```

## Security Considerations

- Runs with root privileges (required for network management)
- Logs may contain network information
- State file contains interface history
- Service can be controlled only by root/sudo users

## Version History

- **v1.0**: Initial implementation with 10-second monitoring
- Designed specifically for eth0 IP address loss recovery
- Integrates with existing Raspberry Pi Network Control Panel 