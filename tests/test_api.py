"""Los nueve endpoints, contra la aplicación ASGI en memoria.

Sin servidor, sin red, sin Ollama: el cliente LLM y el ingestor se sustituyen
por dobles justo después de que arranque el `lifespan`.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from engine.api.app import create_app
from engine.api.websocket import _generate, _sse, state_stream
from engine.database import session_scope
from engine.feeds import TTLCache
from engine.feeds.ingestor import FeedIngestor
from engine.models import FeedEvent, Prediction
from tests.fixtures import AGENT_NAMES, FakeLLM, agent_payload, swarm_payload


@pytest.fixture
async def client(db: None, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    """Aplicación real con LLM y feeds falsos."""
    # La ingesta en segundo plano saldría a internet en cuanto arranque.
    monkeypatch.setenv("FEEDS_ENABLED", "false")
    from engine.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://pythia.test") as http:
        # `lifespan` no corre con ASGITransport, así que se monta el estado a mano.
        from engine.api.app import build_state

        state = build_state()
        llm = FakeLLM([swarm_payload(dict.fromkeys(AGENT_NAMES, 0.72))])
        state.llm = llm  # type: ignore[assignment]
        state.swarm.llm = llm  # type: ignore[assignment]
        for agente in state.swarm.agents:
            agente.llm = llm
        state.ingestor = FeedIngestor([], cache=TTLCache(0))
        app.state.pythia = state
        yield http


@pytest.fixture
def con_eventos(db: None) -> None:
    with session_scope() as session:
        session.add(
            FeedEvent(
                source="USGS",
                event_type="earthquake",
                title="M 6.4 - 120 km SE of Tokyo",
                salience=0.85,
                latitude=35.1,
                longitude=140.9,
            )
        )
        session.add(FeedEvent(source="CAISO", title="Reservas bajo el 6%", salience=0.74))
        session.add(FeedEvent(source="Crypto", title="SOL -22% 24h", salience=0.4))


# ---------------------------------------------------------------------
# 1. /health
# ---------------------------------------------------------------------


class TestHealth:
    async def test_responde_ok(self, client: AsyncClient) -> None:
        r = await client.get("/health")

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["agents"] == 7
        assert body["feeds"]["total"] >= 48
        assert body["horizons"] == ["24h", "week", "month", "year"]

    async def test_incluye_la_latencia_en_cabecera(self, client: AsyncClient) -> None:
        r = await client.get("/health")

        assert "X-Process-Time-Ms" in r.headers

    async def test_health_llm(self, client: AsyncClient) -> None:
        r = await client.get("/health/llm")

        assert r.status_code == 200
        body = r.json()
        assert body["available"] is True
        assert body["model"] == "mistral:7b-instruct-q4_K_M"


# ---------------------------------------------------------------------
# 2-3. Estado del mundo
# ---------------------------------------------------------------------


class TestWorldState:
    async def test_agent_view(self, client: AsyncClient, con_eventos: None) -> None:
        r = await client.get("/agent/view")

        assert r.status_code == 200
        body = r.json()
        assert len(body["events"]) == 3
        assert body["events"][0]["source"] == "USGS", "debe venir ordenado por relevancia"
        assert set(body["sources_active"]) == {"USGS", "CAISO", "Crypto"}
        assert "geopolitical" in body["domains"]

    async def test_agent_view_sin_eventos(self, client: AsyncClient) -> None:
        r = await client.get("/agent/view")

        assert r.status_code == 200
        assert r.json()["events"] == []

    async def test_agent_events_filtra_por_fuente(
        self, client: AsyncClient, con_eventos: None
    ) -> None:
        r = await client.get("/agent/events", params={"source": "USGS"})

        body = r.json()
        assert body["total"] == 1
        assert body["events"][0]["source"] == "USGS"

    async def test_agent_events_filtra_por_relevancia(
        self, client: AsyncClient, con_eventos: None
    ) -> None:
        r = await client.get("/agent/events", params={"min_salience": 0.8})

        assert r.json()["total"] == 1

    async def test_agent_events_pagina(self, client: AsyncClient, con_eventos: None) -> None:
        r = await client.get("/agent/events", params={"limit": 2, "offset": 2})

        body = r.json()
        assert len(body["events"]) == 1
        assert body["total"] == 3

    async def test_agent_events_rechaza_parametros_absurdos(self, client: AsyncClient) -> None:
        assert (await client.get("/agent/events", params={"limit": 9999})).status_code == 422
        assert (await client.get("/agent/events", params={"min_salience": 5})).status_code == 422


# ---------------------------------------------------------------------
# 4-6. Razonamiento
# ---------------------------------------------------------------------


class TestPredict:
    async def test_devuelve_los_siete_votos(
        self, client: AsyncClient, con_eventos: None
    ) -> None:
        r = await client.post("/predict", json={"query": "¿Anomalías globales?", "horizon": "24h"})

        assert r.status_code == 200
        body = r.json()
        assert len(body["agent_votes"]) == 7
        assert body["prediction_id"] is not None
        assert 0.0 <= body["confidence"] <= 1.0
        assert body["latency_ms"] >= 0

    async def test_persiste_la_prediccion(self, client: AsyncClient) -> None:
        r = await client.post("/predict", json={"query": "¿Riesgo?"})

        with session_scope() as session:
            fila = session.get(Prediction, r.json()["prediction_id"])
        assert fila is not None
        assert fila.query_text == "¿Riesgo?"

    async def test_horizonte_invalido(self, client: AsyncClient) -> None:
        r = await client.post("/predict", json={"query": "¿Riesgo?", "horizon": "decade"})

        assert r.status_code == 400
        assert "no soportado" in r.json()["detail"]

    async def test_umbral_a_medida(self, client: AsyncClient) -> None:
        r = await client.post("/predict", json={"query": "¿Riesgo?", "min_confidence": 0.99})

        body = r.json()
        assert body["threshold"] == 0.99
        assert body["meets_threshold"] is False

    async def test_query_vacia(self, client: AsyncClient) -> None:
        assert (await client.post("/predict", json={"query": ""})).status_code == 422

    async def test_le_llega_el_contexto_de_los_feeds(
        self, client: AsyncClient, con_eventos: None
    ) -> None:
        await client.post("/predict", json={"query": "¿Riesgo?"})

        prompt = client._transport.app.state.pythia.swarm.llm.calls[0]["prompt"]  # type: ignore[union-attr]
        assert "USGS" in prompt

    async def test_json_del_modelo_irrecuperable_da_502(self, client: AsyncClient) -> None:
        estado = client._transport.app.state.pythia  # type: ignore[union-attr]
        roto = FakeLLM(["no soy json", "sigo sin serlo"])
        estado.swarm.llm = roto

        r = await client.post("/predict", json={"query": "¿Riesgo?"})

        assert r.status_code == 502
        assert r.json()["error"] == "consenso_fallido"


class TestChat:
    async def test_habla_con_un_solo_agente(self, client: AsyncClient) -> None:
        estado = client._transport.app.state.pythia  # type: ignore[union-attr]
        uno = FakeLLM([agent_payload(0.8)])
        for agente in estado.swarm.agents:
            agente.llm = uno

        r = await client.post("/chat", json={"query": "¿Aguanta la red?", "agent": "Economist"})

        assert r.status_code == 200
        body = r.json()
        assert body["agent"] == "Economist"
        assert body["confidence"] == pytest.approx(0.8)
        assert uno.call_count == 1, "chat no debe convocar al enjambre entero"

    async def test_agente_inexistente(self, client: AsyncClient) -> None:
        r = await client.post("/chat", json={"query": "hola", "agent": "Astrologer"})

        assert r.status_code == 404
        assert "Astrologer" in r.json()["detail"]

    async def test_acepta_person_como_alias_de_agent(self, client: AsyncClient) -> None:
        """La guía de instalación usaba `person` en su ejemplo de /chat."""
        estado = client._transport.app.state.pythia  # type: ignore[union-attr]
        for agente in estado.swarm.agents:
            agente.llm = FakeLLM([agent_payload()])

        r = await client.post("/chat", json={"query": "hola", "person": "Economist"})

        assert r.status_code == 200
        assert r.json()["agent"] == "Economist"


class TestWhatIf:
    async def test_analiza_el_escenario(self, client: AsyncClient) -> None:
        r = await client.post("/whatif", json={"scenario": "El petróleo llega a 150 $/barril"})

        assert r.status_code == 200
        body = r.json()
        assert body["scenario"] == "El petróleo llega a 150 $/barril"
        assert len(body["agent_votes"]) == 7

    async def test_no_se_persiste(self, client: AsyncClient) -> None:
        """Un contrafáctico no tiene desenlace: contaminaría el Brier score."""
        r = await client.post("/whatif", json={"scenario": "X"})

        assert r.json()["persisted"] is False
        with session_scope() as session:
            from sqlalchemy import select

            assert session.scalars(select(Prediction)).all() == []

    async def test_el_escenario_llega_al_prompt(self, client: AsyncClient) -> None:
        await client.post("/whatif", json={"scenario": "Corte total del Estrecho de Ormuz"})

        prompt = client._transport.app.state.pythia.swarm.llm.calls[0]["prompt"]  # type: ignore[union-attr]
        assert "Ormuz" in prompt
        assert "hipotético" in prompt.lower()


# ---------------------------------------------------------------------
# 7-8. Histórico y calibración
# ---------------------------------------------------------------------


class TestPredictionsList:
    async def test_lista_lo_emitido(self, client: AsyncClient) -> None:
        await client.post("/predict", json={"query": "primera", "horizon": "24h"})
        await client.post("/predict", json={"query": "segunda", "horizon": "week"})

        r = await client.get("/predictions")

        assert r.json()["total"] == 2

    async def test_filtra_por_horizonte(self, client: AsyncClient) -> None:
        await client.post("/predict", json={"query": "a", "horizon": "24h"})
        await client.post("/predict", json={"query": "b", "horizon": "week"})

        r = await client.get("/predictions", params={"horizon": "week"})

        body = r.json()
        assert body["total"] == 1
        assert body["predictions"][0]["query"] == "b"

    async def test_filtra_por_probabilidad(self, client: AsyncClient) -> None:
        await client.post("/predict", json={"query": "a"})

        r = await client.get("/predictions", params={"min_probability": 0.99})

        assert r.json()["total"] == 0

    async def test_filtra_por_resueltas(self, client: AsyncClient) -> None:
        await client.post("/predict", json={"query": "a"})

        assert (await client.get("/predictions", params={"resolved": False})).json()["total"] == 1
        assert (await client.get("/predictions", params={"resolved": True})).json()["total"] == 0


class TestScorecard:
    async def test_devuelve_los_siete_agentes(self, client: AsyncClient) -> None:
        r = await client.get("/scorecard")

        assert r.status_code == 200
        body = r.json()
        assert len(body["agents"]) == 7
        assert "brier_note" in body["agents"]["Strategist"]

    async def test_filtra_por_agente(self, client: AsyncClient) -> None:
        r = await client.get("/scorecard", params={"agent": "Skeptic"})

        assert list(r.json()["agents"]) == ["Skeptic"]

    async def test_agente_inexistente(self, client: AsyncClient) -> None:
        r = await client.get("/scorecard", params={"agent": "Nadie"})

        assert r.status_code == 404

    async def test_calibracion_tras_resolver(self, client: AsyncClient) -> None:
        from engine.prediction import resolve

        r = await client.post("/predict", json={"query": "¿Ocurrirá?"})
        resolve(r.json()["prediction_id"], outcome=1.0)

        body = (await client.get("/scorecard")).json()

        assert body["resolved_predictions"] == 1
        cal = body["agents"]["Strategist"]["confidence_calibration"]
        assert cal["actual_accuracy"] == 1.0
        assert cal["reading"] in {"bien calibrado", "prudencia excesiva", "exceso de confianza"}


# ---------------------------------------------------------------------
# 9. SSE
# ---------------------------------------------------------------------


class TestStream:
    """El flujo SSE se prueba sobre el generador, no a través de httpx.

    `ASGITransport` acumula el cuerpo completo antes de devolver la respuesta,
    así que un flujo que por definición no termina lo deja colgado para
    siempre. Probar el generador comprueba exactamente la misma lógica sin
    depender de una limitación del cliente de pruebas.
    """

    async def test_emite_el_primer_estado_sin_esperar(
        self, client: AsyncClient, con_eventos: None
    ) -> None:
        """Sin envío inmediato el cliente vería la pantalla en blanco 30 segundos."""
        estado = client._transport.app.state.pythia  # type: ignore[union-attr]
        gen = _generate(estado, interval=300)

        try:
            trozo = await asyncio.wait_for(anext(gen), timeout=5)
        finally:
            await gen.aclose()

        assert trozo.startswith("event: update")
        datos = json.loads(trozo.split("data: ", 1)[1].strip())
        assert datos["total_events"] == 3
        assert datos["feeds_active"] == 3
        assert len(datos["top_events"]) == 3

    async def test_los_siguientes_esperan_al_intervalo(
        self, client: AsyncClient, con_eventos: None
    ) -> None:
        estado = client._transport.app.state.pythia  # type: ignore[union-attr]
        gen = _generate(estado, interval=1)

        try:
            primero = await asyncio.wait_for(anext(gen), timeout=5)
            segundo = await asyncio.wait_for(anext(gen), timeout=5)
        finally:
            await gen.aclose()

        assert primero.startswith("event: update")
        assert segundo.startswith("event: update")

    async def test_un_fallo_puntual_no_corta_el_flujo(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un error leyendo la base de datos no puede cerrar la conexión."""
        estado = client._transport.app.state.pythia  # type: ignore[union-attr]

        def revienta() -> dict[str, int]:
            raise RuntimeError("la base de datos se cayó")

        monkeypatch.setattr("engine.api.websocket.event_counts", revienta)
        gen = _generate(estado, interval=300)

        try:
            trozo = await asyncio.wait_for(anext(gen), timeout=5)
        finally:
            await gen.aclose()

        assert trozo.startswith("event: error")

    async def test_la_respuesta_es_un_event_stream(self, client: AsyncClient) -> None:
        estado = client._transport.app.state.pythia  # type: ignore[union-attr]

        response = state_stream(estado, interval=30)

        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache"
        # Sin esto, un nginx delante bufferiza el flujo y no llega nada.
        assert response.headers["x-accel-buffering"] == "no"

    def test_formato_sse(self) -> None:
        assert _sse("update", {"a": 1}) == 'event: update\ndata: {"a": 1}\n\n'


# ---------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------


class TestAuth:
    async def test_sin_token_configurado_todo_es_publico(self, client: AsyncClient) -> None:
        assert (await client.get("/agent/view")).status_code == 200

    async def test_con_token_se_exige(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from engine.config import get_settings

        monkeypatch.setenv("API_TOKEN", "secreto-de-prueba")
        get_settings.cache_clear()

        assert (await client.get("/agent/view")).status_code == 401
        assert (
            await client.get("/agent/view", headers={"Authorization": "Bearer malo"})
        ).status_code == 401
        assert (
            await client.get(
                "/agent/view", headers={"Authorization": "Bearer secreto-de-prueba"}
            )
        ).status_code == 200

    async def test_health_sigue_abierto_con_token(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lo consultan los supervisores de proceso, que no llevan credenciales."""
        from engine.config import get_settings

        monkeypatch.setenv("API_TOKEN", "secreto-de-prueba")
        get_settings.cache_clear()

        assert (await client.get("/health")).status_code == 200
