import subprocess
import re
import json
import os
import shutil
from flask import current_app
from .logging import add_log_entry

def ensure_tools_installed():
    """
    Ensure that all required network tools are installed.
    Returns True if all tools are available or were successfully installed,
    False otherwise.
    """
    required_tools = {
        'ping': 'iputils-ping',
        'traceroute': 'traceroute',
        'dig': 'dnsutils',
        'mtr': 'mtr-tiny',
        'iperf3': 'iperf3',
        'nmap': 'nmap',
        'curl': 'curl'
    }
    
    tools_to_install = []
    
    # Check which tools are missing
    for tool, package in required_tools.items():
        try:
            subprocess.check_output(f"which {tool}", shell=True)
        except subprocess.CalledProcessError:
            tools_to_install.append(package)
    
    # If any tools are missing, try to install them
    if tools_to_install:
        add_log_entry(f"Installing missing tools: {', '.join(tools_to_install)}")
        try:
            update_cmd = "sudo apt-get update"
            install_cmd = f"sudo apt-get install -y {' '.join(tools_to_install)}"
            
            subprocess.run(update_cmd, shell=True, check=True)
            subprocess.run(install_cmd, shell=True, check=True)
            
            return True
        except subprocess.CalledProcessError as e:
            add_log_entry(f"Error installing tools: {str(e)}", is_error=True)
            return False
    
    return True

def run_ping(target, count=4, timeout=2, interface=None):
    """
    Run a ping command to the specified target.
    
    Args:
        target: The hostname or IP to ping
        count: Number of packets to send
        timeout: Timeout in seconds
        interface: Specific interface to use for the ping
        
    Returns:
        Dictionary with the ping results
    """
    try:
        # Build the command with optional interface specification
        interface_option = f"-I {interface}" if interface else ""
        cmd = f"ping -c {count} -W {timeout} {interface_option} {target}"
        
        # Run the ping command
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        
        # Parse the ping output to extract key information
        packet_loss_match = re.search(r'(\d+)% packet loss', output)
        rtt_match = re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', output)
        
        packet_loss = packet_loss_match.group(1) if packet_loss_match else "unknown"
        
        rtt_stats = {}
        if rtt_match:
            rtt_stats = {
                'min': float(rtt_match.group(1)),
                'avg': float(rtt_match.group(2)),
                'max': float(rtt_match.group(3)),
                'mdev': float(rtt_match.group(4))
            }
        
        return {
            'success': True,
            'command': cmd,
            'output': output,
            'packet_loss': packet_loss,
            'rtt_stats': rtt_stats
        }
    except subprocess.CalledProcessError as e:
        # Ping returns non-zero exit code when packets are lost
        output = e.output
        
        # Try to extract packet loss information even on failure
        packet_loss_match = re.search(r'(\d+)% packet loss', output)
        packet_loss = packet_loss_match.group(1) if packet_loss_match else "100"
        
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"ping -c {count} -W {timeout} {target}",
            'output': output,
            'error': f"Ping failed with exit code {e.returncode}",
            'packet_loss': packet_loss
        }
    except Exception as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"ping -c {count} -W {timeout} {target}",
            'error': str(e)
        }

def run_traceroute(target, max_hops=30, interface=None):
    """
    Run a traceroute command to the specified target.
    
    Args:
        target: The hostname or IP to trace
        max_hops: Maximum number of hops to trace
        interface: Specific interface to use for the traceroute
        
    Returns:
        Dictionary with the traceroute results
    """
    try:
        # Build the command with optional interface specification
        interface_option = f"-i {interface}" if interface else ""
        cmd = f"traceroute -m {max_hops} {interface_option} {target}"
        
        # Run the traceroute command
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        
        # Parse the traceroute output to extract hops
        hops = []
        for line in output.splitlines()[1:]:  # Skip the header line
            hop_match = re.match(r'\s*(\d+)\s+(.*)', line)
            if hop_match:
                hop_num = int(hop_match.group(1))
                hop_info = hop_match.group(2)
                
                # Extract IP addresses and hostnames
                ip_matches = re.findall(r'\(([\d.]+)\)', hop_info)
                
                hop = {
                    'number': hop_num,
                    'raw': hop_info
                }
                
                if ip_matches:
                    hop['ip'] = ip_matches[0]
                
                hops.append(hop)
        
        return {
            'success': True,
            'command': cmd,
            'output': output,
            'hops': hops
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"traceroute -m {max_hops} {target}",
            'output': e.output if hasattr(e, 'output') else "",
            'error': f"Traceroute failed with exit code {e.returncode}"
        }
    except Exception as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"traceroute -m {max_hops} {target}",
            'error': str(e)
        }

