# Hardware y rendimiento real

El objetivo declarado del proyecto es un **Lenovo ThinkPad L470** con 16 GB de RAM
y gráficos Intel HD 520/530. Este documento dice qué se puede esperar de verdad en
esa máquina, porque la documentación de partida prometía cifras que no se sostienen
y conviene tenerlo claro antes de instalar nada.

## Dos correcciones a la premisa original

### La GPU integrada no libera memoria

El documento de partida sostiene que la GPU Intel «reduce el uso de RAM de CPU en
3-4 GB» y que **sin ella hay OOM inmediato**, hasta llamarla «necesidad
existencial».

Es falso para gráficos integrados. Una HD 520/530 **no tiene memoria propia**:
reserva un bloque de la misma RAM del sistema. Mover los embeddings a la iGPU
cambia quién hace el cálculo, no de dónde sale la memoria. Los 16 GB siguen siendo
16 GB, y el bloque reservado por el controlador gráfico se resta del total
disponible, no se suma.

Lo que sí aporta descargar los embeddings: la CPU queda libre para la inferencia
del modelo. Eso es una mejora real de latencia, no de memoria.

Por eso aquí la GPU es **opcional**. `resolve_device()` prueba XPU → CUDA → CPU y
degrada con un aviso en lugar de reventar. La especificación original pedía
`device="cuda"` para una Intel HD, y esa llamada falla en cuanto se toca: esas GPU
no tienen backend CUDA. En la práctica, en una HD 520/530 los embeddings van a ir
por CPU, porque tampoco hay soporte de PyTorch para ese hardware.

### Los «6-8 segundos» no salen

El documento promete latencia de 6-8 segundos con 48 feeds, 7 agentes y Mistral 7B.
La cuenta:

| Concepto | Valor |
| -------- | ----- |
| Mistral 7B cuantizado a q4 en un i5-6200U | 2-4 tokens/s |
| Tokens por dictamen (`LLM_MAX_TOKENS`) | 384 |
| Tiempo por agente | ~100-190 s |
| **Siete agentes, en serie** | **~12-22 minutos** |

Y en serie es lo que ocurre aunque el código use `asyncio.gather`: un único proceso
de Ollama con un modelo cargado atiende las peticiones de una en una. La
concurrencia del cliente no multiplica la CPU.

De ahí el cambio de diseño principal de este proyecto: **una sola llamada
multi-persona**. El modelo encarna a los siete analistas y devuelve los siete
dictámenes en un JSON. Se pasa de siete generaciones a una.

## Qué esperar de verdad

### Medición real

Ejecutada durante el desarrollo, sobre un modelo 7B cuantizado en CPU, con los
siete agentes y el prompt multi-persona:

```
=== LATENCIA REAL: 478.6s ===
confianza    : 0.3714
discrepancia : 0.0937
votos        : 7 agentes
```

**Ocho minutos para una predicción**, y eso ya *con* la optimización de la llamada
única. Siete llamadas separadas habrían sido cerca de una hora. Es la medida que
justifica todo el diseño del enjambre.

### Tabla de referencia

Las cifras de lectura están medidas; las de generación en otras máquinas son
estimaciones escaladas desde la medición anterior.

| Operación | 7B en CPU | Máquina moderna (8 núcleos) |
| --------- | --------- | --------------------------- |
| Arranque de la API | < 5 s ✅ medido | < 2 s |
| Ronda de ingesta (8 fuentes) | ~15 s ✅ medido, 233 eventos | 5-30 s |
| `/agent/view` | < 100 ms ✅ medido | < 50 ms |
| `/predict` (enjambre completo) | **~8 min** ✅ medido | 30-90 s |
| `/chat` (un agente) | 1-3 min | 10-30 s |

La ingesta y las consultas de lectura son inmediatas. Lo lento es exclusivamente la
generación del modelo. Si el uso que le vas a dar es interactivo, **cambia de
modelo**: es la única palanca que mueve esto de verdad.

### Medir tu latencia

```bash
time curl -s -X POST localhost:8088/predict \
  -H 'Content-Type: application/json' \
  -d '{"query":"¿Anomalías globales?","horizon":"24h"}' | jq '.latency_ms'
```

## Presupuesto de memoria

Con la configuración por defecto y SQLite:

| Componente | RSS aproximado |
| ---------- | -------------- |
| Ollama con Mistral 7B q4 cargado | 4.5-5.5 GB |
| API de Pythia (1 worker, sin embeddings) | 150-250 MB |
| PostgreSQL, si se usa en vez de SQLite | 300 MB-1 GB |
| Embeddings, si se instala el extra | +600 MB-1.2 GB (arrastra torch) |
| Bloque reservado por la iGPU | 256 MB-2 GB, según BIOS |

En 16 GB con SQLite y sin embeddings queda holgura de sobra. El escenario apretado
es PostgreSQL + embeddings + navegador abierto.

### Si vas justo de memoria

Por orden de eficacia:

1. `DATABASE_URL=sqlite:///./pythia.db` en lugar de PostgreSQL.
2. No instalar el extra `[embeddings]`. No hace falta para predecir.
3. `LLM_MAX_TOKENS=256` y `LLM_CONTEXT_LENGTH=2048`.
4. `MIROFISH_AGENTS=4`: menos agentes, prompt más corto, respuesta más corta.
5. `FEEDS_CONCURRENCY=2`.
6. Un modelo más pequeño: `LLM_MODEL=qwen3:1.7b`. Es el cambio con más impacto
   sobre la latencia, a costa de calidad de razonamiento.

## Configuración recomendada para el L470

```bash
DATABASE_URL=sqlite:///./pythia.db
USE_GPU=false                  # la HD 520/530 no tiene backend de PyTorch
LLM_MODEL=mistral:7b-instruct-q4_K_M
LLM_MAX_TOKENS=384
LLM_CONTEXT_LENGTH=4096
LLM_INFERENCE_TIMEOUT=600      # el techo de 20 s del documento original
                               # provocaría un 503 en cada predicción
API_WORKERS=1                  # cada worker duplica el residente
FEEDS_CONCURRENCY=2
```

El `LLM_INFERENCE_TIMEOUT` es el ajuste que más importa: con el valor de 20 s que
traía la documentación de partida, **ninguna predicción llegaría a completarse**
en esta máquina.

## Comprobar el hardware

```bash
free -h                          # memoria total
nproc                            # núcleos
lspci | grep -i vga              # gráficos
df -h /                          # espacio libre (el modelo ocupa ~4.4 GB)
```

Ninguna de estas comprobaciones es un requisito bloqueante. Pythia arranca en
cualquier máquina con Python 3.11+; lo único que cambia es cuánto hay que esperar.
