#!/bin/bash

# Uninstallation script for Network Recovery Monitor
# This script removes the automatic network recovery monitoring system

set -e  # Exit on any error

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

echo "Uninstalling Network Recovery Monitor..."

SERVICE_NAME="network-recovery"

# Stop and disable the service
echo "Stopping and disabling service..."
systemctl stop "$SERVICE_NAME.service" 2>/dev/null || true
systemctl disable "$SERVICE_NAME.service" 2>/dev/null || true
systemctl stop "$SERVICE_NAME-status.service" 2>/dev/null || true
systemctl disable "$SERVICE_NAME-status.service" 2>/dev/null || true

# Remove systemd service files
echo "Removing systemd service files..."
rm -f "/etc/systemd/system/$SERVICE_NAME.service"
rm -f "/etc/systemd/system/$SERVICE_NAME-status.service"

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

# Clean up state files
echo "Cleaning up state files..."
rm -f "/tmp/network-recovery-state"

# Note about log files
echo ""
echo "Network Recovery Monitor uninstalled successfully!"
echo ""
echo "📝 NOTE:"
echo "  Log files are preserved at /var/log/captive/network-recovery.log"
echo "  You can safely delete them if no longer needed:"
echo "    rm -f /var/log/captive/network-recovery.log"
echo ""
echo "  The monitoring script file remains at:"
echo "    /opt/captive/scripts/network-recovery-monitor.sh"
echo "  You can delete it manually if no longer needed."
echo ""
echo "✓ Automatic IP recovery monitoring has been removed" 