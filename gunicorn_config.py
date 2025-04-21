import multiprocessing

bind = "0.0.0.0:80"
workers = 1  # Use only 1 worker for WebSockets to avoid issues
worker_class = "eventlet"
worker_connections = 1000
timeout = 300
keepalive = 5

# Logging
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "debug"
capture_output = True

# Set process name
proc_name = "raspberry_pi_webapp"

# Restart workers after this many requests
max_requests = 10000
max_requests_jitter = 1000

# Preload application code before forking
preload_app = True

# WebSocket settings
websocket_ping_interval = 25
websocket_ping_timeout = 60 