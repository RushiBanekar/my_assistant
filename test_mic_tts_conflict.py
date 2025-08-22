import speech_recognition as sr
import pyttsx3
import time

print('Step 1: Open microphone for 2 seconds...')
r = sr.Recognizer()
with sr.Microphone() as source:
    r.adjust_for_ambient_noise(source, duration=0.5)
    print('Listening briefly...')
    audio = r.listen(source, timeout=2, phrase_time_limit=2)
print('Microphone closed.')

print('Step 2: Try to speak using pyttsx3...')
engine = pyttsx3.init('sapi5')
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)  # Use first available voice
print('Speaking: If you hear this, TTS works after mic use.')
engine.say('If you hear this, TTS works after microphone use.')
engine.runAndWait()
print('Done.')

print('Step 3: Try to speak again...')
engine.say('This is a second test after microphone use.')
engine.runAndWait()
print('All done.')
