#
# File: assistant.py
# Description: Main voice assistant module with AI integration, wake word detection, and API endpoints
# Author: Rushi Banekar
# Date: 16-August-2025
#

import pyautogui
import time
import os
import platform
import speech_recognition as sr
import pyttsx3
import json
import yaml
import subprocess
import webbrowser
import wikipedia
import google.generativeai as genai
from dotenv import load_dotenv
import sys # Import the sys module
from flask import Flask, jsonify, request
from threading import Thread
import pvporcupine
from pvrecorder import PvRecorder
import struct
import pythoncom

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY") # Keeping for completeness, not directly used here

# Initialize Google's Generative AI client
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in .env. Gemini API calls will fail.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# Initialize the model with tools capabilities
# It's better to define the model once with the tools
model = genai.GenerativeModel('gemini-pro', tools=[]) # Tools will be added after definition

def load_config():
    """Loads the YAML configuration file."""
    try:
        with open("config.yaml", "r") as file:
            config_data = yaml.safe_load(file)
            # Ensure 'assistant' section exists and set default for microphone_energy_threshold
            if "assistant" not in config_data:
                config_data["assistant"] = {}
            if "microphone_energy_threshold" not in config_data["assistant"]:
                config_data["assistant"]["microphone_energy_threshold"] = 700 # Default value
            return config_data
    except FileNotFoundError:
        print("config.yaml not found. Please create one with at least 'wake_word'.")
        sys.stdout.flush()
        # Return a default config dictionary if file is not found
        return {"assistant": {"wake_word": "sylvia", "microphone_energy_threshold": 700}}
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        sys.stdout.flush()
        # Return a default config dictionary if parsing fails
        return {"assistant": {"wake_word": "sylvia", "microphone_energy_threshold": 700}}

config = load_config()
WAKE_WORD = config.get("assistant", {}).get("wake_word", "sylvia").lower() # Ensure wake word is lowercased
VOICE_ID = config.get("assistant", {}).get("voice_id", None)
MICROPHONE_ENERGY_THRESHOLD = config.get("assistant", {}).get("microphone_energy_threshold", 700) # Get from config

# Initialize TTS engine
engine = pyttsx3.init()
if VOICE_ID:
    print(f"[DEBUG] Attempting to set voice to ID from config: {VOICE_ID}")
    sys.stdout.flush()
    try:
        engine.setProperty('voice', VOICE_ID)
        current_voice = engine.getProperty('voice')
        if current_voice != VOICE_ID:
            print(f"[WARNING] Requested voice ID {VOICE_ID} was not fully set. Current voice: {current_voice}")
            sys.stdout.flush()
    except Exception as e:
        print(f"[ERROR] Failed to set voice to {VOICE_ID}: {e}")
        sys.stdout.flush()
        print("[DEBUG] Falling back to default voice selection due to error.")
        sys.stdout.flush()
        VOICE_ID = None # Force fallback if setting fails
if not VOICE_ID: # This block now runs if VOICE_ID was None initially or failed to set
    voices = engine.getProperty('voices')
    if voices:
        print("[DEBUG] No specific VOICE_ID set or failed to set. Listing available voices:")
        sys.stdout.flush()
        en_voices = []
        for i, voice in enumerate(voices):
            # Check if voice.languages is not None and contains any string starting with 'en'
            print(f"  Voice {i}: ID='{voice.id}', Name='{voice.name}', Languages='{voice.languages}'")
            sys.stdout.flush()
            if voice.languages and any(lang.lower().startswith('en') for lang in voice.languages):
                en_voices.append(voice.id)

        if en_voices:
            # Prefer Zira if available and English, otherwise pick first English
            zira_voice_id = next((vid for vid in en_voices if "zira" in vid.lower()), None)
            if zira_voice_id:
                engine.setProperty('voice', zira_voice_id)
                print(f"[DEBUG] Selected Zira (English) voice: {zira_voice_id}")
                sys.stdout.flush()
            else:
                engine.setProperty('voice', en_voices[0])
                print(f"[DEBUG] Selected first available English voice: {en_voices[0]}")
                sys.stdout.flush()
        else:
            engine.setProperty('voice', voices[0].id) # Fallback to first available voice
            print(f"[DEBUG] No English voices found. Selected first available voice: {voices[0].id}")
            sys.stdout.flush()
    else:
        print("No voices found. Text-to-speech might not work.")
        sys.stdout.flush()

