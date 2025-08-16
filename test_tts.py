#
# File: test_tts.py
# Description: Test script for text-to-speech engine configuration and functionality
# Author: Rushi Banekar
# Date: 16-August-2025
#

import pyttsx3
import yaml

def load_config():
    """Loads the YAML configuration file."""
    try:
        with open("config.yaml", "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print("config.yaml not found.")
        return {}

def test_tts():
    """Test the TTS engine with different configurations."""
    print("Testing TTS engine...")
    
    # Load config
    config = load_config()
    VOICE_ID = config.get("assistant", {}).get("voice_id", None)
    
    # Initialize TTS engine
    engine = pyttsx3.init()
    
    # Get available voices
    voices = engine.getProperty('voices')
    print(f"Available voices: {len(voices)}")
    for i, voice in enumerate(voices):
        print(f"  {i}: {voice.id} - {voice.name}")
    
    # Test current voice settings
    current_voice = engine.getProperty('voice')
    current_rate = engine.getProperty('rate')
    current_volume = engine.getProperty('volume')
    
    print(f"Current voice: {current_voice}")
    print(f"Current rate: {current_rate}")
    print(f"Current volume: {current_volume}")
    
    # Set voice if specified in config
    if VOICE_ID and voices:
        try:
            engine.setProperty('voice', VOICE_ID)
            print(f"Set voice to: {VOICE_ID}")
        except:
            print(f"Failed to set voice to {VOICE_ID}, using default")
    
    # Ensure volume is at maximum
    engine.setProperty('volume', 1.0)
    
    # Set a reasonable speaking rate
    engine.setProperty('rate', 200)
    
    # Test speech
    test_messages = [
        "I am ready123. Listening for the wake word: Sylvia.",
        "Yes?",
        "Hello, this is a test of the text to speech system."
    ]
    
    for i, message in enumerate(test_messages):
        print(f"Testing message {i+1}: {message}")
        engine.say(message)
        engine.runAndWait()
        input("Press Enter to continue to next test...")

if __name__ == "__main__":
    test_tts()
