# src/main.py
import asyncio
import time
import os

from src.audio_stream import audio_generator
from src.command_parser import handle_command
from src.devices import execute
from src.tts import speak

# --- Simulador de transcripciones por voz ---


async def simulate_transcription_from_voice():
    import speech_recognition as sr
    recognizer = sr.Recognizer()

    print("🎤 Micrófono activado. Hable claramente…")

    with sr.Microphone(sample_rate=16000) as source:
        recognizer.adjust_for_ambient_noise(source)
        print("🟢 Listo para escuchar...")
        while True:
            try:
                print("🎧 Escuchando...")
                audio = recognizer.listen(source, timeout=5)
                print("⏳ Reconociendo...")
                text = recognizer.recognize_google(audio, language='es-MX')
                yield text
            except sr.WaitTimeoutError:
                print("⏱️ Tiempo de espera agotado. No se detectó voz.")
            except sr.UnknownValueError:
                print("❓ No se entendió el audio.")
            except sr.RequestError as e:
                print(f"❌ Error al usar el reconocimiento de voz: {e}")

# --- Procesar el texto como si viniera de AssemblyAI ---


async def process_transcription(text):
    print(f"[📝 Simulado] Transcripción: {text}")
    command = handle_command(text)
    if command:
        print(f"[✅ Comando detectado] → {command}")
        t0 = time.perf_counter()
        execute(command)
        speak(f"Ejecutando {command.replace('_', ' ')}")
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[⏱ Latencia acción + voz]: {elapsed:.2f} ms")

# --- Main offline ---


async def main():
    print("🚀 Iniciando asistente de voz en modo OFFLINE (sin AssemblyAI)...")
    async for text in simulate_transcription_from_voice():
        await process_transcription(text)

# --- Ejecutar ---
if __name__ == "__main__":
    asyncio.run(main())
