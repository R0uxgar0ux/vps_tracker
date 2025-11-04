import os
import time
import json
import requests

TOKEN = os.getenv("TG_TOKEN")
if not TOKEN:
    raise SystemExit("TG_TOKEN is not set in environment")

CHAT_FILE = "chat_id.json"
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# будем помнить offset, чтобы не получать одни и те же сообщения
last_update_id = None

print("🤖 Simple Telegram bot started. Waiting for /start ...")

while True:
    try:
        params = {"timeout": 30}
        if last_update_id:
            params["offset"] = last_update_id + 1

        resp = requests.get(f"{API_URL}/getUpdates", params=params, timeout=35)
        data = resp.json()

        if not data.get("ok"):
            time.sleep(2)
            continue

        for update in data.get("result", []):
            last_update_id = update["update_id"]

            message = update.get("message") or update.get("edited_message")
            if not message:
                continue

            chat_id = message["chat"]["id"]
            text = message.get("text", "")

            if text.strip().lower() == "/start":
                # сохраняем chat_id
                with open(CHAT_FILE, "w") as f:
                    json.dump({"chat_id": chat_id}, f)
                # отвечаем пользователю
                requests.get(f"{API_URL}/sendMessage",
                             params={"chat_id": chat_id,
                                     "text": "✅ Бот активирован! Буду присылать уведомления сюда."})
                print(f"[+] Saved chat_id: {chat_id}")

        # чтобы не крутиться как бешеный
        time.sleep(1)

    except KeyboardInterrupt:
        print("Stopping bot...")
        break
    except Exception as e:
        print("Error:", e)
        time.sleep(3)

