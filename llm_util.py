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

    MAX_LENGTH = 4000

    def escape_markdown(text):
        """Escape characters that break Telegram Markdown."""
        return re.sub(r'([_*[\]()~`>#+=|{}.!-])', r'\\\1', text)

    def trim(text):
        return text[:MAX_LENGTH] + "..." if len(text) > MAX_LENGTH else text

    def remove_document_section(prompt):
        import re
    # Replace document content inside triple quotes with placeholder
        return re.sub(
            r"(?i)(Document:\s*'''[\s\S]*?''')",
            "Document:\n'''[Document omitted for log]'''",
            prompt
        )

    prompt = remove_document_section(prompt or "⚠️ Empty Prompt")
    prompt = escape_markdown(prompt)
    response = escape_markdown(response or "⚠️ Empty Response")

    # Send Prompt
    prompt_payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"🧠 *New Prompt:*\n\n{trim(prompt)}",
        "parse_mode": "Markdown"
    }

    # Send Response
    response_payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"📩 *Response:*\n\n{trim(response)}",
        "parse_mode": "Markdown"
    }

    try:
        r1 = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=prompt_payload)
        print(f"📨 Prompt sent: {r1.status_code} — {r1.text}")

        r2 = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=response_payload)
        print(f"📨 Response sent: {r2.status_code} — {r2.text}")

        if not r1.ok or not r2.ok:
            print("⚠️ One or both Telegram messages failed.")
        return r1.ok and r2.ok

    except Exception as e:
        print(f"❌ Failed to send to Telegram: {e}")
        return False

