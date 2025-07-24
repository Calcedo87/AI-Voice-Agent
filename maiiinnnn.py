""" # src/main.py
from src.tts import speak
from src.devices import execute
from src.command_parser import handle_command
from src.audio_stream import audio_generator
import websockets
import requests
import base64
import time
import json
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()  # Esto carga las variables de .env


print("[DEBUG] Token:", os.getenv("ASSEMBLYAI_TOKEN")[:6])
# --- Configuración global ---
SAMPLE_RATE = 16000
WS_BASE_URL = "wss://api.assemblyai.com/v2/realtime/ws"

# --- Autenticación ---


def get_api_key():
    api_key = os.getenv("ASSEMBLYAI_TOKEN")
    if not api_key:
        raise RuntimeError(
            "⚠️  No se encontró la variable de entorno ASSEMBLYAI_TOKEN.")
    return api_key


def get_ephemeral_token(expires_in=3600):
    """
# Solicita un token temporal para usar en la conexión WebSocket.
"""
    headers = {"Authorization": get_api_key()}
    data = {"expires_in": expires_in}
    response = requests.post(
        "https://api.assemblyai.com/v2/realtime/token", headers=headers, json=data, timeout=10)
    response.raise_for_status()
    return response.json()["token"]

# --- Procesamiento de transcripción ---


async def process_transcription(text):
    """
# Procesa un texto transcrito: ejecuta acción y responde por voz si es un comando válido.
"""
    print(f"[📝 Transcripción] {text}")
    command = handle_command(text)
    if command:
        print(f"[✅ Comando detectado] → {command}")
        t0 = time.perf_counter()
        execute(command)
        speak(f"Ejecutando {command.replace('_', ' ')}")
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[⏱ Latencia acción + voz]: {elapsed:.2f} ms")

# --- Comunicación WebSocket ---


async def connect_to_websocket(ws_url):
    """
# Establece la conexión WebSocket, inicia las tareas de envío y recepción.
"""
    async with websockets.connect(
        ws_url,
        ping_interval=5,
        ping_timeout=20,
        max_size=2**25
    ) as ws:
        print("🔗 Conectado al WebSocket de AssemblyAI")

        # Recibir mensaje de bienvenida del servidor
        ack = await ws.recv()
        print("📨 ACK del servidor:", ack)

        await asyncio.gather(
            send_audio(ws),
            receive_transcriptions(ws)
        )


async def send_audio(ws):
    """
# Toma chunks de audio y los envía codificados en base64 por WebSocket.
"""
    print("🎤 Micrófono abierto. Hable cuando desee...")
    for chunk in audio_generator():
        b64_audio = base64.b64encode(chunk).decode("utf-8")
        payload = json.dumps({"audio_data": b64_audio})
        await ws.send(payload)
        await asyncio.sleep(0.01)

    await ws.send(json.dumps({"terminate_session": True}))


async def receive_transcriptions(ws):
    """
# Recibe y procesa transcripciones desde AssemblyAI.
"""
    while True:
        try:
            message = await ws.recv()
            data = json.loads(message)

            if data.get("message_type") == "FinalTranscript":
                text = data.get("text", "")
                if text:
                    await process_transcription(text)

        except websockets.ConnectionClosed:
            print("🔌 Conexión WebSocket cerrada.")
            break

# --- Punto de entrada principal ---


async def main():
    print("🚀 Iniciando asistente de voz con AssemblyAI...")

    try:
        ephemeral_token = get_ephemeral_token()
        ws_url = f"{WS_BASE_URL}?sample_rate={SAMPLE_RATE}&token={ephemeral_token}"
        print("🔐 Token efímero obtenido.")
        await connect_to_websocket(ws_url)

    except requests.RequestException as e:
        print(f"❌ Error al obtener token: {e}")
    except websockets.InvalidStatusCode as e:
        print(f"❌ Error de conexión WebSocket (código {e.status_code}): {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    asyncio.run(main())
 """
