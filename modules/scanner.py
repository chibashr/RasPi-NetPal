import subprocess
import re
import os
import json
import time
import ipaddress
import threading
import uuid
from datetime import datetime
from .logging import add_log_entry
from pathlib import Path

# Directory to store scan results
SCAN_RESULTS_DIR = Path('data/scan_results')
SCAN_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Store active scans
active_scans = {}

class NetworkScanner:
    def __init__(self, scan_id=None, name=None):
        self.scan_id = scan_id or str(uuid.uuid4())
        self.name = name or f"Scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time = None
        self.end_time = None
        self.status = "pending"  # pending, running, completed, cancelled, error
        self.targets = []
        self.results = []
        self.progress = 0
        self.total_hosts = 0
        self.scanned_hosts = 0
        self.scan_thread = None
        self.options = {
            "timeout": 1,
            "rate_limit": False,
            "rate_limit_delay": 0.1,
            "get_mac": True,
            "get_hostname": True,
            "get_host_type": True,
            "quick_scan": False
        }
        
    def parse_target_range(self, target_range):
        """Parse different formats of IP ranges (CIDR, comma-separated, dashed)"""
        ip_list = []
        
        # Check if it's a CIDR notation
        if '/' in target_range:
            try:
                network = ipaddress.ip_network(target_range, strict=False)
                ip_list = [str(ip) for ip in network.hosts()]
            except Exception as e:
                add_log_entry(f"Error parsing CIDR {target_range}: {str(e)}", is_error=True)
                return []
        
        # Check if it's a comma-separated list
        elif ',' in target_range:
            parts = target_range.split(',')
            for part in parts:
                part = part.strip()
                # Check if it's a range with dash
                if '-' in part:
                    start_ip, end_ip = part.split('-')
                    ip_list.extend(self._expand_ip_range(start_ip, end_ip))
                else:
                    try:
                        # Validate it's a proper IP
                        ipaddress.ip_address(part)
                        ip_list.append(part)
                    except ValueError:
                        add_log_entry(f"Invalid IP address in range: {part}", is_error=True)
        
        # Check if it's a range with dash
        elif '-' in target_range:
            start_ip, end_ip = target_range.split('-')
            ip_list = self._expand_ip_range(start_ip, end_ip)
        
        # Single IP address
        else:
            try:
                ipaddress.ip_address(target_range)
                ip_list.append(target_range)
            except ValueError:
                add_log_entry(f"Invalid IP address: {target_range}", is_error=True)
        
        return ip_list
    
    def _expand_ip_range(self, start_ip, end_ip):
        """Expand a range of IPs from start_ip to end_ip"""
        try:
            start = ipaddress.IPv4Address(start_ip.strip())
            end = ipaddress.IPv4Address(end_ip.strip())
            return [str(ipaddress.IPv4Address(ip)) for ip in range(int(start), int(end) + 1)]
        except Exception as e:
            add_log_entry(f"Error expanding IP range {start_ip}-{end_ip}: {str(e)}", is_error=True)
            return []
    
    def start_scan(self, target_range, options=None):
        """Start a network scan in a separate thread"""
        if options:
            self.options.update(options)
            
        self.targets = self.parse_target_range(target_range)
        self.total_hosts = len(self.targets)
        
        if self.total_hosts == 0:
            add_log_entry(f"No valid targets found in range: {target_range}", is_error=True)
            self.status = "error"
            return False
            
        self.start_time = datetime.now().isoformat()
        self.status = "running"
        self.results = []
        self.scanned_hosts = 0
        self.progress = 0
        
        # Register this scan as active
        active_scans[self.scan_id] = self
        
        # Start the scan in a background thread
        self.scan_thread = threading.Thread(target=self._run_scan)
        self.scan_thread.daemon = True
        self.scan_thread.start()
        
        add_log_entry(f"Started network scan of {self.total_hosts} hosts with ID {self.scan_id}")
        return True
    
    def _run_scan(self):
        """Execute the actual scan (runs in a thread)"""
        try:
            for ip in self.targets:
                if self.status == "cancelled":
                    add_log_entry(f"Scan {self.scan_id} cancelled")
                    break
                    
                result = self._scan_host(ip)
                if result:
                    self.results.append(result)
                
                self.scanned_hosts += 1
                self.progress = int((self.scanned_hosts / self.total_hosts) * 100)
                
                # Apply rate limiting if enabled
                if self.options["rate_limit"] and self.options["rate_limit_delay"] > 0:
                    time.sleep(self.options["rate_limit_delay"])
            
            # Mark as completed if not cancelled
            if self.status != "cancelled":
                self.status = "completed"
                
            self.end_time = datetime.now().isoformat()
            
            # Save the results
            self.save_results()
            
            # Remove from active scans if completed or cancelled
            if self.scan_id in active_scans:
                del active_scans[self.scan_id]
                
        except Exception as e:
            add_log_entry(f"Error in scan {self.scan_id}: {str(e)}", is_error=True)
            self.status = "error"
            self.end_time = datetime.now().isoformat()
            if self.scan_id in active_scans:
                del active_scans[self.scan_id]
    
    def _scan_host(self, ip):
        """Scan a single host IP and return result"""
        result = {
            "ip": ip,
            "timestamp": datetime.now().isoformat(),
            "status": "down",
            "mac": "",
            "hostname": "",
            "host_type": ""
        }
        
        # Adjust timeout for quick scan
        timeout = 0.2 if self.options["quick_scan"] else self.options["timeout"]
        
        # Ping the host 
        ping_cmd = f"ping -c 1 -W {timeout} {ip}"
        try:
            ping_output = subprocess.run(ping_cmd, shell=True, capture_output=True, text=True, timeout=timeout+1)
            if ping_output.returncode == 0:
                result["status"] = "up"
                
                # Extract response time
                time_match = re.search(r'time=(\d+\.?\d*)', ping_output.stdout)
                if time_match:
                    result["response_time"] = float(time_match.group(1))
                else:
                    result["response_time"] = None
                
                # Skip additional checks if quick scan is enabled
                if self.options["quick_scan"]:
                    return result
                
                # Get MAC address if option enabled
                if self.options["get_mac"]:
                    result["mac"] = self._get_mac_address(ip)
                
                # Get hostname if option enabled
                if self.options["get_hostname"]:
                    result["hostname"] = self._get_hostname(ip)
                
                # Try to determine host type if option enabled
                if self.options["get_host_type"]:
                    result["host_type"] = self._get_host_type(ip, result["mac"])
                
                return result
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            add_log_entry(f"Error scanning host {ip}: {str(e)}", is_error=True)
        
        return result if result["status"] == "up" else None
    
    def _get_mac_address(self, ip):
        """Get MAC address for the IP using arp"""
        try:
            # First try to ping to populate the ARP table
            subprocess.run(f"ping -c 1 -W 1 {ip}", shell=True, capture_output=True, text=True, timeout=2)
            
            # Then check the ARP table
            arp_output = subprocess.run(f"arp -n {ip}", shell=True, capture_output=True, text=True, timeout=2)
            mac_match = re.search(r'(([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2}))', arp_output.stdout)
            if mac_match:
                return mac_match.group(1).lower()
        except Exception as e:
            add_log_entry(f"Error getting MAC for {ip}: {str(e)}", is_error=True)
        
        return ""
    
    def _get_hostname(self, ip):
        """Try to resolve hostname for IP"""
        try:
            hostname_output = subprocess.run(f"host {ip}", shell=True, capture_output=True, text=True, timeout=2)
            hostname_match = re.search(r'domain name pointer (.+)\.', hostname_output.stdout)
            if hostname_match:
                return hostname_match.group(1)
        except Exception as e:
            pass
        
        return ""
    
    def _get_host_type(self, ip, mac):
        """Try to determine host type based on MAC and other factors"""
        if not mac:
            return "Unknown"
            
        # Check MAC address vendor
        oui = mac.replace(':', '').replace('-', '')[:6].upper()
        
        # Very basic OUI checking for common vendors
        # In a real implementation, you would have a more comprehensive OUI database
        vendor_map = {
            'B8:27:EB': 'Raspberry Pi',
            'DC:A6:32': 'Raspberry Pi',
            'E4:5F:01': 'Raspberry Pi',
            '00:1A:11': 'Google',
            'F8:1A:67': 'TP-Link',
            '00:12:17': 'Cisco',
            '00:14:22': 'Dell',
            '00:21:5A': 'Hewlett-Packard',
            '00:26:B9': 'Dell',
            '08:00:20': 'Sun Microsystems',
            '00:03:93': 'Apple',
            '00:50:56': 'VMware',
            '00:05:9A': 'Cisco',
            '00:25:90': 'Android/Google',
        }
        
        # Check if any key in vendor_map is a prefix of our MAC
        for prefix, vendor in vendor_map.items():
            prefix = prefix.lower().replace(':', '').replace('-', '')
            if oui.lower().startswith(prefix.lower()):
                return vendor
                
        # Additional checks could be made by probing common ports
        return "Unknown"
    
    def cancel_scan(self):
        """Cancel an ongoing scan"""
        if self.status == "running":
            self.status = "cancelled"
            add_log_entry(f"Cancelling scan {self.scan_id}")
            return True
        return False
    
    def save_results(self):
        """Save scan results to a file"""
        scan_data = {
            "scan_id": self.scan_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "options": self.options,
            "targets": self.targets,
            "total_hosts": self.total_hosts,
            "scanned_hosts": self.scanned_hosts,
            "results": [r for r in self.results if r is not None]
        }
        
        try:
            file_path = SCAN_RESULTS_DIR / f"{self.scan_id}.json"
            with open(file_path, 'w') as f:
                json.dump(scan_data, f, indent=2)
            
            add_log_entry(f"Saved scan results to {file_path}")
            return True
        except Exception as e:
            add_log_entry(f"Error saving scan results: {str(e)}", is_error=True)
            return False
    
    def to_dict(self):
        """Convert scan to dictionary for JSON serialization"""
        return {
            "scan_id": self.scan_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "options": self.options,
            "total_hosts": self.total_hosts,
            "scanned_hosts": self.scanned_hosts,
            "progress": self.progress,
            "result_count": len([r for r in self.results if r is not None])
        }

