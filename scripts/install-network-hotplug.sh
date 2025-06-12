#!/bin/bash

# Installation script for network hotplug detection system
# This script installs udev rules and scripts for automatic network interface detection

set -e  # Exit on any error

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

echo "Installing network hotplug detection system..."

# Define paths
SCRIPT_DIR="/opt/captive/scripts"
UDEV_RULES_DIR="/etc/udev/rules.d"
LOG_DIR="/var/log/captive"

# Create log directory if it doesn't exist
if [ ! -d "$LOG_DIR" ]; then
    echo "Creating log directory: $LOG_DIR"
    mkdir -p "$LOG_DIR"
    chown root:root "$LOG_DIR"
    chmod 755 "$LOG_DIR"
fi

# Make scripts executable
echo "Setting permissions on scripts..."
chmod +x "$SCRIPT_DIR/handle-network-hotplug.sh"
chmod +x "$SCRIPT_DIR/network-monitor.sh"
chmod +x "$SCRIPT_DIR/usb-network-initialize.sh"

# Install udev rule
echo "Installing udev rule..."
cp "$SCRIPT_DIR/99-network-hotplug.rules" "$UDEV_RULES_DIR/"
chown root:root "$UDEV_RULES_DIR/99-network-hotplug.rules"
chmod 644 "$UDEV_RULES_DIR/99-network-hotplug.rules"

# Reload udev rules
echo "Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger

# Test if the hotplug script works
echo "Testing hotplug script..."
if [ -x "$SCRIPT_DIR/handle-network-hotplug.sh" ]; then
    echo "Hotplug script is executable and ready"
else
    echo "ERROR: Hotplug script is not executable"
    exit 1
fi

# Create a systemd service for the network monitor (optional periodic check)
cat > /etc/systemd/system/network-monitor.service << EOF
[Unit]
Description=Network Interface Monitor
After=network.target

[Service]
Type=oneshot
ExecStart=$SCRIPT_DIR/network-monitor.sh
User=root

[Install]
WantedBy=multi-user.target
EOF

# Create a timer for periodic monitoring (every 30 seconds)
cat > /etc/systemd/system/network-monitor.timer << EOF
[Unit]
Description=Run network monitor every 30 seconds
Requires=network-monitor.service

[Timer]
OnCalendar=*:*:0/30
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Enable and start the timer
echo "Setting up periodic network monitoring..."
systemctl daemon-reload
systemctl enable network-monitor.timer
systemctl start network-monitor.timer

echo ""
echo "Network hotplug detection system installed successfully!"
echo ""
echo "Features installed:"
echo "  ✓ Automatic network interface detection via udev rules"
echo "  ✓ Network hotplug handler script"
echo "  ✓ Periodic network monitoring (every 30 seconds)"
echo "  ✓ Logging to $LOG_DIR/network-hotplug.log"
echo ""
echo "You can test the system by:"
echo "  1. Plugging/unplugging an Ethernet cable"
echo "  2. Connecting a USB-to-Ethernet adapter"
echo "  3. Checking logs: tail -f $LOG_DIR/network-hotplug.log"
echo ""
echo "To uninstall, run: $SCRIPT_DIR/uninstall-network-hotplug.sh" 