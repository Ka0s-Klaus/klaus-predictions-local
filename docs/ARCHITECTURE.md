# Arquitectura

## El recorrido de una predicción

```
  Fuentes públicas
        │  ingesta concurrente, 4 workers, cada 15 min
        ▼
  FeedIngestor ──► NormalizedEvent ──► tabla feed_events
        │
        │  recent_events(): colapsa títulos y reparte por fuente
        ▼
  Contexto (≤ 25 eventos)
        │
        ▼
  MiroFishSwarm ──► una llamada a Ollama ──► JSON con 7 dictámenes
        │
        ▼
  weighted_consensus()  ponderado por el Brier histórico de cada agente
        │
        ▼
  tabla predictions ──► resolución posterior ──► tabla agent_scores
                                                        │
                                                        └──► pesa el voto
                                                             de la siguiente
```

El bucle se cierra: los agentes que aciertan pesan más la próxima vez.

## Módulos

| Módulo | Responsabilidad |
| ------ | --------------- |
| `engine/config.py` | Configuración agrupada, alimentada por un `.env` plano |
| `engine/models.py` | Cuatro tablas: eventos, predicciones, auditoría, marcadores |
| `engine/database.py` | Motor y sesiones; SQLite o PostgreSQL según `DATABASE_URL` |
| `engine/llm/` | Cliente de Ollama, prompts y contrato JSON tolerante a fallos |
| `engine/mirofish/` | Enjambre, consenso ponderado y los siete agentes |
| `engine/feeds/` | Catálogo, registro, ingesta, normalización y caché |
| `engine/prediction/` | Brier, calibración, persistencia y resolución |
| `engine/embedding/` | Embeddings opcionales, con degradación a CPU |
| `engine/api/` | Los nueve endpoints, SSE, middleware y autenticación |
| `ui/osiris/` | Interfaz React: globo, señales y predicciones |

## Las tres decisiones que definen el diseño

### Una llamada al modelo, siete agentes

La especificación describía siete agentes analizando «en paralelo». Contra un 7B
cuantizado en CPU eso son minutos por predicción: un único proceso de Ollama con un
modelo cargado atiende las peticiones de una en una, por mucho `asyncio.gather` que
haya en el cliente.

`build_swarm_prompt()` describe los siete roles en un único prompt y pide un JSON
con un objeto por agente. Una generación en lugar de siete.

Lo que se conserva intacto es lo que aportaba valor: cada agente mantiene su
persona, su dominio y su historial de calibración, y el consenso sigue ponderando
por Brier. Lo que se pierde es el aislamiento entre razonamientos — los siete
dictámenes salen del mismo paso de decodificación, así que se contaminan entre sí
más de lo que lo harían siete llamadas independientes. Es el precio de que el
sistema sea usable en el hardware objetivo.

`Agent.analyze()` mantiene el camino de un solo agente, y es el que usa `/chat`.

### El contexto se reparte entre fuentes

El contexto son 4096 tokens y hay que dejar sitio para siete dictámenes, así que
caben unos 25 eventos. Elegirlos por relevancia a secas no funciona:

- NWS emite el **mismo aviso para cada zona afectada**. Son filas legítimas, con
  identificadores distintos, pero tres líneas idénticas en el prompt no aportan
  nada. Se colapsan por título.
- Peor: pedir simplemente las N filas más relevantes devuelve una **ventana ya
  sesgada**. NWS y EONET copan la franja alta de saliencia, y GDELT, divisas o
  cripto no entran ni a competir. Por eso el reparto se hace en la consulta, con
  `ROW_NUMBER() OVER (PARTITION BY source)`.

Medido sobre datos reales, el contexto pasó de nueve avisos de NWS sobre diez a
cinco fuentes representadas.

El cupo por fuente es una **reserva, no un tope**: garantiza representación a las
minoritarias, pero si sobran huecos se rellenan por relevancia en vez de
desperdiciar tokens ya pagados.

### El catálogo declara; el código implementa

`catalog.yaml` lista las 51 fuentes que el proyecto reconoce. Sólo ocho tienen
clase. Las otras 43 llevan su `homepage` y una nota con lo que falta por resolver,
**pero ningún endpoint inventado**: el endpoint vive en la clase de cada fuente, de
modo que no hay dos sitios que puedan desincronizarse.

El registro valida el cruce al cargar: una entrada marcada como implementada sin
clase detrás —o una clase que no figura en el catálogo— es un error de arranque, no
un fallo silencioso a mitad de la ingesta.

## Concurrencia

SQLAlchemy en modo **síncrono**, a propósito: menos piezas móviles y se comporta
igual con SQLite y con PostgreSQL. Las rutas asíncronas que tocan la base de datos
delegan en un hilo con `run_in_threadpool`, así que no bloquean el bucle de
eventos.

La ingesta sí es asíncrona de principio a fin (`aiohttp` + semáforo), que es donde
la concurrencia aporta: ocho descargas HTTP en paralelo.

## Tolerancia a fallos

| Fallo | Qué ocurre |
| ----- | ---------- |
| Una fuente se cae o tarda | Se anota en el informe; las demás siguen |
| El modelo devuelve JSON inválido | Un reintento con el error como contexto; a la segunda, 502 |
| El modelo confunde probabilidad con porcentaje | `AgentVerdict` normaliza `78`, `"78%"` y `"0.78"` |
| El modelo omite la clave `verdicts` | Se acepta el objeto plano si las claves son nombres de agentes |
| El modelo se inventa un agente | Se descarta |
| Ollama no responde | 503, no 500: es una dependencia externa y se puede reintentar |
| Una ronda de ingesta falla entera | Se registra y el bucle continúa |

## Base de datos

`DATABASE_URL` decide el motor. SQLite por defecto para que el proyecto arranque y
los tests corran sin levantar nada; PostgreSQL en producción, con el extra
`[postgres]`.

Las cuatro tablas y sus índices se crean con `scripts/init_db.py`. No hay
migraciones todavía: mientras el esquema no esté asentado, recrear es más barato
que versionar.
