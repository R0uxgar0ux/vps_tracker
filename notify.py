import os
import json
from datetime import datetime, timedelta
import requests

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import VPS, Base, DB_URL  # берем модель и URL БД из app.py

# 1. читаем токен бота из окружения
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")

# 2. читаем chat_id из файла, который создаёт bot.py после /start
CHAT_FILE = os.path.join(os.path.dirname(__file__), "chat_id.json")
TELEGRAM_CHAT_ID = None
if os.path.exists(CHAT_FILE):
    try:
        with open(CHAT_FILE, "r") as f:
            TELEGRAM_CHAT_ID = json.load(f).get("chat_id")
    except Exception:
        TELEGRAM_CHAT_ID = None

# подключаемся к БД
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
session = Session()

today = datetime.utcnow().date()
limit = today + timedelta(days=7)

# выбираем VPS с датой продления в ближайшие 7 дней (и просроченные тоже)
vps_list = session.query(VPS).filter(
    VPS.renewal_date.isnot(None),
    VPS.renewal_date <= limit
).order_by(VPS.renewal_date).all()

# если ничего не истекает — выходим
if not vps_list:
    exit(0)

lines = ["⚠️ VPS renewals approaching:"]
for v in vps_list:
    rd = v.renewal_date.strftime("%Y-%m-%d")
    lines.append(f"- {v.name} ({v.provider or ''}) — {rd}")

text = "\n".join(lines)

# если нет токена или chat_id — просто вывести в консоль
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print(text)

