# Network Hotplug Detection System

## Overview

The Network Hotplug Detection system automatically detects when network cables are plugged into interfaces (especially eth0) and automatically brings them up and configures them. This eliminates the need to manually cycle ports in the web interface when a cable is connected.

## Problem Solved

Previously, when a network cable was plugged into eth0 or other interfaces, the system would detect the physical connection (carrier signal) but the interface would remain in a "DOWN" state, requiring manual intervention through the web interface to cycle the port and activate the connection.

## Solution Implementation

### 1. Udev Rules (`99-network-hotplug.rules`)

The system uses udev rules to detect network interface events:

```bash
# Automatic detection when carrier is detected (cable plugged in)
SUBSYSTEM=="net", ACTION=="change", KERNEL=="eth*", ATTR{carrier}=="1", RUN+="/opt/captive/scripts/handle-network-hotplug.sh %k up"

# Detection for USB network interfaces
SUBSYSTEM=="net", ACTION=="change", KERNEL=="usb*", ATTR{carrier}=="1", RUN+="/opt/captive/scripts/handle-network-hotplug.sh %k up"

# Detection when carrier is lost (cable unplugged)
SUBSYSTEM=="net", ACTION=="change", KERNEL=="eth*", ATTR{carrier}=="0", RUN+="/opt/captive/scripts/handle-network-hotplug.sh %k down"
```

### 2. Hotplug Handler Script (`handle-network-hotplug.sh`)

When a carrier signal is detected, the handler script:

1. **Brings the interface up** if it's administratively down
2. **Requests DHCP lease** if no IP address is assigned
3. **Tests connectivity** to verify the connection works
4. **Logs all actions** for troubleshooting
5. **Notifies the web interface** to refresh display

### 3. Periodic Monitoring

A systemd timer runs network monitoring every 30 seconds as a backup to catch any missed events:

- **Service**: `network-monitor.service`
- **Timer**: `network-monitor.timer`
- **Frequency**: Every 30 seconds

## Installation

### Automatic Installation

Run the installation script with root privileges:

```bash
sudo /opt/captive/scripts/install-network-hotplug.sh
```

This will:
- Install udev rules
- Set up systemd service and timer
- Configure logging
- Make scripts executable
- Test the installation

### Manual Installation

If you prefer manual installation:

1. **Copy udev rules**:
   ```bash
   sudo cp /opt/captive/scripts/99-network-hotplug.rules /etc/udev/rules.d/
   sudo chmod 644 /etc/udev/rules.d/99-network-hotplug.rules
   ```

2. **Make scripts executable**:
   ```bash
   sudo chmod +x /opt/captive/scripts/handle-network-hotplug.sh
   sudo chmod +x /opt/captive/scripts/network-monitor.sh
   ```

3. **Reload udev rules**:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

## Testing

### Test Ethernet Cable

1. **Unplug** an Ethernet cable from eth0
2. **Plug it back in**
3. **Check logs**: `sudo tail -f /var/log/captive/network-hotplug.log`
4. **Verify in web interface** that the interface automatically comes up

### Test USB Network Adapter

1. **Connect** a USB-to-Ethernet adapter
2. **Plug in** an Ethernet cable
3. **Check logs** for automatic configuration
4. **Verify connectivity** in the web interface

## Log Files

The system creates detailed logs in:

- **Hotplug events**: `/var/log/captive/network-hotplug.log`
- **Periodic monitoring**: `/var/log/captive/network-monitor.log`
- **System logs**: `journalctl -t network-hotplug`

### Example Log Output

```
2025-01-21 10:30:15 [HOTPLUG] Network hotplug event: interface=eth0, action=up
2025-01-21 10:30:15 [HOTPLUG] Interface eth0 carrier detected - attempting automatic configuration
2025-01-21 10:30:16 [HOTPLUG] Bringing interface eth0 up
2025-01-21 10:30:16 [HOTPLUG] No IP address on eth0, requesting DHCP lease
2025-01-21 10:30:16 [HOTPLUG] Using dhclient for eth0
2025-01-21 10:30:21 [HOTPLUG] Successfully assigned IP 192.168.1.100 to eth0
2025-01-21 10:30:24 [HOTPLUG] Internet connectivity confirmed on eth0
```

## Troubleshooting

### Interface Not Automatically Coming Up

1. **Check udev rules are installed**:
   ```bash
   ls -la /etc/udev/rules.d/99-network-hotplug.rules
   ```

2. **Verify script permissions**:
   ```bash
   ls -la /opt/captive/scripts/handle-network-hotplug.sh
   ```

3. **Check logs for errors**:
   ```bash
   sudo tail -f /var/log/captive/network-hotplug.log
   ```

4. **Test udev rule manually**:
   ```bash
   sudo udevadm test /sys/class/net/eth0
   ```

### DHCP Not Working

1. **Check if dhclient is available**:
   ```bash
   which dhclient
   ```

2. **Try manual DHCP request**:
   ```bash
   sudo dhclient -v eth0
   ```

3. **Check network configuration**:
   ```bash
   cat /etc/dhcpcd.conf
   ```

### Logs Not Being Created

1. **Check log directory permissions**:
   ```bash
   ls -la /var/log/captive/
   ```

2. **Create log directory manually**:
   ```bash
   sudo mkdir -p /var/log/captive
   sudo chmod 755 /var/log/captive
   ```

## Uninstallation

To remove the hotplug detection system:

```bash
sudo /opt/captive/scripts/uninstall-network-hotplug.sh
```

This will:
- Stop and disable the monitoring timer
- Remove udev rules
- Remove systemd service files
- Reload udev rules

## Integration with Raspberry Pi Network Control Panel

The hotplug system integrates seamlessly with the existing web interface:

1. **Automatic UI refresh** when interfaces change
2. **Status updates** reflected in real-time
3. **No interference** with manual port cycling
4. **Compatible** with existing network management features

## Benefits

- ✅ **Zero manual intervention** required for cable connections
- ✅ **Works with both built-in and USB network interfaces**
- ✅ **Detailed logging** for troubleshooting
- ✅ **Real-time web interface updates**
- ✅ **Fallback periodic monitoring** for reliability
- ✅ **Easy installation and removal**

## Supported Interface Types

- **Ethernet interfaces**: eth0, eth1, etc.
- **USB network adapters**: Automatic detection via udev
- **USB-to-Ethernet dongles**: Full support with carrier detection
- **Built-in interfaces**: Full support for Raspberry Pi Ethernet

This system ensures that the Raspberry Pi Network Control Panel provides a truly plug-and-play experience for network connectivity. 