# Changelog

Todos los cambios notables de este proyecto se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el
proyecto se adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

Esqueleto vertical de Pythia: el camino completo de ingesta a predicción,
funcionando y probado extremo a extremo.

### Added

- **Motor de predicción.** Configuración, cuatro tablas SQLAlchemy 2.0, cliente
  asíncrono de Ollama, enjambre MiroFish con siete agentes, consenso ponderado por
  Brier score, y resolución de predicciones que realimenta la calibración.
- **Ingesta de feeds.** Catálogo de 51 fuentes en YAML con ocho implementadas
  —USGS, EONET, NWS, NHC, SWPC, GDELT, divisas del BCE y cripto—, todas
  verificadas contra el servicio real. Ingestor concurrente que tolera fuentes
  caídas, normalizador común, caché TTL y retención de histórico.
- **API.** Los nueve endpoints de la especificación, flujo SSE de estado,
  autenticación opcional por token y traducción de errores de dominio a códigos
  HTTP.
- **CLI** (`python -m engine.cli`) con predicción, resumen del mundo, ingesta,
  estado, catálogo, marcador y resolución.
- **UI Osiris**: React 19 + Vite 8, globo con three.js, señales en vivo y
  lanzador de predicciones.
- **Documentación**: arquitectura, catálogo de fuentes generado desde el YAML, y
  rendimiento real por hardware.
- Estructura del repositorio: licencia MIT, guía de contribución, código de
  conducta, política de seguridad, plantillas de issues y PR, CODEOWNERS,
  Dependabot y workflows de CI, release y stale.
- `NOTICE` con la atribución a [jangles-byte/Pythia](https://github.com/jangles-byte/Pythia),
  de donde vienen el concepto y la nomenclatura.

### Changed

Desviaciones deliberadas respecto a la especificación de partida, todas
comentadas en el código junto al sitio donde importan:

- **Los siete agentes se resuelven en una sola llamada al modelo.** La
  especificación describía siete llamadas «en paralelo», pero contra un 7B
  cuantizado en CPU se serializan dentro del propio Ollama. Medido: 478 s con la
  llamada única; siete llamadas habrían rondado la hora.
- **La GPU pasa a ser opcional.** La especificación pedía `device="cuda"` para una
  Intel HD 520/530, que no tiene CUDA. Ahora el dispositivo se resuelve probando
  XPU → CUDA → CPU. Relacionado: en gráficos integrados la VRAM es RAM del sistema
  compartida, así que activar la GPU no libera memoria, al contrario de lo que
  afirmaba la documentación.
- **El contexto del enjambre se reparte entre fuentes** con una función de
  ventana, y colapsa títulos repetidos. Sin ello, NWS —que emite un aviso por cada
  zona afectada— copaba nueve de cada diez huecos del prompt.
- El catálogo declara 51 fuentes en lugar de las 48 previstas. Las pendientes
  llevan enlace y notas, pero **ningún endpoint inventado**.

### Fixed

Errores de la especificación que impedían que el código arrancase o funcionase:

- `FeedIngestor` filtraba con `if r is not None` sobre un
  `asyncio.gather(return_exceptions=True)`: las excepciones no son `None` y se
  colaban en la lista de eventos.
- `update_brier_score` nunca actualizaba `correct_predictions`, así que la
  precisión de todos los agentes se quedaba clavada en cero.
- El consenso ponderaba con el peso de todos los agentes aunque sólo hubieran
  votado algunos, diluyendo la media desde el denominador.
- `requirements.txt` incluía `asyncio>=3.4.3`, un backport obsoleto de PyPI que
  ensombrece el módulo de la biblioteca estándar.
- `package.json` fijaba `"three": "^r128"`, que no es semver: no existe ninguna
  versión `r*` en npm y `npm install` fallaba.
- La configuración anidada no leía ni una variable del `.env` plano.
- `datetime.utcnow`, deprecado, sustituido por `datetime.now(UTC)`.
- El script de arranque llevaba una contraseña de PostgreSQL incrustada.
- Las coordenadas fuera de rango se descartan en el normalizador: un `CHECK`
  violado aborta la transacción entera, no sólo la fila.
- `sources_used` se filtra contra las fuentes presentes en el contexto. En una
  ejecución real el modelo copió literalmente el `"…"` del esquema de ejemplo.

[Unreleased]: https://github.com/Ka0s-Klaus/klaus-predictions-local/commits/main
