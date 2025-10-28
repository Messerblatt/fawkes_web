#!/usr/bin/env python3
"""
Fawkes Web Server Runner
Run this script to start the Fawkes web interface
"""

import os
import sys
from app import app, socketio

def main():
    print("=" * 60)
    print("FAWKES WEB INTERFACE")
    print("Privacy Preserving Tool Against Facial Recognition")
    print("=" * 60)
    print()
    
    # Check if fawkes directory exists
    if not os.path.exists('fawkes'):
        print("ERROR: Fawkes directory not found!")
        print("Please ensure the fawkes directory is present with protection.py")
        sys.exit(1)
    
    # Check if protection.py exists
    if not os.path.exists('fawkes/protection.py'):
        print("ERROR: protection.py not found in fawkes directory!")
        print("Please ensure Fawkes is properly installed")
        sys.exit(1)
    
    print("Starting Fawkes web server...")
    print("Access the interface at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print()
    
    try:
        socketio.run(app, debug=False, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server error: {e}")

if __name__ == '__main__':
    main()
