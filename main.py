import difflib
import os
import re
import json
import time
import wave
import queue
import pyaudio
import threading
import pyttsx3
import websocket
from datetime import datetime
from urllib.parse import urlencode
from pathlib import Path

# Carpeta de logs
LOGS_DIR = Path("benchmark_logs")
LOGS_DIR.mkdir(exist_ok=True)
log_file_path = LOGS_DIR / \
    f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Cambio menor para forzar actualización

# ==== CONFIGURACIÓN GENERAL ====

MY_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "MY-API-KEY")

CONNECTION_PARAMS = {
    "sample_rate": 16000,
    "format_turns": True,
}
API_ENDPOINT = f"wss://streaming.assemblyai.com/v3/ws?{urlencode(CONNECTION_PARAMS)}"

SAMPLE_RATE = CONNECTION_PARAMS["sample_rate"]
FRAMES_PER_BUFFER = 800
CHANNELS = 1
FORMAT = pyaudio.paInt16

stop_event = threading.Event()
recorded_frames = []
recording_lock = threading.Lock()

audio = None
stream = None
ws_app = None
audio_thread = None

# ==== COMANDOS DISPONIBLES ====

COMMANDS = {
    "enciende la luz": "light_on",
    "apaga la luz": "light_off",
    "abre la puerta": "door_open",
    "cierra la puerta": "door_close",
    "activar alarma": "alarm_on",
    "desactivar alarma": "alarm_off",
    "dime la hora": "what_time"
}


def normalize_text(txt: str) -> str:
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-záéíóúüñ0-9 ]", "", txt)
    reemplazos = {
        "lus": "luz",
        "And seeing the la loose": "enciende la luz",
        "sierra": "cierra",
        "ativar": "activar",
        "desativar": "desactivar",
        "The Saktiwar": "desactivar",
        "aura": "hora",
    }
    for err, corr in reemplazos.items():
        txt = txt.replace(err, corr)
    return txt


def find_closest_command(text, commands, threshold=0.75):
    matches = difflib.get_close_matches(
        text, commands.keys(), n=1, cutoff=threshold)
    if matches:
        print(f"[🔍 Coincidencia cercana] {text} ≈ {matches[0]}")
        return commands[matches[0]]
    else:
        print(f"[❌ Sin coincidencia cercana para] {text}")
        return None


def handle_command(text: str):
    norm = normalize_text(text)
    return find_closest_command(norm, COMMANDS)


def execute(action: str):
    acciones = {
        "light_on": lambda: print("💡 Luz encendida"),
        "light_off": lambda: print("💤 Luz apagada"),
        "door_open": lambda: print("🚪 Puerta abierta"),
        "door_close": lambda: print("🔒 Puerta cerrada"),
        "alarm_on": lambda: print("🚨 Alarma activada"),
        "alarm_off": lambda: print("✅ Alarma desactivada"),
        "what_time": lambda: print("🕒 Hora actual:", datetime.now().strftime("%H:%M:%S"))
    }
    fn = acciones.get(action)
    if fn:
        fn()
    else:
        print(f"[!] Acción desconocida: {action}")

# ==== RESPUESTA CON VOZ ====


_tts_engine = None


def speak(text: str):
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = pyttsx3.init()
    _tts_engine.say(text)
    _tts_engine.runAndWait()

# ==== LÓGICA DE WS ====


