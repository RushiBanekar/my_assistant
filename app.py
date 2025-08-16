#
# File: app.py
# Description: Flask web application serving as the frontend interface for the voice assistant
# Author: Rushi Banekar
# Date: 2025-08-16
#

import webbrowser
import time
import os
from flask import Flask, render_template, jsonify, request
from threading import Thread
import requests
import logging

class NoAssistantStateFilter(logging.Filter):
    def filter(self, record):
        # Suppress all Werkzeug HTTP request logs
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            if '127.0.0.1 - - [' in record.msg:
                return False
        return True

# Add the filter to the werkzeug logger
logging.getLogger('werkzeug').addFilter(NoAssistantStateFilter())

app = Flask(__name__)

# Backend API configuration
BACKEND_API_URL = 'http://127.0.0.1:5001/api'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_listening', methods=['POST'])
def start_listening_route():
    try:
        response = requests.post(f'{BACKEND_API_URL}/start_listening')
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'error', 'message': f'Backend API unavailable: {str(e)}'})

@app.route('/stop_listening', methods=['POST'])
def stop_listening_route():
    try:
        response = requests.post(f'{BACKEND_API_URL}/stop_listening')
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'error', 'message': f'Backend API unavailable: {str(e)}'})

@app.route('/interaction_history', methods=['GET'])
def interaction_history_route():
    try:
        response = requests.get(f'{BACKEND_API_URL}/interaction_history')
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'error', 'message': f'Backend API unavailable: {str(e)}'})

@app.route('/assistant_state', methods=['GET'])
def assistant_state_route():
    try:
        response = requests.get(f'{BACKEND_API_URL}/assistant_state')
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'error', 'message': f'Backend API unavailable: {str(e)}'})

# Additional API routes for frontend functionality
@app.route('/speak', methods=['POST'])
def speak_route():
    try:
        data = request.get_json()
        response = requests.post(f'{BACKEND_API_URL}/speak', json=data)
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'error', 'message': f'Backend API unavailable: {str(e)}'})

@app.route('/get_ai_response', methods=['POST'])
def get_ai_response_route():
    try:
        data = request.get_json()
        response = requests.post(f'{BACKEND_API_URL}/get_ai_response', json=data)
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'error', 'message': f'Backend API unavailable: {str(e)}'})

def check_backend_health():
    """Check if backend API is running"""
    try:
        response = requests.get(f'{BACKEND_API_URL}/assistant_state', timeout=5)
        return response.status_code == 200
    except:
        return False

def open_browser():
    """Opens the default web browser to the correct URL after a short delay."""
    time.sleep(1) # Give the server a moment to start
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == "__main__":
    print("[INFO] Starting web frontend...")
    print("[INFO] Make sure the backend API is running on port 5001")
    print("[INFO] You can start the backend with: python assistant.py --mode api --port 5001")
    
    # Check if backend is running
    if not check_backend_health():
        print("[WARNING] Backend API is not running. Please start it first.")
        print("[INFO] Run: python assistant.py --mode api --port 5001")
    
    # Check if the reloader is NOT active
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        Thread(target=open_browser).start()
    
    app.run(host='127.0.0.1', port=5000, debug=True)