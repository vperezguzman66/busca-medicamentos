#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create virtualenv if needed
if [ ! -d ".venv" ]; then
  echo "→ Creando entorno virtual..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "→ Instalando dependencias..."
pip install -q -r backend/requirements.txt

if [ ! -d "$HOME/Library/Caches/ms-playwright" ] && [ ! -d "$HOME/.cache/ms-playwright" ]; then
  echo "→ Instalando Chromium para Playwright (Cruz Verde)..."
  python3 -m playwright install chromium
fi

echo ""
echo "✅ BuscaMedicamentos iniciado en http://localhost:8000"
echo "   Presiona Ctrl+C para detener"
echo ""

cd backend
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
