# Enhanced Services Dashboard

## Overview

The Enhanced Services Dashboard provides comprehensive monitoring and management of system services with detailed information views, including special attention to critical services like AnyDesk for remote access.

## Features Added

### 1. Service Details View

Each service now has a "Details" button that provides comprehensive information:

#### Overview Tab
- **Service Name**: The systemd service name
- **Current Status**: Active, inactive, failed, etc.
- **Auto-start Configuration**: Whether the service starts automatically
- **User Context**: Which user the service runs as
- **Working Directory**: Service execution directory
- **Executable Path**: Full command line being executed

#### Status Tab
- **Full systemctl status output**: Complete status information
- **Process ID (PID)**: If the service is running
- **Memory Usage**: Current memory consumption
- **Start Time**: When the service was last started
- **Service Dependencies**: Related services

#### Logs Tab
- **Recent Service Logs**: Last 20 log entries
- **Real-time Logging**: Recent journal entries for the service
- **Error Highlighting**: Errors and warnings are clearly marked
- **Timestamp Information**: When events occurred

#### Configuration Tab
- **Unit File Settings**: Key configuration parameters
- **Environment Variables**: Service environment settings
- **Restart Policies**: How the service handles failures
- **Security Settings**: User, group, and permission settings

### 2. Enhanced Service Information

The main services table now shows:

- **Service Name**: Clear identification
- **Status Badge**: Color-coded status indicators
  - 🟢 **Active**: Service is running normally
  - 🔴 **Inactive**: Service is stopped
  - 🟡 **Failed**: Service has failed
  - 🟣 **Other**: Unknown or transitional states

- **Additional Info**: 
  - Auto-start status (Enabled/Disabled)
  - Memory usage when available
  - Process ID for running services

### 3. AnyDesk Integration

Special support for AnyDesk remote access service:

- **Automatic Detection**: AnyDesk is automatically included in the service list
- **Priority Monitoring**: AnyDesk status is prominently displayed
- **Remote Access Critical**: System recognizes AnyDesk as essential for remote management
- **Detailed Configuration**: View AnyDesk-specific settings and logs

## Service Management

### Restart Services

All services can be restarted through the web interface:

1. **Click "Restart"** on any service
2. **Confirm the action** in the dialog
3. **Monitor progress** with loading indicators
4. **View results** with success/error messages

### View Service Details

1. **Click "Details"** for any service
2. **Browse tabs** for different information types
3. **View real-time data** updated from the system
4. **Close details** by clicking "Details" again

## Supported Services

The system automatically detects and monitors:

### Core System Services
- **SSH**: Secure shell access
- **dhcpcd**: DHCP client daemon
- **networking**: Network management

### Web Services
- **nginx**: Web server
- **apache2**: Alternative web server
- **webpage**: The captive portal application itself

### Remote Access Services
- **AnyDesk**: Remote desktop access (priority monitoring)
- **vncserver-x11-serviced**: VNC server
- **realvnc-vnc-server**: RealVNC server
- **xrdp**: Remote desktop protocol

### Network Services
- **dnsmasq**: DNS and DHCP server
- **hostapd**: Access point daemon

## AnyDesk Special Considerations

AnyDesk is treated as a critical service because:

1. **Remote Access**: Essential for headless Raspberry Pi management
2. **Connectivity**: Allows access even when SSH fails
3. **GUI Access**: Provides desktop environment access
4. **Troubleshooting**: Critical for diagnosing network issues

### AnyDesk Monitoring

The system provides enhanced monitoring for AnyDesk:

- **Status Alerts**: Clear indication when AnyDesk is not running
- **Quick Restart**: One-click restart capability
- **Configuration Access**: View AnyDesk settings and logs
- **Connection Monitoring**: Track AnyDesk connection attempts

### AnyDesk Troubleshooting

Common AnyDesk issues and solutions:

#### Service Not Starting
1. **Check Details Tab**: Look for error messages
2. **View Logs**: Check for permission or configuration issues
3. **Restart Service**: Use the restart button
4. **Manual Check**: SSH in and run `sudo systemctl status anydesk`

#### No Remote Connections
1. **Verify Service Status**: Ensure AnyDesk is active
2. **Check Network**: Ensure internet connectivity
3. **Firewall Settings**: Check if ports are blocked
4. **AnyDesk ID**: Verify the AnyDesk ID hasn't changed

## Interface Features

### Responsive Design
- **Mobile Friendly**: Works on tablets and phones
- **Tab Navigation**: Easy switching between information types
- **Collapsible Details**: Hide/show detailed information
- **Real-time Updates**: Status refreshes automatically

### Dark Mode Support
- **Theme Consistency**: Service details respect dark mode settings
- **Readable Logs**: Log output optimized for both light and dark themes
- **Color-coded Status**: Status badges work in both themes

## API Endpoints

The enhanced services dashboard uses these endpoints:

### Get Service List
```
GET /get_updates
Returns: Array of services with basic information
```

### Get Service Details
```
GET /get_service_details/<service_name>
Returns: Detailed service information including logs and configuration
```

### Restart Service
```
POST /restart_service/<service_name>
Returns: Success/failure status and updated service list
```

## Logging and Monitoring

### Service Activity Logs

All service management actions are logged:

- **Service restarts**: When and by whom
- **Status changes**: Automatic detection of status changes
- **Error conditions**: Failed operations and reasons
- **Configuration changes**: When service settings are modified

### Performance Impact

The enhanced monitoring is designed to be lightweight:

- **Cached Data**: Service information is cached between requests
- **Efficient Updates**: Only changed services trigger updates
- **Background Processing**: Heavy operations run asynchronously
- **Rate Limiting**: Prevents excessive system calls

## Benefits

### For System Administrators
- ✅ **Comprehensive Monitoring**: Complete view of all system services
- ✅ **Quick Diagnostics**: Rapid identification of service issues
- ✅ **Remote Management**: Full service control via web interface
- ✅ **Detailed Logging**: Complete audit trail of service activities

### For Remote Access
- ✅ **AnyDesk Priority**: Ensures remote access remains available
- ✅ **Multi-protocol Support**: VNC, RDP, and AnyDesk monitoring
- ✅ **Quick Recovery**: Fast restart capabilities for failed services
- ✅ **Status Visibility**: Clear indication of remote access availability

### For Troubleshooting
- ✅ **Detailed Logs**: Access to service logs without SSH
- ✅ **Configuration Viewing**: See service settings through web interface
- ✅ **Real-time Status**: Live updates of service conditions
- ✅ **Error Diagnosis**: Clear error messages and troubleshooting info

## Integration with Network Control Panel

The enhanced services dashboard integrates seamlessly with other features:

- **Network Services**: Monitor network-related services alongside interfaces
- **System Health**: Service status contributes to overall system monitoring
- **Automated Recovery**: Failed services can trigger automatic restart attempts
- **Alert System**: Service failures can generate system alerts

This enhancement ensures that the Raspberry Pi Network Control Panel provides enterprise-grade service monitoring and management capabilities while maintaining ease of use for all skill levels. 