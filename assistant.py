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
from threading import Thread
import pvporcupine
from pvrecorder import PvRecorder
import struct
import pythoncom
import argparse

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY") # Keeping for completeness, not directly used here

# Check which API key is available and configure accordingly
# Prioritize Gemini since OpenAI quota is reached
if GEMINI_API_KEY:
    print("[INFO] Using Gemini API")
    genai.configure(api_key=GEMINI_API_KEY)
    USE_OPENAI = False
    USE_GEMINI = True
    # Initialize the model with the correct model name
    model = genai.GenerativeModel('gemini-1.5-flash') # Updated model name
elif OPENAI_API_KEY:
    print("[INFO] Using OpenAI API")
    import openai
    openai.api_key = OPENAI_API_KEY
    USE_OPENAI = True
    USE_GEMINI = False
else:
    print("WARNING: No API key found in .env. AI responses will be limited.")
    USE_OPENAI = False
    USE_GEMINI = False

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
    Uses configurable microphone sensitivity with extended timeout to reduce terminal spam.
    """
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            # Only show initial message, not repeated ones
            r.pause_threshold = 0.8
            r.energy_threshold = MICROPHONE_ENERGY_THRESHOLD
            r.dynamic_energy_threshold = True
            
            # Quick calibration without message
            r.adjust_for_ambient_noise(source, duration=0.3)
            
            try:
                # Shorter timeout for better responsiveness in API mode
                audio = r.listen(source, timeout=5, phrase_time_limit=8)
                
                command = r.recognize_google(audio, language='en-in').lower()
                print(f"You said: {command}")
                sys.stdout.flush()
                return command
                
            except sr.WaitTimeoutError:
                # Only show timeout message occasionally to reduce spam
                return "no_speech_detected"
            except sr.UnknownValueError:
                print("Could not understand audio.")
                sys.stdout.flush()
                return "speech_unintelligible"
            except sr.RequestError as e:
                print(f"Speech service error: {e}")
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
            time.sleep(2) # Reduced wait time for app to open

        # Step 1: Open search and find contact
        pyautogui.hotkey('ctrl', 'f') # Focus search bar
        time.sleep(1)
        pyautogui.typewrite(contact)
        time.sleep(2)  # Wait for search results to appear
        
        # Step 2: Navigate to and select the contact
        pyautogui.press('down')  # Move down to first search result
        time.sleep(0.5)
        pyautogui.press('enter') # Select the contact to open chat
        time.sleep(2.5)  # Wait for chat window to fully load
        
        # Step 3: Type message in the message input box (should be focused automatically)
        pyautogui.typewrite(message)
        time.sleep(0.5)
        
        # Step 4: Send the message
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

def open_website_in_chrome(website):
    """Opens a specific website in Chrome browser."""
    try:
        # Ensure Chrome is open first
        chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        if not os.path.exists(chrome_path):
            chrome_path = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        
        if os.path.exists(chrome_path):
            subprocess.run([chrome_path, f"https://{website}"], check=True)
        else:
            # Fallback to system default browser
            webbrowser.open(f"https://{website}")
        
        return f"Opening {website} in Chrome"
    except Exception as e:
        return f"Failed to open {website} in Chrome: {e}"

def search_in_chrome(query):
    """Opens Chrome and searches for the given query on Google."""
    try:
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        if not os.path.exists(chrome_path):
            chrome_path = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        
        if os.path.exists(chrome_path):
            subprocess.run([chrome_path, search_url], check=True)
        else:
            webbrowser.open(search_url)
        
        return f"Searching for '{query}' in Chrome"
    except Exception as e:
        return f"Failed to search in Chrome: {e}"

def chrome_new_tab():
    """Opens a new tab in Chrome using keyboard shortcut."""
    try:
        # Focus Chrome first (Alt+Tab to cycle to Chrome if needed)
        pyautogui.hotkey('ctrl', 't')  # New tab shortcut
        time.sleep(0.5)
        return "Opened new tab in Chrome"
    except Exception as e:
        return f"Failed to open new tab: {e}"

def chrome_close_tab():
    """Closes current tab in Chrome using keyboard shortcut."""
    try:
        pyautogui.hotkey('ctrl', 'w')  # Close tab shortcut
        time.sleep(0.5)
        return "Closed current tab in Chrome"
    except Exception as e:
        return f"Failed to close tab: {e}"

def chrome_go_back():
    """Goes back to previous page in Chrome."""
    try:
        pyautogui.hotkey('alt', 'left')  # Go back shortcut
        time.sleep(0.5)
        return "Going back to previous page"
    except Exception as e:
        return f"Failed to go back: {e}"

def chrome_refresh():
    """Refreshes current page in Chrome."""
    try:
        pyautogui.press('f5')  # Refresh shortcut
        return "Refreshing current page"
    except Exception as e:
        return f"Failed to refresh page: {e}"

def start_word_dictation():
    """
    Opens a blank Word document and starts dictation mode.
    Continues listening and typing until user says 'end'.
    """
    try:
        # Open Word application
        speak("Opening Word document for dictation...")
        open_application("word")
        
        # Wait for Word to open
        time.sleep(3)
        
        # Create new document (Ctrl+N)
        pyautogui.hotkey('ctrl', 'n')
        time.sleep(2)

        pyautogui.press('enter')
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(1)
        
        speak("The file is ready... what do you want to write?")
        
        # Start dictation loop
        dictation_text = []
        while True:
            try:
                # Listen for dictation
                command = listen_for_command()
                
                if command in ["no_speech_detected", "speech_unintelligible", "speech_service_error"]:
                    continue
                
                # Check for end command
                if "end" in command.lower():
                    speak("Dictation completed. Your document is ready.")
                    break
                
                # Type the dictated text
                if command:
                    # Add proper punctuation and formatting
                    formatted_text = format_dictation_text(command)
                    pyautogui.write(formatted_text + " ")
                    dictation_text.append(formatted_text)
                    print(f"[DICTATION] Added: {formatted_text}")
                    
            except Exception as e:
                print(f"[ERROR] Dictation error: {e}")
                speak("Sorry, there was an error. Please try again.")
                break
                
        return f"Dictation session completed. Total words written: {len(' '.join(dictation_text).split())}"
        
    except Exception as e:
        print(f"[ERROR] Word dictation failed: {e}")
        return "Sorry, I couldn't start Word dictation. Please make sure Microsoft Word is installed."

def format_dictation_text(text):
    """
    Formats dictated text with proper capitalization and punctuation.
    """
    # Capitalize first letter
    text = text.strip()
    if text:
        text = text[0].upper() + text[1:]
    
    # Handle common punctuation commands
    text = text.replace(" period", ".")
    text = text.replace(" comma", ",")
    text = text.replace(" question mark", "?")
    text = text.replace(" exclamation mark", "!")
    text = text.replace(" new line", "\n")
    text = text.replace(" new paragraph", "\n\n")
    
    return text

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
    """Opens a specified application with comprehensive Windows app support."""
    try:
        if platform.system() == "Windows":
            # Handle common application names with specific paths
            app_name_lower = app_name.lower()
            
            # Comprehensive application mappings for Windows
            app_paths = {
                # Communication Apps
                "whatsapp": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\WhatsApp\WhatsApp.exe"),
                    "whatsapp:",
                    "WhatsApp"
                ],
                "discord": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Discord\Update.exe"),
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\Discord\Discord.exe"),
                    "discord"
                ],
                "telegram": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\Telegram Desktop\Telegram.exe"),
                    "telegram"
                ],
                "skype": ["skype", "lync"],
                "zoom": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\Zoom\bin\Zoom.exe"),
                    "zoom"
                ],
                "teams": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Microsoft\Teams\current\Teams.exe"),
                    "ms-teams:",
                    "teams"
                ],
                
                # Web Browsers
                "chrome": [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    "chrome"
                ],
                "firefox": [
                    r"C:\Program Files\Mozilla Firefox\firefox.exe",
                    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
                    "firefox"
                ],
                "edge": ["msedge", "microsoft-edge:"],
                "opera": ["opera"],
                "brave": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"),
                    "brave"
                ],
                
                # Development Tools
                "vscode": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe"),
                    r"C:\Program Files\Microsoft VS Code\Code.exe",
                    "code"
                ],
                "visual studio": [
                    r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\devenv.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\Common7\IDE\devenv.exe",
                    "devenv"
                ],
                "pycharm": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\JetBrains\Toolbox\apps\PyCharm-P\ch-0\*\bin\pycharm64.exe"),
                    "pycharm"
                ],
                "sublime": [
                    r"C:\Program Files\Sublime Text\sublime_text.exe",
                    "sublime_text"
                ],
                "atom": ["atom"],
                "git bash": [
                    r"C:\Program Files\Git\git-bash.exe",
                    "git-bash"
                ],
                
                # Office Applications
                "word": ["winword", "WINWORD.EXE"],
                "excel": ["excel", "EXCEL.EXE"],
                "powerpoint": ["powerpnt", "POWERPNT.EXE"],
                "outlook": ["outlook", "OUTLOOK.EXE"],
                "onenote": ["onenote"],
                
                # Media & Entertainment
                "spotify": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe"),
                    "spotify"
                ],
                "vlc": [
                    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
                    "vlc"
                ],
                "media player": ["wmplayer"],
                "photos": ["ms-photos:"],
                "movies": ["ms-xboxvideo:"],
                "music": ["mswindowsmusic:"],
                
                # System Tools
                "notepad": ["notepad"],
                "calculator": ["calc"],
                "paint": ["mspaint"],
                "explorer": ["explorer"],
                "file explorer": ["explorer"],
                "cmd": ["cmd"],
                "command prompt": ["cmd"],
                "powershell": ["powershell"],
                "task manager": ["taskmgr"],
                "control panel": ["control"],
                "settings": ["ms-settings:"],
                "registry": ["regedit"],
                "device manager": ["devmgmt.msc"],
                "disk management": ["diskmgmt.msc"],
                "services": ["services.msc"],
                "event viewer": ["eventvwr"],
                "system info": ["msinfo32"],
                "character map": ["charmap"],
                "snipping tool": ["snippingtool"],
                "screenshot": ["ms-screenclip:"],
                
                # Gaming
                "steam": [
                    r"C:\Program Files (x86)\Steam\steam.exe",
                    "steam"
                ],
                "epic games": [
                    os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\EpicGamesLauncher\Portal\Binaries\Win32\EpicGamesLauncher.exe"),
                    "epicgameslauncher"
                ],
                "xbox": ["ms-xboxlive:"],
                
                # Utilities
                "7zip": [
                    r"C:\Program Files\7-Zip\7zFM.exe",
                    r"C:\Program Files (x86)\7-Zip\7zFM.exe"
                ],
                "winrar": [
                    r"C:\Program Files\WinRAR\WinRAR.exe",
                    r"C:\Program Files (x86)\WinRAR\WinRAR.exe"
                ],
                "adobe reader": ["AcroRd32"],
                "pdf reader": ["AcroRd32"],
                "teamviewer": ["teamviewer"],
                "anydesk": ["anydesk"]
            }
            
            # Check if it's a known app with specific paths
            if app_name_lower in app_paths:
                paths_to_try = app_paths[app_name_lower]
                for path in paths_to_try:
                    try:
                        if path.endswith('.exe') and os.path.exists(path):
                            os.startfile(path)
                            return f"Opening {app_name}."
                        elif path.endswith(':'):
                            # Try URI scheme
                            os.startfile(path)
                            return f"Opening {app_name}."
                        elif path.endswith('.msc'):
                            # Try MMC snap-in
                            subprocess.run(["mmc", path], check=True)
                            return f"Opening {app_name}."
                        else:
                            # Try generic name or command
                            os.startfile(path)
                            return f"Opening {app_name}."
                    except:
                        continue
                
                # If all specific paths failed, try the original name
                try:
                    os.startfile(app_name)
                    return f"Opening {app_name}."
                except:
                    return f"Sorry, I couldn't find {app_name}. It might not be installed or accessible."
            else:
                # Try opening with the original name for unknown apps
                try:
                    os.startfile(app_name)
                    return f"Opening {app_name}."
                except:
                    return f"Sorry, I couldn't find the application '{app_name}'. Try saying the exact application name or check if it's installed."
                
        elif platform.system() == "Darwin": # macOS
            subprocess.run(["open", "-a", app_name], check=True)
        else: # Linux
            subprocess.run(["xdg-open", app_name], check=True)
            
        
    except FileNotFoundError:
        return f"Sorry, I couldn't find the application '{app_name}'. Try saying the exact application name or check if it's installed."
    except Exception as e:
        print(f"Error opening application {app_name}: {e}")
        sys.stdout.flush()
        return f"Sorry, I encountered an error while trying to open {app_name}. Error: {str(e)}"

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

# Re-initialize the model to include the tools (only if using Gemini)
if USE_GEMINI:
    model = genai.GenerativeModel('gemini-1.5-flash', tools=tools)

def get_ai_response(prompt):
    """Sends a user's prompt to AI API and gets a response, handling tool calls."""
    try:
        if USE_OPENAI:
            # Use OpenAI API (modern client)
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are Sylvia, a helpful and friendly voice assistant. Respond naturally and conversationally."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            text_response = response.choices[0].message.content.strip()
            print(f"[DEBUG] OpenAI response: {text_response}")
            sys.stdout.flush()
            return {"text": text_response}
            
        elif USE_GEMINI:
            # Use Gemini API
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
                print(f"[DEBUG] Gemini response: {text_response}")
                sys.stdout.flush()
                return {"text": text_response}
            else:
                print(f"[DEBUG] Gemini chat response was empty or malformed: {response}")
                sys.stdout.flush()
                return {"text": "I'm having trouble connecting to my brain (empty response). Please try again."}
        else:
            # No API available - provide basic response
            return {"text": "I'm here to help! For advanced responses, please add an API key to your .env file."}

    except Exception as e:
        print(f"ERROR: AI API call failed: {e}")
        sys.stdout.flush()
        return {"text": f"I'm having trouble connecting to my brain. Error: {str(e)}"}

