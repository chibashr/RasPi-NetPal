from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context
import time
import json
import threading
from modules.tools import (
    ensure_tools_installed,
    run_ping,
    run_traceroute,
    run_iperf_client,
    run_dns_lookup,
    run_mtr,
    run_nmap_scan,
    run_http_curl
)
from modules.logging import add_log_entry
import subprocess
from modules.network import get_interfaces

# Create blueprint
bp = Blueprint('tools', __name__, url_prefix='/tools')

@bp.route('/')
def tools_index():
    """Display the network tools page."""
    # Check that required tools are installed
    tools_installed = ensure_tools_installed()
    return render_template('tools.html', tools_installed=tools_installed)

@bp.route('/get_interfaces')
def get_interfaces_route():
    """Return a list of available network interfaces"""
    interfaces = get_interfaces()
    return jsonify(interfaces)

# Helper function to stream command output
def stream_command_output(cmd):
    """Stream the output of a command in real-time."""
    process = subprocess.Popen(
        cmd, 
        shell=True, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,
        text=True, 
        bufsize=1,
        universal_newlines=True
    )
    
    # Send the command first
    yield f"event: command_start\ndata: {json.dumps({'command': cmd})}\n\n"
    
    # Stream output as it becomes available
    complete_output = ""
    for line in iter(process.stdout.readline, ''):
        complete_output += line
        yield f"event: output_chunk\ndata: {json.dumps({'chunk': line})}\n\n"
        time.sleep(0.01)  # Small delay to prevent overwhelming the client
    
    # Wait for process to complete and get return code
    return_code = process.wait()
    success = (return_code == 0)
    
    # Send completion event
    completion_data = {
        'success': success,
        'return_code': return_code,
        'output': complete_output,
    }
    
    yield f"event: command_complete\ndata: {json.dumps(completion_data)}\n\n"

@bp.route('/ping', methods=['POST'])
def ping():
    """Run ping command and return results."""
    target = request.form.get('target', '')
    count = int(request.form.get('count', 4))
    timeout = int(request.form.get('timeout', 2))
    interface = request.form.get('interface', '')
    
    if not target:
        return jsonify({'success': False, 'error': 'No target specified'})
    
    add_log_entry(f"Running ping to {target}" + (f" via {interface}" if interface else ""))
    result = run_ping(target, count, timeout, interface)
    return jsonify(result)

@bp.route('/ping_stream', methods=['POST'])
def ping_stream():
    """Streaming endpoint for ping results"""
    target = request.form.get('target')
    count = request.form.get('count', 4, type=int)
    timeout = request.form.get('timeout', 2, type=int)
    interface = request.form.get('interface')
    
    # Validate target
    if not target:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: target'
        })
    
    # Helper function to stream the ping output
    def generate():
        interface_option = f"-I {interface}" if interface else ""
        cmd = f"ping -c {count} -W {timeout} {interface_option} {target}"
        
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            yield f"Running: {cmd}\n\n"
            
            for line in iter(process.stdout.readline, ''):
                yield line
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                yield f"\nCommand failed with return code {return_code}\n"
        except Exception as e:
            yield f"Error: {str(e)}\n"
    
    return Response(stream_with_context(generate()), mimetype='text/plain')

@bp.route('/traceroute', methods=['POST'])
def traceroute():
    """Run traceroute command and return results."""
    target = request.form.get('target', '')
    max_hops = int(request.form.get('max_hops', 30))
    interface = request.form.get('interface', '')
    
    if not target:
        return jsonify({'success': False, 'error': 'No target specified'})
    
    add_log_entry(f"Running traceroute to {target}" + (f" via {interface}" if interface else ""))
    result = run_traceroute(target, max_hops, interface)
    return jsonify(result)

@bp.route('/traceroute_stream', methods=['POST'])
def traceroute_stream():
    """Streaming endpoint for traceroute results"""
    target = request.form.get('target')
    max_hops = request.form.get('max_hops', 30, type=int)
    interface = request.form.get('interface')
    
    # Validate target
    if not target:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: target'
        })
    
    # Helper function to stream the traceroute output
    def generate():
        interface_option = f"-i {interface}" if interface else ""
        cmd = f"traceroute -m {max_hops} {interface_option} {target}"
        
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            yield f"Running: {cmd}\n\n"
            
            for line in iter(process.stdout.readline, ''):
                yield line
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                yield f"\nCommand failed with return code {return_code}\n"
        except Exception as e:
            yield f"Error: {str(e)}\n"
    
    return Response(stream_with_context(generate()), mimetype='text/plain')

