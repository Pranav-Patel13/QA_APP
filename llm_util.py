import requests, subprocess, socket, time, shutil

OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

def query_ollama(prompt: str, model: str = "llama3") -> str:
    resp = requests.post(OLLAMA_ENDPOINT, json={
        "model": model,
        "prompt": prompt,
        "stream": False
    })
    resp.raise_for_status()
    return resp.json()["response"].strip()

def is_ollama_installed():
    return shutil.which("ollama") is not None

def is_ollama_running(host="localhost", port=11434) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False

def start_ollama() -> bool:
    if not is_ollama_installed():
        print("❌ 'ollama' not in PATH.")
        return False
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    if is_ollama_running():
        print("✅ Ollama started.")
        return True
    print("❌ Couldn't start Ollama. Try `ollama serve` manually.")
    return False
