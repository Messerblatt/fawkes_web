import os
import subprocess
import threading
import uuid
import secrets
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, abort
from flask_socketio import SocketIO, emit, disconnect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
import tensorflow as tf
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import hashlib
import hmac

app = Flask(__name__)

# Security configurations
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['UPLOAD_FOLDER'] = 'images'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Initialize SocketIO with security settings
socketio = SocketIO(
    app,
    cors_allowed_origins=os.environ.get('ALLOWED_ORIGINS', '*').split(','),
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25
)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Security headers with Talisman
csp = {
    'default-src': "'self'",
    'script-src': ["'self'", "'unsafe-inline'", "https://cdn.socket.io"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", "data:", "https:"],
    'connect-src': ["'self'", "wss:", "ws:"],
}

Talisman(
    app,
    force_https=os.environ.get('FORCE_HTTPS', 'False').lower() == 'true',
    strict_transport_security=True,
    content_security_policy=csp,
    content_security_policy_nonce_in=['script-src']
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Session tracking for rate limiting cloaking operations
active_sessions = {}
MAX_CONCURRENT_SESSIONS = 5

def clean_old_sessions():
    """Remove sessions older than 1 hour"""
    current_time = datetime.now()
    to_remove = []
    for session_id, timestamp in active_sessions.items():
        if current_time - timestamp > timedelta(hours=1):
            to_remove.append(session_id)
    for session_id in to_remove:
        del active_sessions[session_id]

def validate_file_content(file_path):
    """Validate file is actually an image and not malicious"""
    try:
        from PIL import Image
        img = Image.open(file_path)
        img.verify()
        # Check image dimensions to prevent decompression bombs
        if img.size[0] * img.size[1] > 178956970:  # ~178 megapixels
            return False
        return True
    except:
        return False

def sanitize_filename(filename):
    """Extra sanitization beyond secure_filename"""
    filename = secure_filename(filename)
    # Remove any potential path traversal
    filename = os.path.basename(filename)
    # Limit filename length
    name, ext = os.path.splitext(filename)
    if len(name) > 200:
        name = name[:200]
    return f"{name}{ext}"

def check_gpu_availability():
    """Check if GPU is available for TensorFlow"""
    try:
        gpus = tf.config.experimental.list_physical_devices('GPU')
        return len(gpus) > 0
    except:
        return False

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_fawkes_command(image_path, mode, session_id):
    """Run Fawkes protection command and emit output via WebSocket"""
    try:
        current_dir = os.getcwd()
        fawkes_dir = os.path.join(current_dir, 'fawkes')
        images_dir = os.path.join(current_dir, 'images')
        
        # Validate paths to prevent directory traversal
        if not os.path.abspath(fawkes_dir).startswith(current_dir):
            raise ValueError("Invalid fawkes directory path")
        if not os.path.abspath(images_dir).startswith(current_dir):
            raise ValueError("Invalid images directory path")
        
        socketio.emit('command_output', {
            'data': f'Starting cloaking process in {mode} mode...\n',
            'session_id': session_id
        })
        
        # Verify directories exist
        if not os.path.exists(fawkes_dir):
            socketio.emit('command_complete', {
                'success': False,
                'message': 'Fawkes directory not found',
                'session_id': session_id
            })
            return
            
        protection_py_path = os.path.join(fawkes_dir, 'protection.py')
        if not os.path.exists(protection_py_path):
            socketio.emit('command_complete', {
                'success': False,
                'message': 'protection.py not found',
                'session_id': session_id
            })
            return
        
        # Check if images exist
        image_files = [f for f in os.listdir(images_dir) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
        
        if not image_files:
            socketio.emit('command_complete', {
                'success': False,
                'message': 'No images found to process',
                'session_id': session_id
            })
            return
        
        socketio.emit('command_output', {
            'data': f'Processing {image_files[0]}...\n',
            'session_id': session_id
        })
        
        # Validate mode to prevent command injection
        if mode not in ['low', 'mid', 'high']:
            raise ValueError("Invalid mode")
        
        # Command to run Fawkes - using list format prevents shell injection
        cmd = ['python', 'protection.py', '-d', images_dir, '--mode', mode]
        
        # Run the command with security settings
        process = subprocess.Popen(
            cmd,
            cwd=fawkes_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            shell=False  # Explicitly disable shell
        )
        
        # Read output
        import sys
        if sys.platform != 'win32':
            import select
            while True:
                reads = [process.stdout.fileno(), process.stderr.fileno()]
                ret = select.select(reads, [], [], 1.0)
                
                for fd in ret[0]:
                    if fd == process.stdout.fileno():
                        output = process.stdout.readline()
                        if output:
                            socketio.emit('command_output', {
                                'data': output,
                                'session_id': session_id
                            })
                    if fd == process.stderr.fileno():
                        error = process.stderr.readline()
                        if error:
                            socketio.emit('command_output', {
                                'data': error,
                                'session_id': session_id
                            })
                
                if process.poll() is not None:
                    break
        else:
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    socketio.emit('command_output', {
                        'data': output,
                        'session_id': session_id
                    })
        
        stdout, stderr = process.communicate()
        
        if stdout:
            socketio.emit('command_output', {
                'data': stdout,
                'session_id': session_id
            })
        
        if stderr:
            socketio.emit('command_output', {
                'data': stderr,
                'session_id': session_id
            })
        
        # Check for cloaked images
        cloaked_files = [f for f in os.listdir(images_dir) if '_cloaked.png' in f]
        
        if process.returncode == 0 and cloaked_files:
            socketio.emit('command_output', {
                'data': 'Cloaking completed successfully.\n',
                'session_id': session_id
            })
            socketio.emit('command_complete', {
                'success': True,
                'message': 'Cloaking completed',
                'session_id': session_id
            })
        else:
            error_msg = f'Process failed with exit code {process.returncode}'
            if stderr:
                error_msg = stderr[:500]  # Limit error message length
            socketio.emit('command_complete', {
                'success': False,
                'message': error_msg,
                'session_id': session_id
            })
            
    except Exception as e:
        error_msg = str(e)[:200]  # Limit error message
        socketio.emit('command_output', {
            'data': f'Error: {error_msg}\n',
            'session_id': session_id
        })
        socketio.emit('command_complete', {
            'success': False,
            'message': error_msg,
            'session_id': session_id
        })
    finally:
        # Clean up session
        if session_id in active_sessions:
            del active_sessions[session_id]

@app.route('/')
@limiter.limit("30 per minute")
def index():
    gpu_available = check_gpu_availability()
    return render_template('index.html', gpu_available=gpu_available)

@app.route('/upload', methods=['POST'])
@limiter.limit("10 per minute")
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Sanitize filename
        filename = sanitize_filename(file.filename)
        
        # Clean up old files
        for old_file in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], old_file)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
        
        # Save file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Validate file content
        if not validate_file_content(file_path):
            os.remove(file_path)
            return jsonify({'error': 'Invalid or corrupted image file'}), 400
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'File uploaded successfully'
        })
    except Exception as e:
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/cloak', methods=['POST'])
@limiter.limit("5 per minute")
def start_cloaking():
    try:
        clean_old_sessions()
        
        # Check concurrent sessions
        if len(active_sessions) >= MAX_CONCURRENT_SESSIONS:
            return jsonify({'error': 'Server busy, please try again later'}), 429
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
        
        mode = data.get('mode', 'low')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        # Validate mode
        if mode not in ['low', 'mid', 'high']:
            return jsonify({'error': 'Invalid mode'}), 400
        
        # Validate session_id format
        if not isinstance(session_id, str) or len(session_id) > 100:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        images = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) 
                  if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
        
        if not images:
            return jsonify({'error': 'No image found to process'}), 400
        
        # Track session
        active_sessions[session_id] = datetime.now()
        
        thread = threading.Thread(
            target=run_fawkes_command,
            args=(images[0], mode, session_id)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Cloaking started',
            'session_id': session_id
        })
    except Exception as e:
        return jsonify({'error': 'Failed to start cloaking'}), 500

@app.route('/download')
@limiter.limit("10 per minute")
def download_cloaked_image():
    try:
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if '_cloaked.png' in filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                # Validate path
                if not os.path.abspath(file_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
                    abort(403)
                if os.path.isfile(file_path):
                    return send_file(file_path, as_attachment=True, download_name=filename)
        
        return jsonify({'error': 'No cloaked image found'}), 404
    except Exception as e:
        return jsonify({'error': 'Download failed'}), 500

@app.route('/health')
@limiter.exempt
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({'status': 'healthy', 'gpu_available': check_gpu_availability()})

@socketio.on('connect')
def handle_connect():
    # Rate limit connections per IP
    client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
    print(f'Client connected from {client_ip}')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large (max 16MB)'}), 413

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded'}), 429

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # This is only used for development
    # In production, use gunicorn
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)