def speak(text):
    """Converts text to speech using the TTS engine and flushes output."""
    print(f"Assistant: {text}")
    sys.stdout.flush() # Ensure this message is displayed immediately
    engine.say(text)
    engine.runAndWait()

def listen_for_command():
    """
    Listens for a voice command and transcribes it.
    Uses configurable microphone sensitivity and improved error handling.
    Flushes output for immediate display.
    """
    r = sr.Recognizer()
    try:
        print("[DEBUG] Checking available microphones...")
        sys.stdout.flush()
        mic_list = sr.Microphone.list_microphone_names()
        print(f"[DEBUG] Available microphones: {mic_list}")
        sys.stdout.flush()
        
        with sr.Microphone() as source:
            print("[DEBUG] Microphone initialized. Adjusting for ambient noise...")
            sys.stdout.flush()
            r.pause_threshold = 0.8
            r.energy_threshold = MICROPHONE_ENERGY_THRESHOLD # <<< FIXED: Now uses configurable threshold
            r.dynamic_energy_threshold = True
            
            print(f"[DEBUG] Current energy threshold for speech detection: {r.energy_threshold}")
            print("[DEBUG] Please wait! Calibrating microphone...")
            sys.stdout.flush()
            r.adjust_for_ambient_noise(source, duration=2)
            print("[DEBUG] Done calibrating. Ready to listen!")
            sys.stdout.flush()
            print("\n[DEBUG] Listening for a command... (Speak now!)")
            sys.stdout.flush()
            
            try:
                audio = r.listen(source, timeout=7, phrase_time_limit=8)
                print("[DEBUG] Audio captured! Processing...")
                sys.stdout.flush()
                
                audio_data = audio.get_raw_data()
                print(f"[DEBUG] Audio data length: {len(audio_data)} bytes")
                sys.stdout.flush()
                
                command = r.recognize_google(audio, language='en-in').lower()
                print(f"[DEBUG] Recognized: {command}")
                sys.stdout.flush()
                return command
                
            except sr.WaitTimeoutError:
                print("[DEBUG] No speech detected within timeout period.")
                sys.stdout.flush()
                return "no_speech_detected"
            except sr.UnknownValueError:
                print("Sorry, I could not understand the audio.")
                sys.stdout.flush()
                return "speech_unintelligible"
            except sr.RequestError as e:
                print(f"Could not request results from Google Speech Recognition service; {e}")
                sys.stdout.flush()
                return "speech_service_error"
                
    except Exception as e:
        print(f"[DEBUG] General error in listen_for_command: {str(e)}")
        sys.stdout.flush()
        if "NoDefaultInputDeviceAvailable" in str(e) or "Input device already in use" in str(e):
            print("[DEBUG] No default input device found. Check your microphone connection.")
            sys.stdout.flush()
        return "general_microphone_error"