def run_iperf_client(server, port=5201, duration=5, protocol='tcp', interface=None):
    """
    Run iperf3 client to test bandwidth.
    
    Args:
        server: The iperf server to connect to
        port: The port to connect on
        duration: Test duration in seconds
        protocol: 'tcp' or 'udp'
        interface: Specific interface to use for the test
        
    Returns:
        Dictionary with the iperf results
    """
    try:
        protocol_flag = '-u' if protocol.lower() == 'udp' else ''
        
        # Add bind option if interface is specified
        bind_option = ""
        if interface:
            from .network import get_interfaces
            interfaces = get_interfaces()
            for iface in interfaces:
                if iface['name'] == interface and iface['addr'] != 'N/A':
                    bind_option = f"--bind {iface['addr']}"
                    break
        
        cmd = f"iperf3 -c {server} -p {port} -t {duration} {protocol_flag} -J {bind_option}"
        
        # Run the iperf command with JSON output
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        
        # Parse the JSON output
        results = json.loads(output)
        
        # Extract key information
        summary = {}
        if protocol.lower() == 'tcp':
            if 'end' in results and 'sum_received' in results['end']:
                summary = {
                    'bits_per_second': results['end']['sum_received']['bits_per_second'],
                    'bytes': results['end']['sum_received']['bytes'],
                    'seconds': results['end']['sum_received']['seconds']
                }
        else:  # UDP
            if 'end' in results and 'sum' in results['end']:
                summary = {
                    'bits_per_second': results['end']['sum']['bits_per_second'],
                    'bytes': results['end']['sum']['bytes'],
                    'seconds': results['end']['sum']['seconds'],
                    'jitter_ms': results['end']['sum']['jitter_ms'],
                    'lost_packets': results['end']['sum']['lost_packets'],
                    'packets': results['end']['sum']['packets']
                }
        
        return {
            'success': True,
            'command': cmd,
            'output': output,
            'summary': summary,
            'json': results
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"iperf3 -c {server} -p {port} -t {duration} {'-u' if protocol.lower() == 'udp' else ''}",
            'output': e.output if hasattr(e, 'output') else "",
            'error': f"iPerf failed with exit code {e.returncode}"
        }
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"iperf3 -c {server} -p {port} -t {duration} {'-u' if protocol.lower() == 'udp' else ''}",
            'output': output if 'output' in locals() else "",
            'error': f"Could not parse iPerf JSON output: {str(e)}"
        }
    except Exception as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"iperf3 -c {server} -p {port} -t {duration} {'-u' if protocol.lower() == 'udp' else ''}",
            'error': str(e)
        }

def run_dns_lookup(target, record_type='A', interface=None):
    """
    Run a DNS lookup using dig.
    
    Args:
        target: The hostname to lookup
        record_type: DNS record type (A, AAAA, MX, etc.)
        interface: Specific interface to use for the lookup
        
    Returns:
        Dictionary with the lookup results
    """
    try:
        # Build the command with optional interface specification
        interface_option = ""
        if interface:
            from .network import get_interfaces
            interfaces = get_interfaces()
            for iface in interfaces:
                if iface['name'] == interface and iface['addr'] != 'N/A':
                    interface_option = f"-b {iface['addr']}"
                    break
        
        cmd = f"dig {interface_option} {target} {record_type} +short"
        
        # Run the dig command
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        
        # Parse the output to extract records
        records = []
        for line in output.strip().splitlines():
            if line:
                records.append(line)
        
        return {
            'success': True,
            'command': cmd,
            'output': output,
            'records': records,
            'count': len(records)
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"dig {target} {record_type} +short",
            'output': e.output if hasattr(e, 'output') else "",
            'error': f"DNS lookup failed with exit code {e.returncode}"
        }
    except Exception as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"dig {target} {record_type} +short",
            'error': str(e)
        }

def run_mtr(target, count=10, interface=None):
    """
    Run MTR (My Traceroute) to the specified target.
    
    Args:
        target: The hostname or IP to trace
        count: Number of pings per hop
        interface: Specific interface to use for the trace
        
    Returns:
        Dictionary with the MTR results
    """
    try:
        # Build the command with optional interface specification
        interface_option = f"--interface {interface}" if interface else ""
        cmd = f"mtr -r -c {count} {interface_option} {target}"
        
        # Run the MTR command
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        
        # Parse the MTR output to extract hops
        hops = []
        header_passed = False
        
        for line in output.splitlines():
            if 'HOST:' in line:
                header_passed = True
                continue
            
            if header_passed and line.strip():
                # MTR output format: HOST, Loss%, Snt, Last, Avg, Best, Wrst, StDev
                parts = line.split()
                if len(parts) >= 8:
                    hop_num_host = parts[0].split('.')
                    
                    if len(hop_num_host) >= 2:
                        hop_num = int(hop_num_host[0])
                        host = '.'.join(hop_num_host[1:])
                        
                        hop = {
                            'number': hop_num,
                            'host': host,
                            'loss_pct': parts[1],
                            'sent': parts[2],
                            'last': parts[3],
                            'avg': parts[4],
                            'best': parts[5],
                            'worst': parts[6],
                            'std_dev': parts[7]
                        }
                        
                        hops.append(hop)
        
        return {
            'success': True,
            'command': cmd,
            'output': output,
            'hops': hops
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"mtr -r -c {count} {target}",
            'output': e.output if hasattr(e, 'output') else "",
            'error': f"MTR failed with exit code {e.returncode}"
        }
    except Exception as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"mtr -r -c {count} {target}",
            'error': str(e)
        }

