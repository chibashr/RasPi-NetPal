# Application Architecture

The Raspberry Pi Network Control Panel is a Flask-based web application designed to manage Raspberry Pi network settings and services. It provides a responsive web interface that works offline on the Raspberry Pi.

## High-Level Architecture

```
+----------------+       +----------------+       +----------------+
|   Web Browser  | <---> |   Flask App    | <---> | System Services|
|   (Client)     |       |   (Server)     |       | (OS/Hardware)  |
+----------------+       +----------------+       +----------------+
                               ^
                               |
                         +----------------+
                         |    Modules     |
                         | (Functionality)|
                         +----------------+
```

## Component Overview

1. **Flask Application (app.py)**
   - Core application server
   - Handles routing, WebSocket connections, and server-side processing
   - Uses Flask-SocketIO for real-time communication

2. **Blueprints (routes/)**
   - Modular route definitions for different functionality areas
   - Each blueprint handles a specific aspect of the application

3. **Modules (modules/)**
   - Core functionality implementations
   - Separate business logic from route handling
   - Handle interactions with system services and hardware

4. **Templates (templates/)**
   - HTML templates for rendering the user interface
   - Uses Jinja2 templating engine

5. **Static Assets (static/)**
   - CSS for styling
   - JavaScript for client-side functionality
   - Images and other static resources

## Communication Flow

1. **Client-Server Communication**
   - HTTP requests for page loading and form submissions
   - WebSockets for real-time updates and console access
   - JSON for structured data exchange

2. **Server-System Communication**
   - System calls via subprocess module
   - Direct file operations for configuration
   - Hardware monitoring via system libraries

## Deployment

The application is designed to run as a systemd service called 'webpage.service' on a Raspberry Pi. It operates completely offline, providing local network management capabilities without requiring internet access. 