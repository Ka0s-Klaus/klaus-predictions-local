# Pythia · klaus-predictions-local

> Oráculo de predicción que se ejecuta **entero en tu máquina**. Feeds públicos, un
> modelo local y un enjambre de agentes cuyo voto se pondera por su historial de
> acierto. Sin nube, sin claves de API, sin coste por consulta.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Ka0s-Klaus/klaus-predictions-local/actions/workflows/ci.yml/badge.svg)](https://github.com/Ka0s-Klaus/klaus-predictions-local/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

## Qué hace

Pythia ingiere señales del mundo real —sismos, tormentas, clima espacial, conflicto,
mercados—, se las da a un LLM que corre en tu propio equipo y somete cada pregunta a
siete analistas especializados. Cada uno emite un dictamen con su nivel de
confianza; el consenso pondera esos votos según lo bien calibrado que haya estado
cada agente históricamente, medido con **Brier score**.

Cuando una predicción vence y registras qué pasó de verdad, los pesos se ajustan.
El sistema aprende quién acierta.

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

## Estado

✅ **v1.0.0 — Primera release funcional.** El camino completo —ingesta → contexto →
enjambre → consenso → persistencia → API → UI— está operativo end-to-end. Predicciones
con streaming en vivo desde el dashboard. Lo que falta es amplitud: fuentes e
integraciones por añadir al catálogo.

| | |
| --- | --- |
| Fuentes | 30 activas de 50 declaradas ([catálogo](docs/FEEDS.md)) |
| Agentes | 7, con voto ponderado por Brier |
| Horizontes | 24h · semana · mes · año |
| Endpoints | 12, con streaming SSE |
| Tests | 178, sin red ni Ollama ni PostgreSQL |

## Instalación

Necesitas Python 3.11+ y [Ollama](https://ollama.com/).

```bash
git clone https://github.com/Ka0s-Klaus/klaus-predictions-local.git
cd klaus-predictions-local

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
ollama pull mistral:7b-instruct-q4_K_M

./start-pythia.sh
```

Por defecto usa SQLite y no necesita nada más. Para PostgreSQL, embeddings o el
resto de extras:

```bash
pip install -e ".[postgres]"     # driver de PostgreSQL
pip install -e ".[embeddings]"   # sentence-transformers (arrastra torch, ~1 GB)
```

## Uso

### API

```text
GET  /health              estado del servicio
GET  /health/llm          ¿responde Ollama?
GET  /agent/view          resumen del estado del mundo
GET  /agent/events        eventos ingeridos, filtrables
POST /predict             predicción del enjambre (bloqueante)
POST /predict/stream      predicción con progreso en vivo (SSE)
POST /chat                conversación con un solo agente
POST /whatif              escenario hipotético (no se persiste)
GET  /predictions         histórico de predicciones
GET  /scorecard           calibración de cada agente
GET  /state/stream        flujo de estado en vivo (SSE)
POST /feeds/refresh       fuerza una ronda de ingesta
```

Documentación interactiva en `http://localhost:8088/docs`.

### Línea de comandos

```bash
python -m engine.cli predict --query "¿Riesgo geopolítico?" --horizon week
python -m engine.cli world-brief
python -m engine.cli ingest            # una ronda de feeds
python -m engine.cli status
python -m engine.cli feeds             # catálogo completo
python -m engine.cli scorecard         # quién acierta más
python -m engine.cli resolve --id 42 --outcome 1
```

### Interfaz

```bash
cd ui/osiris && npm install && npm run dev
```

Globo con los eventos georreferenciados, señales en vivo y lanzador de
predicciones, en `http://localhost:3000`.

## Sobre la latencia

**Una predicción tarda minutos, no segundos, en hardware modesto.** Medido durante
el desarrollo con un modelo 7B cuantizado en CPU: **478 segundos**. Ocho minutos, y
eso ya con la optimización de llamada única.

Por eso los siete agentes se resuelven en **una sola llamada al modelo** en lugar de
siete: un prompt multi-persona devuelve los siete dictámenes de golpe. Mantiene los
roles y el voto ponderado, y divide la latencia por siete.

Si necesitas respuestas rápidas, usa un modelo más pequeño:

```bash
LLM_MODEL=qwen3:1.7b
```

Las cifras medidas, el presupuesto de memoria y los ajustes recomendados están en
[`docs/HARDWARE.md`](docs/HARDWARE.md).

## Documentación

| | |
| --- | --- |
| [Arquitectura](docs/ARCHITECTURE.md) | Cómo encajan las piezas y por qué |
| [Fuentes](docs/FEEDS.md) | Las 51 del catálogo, generado desde el YAML |
| [Hardware](docs/HARDWARE.md) | Rendimiento real y ajustes por máquina |
| [Contribuir](CONTRIBUTING.md) | Flujo de trabajo y convenciones |

## Configuración

Todo se controla desde el `.env`; [`.env.example`](.env.example) documenta cada
variable. Las que más importan:

| Variable | Por defecto | Para qué |
| -------- | ----------- | -------- |
| `LLM_MODEL` | `mistral:7b-instruct-q4_K_M` | Modelo de Ollama |
| `LLM_INFERENCE_TIMEOUT` | `20` | Segundos máximo; recomendado `0` (sin límite) |
| `API_TIMEOUT` | `600` | Timeout de respuesta HTTP; crítico para `/predict/stream` |
| `DATABASE_URL` | `sqlite:///./pythia.db` | SQLite o PostgreSQL |
| `MIROFISH_AGENTS` | `7` | Menos agentes = prompt más corto |
| `FEEDS_UPDATE_INTERVAL` | `900` | Segundos entre rondas de ingesta |
| `API_TOKEN` | vacío | Si lo defines, la API exige `Bearer` |

⚠️ `API_HOST` vale `0.0.0.0` por defecto, lo que incluye tu red local. **Define
`API_TOKEN` si expones el puerto fuera de la máquina.**

## Contribuir

Las contribuciones son bienvenidas. Lee [CONTRIBUTING.md](CONTRIBUTING.md) y respeta
el [Código de Conducta](CODE_OF_CONDUCT.md).

Lo más útil ahora mismo es **implementar fuentes del catálogo**. El patrón está
resuelto: una clase con `parse()` y un test. Las tres más fáciles, todas sin clave y
con formato estable, son **CISA-KEV**, **ReliefWeb** y **Open-Meteo**.

- 🐛 [Reportar un bug](https://github.com/Ka0s-Klaus/klaus-predictions-local/issues/new?template=bug_report.yml)
- 💡 [Proponer algo](https://github.com/Ka0s-Klaus/klaus-predictions-local/issues/new?template=feature_request.yml)
- 💬 [Discussions](https://github.com/Ka0s-Klaus/klaus-predictions-local/discussions)

## Seguridad

Para reportar vulnerabilidades, [SECURITY.md](SECURITY.md). **No abras un issue
público** para fallos de seguridad.

## Créditos

Este proyecto es una implementación propia, pero el concepto, la nomenclatura
—«MiroFish», «Osiris»— y la forma de la API vienen de
[jangles-byte/Pythia](https://github.com/jangles-byte/Pythia), también MIT. Los
detalles están en [NOTICE](NOTICE).

Pythia consume APIs públicas de terceros: USGS, NASA EONET, NOAA, GDELT,
Frankfurter y CoinGecko. Cada una tiene sus propios términos de uso.

## Licencia

[MIT](LICENSE). © 2026 Ka0s-Klaus.
