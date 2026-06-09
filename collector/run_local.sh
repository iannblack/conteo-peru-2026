#!/bin/zsh
# Recolector LOCAL: corre el pipeline desde una IP que ONPE acepta (tu Mac) y
# pushea la data al repo. Pensado para correr cada ~5 min vía LaunchAgent.
# ONPE bloquea las IPs de GitHub Actions, por eso la recolección vive aquí.

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python3"        # venv con deps preinstaladas: NO toca pypi por corrida
GIT=/usr/bin/git
LOG=/tmp/conteo_collector.log

cd "$REPO" || exit 1

if [ ! -x "$PY" ]; then
  echo "$(date '+%FT%T') FALTA el venv ($PY). Crear: uv venv .venv && uv pip install --python .venv/bin/python3 curl_cffi numpy" >>"$LOG"
  exit 0
fi

build() { "$PY" collector/build_outputs.py >>"$LOG" 2>&1; }
if ! build; then
  sleep 25   # la red puede estar reconectando (DNS); reintentar una vez antes de rendirse
  if ! build; then
    echo "$(date '+%FT%T') build FAILED tras reintento (se conserva el último dato)" >>"$LOG"
    exit 0
  fi
fi

"$GIT" add docs/data/latest.json docs/data/history.json
if "$GIT" diff --staged --quiet; then
  exit 0  # sin cambios
fi
"$GIT" commit -q -m "data: actualización ONPE (local) [skip ci]"
"$GIT" pull --rebase --autostash -q origin main 2>>"$LOG" || true
if "$GIT" push -q origin main 2>>"$LOG"; then
  echo "$(date '+%FT%T') pushed OK" >>"$LOG"
else
  echo "$(date '+%FT%T') push FAILED" >>"$LOG"
fi
