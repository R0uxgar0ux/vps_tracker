# VPS Tracker

Простое self-hosted веб-приложение на Flask для учёта VPS:
- имя / провайдер
- IP
- локация по IP (авто)
- дата продления
- цена и валюта
- заметки
- подсчёт общей стоимости по валютам
- иконка провайдера по домену

## Установка

```bash
git clone https://github.com/R0uxgar0ux/vps_tracker.git
cd vps-tracker
bash setup.sh
source venv/bin/activate
python3 app.py
```

После запуска: [http://localhost:5000](http://localhost:5000)

