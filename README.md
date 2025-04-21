# Raspberry Pi Network Control Panel

A web-based control panel for managing Raspberry Pi network settings and services.

## Features

- View and configure network interfaces
- Monitor and restart system services
- View system logs
- Monitor listening ports
- View connected USB devices
- VNC client for remote desktop connections

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/raspberry-pi-network-control.git
   cd raspberry-pi-network-control
   ```

2. Install required dependencies:
   ```
   pip install flask websockify requests
   ```

3. For VNC functionality, you'll need noVNC (downloaded automatically on first run) and websockify:
   ```
   sudo apt-get install git python3-numpy
   ```

For detailed installation instructions, see [Installation Guide](docs/Installation.md).

## Running the application

1. Start the application:
   ```
   sudo python app.py
   ```
   Note: Sudo is required for network configuration and service management.

2. Access the web interface by opening a browser and navigating to:
   ```
   http://your-raspberry-pi-ip:80
   ```

For detailed usage instructions, see [Usage Guide](docs/Usage.md).

## Project Structure

- `app.py` - Main application file
- `modules/` - Contains modular components:
  - `network.py` - Network interface management
  - `system.py` - System services and hardware info
  - `logging.py` - Logging functionality
  - `capture.py` - Packet capture functionality
- `static/` - Static assets:
  - `css/style.css` - Styling
  - `js/main.js` - JavaScript functionality
  - `js/vnc.js` - VNC client functionality
- `templates/` - HTML templates:
  - `index.html` - Main interface
  - `capture.html` - Network capture
  - `vnc.html` - VNC client

For a detailed overview of the application architecture, see [Architecture Documentation](docs/Architecture.md).
For detailed component information, see [Component Documentation](docs/Components.md).

## Offline Usage

This application is designed to work completely offline. All resources are served locally from the Raspberry Pi.

## Service Management

The application runs as a systemd service named 'webpage.service'. You can manage it with:

```bash
# Start the service
sudo systemctl start webpage.service

# Stop the service
sudo systemctl stop webpage.service

# Check status
sudo systemctl status webpage.service

# Enable at boot
sudo systemctl enable webpage.service
```

## Documentation

Complete documentation is available in the [docs](docs/) directory:

- [Architecture Overview](docs/Architecture.md)
- [Component Details](docs/Components.md)
- [Installation Guide](docs/Installation.md)
- [Usage Guide](docs/Usage.md) 