def run_nmap_scan(target, scan_type='basic', interface=None):
    """
    Run an Nmap scan on the specified target.
    
    Args:
        target: The hostname, IP, or network to scan
        scan_type: Type of scan ('basic', 'service', 'os')
        interface: Specific interface to use for the scan
        
    Returns:
        Dictionary with the Nmap results
    """
    try:
        # Build the command with optional interface specification
        interface_option = f"-e {interface}" if interface else ""
        
        if scan_type == 'basic':
            cmd = f"nmap -T4 -F {interface_option} {target}"
        elif scan_type == 'service':
            cmd = f"nmap -T4 -sV -F {interface_option} {target}"
        elif scan_type == 'os':
            cmd = f"nmap -T4 -O {interface_option} {target}"
        else:
            cmd = f"nmap -T4 -F {interface_option} {target}"
        
        # Run the Nmap command
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        
        # Parse the Nmap output to extract hosts and ports
        hosts = []
        current_host = None
        
        for line in output.splitlines():
            # Look for "Nmap scan report for" lines
            host_match = re.search(r'Nmap scan report for (.*?)( \((.*?)\))?$', line)
            if host_match:
                if current_host:
                    hosts.append(current_host)
                
                hostname = host_match.group(1)
                ip = host_match.group(3) if host_match.group(3) else hostname
                
                current_host = {
                    'hostname': hostname,
                    'ip': ip,
                    'ports': []
                }
                continue
            
            # Look for port information
            port_match = re.search(r'(\d+)\/(\w+)\s+(\w+)\s+(.+)', line)
            if port_match and current_host:
                port = {
                    'port': int(port_match.group(1)),
                    'protocol': port_match.group(2),
                    'state': port_match.group(3),
                    'service': port_match.group(4)
                }
                current_host['ports'].append(port)
        
        # Add the last host if there is one
        if current_host:
            hosts.append(current_host)
        
        return {
            'success': True,
            'command': cmd,
            'output': output,
            'hosts': hosts
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"nmap -T4 -F {target}",
            'output': e.output if hasattr(e, 'output') else "",
            'error': f"Nmap scan failed with exit code {e.returncode}"
        }
    except Exception as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"nmap -T4 -F {target}",
            'error': str(e)
        }

def run_http_curl(url, follow_redirects=True, interface=None):
    """
    Make an HTTP request using curl.
    
    Args:
        url: The URL to request
        follow_redirects: Whether to follow redirects
        interface: Specific interface to use for the request
        
    Returns:
        Dictionary with the HTTP request results
    """
    try:
        redirect_flag = "-L" if follow_redirects else ""
        
        # Add interface option if specified
        interface_option = ""
        if interface:
            from .network import get_interfaces
            interfaces = get_interfaces()
            for iface in interfaces:
                if iface['name'] == interface and iface['addr'] != 'N/A':
                    interface_option = f"--interface {iface['addr']}"
                    break
        
        cmd = f"curl -v {redirect_flag} {interface_option} -s -o /dev/null -w '%{{http_code}},%{{time_total}},%{{size_download}},%{{num_redirects}},%{{url_effective}}' {url}"
        
        # Run the curl command
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.PIPE, text=True)
        stderr = subprocess.PIPE.stderr if hasattr(subprocess.PIPE, 'stderr') else ""
        
        # Parse the curl output to extract metrics
        parts = output.strip().split(',')
        
        metrics = {}
        if len(parts) >= 5:
            metrics = {
                'status_code': int(parts[0]),
                'time_seconds': float(parts[1]),
                'size_bytes': int(parts[2]),
                'redirects': int(parts[3]),
                'final_url': parts[4]
            }
        
        # Extract headers from stderr
        headers = {}
        if stderr:
            for line in stderr.splitlines():
                header_match = re.search(r'< ([^:]+): (.*)', line)
                if header_match:
                    header_name = header_match.group(1)
                    header_value = header_match.group(2)
                    headers[header_name] = header_value
        
        return {
            'success': True,
            'command': cmd,
            'output': output,
            'stderr': stderr,
            'metrics': metrics,
            'headers': headers
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"curl -v {'-L' if follow_redirects else ''} -s {url}",
            'output': e.output if hasattr(e, 'output') else "",
            'stderr': e.stderr if hasattr(e, 'stderr') else "",
            'error': f"HTTP request failed with exit code {e.returncode}"
        }
    except Exception as e:
        return {
            'success': False,
            'command': cmd if 'cmd' in locals() else f"curl -v {'-L' if follow_redirects else ''} -s {url}",
            'error': str(e)
        } 