def send_whatsapp_message(contact, message):
    """
    Automates WhatsApp desktop app to send a message to a contact.
    Note: This function relies on pyautogui for UI automation,
    which requires the WhatsApp desktop app to be installed and accessible.
    """
    try:
        desktop_path = os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\WhatsApp\WhatsApp.exe")
        
        if not os.path.exists(desktop_path):
            print("WhatsApp desktop app not found at expected path. Attempting generic open via URI scheme.")
            sys.stdout.flush()
            try:
                if platform.system() == "Windows":
                    subprocess.run(["start", "whatsapp://send?text="], shell=True, check=True)
                elif platform.system() == "Darwin": # macOS
                    subprocess.run(["open", "-a", "WhatsApp"], check=True)
                else: # Linux
                    subprocess.run(["xdg-open", "whatsapp://"], check=True) # Basic Linux URI open
                time.sleep(7) # Give more time for generic open
            except Exception as e:
                print(f"WhatsApp desktop app not found or could not be launched. Error: {e}")
                sys.stdout.flush()
                return f"WhatsApp desktop app not found or could not be launched. Error: {e}"
        else:
            os.startfile(desktop_path)
            time.sleep(5) # Wait for app to open

        pyautogui.hotkey('ctrl', 'f') # Focus search bar
        time.sleep(1)
        pyautogui.typewrite(contact)
        time.sleep(1.5)
        pyautogui.press('enter')
        time.sleep(1.5)
        
        pyautogui.typewrite(message)
        time.sleep(0.5)
        pyautogui.press('enter')
        
        return f"Messaged {contact} on WhatsApp: {message}"
    except pyautogui.FailSafeException:
        print("PyAutoGUI FailSafe triggered. Mouse moved to corner. Operation cancelled. Please ensure your mouse is not in the screen corners during automation.")
        sys.stdout.flush()
        return "PyAutoGUI FailSafe triggered. Mouse moved to corner. Operation cancelled."
    except Exception as e:
        print(f"Failed to send WhatsApp message: {e}. Ensure WhatsApp is open, visible, and no pop-ups are blocking the view.")
        sys.stdout.flush()
        return f"Failed to send WhatsApp message: {e}. Please ensure WhatsApp is open and visible."

def get_wikipedia_info(query):
    """Searches Wikipedia for a query and returns a summary."""
    try:
        wikipedia.set_lang("en")
        if not query or not query.strip():
            return "Please provide a valid search query."
        
        search_results = wikipedia.search(query, results=1)
        if not search_results:
            return f"Sorry, I couldn't find any Wikipedia results for '{query}'."
        
        page_summary = wikipedia.summary(search_results[0], sentences=2)
        return page_summary
    except wikipedia.exceptions.PageError:
        return f"Sorry, I couldn't find any Wikipedia results for '{query}'."
    except wikipedia.exceptions.DisambiguationError as e:
        return f"Your query is too broad. Please be more specific. Here are some options: {', '.join(e.options[:5])}"
    except Exception as e:
        print(f"An unexpected error occurred while searching Wikipedia: {e}")
        sys.stdout.flush()
        return "An error occurred while searching Wikipedia. Please try again later."

def search_web(query):
    """Searches the web using the default browser."""
    try:
        webbrowser.open(f"https://www.google.com/search?q={query}")
        return "Searching the web."
    except Exception as e:
        print(f"Error opening web browser: {e}")
        sys.stdout.flush()
        return "Sorry, I am unable to perform a web search at this time."

def open_application(app_name):
    """Opens a specified application."""
    try:
        if platform.system() == "Windows":
            os.startfile(app_name)
        elif platform.system() == "Darwin": # macOS
            subprocess.run(["open", "-a", app_name], check=True)
        else: # Linux
            subprocess.run(["xdg-open", app_name], check=True)
        return f"Opening {app_name}."
    except FileNotFoundError:
        return f"Sorry, I couldn't find the application '{app_name}'."
    except Exception as e:
        print(f"Error opening application {app_name}: {e}")
        sys.stdout.flush()
        return f"Sorry, I could not open {app_name}."

