#!/bin/bash

# Uninstall script for network hotplug detection system

set -e  # Exit on any error

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

echo "Uninstalling network hotplug detection system..."

# Define paths
UDEV_RULES_DIR="/etc/udev/rules.d"

# Stop and disable the timer
echo "Stopping network monitor timer..."
systemctl stop network-monitor.timer 2>/dev/null || true
systemctl disable network-monitor.timer 2>/dev/null || true

# Remove systemd files
echo "Removing systemd service and timer files..."
rm -f /etc/systemd/system/network-monitor.service
rm -f /etc/systemd/system/network-monitor.timer

# Reload systemd
systemctl daemon-reload

# Remove udev rule
echo "Removing udev rule..."
rm -f "$UDEV_RULES_DIR/99-network-hotplug.rules"

# Reload udev rules
echo "Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger

echo ""
echo "Network hotplug detection system uninstalled successfully!"
echo ""
echo "Note: Log files in /var/log/captive/ have been left intact"
echo "Note: Script files in /opt/captive/scripts/ have been left intact" 