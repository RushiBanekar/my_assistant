#!/usr/bin/env python3
"""
Unified launcher for Sylvia Voice Assistant
Starts both backend API and frontend web interface
Author: Rushi Banekar
"""

import subprocess
import time
import sys
import os
import webbrowser
from threading import Thread
import requests

def check_port_available(port):
    """Check if a port is available"""
    try:
        response = requests.get(f'http://127.0.0.1:{port}', timeout=1)
        return False  # Port is in use
    except:
        return True  # Port is available

def wait_for_backend(port=5001, timeout=30):
    """Wait for backend to be ready"""
    print(f"[INFO] Waiting for backend API on port {port}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f'http://127.0.0.1:{port}/api/assistant_state', timeout=2)
            if response.status_code == 200:
                print("[INFO] ✅ Backend API is ready!")
                return True
        except:
            pass
        time.sleep(1)
    
    print(f"[ERROR] ❌ Backend API failed to start within {timeout} seconds")
    return False

def open_browser_delayed():
    """Open browser after a short delay"""
    time.sleep(3)  # Wait for frontend to start
    try:
        webbrowser.open('http://127.0.0.1:5000')
        print("[INFO] 🌐 Browser opened to http://127.0.0.1:5000")
    except Exception as e:
        print(f"[WARNING] Could not open browser automatically: {e}")
        print("[INFO] Please manually open http://127.0.0.1:5000 in your browser")

def main():
    print("=" * 60)
    print("🎤 SYLVIA VOICE ASSISTANT - UNIFIED LAUNCHER")
    print("=" * 60)
    print("Created by: Rushi Banekar")
    print("Starting both backend API and frontend web interface...")
    print("=" * 60)
    
    # Check if ports are available
    if not check_port_available(5001):
        print("[ERROR] ❌ Port 5001 is already in use. Please stop any running backend.")
        sys.exit(1)
    
    if not check_port_available(5000):
        print("[ERROR] ❌ Port 5000 is already in use. Please stop any running frontend.")
        sys.exit(1)
    
    try:
        # Start backend API server
        print("[INFO] 🚀 Starting backend API server on port 5001...")
        backend_process = subprocess.Popen([
            sys.executable, 'assistant.py', '--mode', 'api', '--port', '5001'
        ], cwd=os.path.dirname(os.path.abspath(__file__)))
        
        # Wait for backend to be ready
        if not wait_for_backend():
            print("[ERROR] Failed to start backend. Terminating...")
            backend_process.terminate()
            sys.exit(1)
        
        # Start frontend web server
        print("[INFO] 🌐 Starting frontend web server on port 5000...")
        frontend_env = os.environ.copy()
        frontend_env['SYLVIA_UNIFIED_LAUNCH'] = 'true'
        frontend_process = subprocess.Popen([
            sys.executable, 'app.py'
        ], cwd=os.path.dirname(os.path.abspath(__file__)), env=frontend_env)
        
        # Open browser in background
        browser_thread = Thread(target=open_browser_delayed, daemon=True)
        browser_thread.start()
        
        print("\n" + "=" * 60)
        print("✅ SYLVIA VOICE ASSISTANT IS NOW RUNNING!")
        print("=" * 60)
        print("🔗 Frontend URL: http://127.0.0.1:5000")
        print("🔗 Backend API: http://127.0.0.1:5001")
        print("=" * 60)
        print("📋 USAGE INSTRUCTIONS:")
        print("1. Click 'Start Listening' in the web interface")
        print("2. Say 'Sylvia' to activate the assistant")
        print("3. Have a conversation with your voice assistant")
        print("4. Say 'exit' or 'bye' to end the conversation")
        print("5. Use Ctrl+C here to stop both servers")
        print("=" * 60)
        
        # Wait for user interruption
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[INFO] 🛑 Shutting down Sylvia Voice Assistant...")
            
            # Terminate processes
            print("[INFO] Stopping frontend server...")
            frontend_process.terminate()
            
            print("[INFO] Stopping backend server...")
            backend_process.terminate()
            
            # Wait for processes to terminate
            frontend_process.wait(timeout=5)
            backend_process.wait(timeout=5)
            
            print("[INFO] ✅ Sylvia Voice Assistant stopped successfully!")
            print("Thank you for using Sylvia! 👋")
            
    except Exception as e:
        print(f"[ERROR] ❌ Failed to start Sylvia Voice Assistant: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
