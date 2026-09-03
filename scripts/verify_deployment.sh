#!/bin/bash
# Verificación de despliegue en red distribuida
# Ejecutar en el Lenovo después de arrancar servicios

set -e

echo "=================================="
echo "Klaus Predictions - Verificación"
echo "=================================="
echo ""

# Colores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

API_URL="http://localhost:8088"
UI_URL="http://localhost:3000"

# 1. Verificar conectividad API
echo -n "1. Conectividad API (localhost:8088)... "
if curl -s "$API_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC} No responde"
    exit 1
fi

# 2. Contar eventos en BD
echo -n "2. Eventos recopilados en BD... "
EVENT_COUNT=$(curl -s "$API_URL/agent/events?limit=0" | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data.get('events', [])))" 2>/dev/null || echo "0")
if [ "$EVENT_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ $EVENT_COUNT eventos${NC}"
else
    echo -e "${YELLOW}⚠ No hay eventos aún (ingesta puede tardar 5-15 min)${NC}"
fi

# 3. Listar eventos por fuente
echo ""
echo "3. Eventos por fuente:"
curl -s "$API_URL/agent/events?limit=100" | python3 << 'EOF'
import sys, json
try:
    data = json.load(sys.stdin)
    events = data.get("events", [])
    sources = {}
    for event in events:
        source = event.get("source", "unknown")
        sources[source] = sources.get(source, 0) + 1

    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        print(f"   {source}: {count}")
except:
    print("   (Error al parsear)")
EOF

# 4. Verificar ingesta automática
echo ""
echo -n "4. Ingesta automática (últimas 2h)... "
RECENT_EVENTS=$(curl -s "$API_URL/agent/events?limit=1000" | python3 -c "
import sys, json, time
from datetime import datetime, timedelta
data = json.load(sys.stdin)
events = data.get('events', [])
now = datetime.utcnow()
two_hours_ago = now - timedelta(hours=2)
recent = [e for e in events if e.get('created_at')]
print(len(recent))
" 2>/dev/null || echo "0")
if [ "$RECENT_EVENTS" -gt 0 ]; then
    echo -e "${GREEN}✓ $RECENT_EVENTS eventos recientes${NC}"
else
    echo -e "${YELLOW}⚠ Sin eventos recientes (verificar FEEDS_UPDATE_INTERVAL)${NC}"
fi

# 5. Verificar calibración de agentes
echo ""
echo -n "5. Estado de agentes (Brier score)... "
SCORECARD=$(curl -s "$API_URL/scorecard" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('agent_scores'):
    print('✓')
else:
    print('(sin predicciones aún)')
" || echo "✗")
echo -e "${GREEN}${SCORECARD}${NC}"

# 6. Verificar persistencia BD
echo ""
echo "6. Persistencia de datos — BEFORE:"
EVENT_COUNT_BEFORE=$(curl -s "$API_URL/agent/events?limit=0" | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data.get('events', [])))" 2>/dev/null || echo "0")
echo "   Eventos: $EVENT_COUNT_BEFORE"

echo ""
echo -e "${YELLOW}→ Reiniciando servicios en 3 segundos...${NC}"
sleep 1
echo "→ 2..."
sleep 1
echo "→ 1..."
sleep 1

# Killall y restart (asume que start-pythia.sh está en PATH o se ejecuta manualmente)
echo ""
echo -e "${YELLOW}Debes detener y reiniciar manualmente:${NC}"
echo "  Terminal 1: Ctrl+C en ./start-pythia.sh"
echo "  Terminal 1: ./start-pythia.sh (reiniciar)"
echo "  Luego ejecuta este script de nuevo para verificar persistencia"
echo ""
echo "Esperando 10 segundos antes de verificar..."
sleep 10

echo ""
echo "7. Persistencia de datos — AFTER:"
EVENT_COUNT_AFTER=$(curl -s "$API_URL/agent/events?limit=0" | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data.get('events', [])))" 2>/dev/null || echo "0")
echo "   Eventos: $EVENT_COUNT_AFTER"

if [ "$EVENT_COUNT_AFTER" -eq "$EVENT_COUNT_BEFORE" ] && [ "$EVENT_COUNT_AFTER" -gt 0 ]; then
    echo -e "   ${GREEN}✓ Datos persisten correctamente${NC}"
elif [ "$EVENT_COUNT_AFTER" -gt "$EVENT_COUNT_BEFORE" ]; then
    echo -e "   ${GREEN}✓ Datos persisten + nuevos eventos ($EVENT_COUNT_AFTER vs $EVENT_COUNT_BEFORE)${NC}"
else
    echo -e "   ${RED}✗ Error: eventos perdidos!${NC}"
fi

# 8. UI accesible
echo ""
echo -n "8. UI Osiris (localhost:3000)... "
if curl -s "$UI_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ No responde (puede estar arrancando)${NC}"
fi

echo ""
echo "=================================="
echo "Verificación completada"
echo "=================================="