# Define the functions available as tools for the AI model
tools = [
    genai.protos.FunctionDeclaration(
        name="get_wikipedia_info",
        description="Get information from Wikipedia about a specific topic.",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "query": genai.protos.Schema(type=genai.protos.Type.STRING, description="The topic to search for on Wikipedia.")
            },
            required=["query"]
        ),
    ),
    genai.protos.FunctionDeclaration(
        name="search_web",
        description="Searches the web for a given query and opens a web browser.",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "query": genai.protos.Schema(type=genai.protos.Type.STRING, description="The search query to use.")
            },
            required=["query"]
        ),
    ),
    genai.protos.FunctionDeclaration(
        name="open_application",
        description="Opens a desktop application by its name (e.g., 'Notepad', 'Chrome', 'Calculator').",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "app_name": genai.protos.Schema(type=genai.protos.Type.STRING, description="The name of the application to open.")
            },
            required=["app_name"]
        ),
    ),
    genai.protos.FunctionDeclaration(
        name="send_whatsapp_message",
        description="Sends a message to a specified contact on WhatsApp desktop app. Requires WhatsApp desktop app to be installed and open.",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "contact": genai.protos.Schema(type=genai.protos.Type.STRING, description="The name of the contact or chat to send the message to."),
                "message": genai.protos.Schema(type=genai.protos.Type.STRING, description="The message text to send.")
            },
            required=["contact", "message"]
        ),
    )
]

# Re-initialize the model to include the tools
model = genai.GenerativeModel('gemini-pro', tools=tools)

def get_ai_response(prompt):
    """Sends a user's prompt to the Gemini API and gets a response, handling tool calls."""
    try:
        if not GEMINI_API_KEY or len(GEMINI_API_KEY.strip()) < 10:
            print("Gemini API key missing or invalid.")
            sys.stdout.flush()
            return {"text": "Gemini API key is missing or invalid. Please check your .env file."}

        chat = model.start_chat(history=[
            {"role": "user", "parts": [f"You are Sylvia, a helpful and friendly voice assistant. User: {prompt}"]}
        ])
        
        response = chat.send_message(prompt)
        
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    function_name = part.function_call.name
                    function_args = {k: v for k, v in part.function_call.args.items()}
                    print(f"[DEBUG] Gemini recommended tool call: {function_name} with args: {function_args}")
                    sys.stdout.flush()
                    return {"tool_call": function_name, "args": function_args}
            
            text_response = response.candidates[0].content.parts[0].text
            print(f"[DEBUG] Gemini text response: {text_response}")
            sys.stdout.flush()
            return {"text": text_response}
        else:
            print(f"[DEBUG] Gemini chat response was empty or malformed: {response}")
            sys.stdout.flush()
            return {"text": "I'm having trouble connecting to my brain (empty response). Please try again."}

    except Exception as e:
        print(f"ERROR: Gemini API call failed: {e}")
        sys.stdout.flush()
        return {"text": f"I'm having trouble connecting to my brain. Error: {str(e)}"}

