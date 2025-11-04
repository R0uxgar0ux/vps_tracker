#!/bin/bash
set -e

echo "🚀 Installing VPS Tracker..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 not found, install it first."
  exit 1
fi

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# создаём БД (app.py сам создаёт, но на всякий — вызовем)
python3 - <<'PY'
from app import Base, engine
Base.metadata.create_all(engine)
print("DB ready.")
PY

echo
echo "✅ Done!"
echo "Run: source venv/bin/activate && python3 app.py"
