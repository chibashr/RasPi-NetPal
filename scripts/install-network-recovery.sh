#!/bin/bash

# Installation script for Network Recovery Monitor
# This script sets up automatic monitoring and recovery for network IP address loss
# Specifically designed to handle eth0 and other interface IP loss issues

set -e  # Exit on any error

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

echo "Installing Network Recovery Monitor..."

# Define paths
SCRIPT_DIR="/opt/captive/scripts"
LOG_DIR="/var/log/captive"
SERVICE_NAME="network-recovery"

# Create log directory if it doesn't exist
if [ ! -d "$LOG_DIR" ]; then
    echo "Creating log directory: $LOG_DIR"
    mkdir -p "$LOG_DIR"
    chown root:root "$LOG_DIR"
    chmod 755 "$LOG_DIR"
fi

# Make recovery script executable
echo "Setting permissions on recovery script..."
chmod +x "$SCRIPT_DIR/network-recovery-monitor.sh"

# Create systemd service for the network recovery daemon
echo "Creating systemd service..."
cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=Network Recovery Monitor - Automatic IP Recovery
Documentation=man:systemd.service(5)
After=network.target network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=$SCRIPT_DIR/network-recovery-monitor.sh daemon
ExecReload=/bin/kill -HUP \$MAINPID
User=root
Group=root
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=network-recovery

# Resource limits
LimitNOFILE=4096
LimitNPROC=256

# Security settings
NoNewPrivileges=false
PrivateTmp=false
ProtectSystem=false
ProtectHome=false

# Environment
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
EOF

# Create a helper service for manual status checking
cat > "/etc/systemd/system/$SERVICE_NAME-status.service" << EOF
[Unit]
Description=Network Recovery Monitor Status Check
After=network.target

[Service]
Type=oneshot
ExecStart=$SCRIPT_DIR/network-recovery-monitor.sh status
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable the service
echo "Configuring systemd services..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME.service"

# Stop any existing network recovery service
systemctl stop "$SERVICE_NAME.service" 2>/dev/null || true

# Start the new service
echo "Starting Network Recovery Monitor service..."
systemctl start "$SERVICE_NAME.service"

# Wait a moment and check status
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME.service"; then
    echo "✓ Network Recovery Monitor service started successfully"
else
    echo "⚠ Warning: Service may not have started properly"
    systemctl status "$SERVICE_NAME.service" --no-pager -l
fi

# Test the script functionality
echo "Testing recovery script functionality..."
if [ -x "$SCRIPT_DIR/network-recovery-monitor.sh" ]; then
    echo "✓ Recovery script is executable"
    
    # Run a quick status check
    echo "Running initial status check..."
    "$SCRIPT_DIR/network-recovery-monitor.sh" status
else
    echo "✗ ERROR: Recovery script is not executable"
    exit 1
fi

echo ""
echo "Network Recovery Monitor installed successfully!"
echo ""
echo "🔍 MONITORING FEATURES:"
echo "  ✓ Monitors eth0 and other network interfaces every 10 seconds"
echo "  ✓ Detects IP address loss on previously working interfaces"
echo "  ✓ Automatically attempts DHCP recovery when IP loss detected"
echo "  ✓ Tests connectivity and recovers from connectivity loss"
echo "  ✓ Prioritizes eth0 interface (your main concern)"
echo "  ✓ Logs all activities to $LOG_DIR/network-recovery.log"
echo "  ✓ Notifies web interface of network changes"
echo ""
echo "📋 MANAGEMENT COMMANDS:"
echo "  • Check status:       systemctl status $SERVICE_NAME"
echo "  • View logs:          journalctl -u $SERVICE_NAME -f"
echo "  • View recovery log:  tail -f $LOG_DIR/network-recovery.log"
echo "  • Manual status:      $SCRIPT_DIR/network-recovery-monitor.sh status"
echo "  • Stop service:       systemctl stop $SERVICE_NAME"
echo "  • Start service:      systemctl start $SERVICE_NAME"
echo "  • Restart service:    systemctl restart $SERVICE_NAME"
echo ""
echo "🚨 IP LOSS DETECTION:"
echo "  The monitor will detect when eth0 (or other interfaces) lose their IP"
echo "  address and automatically retry DHCP every 10 seconds until recovered."
echo "  It handles both complete IP loss and connectivity loss scenarios."
echo ""
echo "📝 LOGS TO WATCH:"
echo "  • Recovery actions:   tail -f $LOG_DIR/network-recovery.log"
echo "  • Service status:     journalctl -u $SERVICE_NAME -f"
echo "  • Hotplug events:     tail -f $LOG_DIR/network-hotplug.log"
echo ""
echo "To uninstall: systemctl stop $SERVICE_NAME && systemctl disable $SERVICE_NAME"
echo "              rm /etc/systemd/system/$SERVICE_NAME*.service && systemctl daemon-reload" 