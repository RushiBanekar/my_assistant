import pyttsx3

def list_voices():
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    print("Available voices on your system:")
    for i, voice in enumerate(voices):
        print(f"[{i}] ID: {voice.id}")
        print(f"    Name: {voice.name}")
        print(f"    Languages: {voice.languages}")
        print(f"    Gender: {voice.gender}")
        print("-" * 20)

if __name__ == "__main__":
    list_voices()