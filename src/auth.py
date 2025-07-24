import os
import requests

def get_ephemeral_token(expires_in=3600):
    api_key = os.getenv("ASSEMBLYAI_TOKEN")
    if not api_key:
        raise RuntimeError("Falta ASSEMBLYAI_TOKEN en el entorno")

    url = "https://api.assemblyai.com/v2/realtime/token"
    headers = {"Authorization": api_key}
    data = {"expires_in": expires_in}
    r = requests.post(url, json=data, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()["token"]
