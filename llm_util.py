import requests
import subprocess
import socket
import time

OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

def query_ollama(prompt: str, model: str = "llama3") -> str:
    response = requests.post(OLLAMA_ENDPOINT, json={
        "model": model,
        "prompt": prompt,
        "stream": False
    })
    response.raise_for_status()
    return response.json()["response"].strip()

# 🔍 Check if Ollama is running
def is_ollama_running(host="localhost", port=11434):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False

# ⚙️ Try to start Ollama if not already running
if not is_ollama_running():
    print("🟡 Ollama AI is not running. Attempting to start it...")
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        if is_ollama_running():
            print("✅ Ollama started successfully.")
        else:
            print("❌ Failed to start Ollama. Please run `ollama serve` manually.")
    except FileNotFoundError:
        print("❌ 'ollama' command not found. Make sure it's installed and in your PATH.")
