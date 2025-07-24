import websockets
import asyncio
import json

async def stream_audio(uri, audio_source_func, on_transcription):
    async with websockets.connect(
        uri,
        ping_interval=5,
        ping_timeout=20,
        max_size=2**25
    ) as ws:
        print("🔗 Conectado al WebSocket de AssemblyAI")

        async def send_audio():
            for chunk in audio_source_func():
                await ws.send(chunk)
                await asyncio.sleep(0.01)  # para mantener ~100 Hz

        async def receive():
            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("message_type") == "FinalTranscript":
                        text = data.get("text", "")
                        if text:
                            await on_transcription(text)
                except websockets.ConnectionClosed:
                    print("🔌 Conexión cerrada")
                    break

        await asyncio.gather(send_audio(), receive())

