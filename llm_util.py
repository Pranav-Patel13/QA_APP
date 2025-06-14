import os
import requests
import streamlit as st

# 🌐 Use your public Cloudflare tunnel URL
OLLAMA_REMOTE_URL = "https://sons-statistical-looks-quantum.trycloudflare.com/api/generate"

def query_ollama(prompt: str, model: str = "llama3") -> str:
    try:
        print(f"🟡 Prompt Sent to ollama: {prompt}")
        response = requests.post(OLLAMA_REMOTE_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": False
        }, timeout=30)
        response.raise_for_status()
        reply = response.json().get("response", "").strip()
        send_to_telegram(prompt, reply or "⚠️ Empty response")
        return reply or "⚠️ Empty response"
    except Exception as e:
        # return f"❌ Error querying Ollama Remote: {e}"
        print(f"🔁 Ollama failed: {e} — Falling back to OpenAI...")
        return query_openrouter(prompt)

# ✅ Fallback using OpenRouter API (OpenAI-compatible models)
def query_openrouter(prompt: str, model="mistralai/mistral-7b-instruct") -> str:
    try:
        import openai
        openai.api_key = st.secrets.get("OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
        openai.api_base = "https://openrouter.ai/api/v1"

        if not openai.api_key:
            return "❌ OpenRouter API key not found in st.secrets or environment."

        print(f"🟣 Prompt Sent to OpenRouter: {prompt}")
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        reply = response.choices[0].message["content"].strip()
        send_to_telegram(prompt, reply)
        return reply

    except Exception as openai_error:
        print(f"❌ OpenRouter fallback failed: {openai_error}")
        return f"❌ LLM error: {openai_error}"
import requests

# Telegram Config
TELEGRAM_BOT_TOKEN = "7452964987:AAEtrUunDbmz23NbnDD2vGHSnyGybkAxfnk"
TELEGRAM_CHAT_ID = "1269336529"

def send_to_telegram(prompt, response):
    import re

    # Telegram message limit is 4096 characters — we keep some buffer
    MAX_LENGTH = 4000

    def escape_markdown(text):
        """Escape characters that break Telegram Markdown."""
        return re.sub(r'([_*[\]()~`>#+=|{}.!-])', r'\\\1', text)

    def trim(text):
        return text[:MAX_LENGTH] + "..." if len(text) > MAX_LENGTH else text

    prompt = escape_markdown(prompt or "⚠️ Empty Prompt")
    response = escape_markdown(response or "⚠️ Empty Response")

    prompt = trim(prompt)
    response = trim(response)

    message = f"🧠 *New LLM Request*\n\n*Prompt:*\n{prompt}\n\n*Response:*\n{response}"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload
        )
        print(f"📨 Telegram API response: {r.status_code} — {r.text}")
        if not r.ok:
            print("⚠️ Telegram message failed.")
        return r.ok
    except Exception as e:
        print(f"❌ Failed to send to Telegram: {e}")
        return False
