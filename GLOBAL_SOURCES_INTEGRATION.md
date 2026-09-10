# 🌐 Integración de Fuentes Globales v2.0

Integración completa de **2,847 fuentes públicas de información** de 195+ países en 12 temas especializados, con perfil **CRITICAL** optimizado para predicción de alertas.

## 📋 Tabla de Contenidos

- [Guía Rápida](#guía-rápida)
- [Pasos Detallados](#pasos-detallados)
- [Estructura de Fuentes](#estructura-de-fuentes)
- [Validación](#validación)
- [Troubleshooting](#troubleshooting)

---

## 🚀 Guía Rápida

**Opción 1: Ejecutar todo automáticamente**

```bash
cd /Users/asantacana/proyectos/klaus-predictions-local
bash scripts/integrate_global_sources.sh
```

**Opción 2: Paso a paso (si necesitas control)**

Sigue la sección [Pasos Detallados](#pasos-detallados).

---

## 📝 Pasos Detallados

### Paso 1: Parser del Markdown v2.0

Convierte el markdown Pythia a JSON estructurado:

```bash
cd /Users/asantacana/proyectos/klaus-predictions-local

python3 scripts/parse_pythia_sources.py \
  /Users/asantacana/proyectos/pythia/fuentes-globales-completa-v2.md \
  data/sources-global-v2.json
```

**Salida esperada:**
```
✓ Extraídas 2847 fuentes

📊 Estadísticas:
  Total fuentes: 2847
  Países: 195
  Dominios: 12
  
  Por calidad:
    excellent: 1650 (57.9%)
    very_good: 950 (33.4%)
    good: 200 (7.0%)
    acceptable: 47 (1.7%)
```

### Paso 2: Aplicar Perfil CRITICAL

Reweighting de scores optimizado para predicción de alertas:

```bash
python3 scripts/apply_critical_profile.py \
  data/sources-global-v2.json \
  data/sources-global-v2-critical.json \
  critical
```

**Perfil CRITICAL prioriza:**
- Fiabilidad (35%) — Fuentes que NO fallan
- Actualización (30%) — Real-time > Diario > Semanal
- Cobertura (15%) — Global > Regional
- Integridad (12%) — Datos completos
- Accesibilidad (8%) — Funciona siempre

**Resultado:**
- ✅ Fuentes real-time (NOAA, CISA, Euronext) → Scores SUBEN
- ✅ Fuentes diarias (AEMET, CFR) → Scores estables
- ⚠️  Fuentes semanales → Scores BAJAN
- ❌ Fuentes trimestrales → Scores BAJAN mucho

### Paso 3: Generar Entradas de Catálogo

Crea entries YAML y factory de fuentes genéricas:

```bash
python3 scripts/generate_catalog_entries.py \
  data/sources-global-v2-critical.json \
  engine/feeds/catalog-global.yaml \
  engine/feeds/sources/global_factory.py
```

**Genera:**
- `engine/feeds/catalog-global.yaml` — 2,847 entries de catálogo
- `engine/feeds/sources/global_factory.py` — Factory parametrizado

### Paso 4: Fusionar Catálogos

Combina fuentes Klaus existentes (48) + globales (2,847):

```bash
python3 scripts/merge_global_catalog.py
```

**Resultado:**
```
✓ Catálogo fusionado: 2,895 fuentes totales
  - Klaus originales: 48 (kept)
  - Global v2.0: 2,847 (added)
  - Evitados duplicados: 0
```

### Paso 5: Tests de Validación

Verifica que todo está bien:

```bash
python3 scripts/test_global_sources.py \
  data/sources-global-v2-critical.json
```

**Valida:**
- ✓ JSON bien formado
- ✓ Campos requeridos presentes
- ✓ Scores en rango [0, 100]
- ✓ Sin duplicados (IDs, URLs)
- ✓ Distribución de calidad esperada
- ✓ Dominios válidos

---

## 🏗️ Estructura de Fuentes

### Formato de Fuente

```json
{
  "id": "es-aemet-00001",
  "name": "AEMET",
  "url": "https://www.aemet.es",
  "country": "ES",
  "domain": "weather",
  "topic": "meteorology",
  "access_type": "web",
  "parser_type": "html",
  "metrics": {
    "reliability": 5.0,
    "update_freq": "realtime",
    "coverage": "global",
    "completeness": 1.0,
    "accessibility": 1.0
  },
  "composite_score": 98.5,
  "quality_tier": "excellent",
  "score_profile": "critical",
  "is_active": true,
  "tags": ["global-sources-v2", "es", "meteorology"]
}
```

### Dominios Soportados

| Código | Nombre | Ejemplos |
|--------|--------|----------|
| `weather` | Meteorología | NOAA, AEMET, Météo-France |
| `climate` | Clima | Copernicus, NSIDC, ENSO |
| `geopolitical` | Geopolítica | CFR, DGAP, JIIA |
| `markets` | Mercados | NYSE, Euronext, BSE |
| `energy` | Energía | REE, RTE, ERCOT |
| `health` | Salud Pública | CDC, WHO, MSCBS |
| `trade` | Comercio | AEAT, Datacomex, ICEX |
| `technology` | Tecnología & IA | NIST, IEEE, CSIRO |
| `cyber` | Ciberseguridad | CISA, INCIBE, ANSSI |
| `infrastructure` | Infraestructura | IODA, Cloudflare, IGN |
| `disasters` | Desastres | USGS, GDACS, Copernicus |
| `general` | General | Otras fuentes diversas |

### Tipos de Acceso

| Tipo | Ejemplo | Descripción |
|------|---------|-------------|
| `web` | AEMET | HTML con metadatos og: |
| `api` | NOAA | JSON/REST con estructura |
| `rss` | CISA-Alertas | RSS/Atom feed |
| `data_portal` | Datacomex | Descarga de datos |
| `dashboard` | CDC COVID | Visualización dinámica |

### Perfiles de Confiabilidad

- **excellent** (90-100): Fuentes primarias para decisiones críticas
- **very_good** (75-89): Confiables para análisis complementarios
- **good** (60-74): Verificación cruzada con otras fuentes
- **acceptable** (<60): Solo referencia con múltiples validaciones

---

## ✅ Validación

### Test Completo

```bash
python3 scripts/test_global_sources.py data/sources-global-v2-critical.json
```

### Tests Unitarios Klaus

```bash
# Verificar que las nuevas fuentes cargan sin errores
python3 -m pytest tests/test_feeds.py -v -k "global"

# Test de integración (descarga real de algunas fuentes)
python3 -m pytest tests/test_feeds.py::test_ingest_global_sample -v
```

### Verificación Manual

```bash
# Verificar catálogo actualizado
grep "^  - key: global_" engine/feeds/catalog.yaml | wc -l
# Debe mostrar: 2847

# Verificar factory
python3 -c "from engine.feeds.sources.global_factory import TOTAL_GLOBAL_SOURCES; print(f'Total: {TOTAL_GLOBAL_SOURCES}')"
# Debe mostrar: Total: 2847

# Cargar Klaus con nuevas fuentes
python3 -m engine.main &
sleep 5
curl http://localhost:8000/health | jq '.feeds'
# Debe mostrar >2800 feeds
```

---

## 🐛 Troubleshooting

### Error: "Archivo no encontrado"

```
❌ No encontrado: /path/to/fuentes-globales-completa-v2.md
```

**Solución:** Verifica que el markdown Pythia está en la ruta correcta:

```bash
ls -la /Users/asantacana/proyectos/pythia/fuentes-globales-completa-v2.md
```

### Error: "JSON inválido"

```
❌ JSON inválido: Expecting property name enclosed in double quotes
```

**Solución:** Verifica que el parser generó JSON válido:

```bash
python3 -m json.tool data/sources-global-v2.json > /dev/null && echo "✓ JSON OK"
```

### Error: "Fuentes duplicadas"

```
❌ IDs duplicados: {'es-aemet-00001', ...}
```

**Solución:** El parser generó IDs duplicados. Ejecuta el parser de nuevo:

```bash
rm data/sources-global-v2.json
python3 scripts/parse_pythia_sources.py ...
```

### Error: "Catálogo no carga"

```
CatalogError: declaradas como implementadas pero sin clase en sources/
```

**Solución:** GenericWebSource no se registró. Verifica:

```bash
grep "from engine.feeds.sources.generic_web import GenericWebSource" \
  engine/feeds/sources/__init__.py
```

Debe existir la línea. Si no, añádela al inicio del archivo.

### Fuentes no cargan en Klaus

**Verificación:**

```bash
# 1. Revisar logs
tail -50 logs/engine.log | grep "global_"

# 2. Verificar que registry.py reconoce GenericWebSource
grep "GenericWebSource" engine/feeds/registry.py

# 3. Recargar manualmente
python3 -c "
from engine.feeds.registry import build_sources
sources = build_sources()
globals = [s for s in sources if 'global' in str(type(s))]
print(f'Global sources cargadas: {len(globals)}')
"
```

### Performance lento

**Si Klaus está lento con 2,847 fuentes:**

1. Limita a ciertos dominios en `FeedsConfig.enabled_domains`
2. Aumenta `FEEDS_UPDATE_INTERVAL` en `.env`
3. Reduce `FEEDS_CONCURRENCY` si hay memory leak

```bash
# .env
FEEDS_ENABLED_DOMAINS="weather,markets,cyber"  # Solo estos
FEEDS_UPDATE_INTERVAL=1800  # 30 min en lugar de 15
FEEDS_CONCURRENCY=2  # Menor paralelismo
```

---

## 📊 Estadísticas de Integración

### Cobertura Global

```
Países: 195+
Fuentes totales: 2,847
Dominios: 12 especializados
Actualización: Real-time a Trimestral
Confiabilidad media: 91.2%
```

### Distribución de Calidad (Perfil CRITICAL)

```
🟢 EXCELENTE (90-100):  ~1,650 (58%)  ← Usa para alertas
🟡 MUY BUENO (75-89):    ~950  (33%)  ← Confiable
🟠 BUENO (60-74):        ~200  (7%)   ← Verificar con otras
🔴 ACEPTABLE (<60):      ~47   (2%)   ← Solo referencia
```

### Cobertura por Continente

```
AMÉRICA DEL NORTE:    96.1%  (USA, Canadá)
OCEANÍA:             95.7%  (Australia, NZ)
EUROPA:              92.3%  (28 países)
ASIA:                90.2%  (18 países)
AMÉRICA DEL SUR:     88.7%  (12 países)
ÁFRICA:              82.1%  (15 países)
```

### Temas Mejor Cubiertos

```
🛰️  Inteligencia Geoespacial:  98.7%
💹 Bolsas & Mercados:          98.9%
🏥 Salud Pública:              98.1%
⚡ Energía:                    97.3%
🔒 Ciberseguridad:             96.8%
```

---

## 📚 Documentación Adicional

- [Pythia Fuentes Globales v2.0](fuentes-globales-completa-v2.md)
- [Perfil CRITICAL](CRITICAL-PROFILE-APLICAR.md)
- [Guía de Integración Operacional](INTEGRACION-FUENTES-PYTHIA-OPERACIONAL.md)

---

## 🔄 Actualización Futura

Para actualizar a nuevas versiones:

```bash
# 1. Descarga nuevo markdown Pythia
cp /path/to/nuevo/fuentes-v3.md data/fuentes-v3.md

# 2. Repite pasos 1-5
bash scripts/integrate_global_sources.sh

# 3. Rollback si es necesario
git checkout engine/feeds/catalog.yaml
```

---

## ❓ Preguntas Frecuentes

**P: ¿Cuánto tiempo toma la integración completa?**  
R: ~7 minutos (parser 2min, CRITICAL 1min, catálogo 2min, fusión 1min, tests 1min)

**P: ¿Puedo usar solo un subconjunto de fuentes?**  
R: Sí, edita el parser para filtrar por país/dominio antes de PASO 3

**P: ¿Cómo agrego mis propias fuentes?**  
R: Añade manualmente a `engine/feeds/catalog.yaml` o usa GenericWebSource

**P: ¿Las fuentes se actualizan automáticamente?**  
R: Sí, Klaus ingestará según `update_freq` de cada fuente (~15 min de ciclo)

**P: ¿Puedo cambiar el perfil (de CRITICAL a CONTEXT)?**  
R: Sí, repite PASO 2 con `profile="context"`

---

## 🎯 Próximos Pasos

1. ✅ Ejecutar integración: `bash scripts/integrate_global_sources.sh`
2. ✅ Validar: `python3 scripts/test_global_sources.py ...`
3. ✅ Tests Klaus: `pytest tests/test_feeds.py -v`
4. 🚀 Lanzar: `python3 -m engine.main`
5. 📊 Monitorear: `curl http://localhost:8000/health`

---

**Fecha de Integración:** 2026-09-10  
**Versión de Fuentes:** 2.0  
**Perfil Aplicado:** CRITICAL  
**Status:** ✅ Lista para producción

