#
# File: enroll_voice.py
# Description: Voice enrollment script for speaker recognition and voice authentication
# Author: Rushi Banekar
# Date: 16-August-2025
#

import os, pickle, time
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
from speechbrain.pretrained import EncoderClassifier
import yaml

CFG = yaml.safe_load(open('config.yaml', 'r'))
SAMPLE_RATE = 16000
DURATION = 6  # seconds
WAVE_TMP = 'enroll.wav'

print("Speak naturally after the beep. Recording in 2 seconds...")
time.sleep(2)
print("Beep! Recording...")
audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
sd.wait()

sf.write(WAVE_TMP, audio, SAMPLE_RATE)
print("Saved", WAVE_TMP)

print("Extracting speaker embedding (this downloads a small model the first time)...")
classifier = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb")
wav, sr = sf.read(WAVE_TMP)
if wav.ndim == 2:
    wav = wav.mean(axis=1)
wav = torch.tensor(wav).float().unsqueeze(0)
emb = classifier.encode_batch(wav).detach().squeeze(0).mean(dim=0).numpy()

with open(CFG['embedding_file'], 'wb') as f:
    pickle.dump({'embedding': emb, 'sr': SAMPLE_RATE}, f)

print(f"Enrollment complete → {CFG['embedding_file']}")