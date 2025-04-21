# Usage Guide

This guide provides instructions for using the Raspberry Pi Network Control Panel.

## Accessing the Interface

Access the web interface by opening a browser on any device connected to the same network as your Raspberry Pi and navigating to:

```
http://[raspberry-pi-ip-address]:80
```

Replace `[raspberry-pi-ip-address]` with the actual IP address of your Raspberry Pi.

## Main Features

### Dashboard

The dashboard provides an overview of system status including:
- CPU usage
- Memory usage
- Storage usage
- Temperature
- Network interface status
- Running services

### Network Management

#### Interface Configuration

Navigate to the Network section to:
- View all network interfaces
- Configure IP addresses (static or DHCP)
- Enable/disable interfaces
- View connection status

#### Connection Sharing

The connection sharing feature allows you to:
- Share an internet connection between interfaces
- Set up the Raspberry Pi as a network gateway
- Configure NAT and routing

### System Management

#### Service Control

In the Services section, you can:
- View all system services
- Start/stop/restart services
- View service logs
- Configure service autostart

#### System Logs

The Logs section provides access to:
- System logs
- Application logs
- Filtering and search capabilities

### Network Tools

#### Packet Capture

The Capture tool allows you to:
- Capture packets on any interface
- Filter captures by protocol, port, or address
- Download captures for analysis
- View real-time packet information

#### Network Diagnostics

Available diagnostic tools include:
- Ping
- Traceroute
- DNS lookup
- Port scanning

### TFTP Server

The TFTP server feature allows you to:
- Share files via TFTP protocol
- Configure server options
- Monitor file transfers

### Terminal Console

The web-based terminal console allows you to:
- Execute commands directly on the Raspberry Pi
- Navigate the filesystem
- Run scripts
- View command output in real-time

## Tips and Best Practices

### Performance Optimization

- Regularly check system logs for errors
- Clean up old capture files to free storage space
- Restart the application if performance degrades

### Security Considerations

- This application is designed for use on a local network
- No authentication is provided by default
- Consider adding a reverse proxy with authentication for additional security

### Offline Operation

This application operates completely offline. It does not require internet connectivity for any functionality except for sharing an internet connection from one interface to another. 