from dotenv import load_dotenv
load_dotenv()
import os, requests


def send(text):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[notify] telegram not configured")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=5)
    except Exception as e:
        print("[notify] failed:", e)


if __name__ == "__main__":
    send("Guardrail test alert")