@bp.route('/iperf', methods=['POST'])
def iperf():
    """Run iperf client and return results."""
    server = request.form.get('server', '')
    port = int(request.form.get('port', 5201))
    duration = int(request.form.get('duration', 5))
    protocol = request.form.get('protocol', 'tcp')
    interface = request.form.get('interface', '')
    
    if not server:
        return jsonify({'success': False, 'error': 'No server specified'})
    
    add_log_entry(f"Running iperf3 client to {server}:{port}" + (f" via {interface}" if interface else ""))
    result = run_iperf_client(server, port, duration, protocol, interface)
    return jsonify(result)

@bp.route('/iperf_stream', methods=['POST'])
def iperf_stream():
    """Streaming endpoint for iperf client results"""
    server = request.form.get('server')
    port = request.form.get('port', 5201, type=int)
    duration = request.form.get('duration', 5, type=int)
    protocol = request.form.get('protocol', 'tcp')
    interface = request.form.get('interface')
    
    # Validate server
    if not server:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: server'
        })
    
    # Helper function to stream the iperf output
    def generate():
        protocol_flag = '-u' if protocol.lower() == 'udp' else ''
        
        bind_option = ""
        if interface:
            interfaces = get_interfaces()
            for iface in interfaces:
                if iface['name'] == interface and iface['addr'] != 'N/A':
                    bind_option = f"--bind {iface['addr']}"
                    break
        
        cmd = f"iperf3 -c {server} -p {port} -t {duration} {protocol_flag} {bind_option}"
        
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            yield f"Running: {cmd}\n\n"
            
            for line in iter(process.stdout.readline, ''):
                yield line
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                yield f"\nCommand failed with return code {return_code}\n"
        except Exception as e:
            yield f"Error: {str(e)}\n"
    
    return Response(stream_with_context(generate()), mimetype='text/plain')

@bp.route('/dns', methods=['POST'])
def dns_lookup():
    """Run DNS lookup and return results."""
    target = request.form.get('target', '')
    record_type = request.form.get('type', 'A')
    interface = request.form.get('interface', '')
    
    if not target:
        return jsonify({'success': False, 'error': 'No target specified'})
    
    add_log_entry(f"Running DNS lookup for {target} ({record_type})" + (f" via {interface}" if interface else ""))
    result = run_dns_lookup(target, record_type, interface)
    return jsonify(result)

@bp.route('/dns_stream', methods=['POST'])
def dns_stream():
    """Streaming endpoint for DNS lookup results"""
    target = request.form.get('target')
    record_type = request.form.get('record_type', 'A')
    interface = request.form.get('interface')
    
    # Validate target
    if not target:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: target'
        })
    
    # Helper function to stream the DNS lookup output
    def generate():
        interface_option = ""
        if interface:
            interfaces = get_interfaces()
            for iface in interfaces:
                if iface['name'] == interface and iface['addr'] != 'N/A':
                    interface_option = f"-b {iface['addr']}"
                    break
        
        cmd = f"dig {interface_option} {target} {record_type}"
        
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            yield f"Running: {cmd}\n\n"
            
            for line in iter(process.stdout.readline, ''):
                yield line
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                yield f"\nCommand failed with return code {return_code}\n"
        except Exception as e:
            yield f"Error: {str(e)}\n"
    
    return Response(stream_with_context(generate()), mimetype='text/plain')

@bp.route('/mtr', methods=['POST'])
def mtr():
    """Run MTR and return results."""
    target = request.form.get('target', '')
    count = int(request.form.get('count', 10))
    interface = request.form.get('interface', '')
    
    if not target:
        return jsonify({'success': False, 'error': 'No target specified'})
    
    add_log_entry(f"Running MTR to {target}" + (f" via {interface}" if interface else ""))
    result = run_mtr(target, count, interface)
    return jsonify(result)