def run_assistant():
    """Main loop for the voice assistant."""
    print("[INFO] Starting assistant...")
    speak(f"Hello, I am Sylvia. I am ready. Listening for the wake word, {WAKE_WORD}.")
    while True:
        try:
            command = listen_for_command()

            if command in ["speech_unintelligible", "speech_service_error", "general_microphone_error", "no_speech_detected"]:
                if command == "no_speech_detected":
                    print("[INFO] No speech detected for wake word. Continuing loop.")
                    sys.stdout.flush()
                elif command == "speech_unintelligible":
                    speak("Sorry, I didn't understand what you said for the wake word. Please try again.")
                elif command == "speech_service_error":
                    speak("I'm having trouble connecting to the speech recognition service for the wake word. Please check your internet connection.")
                elif command == "general_microphone_error":
                    speak("There's an issue with my microphone. Please check your audio input devices.")
                continue

            # Ensure the wake word detection is robust
            if WAKE_WORD in command:
                speak("Yes?")
                
                user_command = listen_for_command()
                
                if user_command == "no_speech_detected":
                    speak("Sorry, I didn't hear your command after the wake word. Please try again.")
                    continue
                elif user_command == "speech_unintelligible":
                    speak("I heard something, but I couldn't understand your command. Please speak clearly.")
                    continue
                elif user_command == "speech_service_error":
                    speak("I'm having trouble with the speech recognition service for your command. Please check your internet connection.")
                    continue
                elif user_command == "general_microphone_error":
                    speak("There's still an issue with my microphone. Can you try again or check your audio settings?")
                    continue
                
                response_data = get_ai_response(user_command)

                if response_data.get("text"):
                    speak(response_data["text"])
                elif response_data.get("tool_call"):
                    function_name = response_data["tool_call"]
                    args = response_data["args"]
                    
                    if function_name == "get_wikipedia_info":
                        result = get_wikipedia_info(**args)
                        speak(result)
                    elif function_name == "search_web":
                        result = search_web(**args)
                        speak(result)
                    elif function_name == "open_application":
                        result = open_application(**args)
                        speak(result)
                    elif function_name == "send_whatsapp_message":
                        result = send_whatsapp_message(**args)
                        speak(result)
                    else:
                        speak("I don't have the ability to perform that specific action.")
                else:
                    speak("I am not sure how to respond to that.")
        except Exception as e:
            print(f"An unexpected error occurred in the main assistant loop: {e}")
            sys.stdout.flush()
            speak("I encountered an unexpected error. Please try again.")

# Flask API setup
app = Flask(__name__)
assistant_thread = None
is_listening = False
is_wake_word_detected = False
interaction_history = []

# API Routes
@app.route('/api/start_listening', methods=['POST'])
def start_listening_api():
    global assistant_thread, is_listening
    if assistant_thread is None or not assistant_thread.is_alive():
        is_listening = True
        assistant_thread = Thread(target=run_background_assistant)
        assistant_thread.daemon = True
        assistant_thread.start()
        return jsonify({'status': 'started', 'message': 'Assistant started listening'})
    return jsonify({'status': 'already_running', 'message': 'Assistant is already listening'})

@app.route('/api/stop_listening', methods=['POST'])
def stop_listening_api():
    global is_listening
    is_listening = False
    return jsonify({'status': 'stopped', 'message': 'Assistant stopped listening'})

@app.route('/api/interaction_history', methods=['GET'])
def get_interaction_history_api():
    return jsonify({'history': interaction_history})

@app.route('/api/assistant_state', methods=['GET'])
def get_assistant_state_api():
    global is_listening
    return jsonify({'is_listening': is_listening})

@app.route('/api/speak', methods=['POST'])
def speak_api():
    data = request.get_json()
    text = data.get('text', '')
    if text:
        speak(text)
        return jsonify({'status': 'success', 'message': 'Text spoken'})
    return jsonify({'status': 'error', 'message': 'No text provided'})

@app.route('/api/get_ai_response', methods=['POST'])
def get_ai_response_api():
    data = request.get_json()
    prompt = data.get('prompt', '')
    if prompt:
        response = get_ai_response(prompt)
        return jsonify({'response': response})
    return jsonify({'status': 'error', 'message': 'No prompt provided'})

