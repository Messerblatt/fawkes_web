import os
import sys
import re
import json
import time
import shutil
import subprocess
import threading
import uuid
import secrets
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, abort, g
from flask_socketio import SocketIO, emit, disconnect, join_room
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
    'img-src': ["'self'", "data:", "blob:", "https:"],
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

# ---------------------------------------------------------------------------
# Job store: every cloaked image lives in its own directory
#   images/jobs/<client_id>/<job_id>/{meta.json, <name>_cloaked.png}
# and is deleted (overwritten with random data, then unlinked) after
# RETENTION_HOURS. The client_id is a random cookie, so each browser only
# sees its own history.
# ---------------------------------------------------------------------------
def _retention_hours():
    try:
        value = float(os.environ.get('FAWKES_RETENTION_HOURS', '12'))
        return value if value > 0 else 12.0
    except ValueError:
        return 12.0

RETENTION_HOURS = _retention_hours()
RETENTION_SECONDS = RETENTION_HOURS * 3600
MAX_JOBS_PER_CLIENT = 50
JOBS_ROOT = os.path.join(os.getcwd(), app.config['UPLOAD_FOLDER'], 'jobs')
os.makedirs(JOBS_ROOT, exist_ok=True)

ID_RE = re.compile(r'^[0-9a-f]{32}$')
CLIENT_COOKIE = 'fawkes_client'

def job_path(client_id, job_id):
    if not ID_RE.match(client_id) or not ID_RE.match(job_id):
        raise ValueError('Invalid id')
    return os.path.join(JOBS_ROOT, client_id, job_id)

def read_meta(job_dir):
    try:
        with open(os.path.join(job_dir, 'meta.json')) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

def write_meta(job_dir, meta):
    tmp = os.path.join(job_dir, 'meta.json.tmp')
    with open(tmp, 'w') as f:
        json.dump(meta, f)
    os.replace(tmp, os.path.join(job_dir, 'meta.json'))

def secure_delete_file(path, passes=2):
    """Overwrite a file with random bytes, flush to disk, then unlink it.

    Best effort: on copy-on-write / SSD / thin-provisioned storage the old
    blocks may still exist physically, but the file is unreachable and its
    logical content has been overwritten.
    """
    try:
        if not os.path.islink(path) and os.path.isfile(path):
            size = os.path.getsize(path)
            with open(path, 'r+b') as f:
                for _ in range(passes):
                    f.seek(0)
                    remaining = size
                    while remaining > 0:
                        chunk = min(1 << 20, remaining)
                        f.write(os.urandom(chunk))
                        remaining -= chunk
                    f.flush()
                    os.fsync(f.fileno())
    except OSError:
        pass
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError:
        pass

def secure_delete_dir(path):
    for root, _dirs, files in os.walk(path):
        for name in files:
            secure_delete_file(os.path.join(root, name))
    shutil.rmtree(path, ignore_errors=True)

def iter_client_jobs(client_id):
    """Yield (job_id, job_dir, meta) for one client."""
    client_dir = os.path.join(JOBS_ROOT, client_id)
    try:
        names = os.listdir(client_dir)
    except OSError:
        return
    for job_id in names:
        job_dir = os.path.join(client_dir, job_id)
        if ID_RE.match(job_id) and os.path.isdir(job_dir):
            yield job_id, job_dir, read_meta(job_dir)

def cleanup_expired():
    """Delete expired jobs, orphaned/crashed jobs and empty client dirs."""
    now = time.time()
    try:
        clients = os.listdir(JOBS_ROOT)
    except OSError:
        return
    for client_id in clients:
        client_dir = os.path.join(JOBS_ROOT, client_id)
        if not ID_RE.match(client_id) or not os.path.isdir(client_dir):
            continue
        for job_id, job_dir, meta in iter_client_jobs(client_id):
            if job_id in active_sessions:
                continue
            if meta is None:
                try:
                    expires = os.path.getmtime(job_dir) + RETENTION_SECONDS
                except OSError:
                    continue
                if now >= expires:
                    secure_delete_dir(job_dir)
                continue
            # a job left in "processing" without a running thread = crashed
            crashed = meta.get('status') == 'processing'
            if crashed or now >= meta.get('expires_at', 0):
                secure_delete_dir(job_dir)
        try:
            os.rmdir(client_dir)  # only succeeds if empty
        except OSError:
            pass

