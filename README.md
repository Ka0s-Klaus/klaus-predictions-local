---
tags: [proyecto/klaus-predictions-local, tipo/referencia, prediccion/fuentes]
---

# 🔮 Pythia · klaus-predictions-local

> **Oráculo de predicción que se ejecuta entero en tu máquina.** Feeds públicos, modelo local y enjambre de agentes cuyo voto se pondera por su historial de acierto. Sin nube, sin claves de API, sin coste por consulta.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Ka0s-Klaus/klaus-predictions-local/actions/workflows/ci.yml/badge.svg)](https://github.com/Ka0s-Klaus/klaus-predictions-local/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)]([[CONTRIBUTING|CONTRIBUTING.md]])

---

## 🤔 ¿Qué hago? ¿Cómo lo hago? ¿Y para qué lo hago?

**¿Qué hago:** Pythia ingiere señales del mundo real —sismos, tormentas, clima espacial, conflicto, mercados—, se las da a un LLM que corre en tu propio equipo y somete cada pregunta a siete analistas especializados. Cada uno emite un dictamen con su nivel de confianza; el consenso pondera esos votos según lo bien calibrado que haya estado cada agente históricamente, medido con **Brier score**.

**¿Cómo lo hago:** El sistema ingiere feeds públicos continuamente, consolida eventos georreferenciados, ejecuta un modelo LLM local (Ollama), y orquesta un enjambre de agentes especializados (Estratega, Economista, Escéptico, Naturalista, Analista Técnico, Experto Climático, Geopolítico) que emiten votos ponderados por su histórico de calibración.

**¿Para qué lo hago:** El análisis predictivo hoy requiere depender de APIs privadas, claves de acceso costosas y latencias cloud. Pythia democratiza la capacidad de hacer predicciones calibradas con datos públicos y modelos que caben en una máquina personal, aprendiendo de cada evento que registres.

### Ejemplo: Predicción en acción

```bash
curl -s -X POST localhost:8088/predict \
  -H 'Content-Type: application/json' \
  -d '{"query":"¿Riesgo de tensión en la red eléctrica?","horizon":"24h"}' | jq
```

```json
{
  "prediction": "Convergen aviso de tormenta severa y alerta geomagnética G2…",
  "confidence": 0.71,
  "dissent": 0.14,
  "agent_votes": {
    "Strategist": 0.74, "Economist": 0.68, "Skeptic": 0.52,
    "Naturalist": 0.81, "Tech_Analyst": 0.70,
    "Climate_Expert": 0.77, "Geopolitical": 0.65
  },
  "sources_used": ["NWS", "SWPC"]
}
```

---

## ✅ Estado v1.0.0

**Primera release funcional.** El camino completo —ingesta → contexto → enjambre → consenso → persistencia → API → UI— está operativo end-to-end. Predicciones con streaming en vivo desde el dashboard. Lo que falta es amplitud: fuentes e integraciones por añadir al catálogo.

| Métrica | Valor |
|---|---|
| 📊 **Fuentes activas** | 30 de 50 declaradas ([catálogo](docs/FEEDS.md)) |
| 🧠 **Agentes** | 7, con voto ponderado por Brier Score |
| ⏱️ **Horizontes** | 24h · semana · mes · año |
| 🔗 **Endpoints** | 12, con streaming SSE |
| 🧪 **Tests** | 178, sin dependencias de red/Ollama/PostgreSQL |

---

## 🏗️ Arquitectura

```mermaid
graph TD
    FEEDS["📡 30+ Feeds Públicos\n(USGS, NASA, NOAA, GDELT)"]
    INGEST["🔄 Ingesta Continua"]
    EVENTS["📊 Consolidador de Eventos"]
    LLM["🧠 LLM Local\n(Ollama + mistral/qwen)")
    SWARM["🐝 Enjambre de 7 Agentes"]
    CONSENSUS["🤝 Consenso por Brier Score"]
    API["📡 API REST + SSE"]
    DASHBOARD["📈 Dashboard Osiris\n(React + Mapbox)"]
    DB["🗄️ SQLite/PostgreSQL"]
    
    FEEDS --> INGEST
    INGEST --> EVENTS
    EVENTS --> LLM
    LLM --> SWARM
    SWARM --> CONSENSUS
    CONSENSUS --> API
    API --> DASHBOARD
    CONSENSUS --> DB
    DB --> API
```

**Stack:**
- 🔧 **Motor:** Python 3.11+ con FastAPI
- 🧠 **LLM:** Ollama (local) con modelos cuantizados
- 🐝 **Enjambre:** 7 agentes especializados con pesos Brier Score
- 💾 **BD:** SQLite (default) o PostgreSQL
- 🎨 **UI:** React 18 + Tailwind + Mapbox GL
- 🔌 **Feeds:** 30+ integradores públicos (sin API keys)

---

## 🚀 Instalación rápida

### Requisitos
- Python 3.11+
- [Ollama](https://ollama.com/) (para ejecutar LLM local)
- Docker (opcional, para PostgreSQL)

### Pasos

```bash
# Clonar
git clone https://github.com/Ka0s-Klaus/klaus-predictions-local.git
cd klaus-predictions-local

# Entorno Python
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Configuración
cp .env.example .env
ollama pull mistral:7b-instruct-q4_K_M

# Iniciar sistema
./start-pythia.sh
```

**Por defecto** usa SQLite (plug-and-play). Para PostgreSQL o embeddings:

```bash
pip install -e ".[postgres]"     # driver PostgreSQL
pip install -e ".[embeddings]"   # sentence-transformers + torch
```

---

## 🎯 Uso

### 📡 API REST

| Endpoint | Método | Descripción |
|---|---|---|
| `/health` | GET | Estado del servicio |
| `/health/llm` | GET | ¿Responde Ollama? |
| `/agent/view` | GET | Resumen del estado del mundo |
| `/agent/events` | GET | Eventos ingeridos (filtrables) |
| 🔮 `/predict` | POST | Predicción del enjambre (bloqueante) |
| 🔮 `/predict/stream` | POST | Predicción con progreso en vivo (SSE) |
| 💬 `/chat` | POST | Conversación con un solo agente |
| 🔄 `/whatif` | POST | Escenario hipotético (no persiste) |
| 📊 `/predictions` | GET | Histórico de predicciones |
| 📈 `/scorecard` | GET | Calibración de cada agente |
| 🌊 `/state/stream` | GET | Flujo de estado en vivo (SSE) |
| 🔄 `/feeds/refresh` | POST | Fuerza una ronda de ingesta |

📚 **Docs interactiva:** http://localhost:8088/docs

### 🖥️ Línea de comandos

```bash
python -m engine.cli predict --query "¿Riesgo geopolítico?" --horizon week
python -m engine.cli world-brief                    # resumen del mundo
python -m engine.cli ingest                        # una ronda de feeds
python -m engine.cli status                        # estado del sistema
python -m engine.cli feeds                         # catálogo completo
python -m engine.cli scorecard                     # quién acierta más
python -m engine.cli resolve --id 42 --outcome 1   # registrar resultado
```

### 🎨 Dashboard (Osiris)

```bash
cd ui/osiris && npm install && npm run dev
```

Globo interactivo con eventos georreferenciados, señales en vivo y lanzador de predicciones.
**URL:** http://localhost:3000

---

## ⏱️ Sobre la latencia

**⚠️ Una predicción tarda minutos, no segundos, en hardware modesto.** Medido durante el desarrollo con un modelo 7B cuantizado en CPU: **478 segundos** (8 minutos).

**Optimización:** Los siete agentes se resuelven en **una sola llamada al modelo** (no siete). Un prompt multi-persona devuelve los siete dictámenes de golpe, manteniendo roles y voto ponderado.

**Para respuestas más rápidas:**

```bash
LLM_MODEL=qwen3:1.7b              # Modelo más pequeño
LLM_INFERENCE_TIMEOUT=0           # Sin timeout (recomendado)
```

📊 Cifras detalladas, presupuesto de memoria y ajustes por máquina: [`docs/HARDWARE.md`](docs/HARDWARE.md)

---

## ⚙️ Configuración

Todo se controla desde `.env`. Archivo: [`.env.example`](.env.example)

| Variable | Defecto | Descripción |
|---|---|---|
| `LLM_MODEL` | `mistral:7b-instruct-q4_K_M` | Modelo de Ollama |
| `LLM_INFERENCE_TIMEOUT` | `20` | Segundos máximo (recomendado: `0` = sin límite) |
| `API_TIMEOUT` | `600` | Timeout HTTP; crítico para `/predict/stream` |
| `DATABASE_URL` | `sqlite:///./pythia.db` | SQLite o PostgreSQL |
| `MIROFISH_AGENTS` | `7` | Número de agentes (menos = prompt más corto) |
| `FEEDS_UPDATE_INTERVAL` | `900` | Segundos entre rondas de ingesta |
| `API_TOKEN` | (vacío) | Si se define, exige `Bearer {token}` |

⚠️ `API_HOST` por defecto es `0.0.0.0` (incluye red local). **Define `API_TOKEN` si expones el puerto fuera de la máquina.**

---

## 📚 Documentación

| Doc | Contenido |
|---|---|
| [🏗️ Arquitectura](docs/ARCHITECTURE.md) | Cómo encajan las piezas y por qué |
| [📡 Fuentes](docs/FEEDS.md) | Las 51 del catálogo, generado desde YAML |
| [💻 Hardware](docs/HARDWARE.md) | Rendimiento real y ajustes por máquina |
| [🤝 Contribuir](CONTRIBUTING.md) | Flujo de trabajo y convenciones |

---

## 🤝 Contribuir

Las contribuciones son bienvenidas. Lee [CONTRIBUTING.md](CONTRIBUTING.md) y respeta el [Código de Conducta](CODE_OF_CONDUCT.md).

**Lo más útil ahora:** implementar fuentes del catálogo. Patrón resuelto: una clase con `parse()` y un test. Las más fáciles (sin API key, formato estable):
- **CISA-KEV**
- **ReliefWeb**
- **Open-Meteo**

### Contacto

- 🐛 [Reportar bug](https://github.com/Ka0s-Klaus/klaus-predictions-local/issues/new?template=bug_report.yml)
- 💡 [Proponer feature](https://github.com/Ka0s-Klaus/klaus-predictions-local/issues/new?template=feature_request.yml)
- 💬 [Discusiones](https://github.com/Ka0s-Klaus/klaus-predictions-local/discussions)

---

## 🔐 Seguridad

Para reportar vulnerabilidades: [SECURITY.md](SECURITY.md)

**⚠️ No abras un issue público para fallos de seguridad.**

---

## 🙏 Créditos

Este proyecto es una implementación propia. Concepto, nomenclatura («MiroFish», «Osiris») y forma de API inspiradas en [jangles-byte/Pythia](https://github.com/jangles-byte/Pythia) (MIT). Detalles: [NOTICE](NOTICE).

**APIs públicas consumidas:** USGS, NASA EONET, NOAA, GDELT, Frankfurter, CoinGecko. Cada una tiene sus propios términos de uso.

---

## 📄 Licencia

[MIT](LICENSE) — Libre para uso comercial, modificación y distribución.

© 2026 Ka0s-Klaus
