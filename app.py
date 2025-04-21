from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import eventlet
import subprocess
import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from queue import Queue, Empty
import threading

# Patch standard library for eventlet
eventlet.monkey_patch()

# Create command queue and worker thread
command_queue = Queue()
thread = None

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1024 * 1024 * 10, backupCount=5)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

# Create app instance
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# Initialize SocketIO with cors_allowed_origins set to "*" to allow connections from any origin
socketio = SocketIO(
    app, 
    async_mode='eventlet',
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    path='/socket.io'
)

# Worker function to process console commands
def console_worker():
    """Background worker that processes commands from the queue."""
    while True:
        try:
            # Get the next command from the queue
            cmd, cwd = command_queue.get(timeout=1.0)
            
            app.logger.info(f"WebSocket: Received command: {cmd}")
            
            # Handle empty command (just pressing Enter) or just whitespace
            if not cmd.strip():
                socketio.emit('message', '\n', namespace='/console')
                socketio.emit('command_complete', namespace='/console')
                continue
            
            try:
                # Execute the command in the specified directory
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=cwd,
                    text=True
                )
                
                # Stream output line by line
                for line in iter(process.stdout.readline, ''):
                    if line:
                        socketio.emit('message', line, namespace='/console')
                
                # Make sure the process has completed
                process.wait()
                
                # Emit command complete event to client
                socketio.emit('command_complete', namespace='/console')
                
            except Exception as e:
                app.logger.error(f"Command execution error: {str(e)}")
                socketio.emit('message', f"Error: {str(e)}\n", namespace='/console')
                socketio.emit('command_complete', namespace='/console')
                
        except Empty:
            # No commands in queue, sleep briefly
            eventlet.sleep(0.1)
        except Exception as e:
            app.logger.error(f"Console worker error: {str(e)}")
            eventlet.sleep(1.0)  # Sleep longer on error

# Store session data
sessions = {}

@app.route('/')
def index():
    # Check if there's a pending connection sharing confirmation
    try:
        from modules.connection_sharing import get_sharing_status, CONFIRMATION_TIMEOUT
        status = get_sharing_status()
        
        if status.get('pending_confirmation', False):
            # Calculate remaining time
            import time
            timestamp = status.get('timestamp', time.time())
            elapsed = time.time() - timestamp
            remaining = max(0, int(CONFIRMATION_TIMEOUT - elapsed))
            
            # Render the confirmation page with the current config and timeout
            return render_template('connection_confirm.html', 
                                  config=status, 
                                  timeout=remaining)
    except Exception as e:
        app.logger.error(f"Error checking connection sharing status: {str(e)}")
    
    # If no pending confirmation or error, show the normal index page
    return render_template('index.html')

# Import and register blueprint routes
from routes.control import bp as control_bp
app.register_blueprint(control_bp)

# Import other route blueprints
try:
    from routes.capture import bp as capture_bp
    app.register_blueprint(capture_bp)
except ImportError:
    app.logger.warning("Capture routes not found")

try:
    from routes.tools import bp as tools_bp
    app.register_blueprint(tools_bp)
except ImportError:
    app.logger.warning("Tools routes not found")

try:
    from routes.system import bp as system_bp
    app.register_blueprint(system_bp)
except ImportError:
    app.logger.warning("System routes not found")

try:
    from routes.network import bp as network_bp
    app.register_blueprint(network_bp)
except ImportError:
    app.logger.warning("Network routes not found")

try:
    from routes.tftp import bp as tftp_bp
    app.register_blueprint(tftp_bp)
except ImportError:
    app.logger.warning("TFTP routes not found")

try:
    from routes.connection_sharing import bp as connection_sharing_bp
    app.register_blueprint(connection_sharing_bp)
except ImportError:
    app.logger.warning("Connection sharing routes not found")

try:
    from routes.scan import bp as scan_bp
    app.register_blueprint(scan_bp)
except ImportError:
    app.logger.warning("Network scan routes not found")

# Register docs blueprint
try:
    from routes.docs import bp as docs_bp
    app.register_blueprint(docs_bp)
except ImportError:
    app.logger.warning("Documentation routes not found")

# Register issues API blueprint
try:
    from routes.issues import bp as issues_bp
    app.register_blueprint(issues_bp)
except ImportError:
    app.logger.warning("Issue API routes not found")

# Helper function to handle cd command specially
def handle_cd_command(session_id, command):
    parts = command.split(None, 1)
    if len(parts) > 1:
        target_dir = parts[1].strip()
        # Handle cd .. and other relative paths
        if target_dir.startswith('/'):
            # Absolute path
            new_cwd = target_dir
        else:
            # Relative path
            current_cwd = sessions[session_id]['cwd']
            new_cwd = os.path.normpath(os.path.join(current_cwd, target_dir))
        
        try:
            # Check if directory exists and is accessible
            if os.path.isdir(new_cwd):
                sessions[session_id]['cwd'] = new_cwd
                return True, f"Changed directory to {new_cwd}"
            else:
                return False, f"cd: {target_dir}: No such file or directory"
        except Exception as e:
            return False, f"cd: error: {str(e)}"
    else:
        # Plain 'cd' goes to home directory
        home_dir = os.path.expanduser("~")
        sessions[session_id]['cwd'] = home_dir
        return True, f"Changed directory to {home_dir}"