@bp.route('/mtr_stream', methods=['POST'])
def mtr_stream():
    """Streaming endpoint for MTR results"""
    target = request.form.get('target')
    count = request.form.get('count', 10, type=int)
    interface = request.form.get('interface')
    
    # Validate target
    if not target:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: target'
        })
    
    # Helper function to stream the MTR output
    def generate():
        interface_option = f"--interface {interface}" if interface else ""
        cmd = f"mtr -r -c {count} {interface_option} {target}"
        
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            yield f"Running: {cmd}\n\n"
            
            for line in iter(process.stdout.readline, ''):
                yield line
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                yield f"\nCommand failed with return code {return_code}\n"
        except Exception as e:
            yield f"Error: {str(e)}\n"
    
    return Response(stream_with_context(generate()), mimetype='text/plain')

@bp.route('/nmap', methods=['POST'])
def nmap():
    """Run nmap scan and return results."""
    target = request.form.get('target', '')
    scan_type = request.form.get('scan_type', 'basic')
    interface = request.form.get('interface', '')
    
    if not target:
        return jsonify({'success': False, 'error': 'No target specified'})
    
    add_log_entry(f"Running nmap {scan_type} scan on {target}" + (f" via {interface}" if interface else ""))
    result = run_nmap_scan(target, scan_type, interface)
    return jsonify(result)

@bp.route('/nmap_stream', methods=['POST'])
def nmap_stream():
    """Streaming endpoint for nmap scan results"""
    target = request.form.get('target')
    scan_type = request.form.get('scan_type', 'basic')
    interface = request.form.get('interface')
    
    # Validate target
    if not target:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: target'
        })
    
    # Helper function to stream the nmap output
    def generate():
        interface_option = f"-e {interface}" if interface else ""
        
        if scan_type == 'basic':
            cmd = f"nmap -T4 -F {interface_option} {target}"
        elif scan_type == 'service':
            cmd = f"nmap -T4 -sV -F {interface_option} {target}"
        elif scan_type == 'os':
            cmd = f"nmap -T4 -O {interface_option} {target}"
        else:
            cmd = f"nmap -T4 -F {interface_option} {target}"
        
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            yield f"Running: {cmd}\n\n"
            
            for line in iter(process.stdout.readline, ''):
                yield line
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                yield f"\nCommand failed with return code {return_code}\n"
        except Exception as e:
            yield f"Error: {str(e)}\n"
    
    return Response(stream_with_context(generate()), mimetype='text/plain')

@bp.route('/http', methods=['POST'])
def http_request():
    """Make HTTP request and return results."""
    url = request.form.get('url', '')
    follow_redirects = request.form.get('follow_redirects', 'true') == 'true'
    interface = request.form.get('interface', '')
    
    if not url:
        return jsonify({'success': False, 'error': 'No URL specified'})
    
    # Add http:// if not present
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url
    
    add_log_entry(f"Making HTTP request to {url}" + (f" via {interface}" if interface else ""))
    result = run_http_curl(url, follow_redirects, interface)
    return jsonify(result)

@bp.route('/http_stream', methods=['POST'])
def http_stream():
    """Streaming endpoint for HTTP request results"""
    url = request.form.get('url')
    follow_redirects = request.form.get('follow_redirects', 'true') == 'true'
    interface = request.form.get('interface')
    
    # Validate URL
    if not url:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: url'
        })
    
    # Add http:// prefix if missing
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url
    
    # Helper function to stream the HTTP request output
    def generate():
        redirect_flag = "-L" if follow_redirects else ""
        
        interface_option = ""
        if interface:
            interfaces = get_interfaces()
            for iface in interfaces:
                if iface['name'] == interface and iface['addr'] != 'N/A':
                    interface_option = f"--interface {iface['addr']}"
                    break
        
        cmd = f"curl -v {redirect_flag} {interface_option} {url}"
        
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            yield f"Running: {cmd}\n\n"
            
            for line in iter(process.stdout.readline, ''):
                yield line
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                yield f"\nCommand failed with return code {return_code}\n"
        except Exception as e:
            yield f"Error: {str(e)}\n"
    
    return Response(stream_with_context(generate()), mimetype='text/plain') 