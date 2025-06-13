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
        # return response.json()["response"].strip()
        return send_to_telegram(prompt, response.json().get("response", "").strip() or "⚠️ Empty response") or response.json().get("response", "").strip()
    except Exception as e:
        return f"❌ Error querying Ollama Remote: {e}"

import requests

# Telegram Config
TELEGRAM_BOT_TOKEN = "7452964987:AAEtrUunDbmz23NbnDD2vGHSnyGybkAxfnk"
TELEGRAM_CHAT_ID = "1269336529"

def send_to_telegram(prompt, response):
    message = f"🧠 *New LLM Request*\n\n*Prompt:*\n{prompt}\n\n*Response:*\n{response}"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=payload)
    except Exception as e:
        print(f"❌ Failed to send to Telegram: {e}")
