# src/main.py
import os
import asyncio
import json
import time
import base64
import requests
from src.tts import speak
from src.devices import execute
from src.command_parser import handle_command
from src.audio_stream import audio_generator

from dotenv import load_dotenv
import websockets.legacy.client as ws_client
from websockets.exceptions import ConnectionClosed, InvalidStatusCode

from src.audio_stream import audio_generator
from src.command_parser import handle_command
from src.devices import execute
from src.tts import speak

# --- Cargar variables de entorno ---
load_dotenv()
API_KEY = os.getenv("ASSEMBLYAI_TOKEN")


def get_ephemeral_token():
    api_key = os.getenv("ASSEMBLYAI_TOKEN")
    url = "https://api.assemblyai.com/v2/realtime/token"
    headers = {"Authorization": api_key}
    data = {"expires_in": 3600}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["token"]


ephemeral_token = get_ephemeral_token()
WS_ENDPOINT = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000&token={ephemeral_token}"


if not API_KEY:
    raise RuntimeError(
        "⚠️ No se encontró ASSEMBLYAI_TOKEN en el entorno o .env")

# --- Procesamiento de transcripciones ---


async def process_transcription(text):
    print(f"[📝 Transcripción] {text}")
    command = handle_command(text)
    if command:
        print(f"[✅ Comando detectado] → {command}")
        t0 = time.perf_counter()
        execute(command)
        speak(f"Ejecutando {command.replace('_', ' ')}")
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[⏱ Latencia acción + voz]: {elapsed:.2f} ms")

# --- Envío de audio al WebSocket ---


async def send_audio(ws):
    print("🎤 Micrófono abierto. Hable cuando desee...")
    for chunk in audio_generator():
        b64_audio = base64.b64encode(chunk).decode("utf-8")
        await ws.send(json.dumps({"audio_data": b64_audio}))
        await asyncio.sleep(0.01)

# --- Recepción de transcripciones ---


async def receive_transcriptions(ws):
    while True:
        try:
            message = await ws.recv()
            data = json.loads(message)

            # Mensaje de inicio de sesión (ACK)
            if data.get("message_type") == "SessionBegins":
                print(f"📨 Sesión iniciada. ID: {data.get('session_id')}")

            # Transcripción final
            elif data.get("message_type") == "FinalTranscript":
                text = data.get("text", "")
                if text:
                    await process_transcription(text)

        except ConnectionClosed as e:
            print(f"🔌 Conexión cerrada: {e}")
            break

# --- Función principal ---


async def main():
    print("🚀 Iniciando asistente de voz con AssemblyAI Universal‑Streaming...")

    try:
        async with ws_client.connect(
            WS_ENDPOINT,
            ping_interval=5,
            ping_timeout=20,
            max_size=2**25
        ) as ws:
            await asyncio.gather(
                send_audio(ws),
                receive_transcriptions(ws)
            )

    except InvalidStatusCode as e:
        print(f"❌ Error HTTP {e.status_code} al conectar al WebSocket: {e}")
    except ConnectionClosed as e:
        print(f"❌ Conexión cerrada inesperadamente: {e}")
    except Exception as e:
        print(f"❌ Error general: {e}")

# --- Ejecutar ---
if __name__ == "__main__":
    asyncio.run(main())
