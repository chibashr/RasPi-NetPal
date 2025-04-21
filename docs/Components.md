# System Components

This document details the major components of the Raspberry Pi Network Control Panel and how they interact.

## Core Components

### Application Server (app.py)
- Flask application entry point
- WebSocket initialization and management
- Route registration and blueprint integration
- Session management
- Console worker threading

### Routes (routes/)

The application is organized into modular blueprints:

- **control.py**: Core control panel functionality
- **capture.py**: Network packet capture interface
- **network.py**: Network interface management
- **system.py**: System monitoring and management
- **tools.py**: Utility tools and diagnostics
- **tftp.py**: TFTP server management
- **connection_sharing.py**: Internet connection sharing

Each blueprint handles routing for a specific functional area of the application.

### Modules (modules/)

The business logic is separated into modules:

- **capture.py**: Network packet capture functionality using tcpdump
- **network.py**: Network configuration and monitoring utilities
- **system.py**: System service management and hardware information
- **tools.py**: System diagnostic tools
- **tftp.py**: TFTP server implementation
- **connection_sharing.py**: Internet connection sharing between interfaces
- **logging.py**: Logging configuration and utilities

## Data Flow

1. User requests come through the Flask routing system
2. Routes call appropriate module functions
3. Modules interact with the system through subprocess calls or direct API interactions
4. Results are returned to routes
5. Routes format and return responses to the client

## Directory Structure

```
/
├── app.py                   # Main application entry point
├── gunicorn_config.py       # Gunicorn WSGI server configuration
├── modules/                 # Business logic modules
├── routes/                  # Route blueprints
├── static/                  # Static web assets
│   ├── css/                 # Stylesheets
│   ├── js/                  # JavaScript files
│   └── img/                 # Images
├── templates/               # HTML templates
├── captures/                # Storage for network captures
├── transfers/               # File transfer storage
├── logs/                    # Application logs
└── data/                    # Application data storage
```

## Key Interactions

### WebSocket Console
- Provides live terminal access through the browser
- Implemented in app.py using Flask-SocketIO
- Allows command execution and real-time output

### Packet Capture
- Interfaces with tcpdump through the capture module
- Provides real-time packet capture visualization
- Stores capture files in the captures/ directory

### Network Management
- Configures network interfaces via the network module
- Manages connection sharing between interfaces
- Monitors network status and connectivity

### System Management
- Monitors system resources (CPU, memory, temperature)
- Controls system services through systemd
- Provides hardware information 