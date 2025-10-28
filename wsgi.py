"""
WSGI entry point for Gunicorn
"""
from app import app, socketio

if __name__ == '__main__':
    socketio.run(app)
