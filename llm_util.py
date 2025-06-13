import requests

# 🌐 Use your public Cloudflare tunnel URL
OLLAMA_REMOTE_URL = "https://gs-recorder-producers-stomach.trycloudflare.com/api/generate"

def query_ollama(prompt: str, model: str = "llama3") -> str:
    try:
        print(f"🟡 Prompt Sent: {prompt}")
        response = requests.post(OLLAMA_REMOTE_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": False
        })
        response.raise_for_status()
        print(f"🟢 Response: {response}")
        return response.json()["response"].strip()
    except Exception as e:
        return f"❌ Error querying Ollama Remote: {e}"
