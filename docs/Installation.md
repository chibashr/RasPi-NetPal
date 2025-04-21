# Installation Guide (THIS IS PREINSTALLED AND THIS DOES NOT HAVE TO BE DONE)

This guide describes how to install and configure the Raspberry Pi Network Control Panel on a Raspberry Pi.

## Prerequisites

- Raspberry Pi 5 (or compatible) with Raspbian installed
- Python 3.6 or higher
- Network connectivity for initial setup

## Installation Steps

### 1. Clone the Repository (DOES NOT EXIST YET)

```bash
git clone https://github.com/yourusername/raspberry-pi-network-control.git
cd raspberry-pi-network-control
```

### 2. Install Dependencies

```bash
# Install required system packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev tcpdump tshark git python3-numpy

# Install Python dependencies
pip3 install -r requirements.txt
```

If no requirements.txt exists, install the following packages:

```bash
pip3 install flask flask-socketio eventlet gunicorn
```

### 3. Set Up System Service

Create a systemd service file to run the application as a service:

```bash
sudo nano /etc/systemd/system/webpage.service
```

Add the following content:

```ini
[Unit]
Description=Raspberry Pi Network Control Panel
After=network.target

[Service]
User=pi
WorkingDirectory=/path/to/raspberry-pi-network-control
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Replace `/path/to/raspberry-pi-network-control` with the actual path to the cloned repository.

### 4. Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable webpage.service
sudo systemctl start webpage.service
```

### 5. Verify Installation

Check the status of the service:

```bash
sudo systemctl status webpage.service
```

## Access the Web Interface

Once installed, you can access the web interface by opening a browser and navigating to:

```
http://[raspberry-pi-ip-address]:80
```

Where `[raspberry-pi-ip-address]` is the IP address of your Raspberry Pi.

## Troubleshooting

### Service Not Starting

Check the logs for errors:

```bash
journalctl -u webpage.service
```

### Permission Issues

If you encounter permission issues, make sure the user running the service has appropriate permissions for network configuration and service management.

### Port Already in Use

If port 80 is already in use, modify the port in app.py or configure the service to use a different port. 