def cleanup_legacy_files():
    """Securely erase image files left directly in images/ by the old
    single-folder version (the new code only uses images/jobs/...)."""
    base = os.path.join(os.getcwd(), app.config['UPLOAD_FOLDER'])
    try:
        names = os.listdir(base)
    except OSError:
        return
    for name in names:
        path = os.path.join(base, name)
        if os.path.isfile(path) and name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            secure_delete_file(path)
            print(f'Erased legacy file: {name}')

_cleanup_state = {'last': 0.0, 'loop_started': False}

def _cleanup_loop():
    while True:
        socketio.sleep(60)
        try:
            cleanup_expired()
            _cleanup_state['last'] = time.time()
        except Exception as e:
            print(f'Cleanup error: {e}')

@app.before_request
def identify_client():
    cid = request.cookies.get(CLIENT_COOKIE, '')
    g.new_client = False
    if not ID_RE.match(cid):
        cid = secrets.token_hex(16)
        g.new_client = True
    g.client_id = cid
    # lazy start of the periodic cleanup (works with gunicorn preload_app)
    if not _cleanup_state['loop_started']:
        _cleanup_state['loop_started'] = True
        cleanup_legacy_files()
        cleanup_expired()
        socketio.start_background_task(_cleanup_loop)
    elif time.time() - _cleanup_state['last'] > 30:
        _cleanup_state['last'] = time.time()
        cleanup_expired()

@app.after_request
def persist_client_cookie(resp):
    if getattr(g, 'new_client', False):
        resp.set_cookie(CLIENT_COOKIE, g.client_id, max_age=365 * 24 * 3600,
                        httponly=True, samesite='Lax',
                        secure=app.config['SESSION_COOKIE_SECURE'])
    return resp

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

def _cpu_limit_percent():
    try:
        value = float(os.environ.get('FAWKES_CPU_LIMIT_PERCENT', '20'))
        return value if value >= 0 else 20.0
    except ValueError:
        return 20.0

# max CPU for Mid/High, as % of the TOTAL CPU capacity of the machine
# (20 on 2 cores = 40% of one core). 0 disables the limit.
CPU_LIMIT_PERCENT = _cpu_limit_percent()
ADVANCED_MEMORY_MAX = os.environ.get('FAWKES_ADVANCED_MEMORY_MAX', '1500M')
_cpu_limit_ok = {'checked': False, 'ok': False}

def _usable_cores():
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:
        return max(1, os.cpu_count() or 1)

def cpu_limit_available():
    """systemd-run --scope (cgroup CPUQuota) must work in this environment."""
    if not _cpu_limit_ok['checked']:
        _cpu_limit_ok['checked'] = True
        sd = shutil.which('systemd-run')
        if sd:
            try:
                r = subprocess.run([sd, '--scope', '--quiet', '--collect', '--', 'true'],
                                   capture_output=True, timeout=15)
                _cpu_limit_ok['ok'] = r.returncode == 0
            except (OSError, subprocess.SubprocessError):
                pass
    return _cpu_limit_ok['ok']

def build_fawkes_command(job_dir, mode):
    """Return (argv, note). Mid/High run in a CPU-capped, low-priority cgroup scope."""
    base = [sys.executable, 'protection.py', '-d', job_dir, '--mode', mode]
    if mode not in ('mid', 'high') or CPU_LIMIT_PERCENT <= 0:
        return base, None
    if not cpu_limit_available():
        return ['nice', '-n', '19'] + base, 'CPU cap unavailable here, running at lowest priority instead.'
    quota = max(5, int(round(CPU_LIMIT_PERCENT * _usable_cores())))
    argv = [shutil.which('systemd-run'), '--scope', '--quiet', '--collect',
            '-p', f'CPUQuota={quota}%', '-p', f'MemoryMax={ADVANCED_MEMORY_MAX}',
            '--', 'nice', '-n', '19'] + base
    return argv, f'CPU limited to {CPU_LIMIT_PERCENT:g}% of the server (slower, but the server stays responsive).'