def run_background_assistant():
    """Background assistant with wake word detection for API mode"""
    pythoncom.CoInitialize()
    global is_listening, interaction_history, is_wake_word_detected
    try:
        # 1. The "I am ready..." voice message starts here, before the recorder.
        speak(f"I am ready. Listening for the wake word: 'Sylvia'.")
        print("\n=== WAKE WORD DETECTION DEBUG ===")
        print(f"Listening for the wake word: 'Sylvia'...")
        
        # List all available audio input devices
        print("\n[DEBUG] Available audio input devices:")
        devices = PvRecorder.get_audio_devices()
        for idx, device in enumerate(devices):
            print(f"  {idx}: {device}")
        
        # Print the Picovoice model file path
        model_path = os.path.abspath('Sylvia_en_windows_v3_0_0.ppn')
        print(f"\n[DEBUG] Using wake word model: {model_path}")
        if not os.path.exists(model_path):
            print("[ERROR] Wake word model file not found!")
            speak("Error: Wake word model file not found.")
            return
        
        try:
            # The correct argument is keyword_paths, which takes a list.
            porcupine = pvporcupine.create(
                access_key=PICOVOICE_ACCESS_KEY,
                keyword_paths=['Sylvia_en_windows_v3_0_0.ppn']
            )
            print("Successfully initialized Picovoice")
            
            # 2. Now, start the recorder after the initial voice message.
            recorder = PvRecorder(
                device_index=-1,  # -1 for default device
                frame_length=porcupine.frame_length
            )
            print(f"Starting recorder with device index: {recorder.selected_device}")
            recorder.start()
            print("Recorder started successfully")
            
        except Exception as e:
            print(f"Error initializing voice detection: {str(e)}")
            speak("I'm having trouble with the microphone. Please check your audio settings.")
            return
        
        print("\n[DEBUG] Starting wake word detection loop...")
        print("[DEBUG] Speak the wake word 'Sylvia' to activate the assistant.")
        
        while is_listening:
            pcm = recorder.read()
            if not pcm:
                print("[DEBUG] No audio data received from the microphone.")
                continue
                
            keyword_index = porcupine.process(pcm)
            
            # Print audio level for debugging (optional)
            rms = (sum(abs(sample) for sample in pcm) / len(pcm)) if pcm else 0
            print(f"\r[DEBUG] Audio level: {rms:.1f} (speak louder if below 100)", end="", flush=True)
            
            if keyword_index >= 0:
                print("\n[DEBUG] Wake word detected!")
                print("\n=== WAKE WORD DETECTED ===")
                try:
                    is_wake_word_detected = True
                    speak("Yes?")

                    # --- Enter persistent command mode ---
                    while is_listening:
                        command = listen_for_command()
                        if command in ["unknown_value", "request_error", "error"]:
                            continue
                        # Allow "stop listening" or "goodbye" to exit
                        if any(word in command for word in ["exit", "bye", "goodbye", "stop listening"]):
                            speak("Goodbye! Have a nice day.")
                            is_listening = False
                            break
                        interaction_history.append({'role': 'user', 'content': command})
                        response_data = get_ai_response(command)
                        available_functions = {
                            "open_application": open_application,
                            "search_web": search_web,
                            "get_wikipedia_info": get_wikipedia_info
                        }
                        if response_data.get("text"):
                            response_text = response_data["text"]
                            speak(response_text)
                            interaction_history.append({'role': 'assistant', 'content': response_text})
                        elif response_data.get("tool_call"):
                            function_name = response_data["tool_call"]
                            args = response_data["args"]
                            if function_name in available_functions:
                                interaction_history.append({'role': 'assistant', 'content': f"Calling tool: {function_name} with args: {args}"})
                                available_functions[function_name](**args)
                    break  # Exit outer while loop after persistent mode

                except Exception as e:
                    print(f"An error occurred after wake word detection: {e}")
                    speak("I encountered an error. Please check the logs.")

    except Exception as e:
        print(f"An error occurred in the background assistant: {e}")
        is_listening = False
    finally:
        if 'recorder' in locals() and recorder is not None:
            recorder.stop()
            recorder.delete()
        if 'porcupine' in locals() and porcupine is not None:
            porcupine.delete()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Voice Assistant')
    parser.add_argument('--mode', choices=['console', 'api'], default='console', 
                       help='Run in console mode or API server mode')
    parser.add_argument('--port', type=int, default=5001, 
                       help='Port for API server (default: 5001)')
    args = parser.parse_args()
    
    if args.mode == 'console':
        print("[INFO] Starting assistant in console mode...")
        run_assistant()
    else:
        print(f"[INFO] Starting assistant API server on port {args.port}...")
        app.run(host='127.0.0.1', port=args.port, debug=False)