def get_custom_response(user_input):
    """
    Returns a custom response for specific user inputs.
    Add your custom if/else statements here for personalized responses.
    """
    user_input = user_input.lower().strip()
    
    # Personal greetings and questions
    if user_input in ["how are you", "how are you doing", "how's it going"]:
        return "I'm doing great! Ready to help you with anything you need."
    
    elif user_input in ["what's your name", "who are you", "what are you"]:
        return "I'm Sylvia, your voice assistant. I can help you with WhatsApp messages, Chrome automation, web searches, and much more!"
    
    elif user_input in ["good morning", "good afternoon", "good evening"]:
        return "Good day to you too! How can I assist you today?"
    
    elif user_input in ["thank you", "thanks", "thank you sylvia"]:
        return "You're very welcome! I'm always happy to help."
    
    elif user_input in ["what can you do", "what are your features", "help"]:
        return "I can send WhatsApp messages, open websites in Chrome, search the web, get Wikipedia information, open applications, and much more. Just ask me naturally!"
    
    elif user_input in ["what time is it", "current time", "time"]:
        from datetime import datetime
        current_time = datetime.now().strftime("%I:%M %p")
        return f"The current time is {current_time}."
    
    elif user_input in ["what's the date", "today's date", "date"]:
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        return f"Today is {current_date}."
    
    elif user_input in ["good job", "well done", "great work"]:
        return "Thank you! I'm glad I could help you successfully."
    
    elif user_input in ["you're smart", "you're intelligent", "clever"]:
        return "Thank you for the kind words! I try my best to be helpful and efficient."
    
    # Fun responses
    elif user_input in ["tell me a joke", "joke", "make me laugh"]:
        return "Why don't scientists trust atoms? Because they make up everything!"
    
    elif user_input in ["sing a song", "sing something"]:
        return "I'm better at helping you with tasks than singing, but here's my attempt: 'I'm Sylvia, your assistant true, here to help with all you do!'"
    
    elif user_input in ["who is your creator", "who created you", "created you"]:
        return "My creator is Rushi Banekar."
    
    # Word dictation feature
    elif "write something in word" in user_input or "dictate to word" in user_input or "word dictation" in user_input:
        return start_word_dictation()
    
    # Return None if no custom response found
    return None