def run_fawkes_command(job_id, client_id, mode):
    """Run Fawkes on one job directory and report progress to that client only."""
    def emit_out(text):
        socketio.emit('command_output', {'data': text, 'session_id': job_id}, to=client_id)

    def emit_done(success, message):
        socketio.emit('command_complete', {
            'success': success, 'message': message,
            'session_id': job_id, 'job_id': job_id
        }, to=client_id)
        socketio.emit('jobs_changed', {}, to=client_id)

    job_dir = job_path(client_id, job_id)
    fawkes_dir = os.path.join(os.getcwd(), 'fawkes')
    try:
        if mode not in ['low', 'mid', 'high']:
            raise ValueError('Invalid mode')
        if not os.path.exists(os.path.join(fawkes_dir, 'protection.py')):
            raise ValueError('protection.py not found')
        meta = read_meta(job_dir)
        if meta is None:
            raise ValueError('Job not found')

        meta['status'] = 'processing'
        meta['mode'] = mode
        write_meta(job_dir, meta)
        socketio.emit('jobs_changed', {}, to=client_id)

        emit_out(f'Starting cloaking process in {mode} mode...\n')
        emit_out(f"Processing {meta.get('name', 'image')}...\n")

        # list format + shell=False prevents shell injection
        cmd, limit_note = build_fawkes_command(job_dir, mode)
        if limit_note:
            emit_out(limit_note + '\n')
        process = subprocess.Popen(
            cmd, cwd=fawkes_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1, shell=False
        )
        tail = []
        for line in process.stdout:
            tail.append(line)
            tail = tail[-15:]
            emit_out(line)
        process.wait()

        cloaked = [f for f in os.listdir(job_dir) if '_cloaked.' in f]
        if process.returncode == 0 and cloaked:
            # the original face photo is no longer needed: wipe it now
            for name in os.listdir(job_dir):
                if name not in cloaked and name != 'meta.json':
                    secure_delete_file(os.path.join(job_dir, name))
            now = time.time()
            meta.update({
                'status': 'done',
                'cloaked_file': cloaked[0],
                'finished_at': now,
                'expires_at': now + RETENTION_SECONDS,
            })
            write_meta(job_dir, meta)
            emit_out('Cloaking completed successfully.\n')
            emit_done(True, 'Cloaking completed')
        else:
            message = ''.join(tail)[-500:].strip() or f'Process failed with exit code {process.returncode}'
            secure_delete_dir(job_dir)
            emit_done(False, message)
    except Exception as e:
        error_msg = str(e)[:200]
        emit_out(f'Error: {error_msg}\n')
        secure_delete_dir(job_dir)
        emit_done(False, error_msg)
    finally:
        active_sessions.pop(job_id, None)

@app.route('/')
@limiter.limit("30 per minute")
def index():
    gpu_available = check_gpu_availability()
    return render_template('index.html', gpu_available=gpu_available,
                           retention_hours=RETENTION_HOURS)

def serialize_job(job_id, meta):
    return {
        'id': job_id,
        'name': meta.get('name', 'image'),
        'mode': meta.get('mode'),
        'status': meta.get('status'),
        'remaining_seconds': max(0, int(meta.get('expires_at', 0) - time.time())),
    }

def get_owned_job(job_id):
    """Return (job_dir, meta) for a job owned by the current client, else 404."""
    if not ID_RE.match(job_id):
        abort(404)
    job_dir = job_path(g.client_id, job_id)
    meta = read_meta(job_dir) if os.path.isdir(job_dir) else None
    if meta is None:
        abort(404)
    return job_dir, meta

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

        filename = sanitize_filename(file.filename)
        if not allowed_file(filename):
            return jsonify({'error': 'Invalid file type'}), 400

        jobs = list(iter_client_jobs(g.client_id))
        # a new upload replaces this client's previous not-yet-cloaked upload
        for old_id, old_dir, old_meta in jobs:
            if old_meta and old_meta.get('status') == 'uploaded':
                secure_delete_dir(old_dir)
        if len(jobs) >= MAX_JOBS_PER_CLIENT:
            return jsonify({'error': 'Too many stored images, delete some first'}), 429

        job_id = secrets.token_hex(16)
        job_dir = job_path(g.client_id, job_id)
        os.makedirs(job_dir)
        file_path = os.path.join(job_dir, filename)
        file.save(file_path)

        if not validate_file_content(file_path):
            secure_delete_dir(job_dir)
            return jsonify({'error': 'Invalid or corrupted image file'}), 400

        now = time.time()
        write_meta(job_dir, {
            'id': job_id, 'name': filename, 'status': 'uploaded',
            'created_at': now, 'expires_at': now + RETENTION_SECONDS,
        })
        return jsonify({
            'success': True,
            'filename': filename,
            'job_id': job_id,
            'message': 'File uploaded successfully'
        })
    except Exception as e:
        return jsonify({'error': 'Upload failed'}), 500

