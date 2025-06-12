# Serial Communication Module

The Serial Communication module provides comprehensive management and interaction capabilities for serial devices connected to your Raspberry Pi. This module enables real-time communication, device management, and external program connectivity.

## Features

### Core Functionality
- **Device Discovery**: Automatically detects USB-to-Serial adapters, Arduino boards, and built-in serial ports
- **Real-time Communication**: WebSocket-based terminal for immediate data exchange
- **Multi-device Support**: Connect to multiple serial devices simultaneously
- **Tab Autocomplete**: Dynamic command completion based on device type
- **Command History**: Navigate through previously sent commands
- **Output Logging**: Download communication logs for analysis

### Advanced Features
- **External Connectivity**: TCP-to-Serial bridge for external program access
- **Device Testing**: Connection verification and troubleshooting tools
- **Baud Rate Management**: Support for common baud rates from 300 to 921600
- **Error Handling**: Comprehensive connection monitoring and recovery

## Supported Devices

The module supports various serial device types:

### USB Serial Devices
- **USB-to-Serial Adapters**: FTDI, CH340, CP2102, etc.
- **Arduino Boards**: Uno, Mega, ESP32, ESP8266
- **Development Boards**: Raspberry Pi Pico, STM32, etc.

### Built-in Serial Ports
- **Raspberry Pi UART**: `/dev/ttyAMA0`, `/dev/ttyS0`
- **USB ACM Devices**: `/dev/ttyACM*`

### Detection Paths
The module scans the following device paths:
- `/dev/ttyUSB*` - USB serial adapters
- `/dev/ttyACM*` - USB CDC ACM devices
- `/dev/ttyS*` - Built-in serial ports
- `/dev/ttyAMA*` - ARM serial ports
- `/dev/serial/by-id/*` - Devices by ID
- `/dev/serial/by-path/*` - Devices by path

## Web Interface

### Navigation
Access the serial communication interface through:
- **Main Menu**: Click "Serial Comm" in the navigation bar
- **Direct URL**: `http://your-pi-ip/serial`

### Interface Layout

#### Device Panel (Left Side)
- **Device List**: Shows all detected serial devices with connection status
- **Connection Controls**: Baud rate selection and connection buttons
- **Device Information**: Shows device path, manufacturer, and description
- **Status Indicators**: Visual connection status with colored indicators

#### Terminal Panel (Right Side)
- **Real-time Terminal**: Black terminal with green text for output
- **Command Input**: Type commands with autocomplete support
- **Terminal Controls**: Clear output, download logs
- **Device Selection**: Shows currently selected device information

### Device Management

#### Connecting to Devices
1. Select a device from the device list
2. Choose appropriate baud rate (common rates: 9600, 115200)
3. Click "Connect" to establish connection
4. Green indicator shows successful connection

#### Device Testing
- Use "Test" button to verify device accessibility
- Checks device permissions and basic communication
- Provides detailed error messages for troubleshooting

#### Disconnection
- Individual disconnect: Select device and click "Disconnect"
- Disconnect all: Click "Disconnect All" to close all connections

### Terminal Features

#### Command Input
- **Enter Key**: Send command to selected device
- **Up/Down Arrows**: Navigate command history
- **Tab Key**: Trigger autocomplete suggestions
- **Real-time Input**: Type and see suggestions as you type

#### Autocomplete System
The autocomplete system provides:
- **Common Commands**: Standard Linux/Unix commands
- **Device-specific Commands**: Commands based on detected device type
- **Context-aware Suggestions**: Relevant completions for current input

#### Output Display
- **Timestamped Output**: Each line shows timestamp and data type
- **Color-coded Messages**:
  - Green: Normal output and success messages
  - Red: Error messages
  - Yellow: Warning messages
  - Blue: Information messages
  - Yellow: Commands sent

#### Log Management
- **Download Logs**: Save communication history to text file
- **Clear Terminal**: Remove all output from display
- **Persistent History**: Command history maintained during session

## External Program Connectivity

### TCP-to-Serial Bridge

The serial bridge script allows external programs to connect to serial devices via TCP sockets.

#### Usage
```bash
# Basic usage
python3 scripts/serial_bridge.py --device /dev/ttyUSB0 --baudrate 9600 --port 9000

# Advanced usage with multiple clients
python3 scripts/serial_bridge.py -d /dev/ttyUSB0 -b 115200 -p 9001 -m 5
```

#### Parameters
- `--device, -d`: Serial device path (required)
- `--baudrate, -b`: Baud rate (default: 9600)
- `--port, -p`: TCP port for bridge (default: 9000)
- `--max-clients, -m`: Maximum concurrent clients (default: 10)
- `--status-interval, -s`: Status report interval in seconds

#### Connecting External Programs

##### Using Telnet
```bash
telnet localhost 9000
```

##### Using Python
```python
import socket

# Connect to bridge
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('localhost', 9000))

# Send data
sock.send(b'AT\r\n')

# Receive data
response = sock.recv(1024)
print(response.decode())

sock.close()
```

