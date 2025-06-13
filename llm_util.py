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
        }, timeout=10)
        response.raise_for_status()
        reply = response.json().get("response", "").strip()
        send_to_telegram(prompt, reply or "⚠️ Empty response")
        return reply or "⚠️ Empty response"
    except Exception as e:
        print(f"❌ Ollama failed: {e} — Falling back to OpenAI...")
        return query_openai(prompt)

# ✅ OpenAI fallback
def query_openai(prompt: str, model="gpt-3.5-turbo") -> str:
    try:
        import openai
        openai.api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

        if not openai.api_key:
            return "❌ OpenAI API key not found in st.secrets or environment."

        print(f"🟣 Prompt Sent to OpenAI: {prompt}")
        chat_response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        reply = chat_response.choices[0].message["content"].strip()
        send_to_telegram(prompt, reply)
        return reply

    except Exception as openai_error:
        print(f"❌ OpenAI fallback failed: {openai_error}")
        return f"❌ LLM error: {openai_error}"

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
        # return True
    except Exception as e:
        print(f"❌ Failed to send to Telegram: {e}")
        # return False
