#!/bin/bash
# Integración completa: fuentes Pythia v2.0 → Klaus
#
# Este script ejecuta todos los pasos en orden:
#   1. Parser markdown → JSON
#   2. Aplicar perfil CRITICAL
#   3. Generar entradas de catálogo
#   4. Fusionar catálogos
#   5. Tests de validación
#
# Uso:
#   bash scripts/integrate_global_sources.sh

set -e  # Exit on error

echo "=================================="
echo "🚀 Integración Global Sources v2.0"
echo "=================================="

# Detecta rutas
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data"
PYTHIA_SOURCES="/Users/asantacana/proyectos/pythia/fuentes-globales-completa-v2.md"

# Verifica prerequisitos
echo -e "\n📋 Verificando prerequisitos..."

if [ ! -f "$PYTHIA_SOURCES" ]; then
    echo "❌ No encontrado: $PYTHIA_SOURCES"
    echo "   Especifica la ruta al markdown Pythia v2.0"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no encontrado"
    exit 1
fi

if ! python3 -c "import yaml" 2>/dev/null; then
    echo "⚠️  PyYAML no instalado, instalando..."
    pip install pyyaml
fi

mkdir -p "$DATA_DIR"
echo "✓ Prerequisitos OK"

# PASO 1: Parser
echo -e "\n📂 PASO 1: Parseando markdown v2.0..."
python3 "$SCRIPT_DIR/parse_pythia_sources.py" \
    "$PYTHIA_SOURCES" \
    "$DATA_DIR/sources-global-v2.json"

if [ ! -f "$DATA_DIR/sources-global-v2.json" ]; then
    echo "❌ Error: parser no generó archivo"
    exit 1
fi
echo "✓ Parser completado"

# PASO 2: Aplicar perfil CRITICAL
echo -e "\n⚙️  PASO 2: Aplicando perfil CRITICAL..."
python3 "$SCRIPT_DIR/apply_critical_profile.py" \
    "$DATA_DIR/sources-global-v2.json" \
    "$DATA_DIR/sources-global-v2-critical.json" \
    "critical"

if [ ! -f "$DATA_DIR/sources-global-v2-critical.json" ]; then
    echo "❌ Error: apply_critical_profile no generó archivo"
    exit 1
fi
echo "✓ Perfil CRITICAL aplicado"

# PASO 3: Generar catálogo
echo -e "\n🔧 PASO 3: Generando entradas de catálogo..."
python3 "$SCRIPT_DIR/generate_catalog_entries.py" \
    "$DATA_DIR/sources-global-v2-critical.json" \
    "$PROJECT_DIR/engine/feeds/catalog-global.yaml" \
    "$PROJECT_DIR/engine/feeds/sources/global_factory.py"

if [ ! -f "$PROJECT_DIR/engine/feeds/catalog-global.yaml" ]; then
    echo "❌ Error: generate_catalog_entries no generó catálogo"
    exit 1
fi
echo "✓ Catálogo generado"

# PASO 4: Fusionar catálogos
echo -e "\n🔀 PASO 4: Fusionando catálogos..."
cd "$PROJECT_DIR"
python3 scripts/merge_global_catalog.py

if [ ! -f "$PROJECT_DIR/engine/feeds/catalog.yaml" ]; then
    echo "❌ Error: merge no fusionó catálogos"
    exit 1
fi
echo "✓ Catálogos fusionados"

# PASO 5: Tests de validación
echo -e "\n✅ PASO 5: Ejecutando tests de validación..."
python3 "$SCRIPT_DIR/test_global_sources.py" \
    "$DATA_DIR/sources-global-v2-critical.json"

# Resumen
echo -e "\n=================================="
echo "✅ INTEGRACIÓN COMPLETADA"
echo "=================================="
echo ""
echo "📊 RESUMEN:"
total_sources=$(python3 -c "import json; print(len(json.load(open('$DATA_DIR/sources-global-v2-critical.json'))['sources']))")
echo "  • Total fuentes integradas: $total_sources"
echo "  • Catálogo actualizado: engine/feeds/catalog.yaml"
echo "  • Factory generado: engine/feeds/sources/global_factory.py"
echo ""
echo "🔧 PRÓXIMOS PASOS:"
echo "  1. Revisar engine/feeds/catalog.yaml"
echo "  2. Tests: python -m pytest tests/test_feeds.py -v"
echo "  3. Ejecutar Klaus: python -m engine.main"
echo ""
echo "💾 ARCHIVOS GENERADOS:"
echo "  • $DATA_DIR/sources-global-v2.json"
echo "  • $DATA_DIR/sources-global-v2-critical.json"
echo "  • $PROJECT_DIR/engine/feeds/catalog-global.yaml"
echo "  • $PROJECT_DIR/engine/feeds/sources/global_factory.py"
echo ""