@app.route('/cloak', methods=['POST'])
@limiter.limit("5 per minute")
def start_cloaking():
    try:
        clean_old_sessions()

        if len(active_sessions) >= MAX_CONCURRENT_SESSIONS:
            return jsonify({'error': 'Server busy, please try again later'}), 429

        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid request'}), 400

        mode = data.get('mode', 'low')
        job_id = data.get('job_id', '')
        if mode not in ['low', 'mid', 'high']:
            return jsonify({'error': 'Invalid mode'}), 400
        if not isinstance(job_id, str) or not ID_RE.match(job_id):
            return jsonify({'error': 'Invalid job ID'}), 400

        job_dir = job_path(g.client_id, job_id)
        meta = read_meta(job_dir) if os.path.isdir(job_dir) else None
        if meta is None or meta.get('status') != 'uploaded' or job_id in active_sessions:
            return jsonify({'error': 'No image found to process'}), 400

        active_sessions[job_id] = datetime.now()
        thread = threading.Thread(
            target=run_fawkes_command,
            args=(job_id, g.client_id, mode)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Cloaking started',
            'session_id': job_id,
            'job_id': job_id
        })
    except Exception as e:
        return jsonify({'error': 'Failed to start cloaking'}), 500

@app.route('/api/jobs')
@limiter.exempt
def list_jobs():
    """History of this browser's cloaked images (newest first)."""
    jobs = []
    for job_id, _dir, meta in iter_client_jobs(g.client_id):
        if meta and meta.get('status') in ('done', 'processing'):
            jobs.append((meta.get('created_at', 0), serialize_job(job_id, meta)))
    jobs.sort(key=lambda item: item[0], reverse=True)
    resp = jsonify({
        'retention_hours': RETENTION_HOURS,
        'jobs': [j for _, j in jobs],
    })
    resp.headers['Cache-Control'] = 'no-store'
    return resp

def _send_cloaked(job_id, as_attachment):
    job_dir, meta = get_owned_job(job_id)
    if meta.get('status') != 'done' or time.time() >= meta.get('expires_at', 0):
        abort(404)
    file_path = os.path.join(job_dir, os.path.basename(meta.get('cloaked_file', '')))
    if not os.path.isfile(file_path):
        abort(404)
    resp = send_file(file_path, mimetype='image/png', as_attachment=as_attachment,
                     download_name=os.path.basename(meta['cloaked_file']))
    resp.headers['Cache-Control'] = 'private, no-store'
    return resp

@app.route('/api/jobs/<job_id>/preview')
@limiter.exempt
def job_preview(job_id):
    return _send_cloaked(job_id, as_attachment=False)

@app.route('/api/jobs/<job_id>/download')
@limiter.limit("30 per minute")
def job_download(job_id):
    return _send_cloaked(job_id, as_attachment=True)

@app.route('/api/jobs/<job_id>', methods=['DELETE'])
@limiter.limit("30 per minute")
def job_delete(job_id):
    job_dir, _meta = get_owned_job(job_id)
    if job_id in active_sessions:
        return jsonify({'error': 'Job is still processing'}), 409
    secure_delete_dir(job_dir)
    return jsonify({'success': True})

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
    # each browser listens only to its own events (private room = client id)
    client_id = request.cookies.get(CLIENT_COOKIE, '')
    if ID_RE.match(client_id):
        join_room(client_id)

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