def run_assistant():
    """Main loop for the voice assistant."""
    print("[INFO] Starting assistant...")
    speak(f"I am ready...")
    is_active = True  # Track if assistant is active or deactivated
    in_conversation = False  # Track if we're in continuous conversation mode
        
    while True:
        try:
            command = listen_for_command()

            if command in ["speech_unintelligible", "speech_service_error", "general_microphone_error", "no_speech_detected"]:
                if command == "no_speech_detected":
                    # Reduced verbosity - only show status occasionally
                    pass  # Silent timeout to prevent terminal spam
                elif command == "speech_unintelligible":
                    if is_active:
                        if in_conversation:
                            speak("Sorry, I didn't understand that. Please try again.")
                        else:
                            speak("Sorry, I didn't understand what you said for the wake word. Please try again.")
                elif command == "speech_service_error":
                    if is_active:
                        speak("I'm having trouble connecting to the speech recognition service. Please check your internet connection.")
                elif command == "general_microphone_error":
                    if is_active:
                        speak("There's an issue with my microphone. Please check your audio input devices.")
                continue

            # Check for reactivation commands when deactivated
            if not is_active:
                if WAKE_WORD in command:
                    is_active = True
                    in_conversation = True
                    speak("I'm back! How can I help you?")
                    continue
                else:
                    # Ignore all other commands when deactivated
                    continue

            # Check for exit/bye commands to end conversation and deactivate
            if any(word in command for word in ["exit", "bye", "goodbye", "deactivate"]):
                speak("Goodbye! I'll be here when you need me. Just say my name to bring me back.")
                is_active = False
                in_conversation = False
                continue

            # If we're in conversation mode, process commands directly
            if in_conversation:
                user_command = command
                
                # Check for custom predefined responses first
                custom_response = get_custom_response(user_command)
                if custom_response:
                    speak(custom_response)
                    continue
                
                # Handle Word dictation command
                if "write something in word" in user_command or "dictate to word" in user_command or "word dictation" in user_command:
                    result = start_word_dictation()
                    speak(result)
                    continue
                
                # Handle direct application opening commands without Gemini API
                if user_command.startswith("open "):
                    app_name = user_command.replace("open ", "").strip()
                    result = open_application(app_name)
                    speak(result)
                    continue
                
                # Handle direct web search commands without Gemini API
                if user_command.startswith("search "):
                    query = user_command.replace("search ", "").strip()
                    result = search_web(query)
                    speak(result)
                    continue
                
                # Handle direct Wikipedia commands without Gemini API
                if user_command.startswith("wikipedia ") or user_command.startswith("wiki "):
                    query = user_command.replace("wikipedia ", "").replace("wiki ", "").strip()
                    result = get_wikipedia_info(query)
                    speak(result)
                    continue
                
                # Handle direct WhatsApp messaging commands without Gemini API
                if "message" in user_command.lower() and "on whatsapp" in user_command.lower():
                    # Check for interactive messaging pattern: "I want to send message to [contact] on whatsapp"
                    if "i want to send message to" in user_command.lower():
                        try:
                            # Extract contact name from "I want to send message to [contact] on whatsapp"
                            contact_part = user_command.lower().replace("i want to send message to ", "").replace(" on whatsapp", "").strip()
                            contact = contact_part.capitalize()
                            
                            if contact:
                                speak(f"What message do you want to send to {contact}?")
                                print(f"[INFO] Waiting for message to send to {contact}...")
                                
                                # Listen for the message content
                                message_command = listen_for_command()
                                
                                if message_command not in ["no_speech_detected", "speech_unintelligible", "speech_service_error", "general_microphone_error"]:
                                    speak(f"Sending message to {contact} on WhatsApp: {message_command}")
                                    result = send_whatsapp_message(contact, message_command)
                                    speak(result)
                                else:
                                    speak("I couldn't hear your message clearly. Please try again.")
                                continue
                            else:
                                speak("Please specify a contact name. For example: I want to send message to Prabhav on WhatsApp")
                                continue
                        except Exception as e:
                            speak("Sorry, I couldn't understand the contact name. Please try again.")
                            continue
                    
                    # Handle direct messaging pattern: "Message Prabhav hi on whatsapp"
                    else:
                        try:
                            # Remove "message" and "on whatsapp" to extract contact and message
                            command_clean = user_command.lower().replace("message ", "").replace(" on whatsapp", "").strip()
                            
                            # Split into words to find contact (first word) and message (remaining words)
                            words = command_clean.split()
                            if len(words) >= 2:
                                contact = words[0].capitalize()  # Capitalize contact name
                                message = " ".join(words[1:])    # Join remaining words as message
                                
                                speak(f"Sending message to {contact} on WhatsApp: {message}")
                                result = send_whatsapp_message(contact, message)
                                speak(result)
                                continue
                            else:
                                speak("Please specify both a contact name and message. For example: Message Prabhav hi on WhatsApp, or say: I want to send message to Prabhav on WhatsApp")
                                continue
                        except Exception as e:
                            speak(f"Sorry, I couldn't parse the WhatsApp command. Please try again with format: Message contact name message on WhatsApp")
                            continue
                
                # Handle Chrome automation commands without Gemini API
                if "chrome" in user_command.lower():
                    # Open website in Chrome - "open youtube in chrome" or "go to facebook in chrome"
                    if ("open" in user_command.lower() or "go to" in user_command.lower()) and "in chrome" in user_command.lower():
                        website = user_command.lower().replace("open ", "").replace("go to ", "").replace(" in chrome", "").strip()
                        result = open_website_in_chrome(website)
                        speak(result)
                        continue
                    
                    # Search in Chrome - "search python tutorial in chrome"
                    elif "search" in user_command.lower() and "in chrome" in user_command.lower():
                        query = user_command.lower().replace("search ", "").replace(" in chrome", "").strip()
                        result = search_in_chrome(query)
                        speak(result)
                        continue
                    
                    # New tab - "new tab in chrome" or "open new tab"
                    elif "new tab" in user_command.lower():
                        result = chrome_new_tab()
                        speak(result)
                        continue
                    
                    # Close tab - "close tab in chrome" or "close current tab"
                    elif "close tab" in user_command.lower():
                        result = chrome_close_tab()
                        speak(result)
                        continue
                    
                    # Go back - "go back in chrome" or "back"
                    elif "go back" in user_command.lower() or user_command.lower().strip() == "back":
                        result = chrome_go_back()
                        speak(result)
                        continue
                    
                    # Refresh - "refresh page" or "reload page"
                    elif "refresh" in user_command.lower() or "reload" in user_command.lower():
                        result = chrome_refresh()
                        speak(result)
                        continue
                
                # Try Gemini API for other commands (will fallback gracefully if no API key)
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
                continue

            # Initial wake word detection to start conversation
            if WAKE_WORD in command:
                speak("Yes?")
                in_conversation = True
                continue
        except Exception as e:
            print(f"An unexpected error occurred in the main assistant loop: {e}")
            sys.stdout.flush()
            speak("I encountered an unexpected error. Please try again.")



# Console assistant functionality
if __name__ == "__main__":
    print("[INFO] Starting Sylvia Voice Assistant...")
    sys.stdout.flush()
    run_assistant()
