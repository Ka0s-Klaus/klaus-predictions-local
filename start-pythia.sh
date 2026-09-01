#!/usr/bin/env bash
#
# Arranca Pythia: Ollama, la API y (si existe) la UI Osiris.
#
#   ./start-pythia.sh              todo
#   ./start-pythia.sh --no-ui      solo el motor
#   ./start-pythia.sh --no-ollama  sin levantar Ollama (ya está en marcha)
#
# A diferencia del script de la documentación de partida, aquí no hay ninguna
# contraseña incrustada: todo sale del .env.

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; DIM='\033[2m'; NC='\033[0m'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${PYTHIA_LOG_DIR:-$ROOT/logs}"
VENV="${VIRTUAL_ENV:-$ROOT/.venv}"

START_UI=1
START_OLLAMA=1
for arg in "$@"; do
  case "$arg" in
    --no-ui) START_UI=0 ;;
    --no-ollama) START_OLLAMA=0 ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo -e "${RED}Opción desconocida: $arg${NC}"; exit 2 ;;
  esac
done

mkdir -p "$LOG_DIR"
PIDS=()

cleanup() {
  echo -e "\n${YELLOW}Deteniendo…${NC}"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo -e "${GREEN}Listo.${NC}"
}
trap cleanup EXIT INT TERM

log()  { echo -e "${YELLOW}$*${NC}"; }
ok()   { echo -e "${GREEN}  ✓ $*${NC}"; }
warn() { echo -e "${YELLOW}  ○ $*${NC}"; }
die()  { echo -e "${RED}  ✗ $*${NC}"; exit 1; }

# ---------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------

if [ ! -f "$ROOT/.env" ]; then
  warn "No hay .env; se copia de .env.example"
  cp "$ROOT/.env.example" "$ROOT/.env"
fi

# `set -a` exporta todo lo que se defina a continuación. Se acota al `source`
# para no exportar de más.
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

API_PORT="${API_PORT:-8088}"
LLM_BASE_URL="${LLM_BASE_URL:-http://localhost:11434/api}"
LLM_MODEL="${LLM_MODEL:-mistral:7b-instruct-q4_K_M}"

if [ ! -d "$VENV" ]; then
  die "No existe el entorno virtual en $VENV. Créalo con: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# ---------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------

if [ "$START_OLLAMA" -eq 1 ]; then
  log "[1/4] Ollama"
  if ! command -v ollama >/dev/null 2>&1; then
    warn "ollama no está instalado; la API arrancará pero /predict fallará con 503"
  elif curl -sf "${LLM_BASE_URL%/api}/api/tags" >/dev/null 2>&1; then
    ok "ya estaba en marcha"
  else
    ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
    PIDS+=($!)
    for _ in $(seq 1 40); do
      curl -sf "${LLM_BASE_URL%/api}/api/tags" >/dev/null 2>&1 && break
      sleep 1
    done
    curl -sf "${LLM_BASE_URL%/api}/api/tags" >/dev/null 2>&1 \
      && ok "arrancado" \
      || warn "no responde; revisa $LOG_DIR/ollama.log"
  fi

  if command -v ollama >/dev/null 2>&1; then
    if ollama list 2>/dev/null | grep -q "${LLM_MODEL%%:*}"; then
      ok "modelo $LLM_MODEL disponible"
    else
      warn "descargando $LLM_MODEL (la primera vez tarda)"
      ollama pull "$LLM_MODEL" || warn "no se pudo descargar el modelo"
    fi
  fi
else
  log "[1/4] Ollama omitido (--no-ollama)"
fi

# ---------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------

log "[2/4] Base de datos"
python "$ROOT/scripts/init_db.py" >/dev/null && ok "esquema listo"

# ---------------------------------------------------------------------
# API
# ---------------------------------------------------------------------

log "[3/4] API"
if curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1; then
  die "el puerto $API_PORT ya está ocupado"
fi

python -m engine.main > "$LOG_DIR/engine.log" 2>&1 &
PIDS+=($!)

for _ in $(seq 1 30); do
  curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1 \
  && ok "escuchando en http://127.0.0.1:$API_PORT" \
  || die "no arrancó; revisa $LOG_DIR/engine.log"

# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------

if [ "$START_UI" -eq 1 ] && [ -d "$ROOT/ui/osiris" ] && command -v npm >/dev/null 2>&1; then
  log "[4/4] Osiris"
  cd "$ROOT/ui/osiris"
  [ -d node_modules ] || npm install > "$LOG_DIR/osiris-install.log" 2>&1
  npm run dev > "$LOG_DIR/osiris.log" 2>&1 &
  PIDS+=($!)
  cd "$ROOT"
  sleep 3
  ok "http://127.0.0.1:3000"
else
  log "[4/4] Osiris omitido"
fi

# ---------------------------------------------------------------------

echo
echo -e "${GREEN}Pythia en marcha.${NC}"
echo -e "  API    http://127.0.0.1:$API_PORT"
echo -e "  Docs   http://127.0.0.1:$API_PORT/docs"
[ "$START_UI" -eq 1 ] && echo -e "  UI     http://127.0.0.1:3000"
echo -e "  Logs   $LOG_DIR/"
echo
echo -e "${DIM}Prueba:  curl -s http://127.0.0.1:$API_PORT/agent/view | jq '.events[0]'${NC}"
echo -e "${DIM}Ctrl-C para detenerlo todo.${NC}"
echo

wait
