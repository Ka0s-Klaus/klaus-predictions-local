#!/bin/bash
# Inspecciona la BD SQLite directamente (sin API)

DB_FILE="${1:-./pythia.db}"

if [ ! -f "$DB_FILE" ]; then
    echo "Error: BD no encontrada en $DB_FILE"
    exit 1
fi

echo "=================================="
echo "Inspección de BD — $DB_FILE"
echo "=================================="
echo ""

# Total de eventos
echo "1. Total de eventos:"
sqlite3 "$DB_FILE" "SELECT COUNT(*) as total FROM feed_events;"

# Eventos por fuente
echo ""
echo "2. Eventos por fuente:"
sqlite3 "$DB_FILE" << 'SQL'
SELECT
    source,
    COUNT(*) as count,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM feed_events
GROUP BY source
ORDER BY count DESC;
SQL

# Eventos más recientes
echo ""
echo "3. Últimos 10 eventos:"
sqlite3 "$DB_FILE" << 'SQL'
SELECT
    datetime(created_at) as created,
    source,
    title
FROM feed_events
ORDER BY created_at DESC
LIMIT 10;
SQL

# Predicciones registradas
echo ""
echo "4. Total de predicciones:"
sqlite3 "$DB_FILE" "SELECT COUNT(*) as total FROM predictions;"

# Puntuaciones de agentes
echo ""
echo "5. Agentes y Brier score:"
sqlite3 "$DB_FILE" << 'SQL'
SELECT
    agent_name,
    COUNT(*) as predictions,
    ROUND(AVG(brier_score), 3) as avg_brier,
    MIN(brier_score) as best,
    MAX(brier_score) as worst
FROM agent_scores
GROUP BY agent_name
ORDER BY avg_brier ASC;
SQL

echo ""
echo "=================================="