def on_open(ws):
    print("🔗 WebSocket abierto")
    print(f"Conectado a: {API_ENDPOINT}")

    def stream_audio():
        global stream
        print("🎤 Iniciando streaming de audio...")
        while not stop_event.is_set():
            try:
                audio_data = stream.read(
                    FRAMES_PER_BUFFER, exception_on_overflow=False)
                with recording_lock:
                    recorded_frames.append(audio_data)
                ws.send(audio_data, websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                if not stop_event.is_set():
                    print(f"[Audio] Error: {e}")
                break
        print("🛑 Streaming de audio detenido.")

    global audio_thread
    audio_thread = threading.Thread(target=stream_audio, daemon=True)
    audio_thread.start()


def on_message(ws, message):
    try:
        data = json.loads(message)
        msg_type = data.get("type")

        if msg_type == "Begin":
            sid = data.get("id")
            exp = data.get("expires_at")
            print(
                f"\n🟢 Sesión iniciada: ID={sid}, expira={datetime.fromtimestamp(exp)}")

        elif msg_type == "Turn":
            transcript = data.get("transcript", "")
            if data.get("turn_is_formatted", False):
                print(f"\n[✔️ Final] {transcript}")
                process_transcription(transcript)
            else:
                print(f"\r[··· Parcial] {transcript}", end="")

        elif msg_type == "Termination":
            adur = data.get("audio_duration_seconds", 0)
            sdur = data.get("session_duration_seconds", 0)
            print(f"\n🔚 Terminación: Audio={adur:.2f}s, Sesión={sdur:.2f}s")

    except json.JSONDecodeError as e:
        print(f"[WS] JSON error: {e}")
    except Exception as e:
        print(f"[WS] Error al procesar: {e}")


def on_error(ws, error):
    print(f"\n[WS] Error: {error}")
    stop_event.set()


def on_close(ws, code, msg):
    print(f"\n🔌 WebSocket cerrado. Status={code}, Msg={msg}")
    save_wav_file()
    cleanup_audio()

# ==== SALVAR LOS LOGS ====


def log_command_result(text, action, latency_ms):
    try:
        with open(log_file_path, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%H:%M:%S")
            f.write(
                f"[{timestamp}] Texto: {text} | Acción: {action} | Latencia: {latency_ms:.2f} ms\n")
    except Exception as e:
        print(f"[Log] Error escribiendo log: {e}")


# ==== PROCESAR TEXTO ====


def process_transcription(text: str):
    cmd = handle_command(text)
    if cmd:
        print(f"[✅ Comando detectado] → {cmd}")
        t0 = time.perf_counter()
        execute(cmd)
        speak(f"Ejecutando {cmd.replace('_', ' ')}")
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[⏱ Latencia acción+voz]: {elapsed:.2f} ms")
        log_command_result(text, cmd, elapsed)


# ==== GUARDADO DE AUDIO Y LIMPIEZA ====


def save_wav_file():
    if not recorded_frames:
        print("No hay audio para guardar.")
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"recorded_{ts}.wav"
    try:
        with wave.open(fname, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            with recording_lock:
                wf.writeframes(b"".join(recorded_frames))
        print(f"💾 Audio guardado: {fname}")
    except Exception as e:
        print(f"[WAV] Error: {e}")


def cleanup_audio():
    global stream, audio, audio_thread
    stop_event.set()
    if stream:
        try:
            if stream.is_active():
                stream.stop_stream()
            stream.close()
        except:
            pass
    if audio:
        try:
            audio.terminate()
        except:
            pass
    if audio_thread and audio_thread.is_alive():
        audio_thread.join(timeout=1.0)

# ==== MAIN ====


def run():
    global audio, stream, ws_app

    if not YOUR_API_KEY or YOUR_API_KEY == "YOUR-API-KEY":
        print("❌ API Key faltante.")
        return

    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(
            input=True,
            frames_per_buffer=FRAMES_PER_BUFFER,
            channels=CHANNELS,
            format=FORMAT,
            rate=SAMPLE_RATE,
        )
        print("🎙️ Micrófono listo. Habla cuando quieras. Ctrl+C para salir.")
    except Exception as e:
        print(f"❌ Error abriendo micrófono: {e}")
        if audio:
            audio.terminate()
        return

    ws_app = websocket.WebSocketApp(
        API_ENDPOINT,
        header={"Authorization": MY_API_KEY},
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    ws_thread = threading.Thread(target=ws_app.run_forever, daemon=True)
    ws_thread.start()

    try:
        while ws_thread.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 Ctrl+C detectado. Cerrando...")
        stop_event.set()
        try:
            if ws_app and ws_app.sock and ws_app.sock.connected:
                ws_app.send(json.dumps({"type": "Terminate"}))
                time.sleep(1)
        except Exception as e:
            print(f"[WS] Error al cerrar sesión: {e}")
        if ws_app:
            ws_app.close()
        ws_thread.join(timeout=2.0)
    finally:
        cleanup_audio()
        print("👋 Listo. Saliendo.")


if __name__ == "__main__":
    run()
