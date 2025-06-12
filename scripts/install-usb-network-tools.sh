#!/bin/bash

# This script installs the USB network handling components

echo "Installing USB network tools..."

# Create log directory if it doesn't exist
mkdir -p /var/log/captive
touch /var/log/captive/usb-network.log
touch /var/log/captive/network-monitor.log
chmod 644 /var/log/captive/usb-network.log
chmod 644 /var/log/captive/network-monitor.log

# Make the scripts executable
chmod +x /opt/captive/scripts/usb-network-initialize.sh
chmod +x /opt/captive/scripts/network-monitor.sh

# Install udev rules
echo "Installing udev rules..."
cp /opt/captive/scripts/90-usb-network.rules /etc/udev/rules.d/
# Reload udev rules
udevadm control --reload-rules
udevadm trigger

# Install systemd service and timer for network monitoring
echo "Installing systemd services..."
cp /opt/captive/scripts/captive-network-monitor.service /etc/systemd/system/
cp /opt/captive/scripts/captive-network-monitor.timer /etc/systemd/system/

# Enable and start the timer
systemctl daemon-reload
systemctl enable captive-network-monitor.timer
systemctl start captive-network-monitor.timer

echo "USB network tools installed successfully"
echo "To manually cycle a USB interface, use the cycle button in the web interface"
echo "To monitor logs, use: tail -f /var/log/captive/usb-network.log"

# Run the network monitor once to detect any current USB interfaces
/opt/captive/scripts/network-monitor.sh

exit 0 