def get_saved_scans():
    """Get list of all saved scans"""
    scans = []
    try:
        for file_path in SCAN_RESULTS_DIR.glob('*.json'):
            try:
                with open(file_path, 'r') as f:
                    scan_data = json.load(f)
                    scans.append({
                        "scan_id": scan_data.get("scan_id", ""),
                        "name": scan_data.get("name", ""),
                        "start_time": scan_data.get("start_time", ""),
                        "end_time": scan_data.get("end_time", ""),
                        "status": scan_data.get("status", ""),
                        "total_hosts": scan_data.get("total_hosts", 0),
                        "scanned_hosts": scan_data.get("scanned_hosts", 0),
                        "result_count": len(scan_data.get("results", []))
                    })
            except Exception as e:
                add_log_entry(f"Error reading scan file {file_path}: {str(e)}", is_error=True)
    except Exception as e:
        add_log_entry(f"Error listing scan files: {str(e)}", is_error=True)
    
    # Sort by start time (newest first)
    scans.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    return scans

def get_scan_results(scan_id):
    """Get detailed results for a specific scan"""
    try:
        # First check if it's an active scan
        if scan_id in active_scans:
            scan = active_scans[scan_id]
            return {
                "scan_id": scan.scan_id,
                "name": scan.name,
                "start_time": scan.start_time,
                "end_time": scan.end_time,
                "status": scan.status,
                "options": scan.options,
                "targets": scan.targets,
                "total_hosts": scan.total_hosts,
                "scanned_hosts": scan.scanned_hosts,
                "progress": scan.progress,
                "results": [r for r in scan.results if r is not None]
            }
        
        # Otherwise look for saved scan
        file_path = SCAN_RESULTS_DIR / f"{scan_id}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        add_log_entry(f"Error getting scan results for {scan_id}: {str(e)}", is_error=True)
    
    return None

def rename_scan(scan_id, new_name):
    """Rename a saved scan"""
    try:
        file_path = SCAN_RESULTS_DIR / f"{scan_id}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                scan_data = json.load(f)
            
            # Update the name
            scan_data["name"] = new_name
            
            # Save back to file
            with open(file_path, 'w') as f:
                json.dump(scan_data, f, indent=2)
            
            add_log_entry(f"Renamed scan {scan_id} to '{new_name}'")
            return True
    except Exception as e:
        add_log_entry(f"Error renaming scan {scan_id}: {str(e)}", is_error=True)
    
    return False

def delete_scan(scan_id):
    """Delete a saved scan"""
    try:
        file_path = SCAN_RESULTS_DIR / f"{scan_id}.json"
        if file_path.exists():
            file_path.unlink()
            add_log_entry(f"Deleted scan {scan_id}")
            return True
    except Exception as e:
        add_log_entry(f"Error deleting scan {scan_id}: {str(e)}", is_error=True)
    
    return False

def get_active_scans():
    """Get list of all currently active scans"""
    return {scan_id: scan.to_dict() for scan_id, scan in active_scans.items()} 