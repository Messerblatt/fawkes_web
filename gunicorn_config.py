"""
Gunicorn configuration file for production deployment
"""
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = 1  # SocketIO requires 1 worker with eventlet
worker_class = 'eventlet'
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'fawkes-web'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = '/path/to/key.pem'
# certfile = '/path/to/cert.pem'

# Environment
raw_env = [
    'FLASK_ENV=production',
]

# Preload app for better performance
preload_app = True  # Set to False for SocketIO

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