# WebSocket for console access
@socketio.on('connect', namespace='/console')
def console_connect():
    """Handle client connection to the console."""
    session_id = request.sid
    session = sessions.get(session_id, {})
    session['cwd'] = os.getcwd()
    try:
        # Get username and hostname for session info (not for output)
        result = subprocess.check_output(['whoami'], stderr=subprocess.STDOUT, text=True).strip()
        session['username'] = result
    except Exception:
        session['username'] = 'admin'
    
    try:
        result = subprocess.check_output(['hostname'], stderr=subprocess.STDOUT, text=True).strip()
        session['hostname'] = result
    except Exception:
        session['hostname'] = 'raspberrypi'
    
    # Save session
    sessions[session_id] = session
    
    # Send clean welcome message without prompt - client will add the prompt
    socketio.emit('message', 'Connected to console server\n', namespace='/console')

@socketio.on('disconnect', namespace='/console')
def console_disconnect():
    app.logger.info('WebSocket: Client disconnected from console')
    # Clean up session data
    if request.sid in sessions:
        del sessions[request.sid]

@socketio.on('tab_completion', namespace='/console')
def handle_tab_completion(input_text):
    """Process tab completion requests from the client."""
    session_id = request.sid
    session = sessions.get(session_id, {})
    
    if not session or 'cwd' not in session:
        # No valid session, return empty results
        socketio.emit('tab_completion_result', {'completions': []}, namespace='/console')
        return
    
    cwd = session['cwd']
    app.logger.info(f"Tab completion request: {input_text} in directory {cwd}")
    
    try:
        # Use the bash built-in compgen command to get completions
        # This gives us file/directory completions as well as command completions
        cmd = f"cd {cwd} && compgen -c -f -A function -A alias -A builtin -A keyword -- '{input_text}' | sort -u"
        result = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, executable='/bin/bash')
        
        # Process the completions
        completions = result.strip().split('\n')
        
        # Filter out empty results
        completions = [comp for comp in completions if comp.strip()]
        
        # If only one completion and it's a directory, add trailing slash
        if len(completions) == 1 and os.path.isdir(os.path.join(cwd, completions[0])):
            completions[0] = completions[0] + '/'
        
        app.logger.info(f"Tab completions found: {len(completions)}")
        
        # Return the completions to the client
        socketio.emit('tab_completion_result', {'completions': completions}, namespace='/console')
        
    except Exception as e:
        app.logger.error(f"Tab completion error: {str(e)}")
        # Return empty results on error
        socketio.emit('tab_completion_result', {'completions': []}, namespace='/console')

@socketio.on('message', namespace='/console')
def console_message(message):
    """Process a command from the client."""
    global thread
    if not thread or not thread.is_alive():
        thread = socketio.start_background_task(target=console_worker)
        
    # Store current working directory in session
    session_id = request.sid
    session = sessions.get(session_id, {})
    if 'cwd' not in session:
        session['cwd'] = os.getcwd()
    
    # Store/update the session
    sessions[session_id] = session
    
    # Special handling for cd command to track directory changes
    if message.startswith('cd ') or message.strip() == 'cd':
        try:
            # Use our helper function to handle cd
            success, message_text = handle_cd_command(session_id, message)
            
            if success:
                # Change the actual working directory to match
                os.chdir(sessions[session_id]['cwd'])
                
                # Send directory change notification
                socketio.emit('message', message_text, namespace='/console')
            else:
                # Send error message
                socketio.emit('message', message_text + '\n', namespace='/console')
                
            # Indicate command is complete
            socketio.emit('command_complete', namespace='/console')
            return
        except Exception as e:
            # Send error without a prompt
            socketio.emit('message', f"cd: {str(e)}\n", namespace='/console')
            socketio.emit('command_complete', namespace='/console')
            return
    
    # Special handling for pwd
    elif message.strip() == 'pwd':
        socketio.emit('message', f"{session['cwd']}\n", namespace='/console')
        socketio.emit('command_complete', namespace='/console')
        return
    
    # Special handling for whoami
    elif message.strip() == 'whoami':
        try:
            result = subprocess.check_output(['whoami'], stderr=subprocess.STDOUT, text=True).strip()
            socketio.emit('message', f"{result}\n", namespace='/console')
        except Exception:
            socketio.emit('message', "admin\n", namespace='/console')
        socketio.emit('command_complete', namespace='/console')
        return
    
    # Special handling for hostname
    elif message.strip() == 'hostname':
        try:
            result = subprocess.check_output(['hostname'], stderr=subprocess.STDOUT, text=True).strip()
            socketio.emit('message', f"{result}\n", namespace='/console')
        except Exception:
            socketio.emit('message', "raspberrypi\n", namespace='/console')
        socketio.emit('command_complete', namespace='/console')
        return
    
    # For all other commands - execute in the tracked current directory
    command_queue.put((message, session['cwd']))

# Main entry point for running the app directly
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) # Console implementation updated
