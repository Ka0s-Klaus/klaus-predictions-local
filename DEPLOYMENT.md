# Guía de Despliegue — Klaus Predictions en Red Local

## Arquitectura

```
Mac (desarrollo)
  ↓ (git push/pull)
Lenovo L470 192.168.1.108 — Corre API Pythia + Osiris UI
  ↓
Otro nodo 192.168.1.126 — Corre Ollama con mistral:7b-instruct-q4_K_M
```

## Paso 0: Verificaciones previas

En el Lenovo, antes de empezar:

```bash
# 1. Verificar Ollama está corriendo
curl -s http://192.168.1.126:11434/api/tags | head -20

# 2. Verificar Python 3.11+ y PostgreSQL (opcional, por defecto usa SQLite)
python3 --version
sqlite3 --version
```

## Paso 1: Clonar/actualizar el repositorio

En el Lenovo:

```bash
cd ~
git clone https://github.com/Ka0s-Klaus/klaus-predictions-local.git
# O si ya existe:
cd klaus-predictions-local
git pull origin main
```

## Paso 2: Crear .env desde .env.example

En el Lenovo, en la carpeta del proyecto:

```bash
cp .env.example .env
```

El archivo `.env.example` usa **localhost por defecto** para desarrollo. Si Ollama está en otra máquina de la red, personaliza:

```ini
# Si Ollama está en otra máquina:
LLM_BASE_URL=http://192.168.1.126:11434/api

# Si accedes desde otra máquina en la red:
CORS_ORIGINS=http://192.168.1.108:3000,http://192.168.1.108:8088

API_HOST=0.0.0.0
FEEDS_UPDATE_INTERVAL=900
API_TIMEOUT=600     # Crítico: predicciones tardan ~8 min en CPU
```

Edita `.env` según tu setup:

```bash
nano .env
# O con tu editor favorito
```

## Paso 3: Instalar dependencias

En el Lenovo:

```bash
python3 -m venv .venv
source .venv/bin/activate

# Instalar con extras: API, PostgreSQL (opcional), embeddings (opcional)
pip install -e ".[api]"
# O con todo (requiere ~2GB de espacio para torch):
# pip install -e ".[api,postgres,embeddings]"
```

## Paso 4: Inicializar base de datos

```bash
# Por defecto crea pythia.db (SQLite)
python3 scripts/init_db.py
```

## Paso 5: Verificar fuentes

```bash
python3 -m engine.cli feeds
# Debe listar 40 fuentes implementadas
```

## Paso 6: Prueba rápida de ingesta

```bash
python3 -m engine.cli ingest
# Debe hacer una ronda de 40 fuentes en paralelo (~2-5 minutos)
# Verá errores ocasionales (API rate limits, conectividad), es normal
```

## Paso 7: Arrancar la plataforma

Terminal 1 — API backend:

```bash
./start-pythia.sh
# O manualmente:
python3 -m engine.main
```

Verás en console:
```
Pythia Oracle started on http://0.0.0.0:8088
API docs at http://localhost:8088/docs
```

Terminal 2 — Frontend Osiris:

```bash
cd ui/osiris
npm install  # primera vez
npm run dev
```

Verás:
```
  VITE v... ready in ... ms
  ➜  Local:   http://localhost:3000
  ➜  Network: http://192.168.1.108:3000
```

## Paso 8: Acceder desde cualquier dispositivo de la red

Abre en el navegador:

```
http://192.168.1.108:3000
```

Deberías ver:
- Globo con eventos georreferenciados
- Panel de predicciones
- Historial de eventos

## Paso 9: Probar API manualmente

```bash
# Salud del sistema
curl http://192.168.1.108:8088/health

# Listado de eventos
curl http://192.168.1.108:8088/agent/events?limit=10

# Ver estado del mundo
curl http://192.168.1.108:8088/agent/view

# Hacer una predicción bloqueante (tarda 8-10 minutos en CPU)
curl -X POST http://192.168.1.108:8088/predict \
  -H 'Content-Type: application/json' \
  -d '{"query":"¿Riesgo de inundación en próximas 24h?","horizon":"24h"}'

# Predicción con streaming en vivo (con heartbeats cada segundo)
curl -X POST http://192.168.1.108:8088/predict/stream \
  -H 'Content-Type: application/json' \
  -d '{"query":"¿Riesgo de inundación en próximas 24h?","horizon":"24h"}'
```

## Monitoreo en vivo

Mientras la plataforma corre:

```bash
# Ver eventos ingeridos en tiempo real (SSE)
curl http://192.168.1.108:8088/state/stream

# Ver estado de los agentes (Brier score)
curl http://192.168.1.108:8088/scorecard | jq
```

## Troubleshooting

### Error: "Cannot connect to Ollama at 192.168.1.126:11434"

```bash
# En la máquina con Ollama (192.168.1.126):
ollama list
ollama serve
# Por defecto escucha en localhost:11434. Para escuchar en 0.0.0.0:
# Configura en ~/.config/ollama/ollama.conf (Linux) o desde la GUI (Mac/Windows)
```

### Error: "CORS origin not allowed"

Si accedes desde una IP no en `CORS_ORIGINS`, actualiza `.env`:

```ini
CORS_ORIGINS=http://192.168.1.108:3000,http://192.168.1.108:8088,http://192.168.1.XXX:3000
```

Reinicia la API.

### Fuentes no devuelven datos

```bash
# Revisar logs de ingesta
python3 -m engine.cli ingest --verbose

# Algunos endpoints tienen rate limits (GDELT, OFAC). Es normal que fallen ocasionalmente.
```

### Base de datos llena (SQLite)

SQLite tiene límites. Para producción, considera PostgreSQL:

```bash
pip install -e ".[postgres]"

# En .env:
DATABASE_URL=postgresql://user:pass@localhost:5432/pythia_oracle

# Crear DB:
createdb pythia_oracle
python3 scripts/init_db.py
```

## Configuración avanzada

### Cambiar modelo de Ollama

En `.env`:

```ini
LLM_MODEL=qwen3:1.7b
# O cualquier modelo que tengas descargado:
# ollama list
```

### Cambiar intervalo de ingesta

```ini
FEEDS_UPDATE_INTERVAL=600  # 10 minutos (por defecto 900 = 15 min)
```

### Usar embeddings (GPU si está disponible)

```bash
pip install -e ".[embeddings]"

# En .env:
USE_GPU=true
EMBEDDING_DEVICE=cuda  # o auto
```

### Activar auditoría (logs de predicciones)

```ini
AUDIT_ENABLED=true
AUDIT_SAMPLE_RATE=1.0  # 100% de predicciones
```

## Verificación final

```bash
# Checklist:
# ✓ Ollama en 192.168.1.126:11434 respondiendo
# ✓ API en 192.168.1.108:8088 corriendo
# ✓ UI en 192.168.1.108:3000 accesible
# ✓ Mínimo 10 fuentes con datos en /agent/events
# ✓ Brier score visible en /scorecard (después de primeras predicciones)
# ✓ FEEDS_UPDATE_INTERVAL en marcha (ingesta cada 15 min)
```

---

**Tiempo total de setup:** ~15 minutos (sin descargas, con deps ya en pip cache)  
**Ingesta inicial:** ~5 minutos (40 fuentes en paralelo, depende de ancho de banda)  
**Predicción típica:** 8-10 minutos (CPU), 2-4 minutos (GPU si está disponible)