##### Using Node.js
```javascript
const net = require('net');

const client = new net.Socket();
client.connect(9000, 'localhost', () => {
    console.log('Connected to serial bridge');
    client.write('AT\r\n');
});

client.on('data', (data) => {
    console.log('Received:', data.toString());
});

client.on('close', () => {
    console.log('Connection closed');
});
```

### Bridge Features
- **Multiple Clients**: Multiple programs can connect simultaneously
- **Data Broadcasting**: All clients receive serial output
- **Statistics**: Connection statistics and data transfer monitoring
- **Auto-reconnect**: Handles serial device disconnections gracefully

## API Endpoints

### Device Management
- `GET /serial/devices` - List available devices
- `GET /serial/connected_devices` - List connected devices
- `GET /serial/baudrates` - Get supported baud rates
- `POST /serial/connect` - Connect to device
- `POST /serial/disconnect` - Disconnect from device
- `POST /serial/disconnect_all` - Disconnect all devices
- `POST /serial/test_device` - Test device connection

### Communication
- `POST /serial/send_command` - Send command to device
- `GET /serial/device_output/<device_path>` - Get device output
- `GET /serial/download_output/<device_path>` - Download output log

### WebSocket Events
- **Namespace**: `/serial`
- **Events**:
  - `connect` - Client connection
  - `device_list` - Device list updates
  - `serial_output` - Real-time output
  - `send_command` - Send command
  - `refresh_devices` - Refresh device list

## Common Use Cases

### Arduino Development
1. Connect Arduino via USB
2. Select device (usually `/dev/ttyACM0` or `/dev/ttyUSB0`)
3. Set baud rate to 9600 or 115200
4. Use Serial Monitor functionality through web interface

### ESP32/ESP8266 Development
1. Connect ESP board via USB
2. Select appropriate device
3. Set baud rate to 115200
4. Monitor debug output and send AT commands

### IoT Device Communication
1. Connect IoT device via USB-to-Serial adapter
2. Configure appropriate baud rate
3. Send configuration commands
4. Monitor sensor data output

### Debugging Embedded Systems
1. Connect UART pins to USB-to-Serial adapter
2. Use bridge script for external debugger access
3. Monitor system logs and debug output
4. Send debug commands in real-time

## Troubleshooting

### Device Not Detected
1. Check physical connections
2. Verify device is powered
3. Check USB cable functionality
4. Refresh device list
5. Check system logs: `dmesg | grep tty`

### Permission Denied
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Set device permissions
sudo chmod 666 /dev/ttyUSB0

# Restart application
sudo systemctl restart webpage.service
```

### Connection Failed
1. Verify correct baud rate
2. Check if device is in use by another program
3. Test device with system tools:
   ```bash
   # Test with screen
   screen /dev/ttyUSB0 9600
   
   # Test with minicom
   minicom -D /dev/ttyUSB0 -b 9600
   ```

### Bridge Connection Issues
1. Check if TCP port is available: `netstat -ln | grep :9000`
2. Verify firewall settings
3. Check bridge script logs
4. Ensure serial device is accessible

## Security Considerations

### Access Control
- Serial communication requires appropriate user permissions
- Bridge script should be run with minimal privileges
- Consider firewall rules for TCP bridge ports

### Data Security
- Serial communication is unencrypted
- Sensitive data should be protected at application level
- Monitor bridge connections for unauthorized access

## Dependencies

### Python Packages
- `pyserial` - Serial communication library
- `flask` - Web framework
- `flask-socketio` - WebSocket support
- `eventlet` - Async framework

### System Requirements
- Linux with USB support
- Serial device drivers (usually included)
- Python 3.6 or higher

## Installation Notes

The serial communication module is automatically installed with the main application. To install dependencies manually:

```bash
# Install Python dependencies
pip install pyserial

# Make bridge script executable
chmod +x scripts/serial_bridge.py

# Restart application
sudo systemctl restart webpage.service
```

## Future Enhancements

### Planned Features
- **File Transfer**: XMODEM/YMODEM support for file transfers
- **Protocol Analysis**: Built-in protocol analyzers for common serial protocols
- **Scripting Support**: Automated command sequences and testing
- **Advanced Autocomplete**: Learn from device responses for better suggestions
- **Session Recording**: Record and replay communication sessions
- **Multi-baud Detection**: Automatic baud rate detection
- **Hardware Flow Control**: RTS/CTS and DTR/DSR support

### Integration Opportunities
- **Network Tools**: Integration with network scanning and monitoring
- **System Monitoring**: Link with system performance metrics
- **Logging System**: Enhanced integration with application logging
- **Documentation**: Auto-generation of device communication docs

## Support

For issues, feature requests, or questions about the serial communication module:

1. Check the troubleshooting section above
2. Review system logs for error messages
3. Test with standard system tools to isolate issues
4. Use the application's issue reporting feature
5. Consult the main application documentation

The serial communication module is designed to be robust and user-friendly, providing professional-grade serial communication capabilities through an intuitive web interface. 