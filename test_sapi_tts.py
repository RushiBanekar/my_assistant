#
# File: test_sapi_tts.py
# Description: Test script for Windows SAPI text-to-speech engine functionality
# Author: Rushi Banekar
# Date: 16-August-2025
#

import win32com.client

def test_sapi_tts():
    """Test Windows SAPI TTS engine."""
    print("Testing Windows SAPI TTS...")
    
    try:
        # Initialize Windows SAPI TTS engine
        tts_engine = win32com.client.Dispatch("SAPI.SpVoice")
        
        # Get available voices
        voices = tts_engine.GetVoices()
        print(f"Available voices: {voices.Count}")
        for i in range(voices.Count):
            voice = voices.Item(i)
            print(f"  {i}: {voice.GetDescription()}")
        
        # Test messages
        test_messages = [
            "I am ready. Listening for the wake word: Sylvia.",
            "Yes?",
            "Hello, this is a test of the Windows SAPI text to speech system."
        ]
        
        for i, message in enumerate(test_messages):
            print(f"Speaking: {message}")
            tts_engine.Speak(message)
            print("Done speaking.")
        
        print("TTS test completed successfully!")
        return True
        
    except Exception as e:
        print(f"TTS test failed: {e}")
        return False

if __name__ == "__main__":
    test_sapi_tts()
