import sounddevice as sd
import numpy as np
import queue

q = queue.Queue()

def audio_callback(indata, frames, time, status):
    if status:
        print(f"[Audio callback status] {status}")
    q.put(bytes(indata))

def audio_generator():
    stream = sd.InputStream(
        samplerate=16000,
        blocksize=8000,
        dtype='int16',
        channels=1,
        callback=audio_callback
    )
    with stream:
        print("🎤 Micrófono abierto...")
        while True:
            data = q.get()
            yield data

