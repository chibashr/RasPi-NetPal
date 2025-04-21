#!/bin/bash
# wlan0_dhcp_service.sh
# This script creates and enables a systemd service to run wlan0_dhcp_fix.sh at boot

echo "Creating wlan0-dhcp-fix.service..."

# Create systemd service file
sudo tee /etc/systemd/system/wlan0-dhcp-fix.service > /dev/null << EOF
[Unit]
Description=WLAN0 DHCP Fix Service
After=network.target hostapd.service dnsmasq.service
Wants=network.target

[Service]
Type=oneshot
ExecStart=/opt/captive/scripts/wlan0_dhcp_fix.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable the service
echo "Enabling wlan0-dhcp-fix.service..."
sudo systemctl enable wlan0-dhcp-fix.service

# Start the service now
echo "Starting wlan0-dhcp-fix.service..."
sudo systemctl start wlan0-dhcp-fix.service

# Check service status
echo "Service status:"
sudo systemctl status wlan0-dhcp-fix.service

echo "Installation complete. The DHCP fix will run automatically on next boot."
echo "You can manually run it anytime with: sudo systemctl restart wlan0-dhcp-fix.service" 