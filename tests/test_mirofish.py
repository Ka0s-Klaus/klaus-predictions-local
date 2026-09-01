"""Enjambre, consenso y calibración."""

from __future__ import annotations

import json

import pytest

from engine.llm.schemas import AgentVerdict, MalformedResponseError, extract_json
from engine.mirofish import MiroFishSwarm, build_agents, weighted_consensus
from engine.mirofish.agents.base import NEUTRAL_BRIER
from engine.mirofish.swarm import SwarmError
from tests.fixtures import SAMPLE_EVENTS, FakeLLM, agent_payload, swarm_payload


class TestSwarmRun:
    async def test_una_sola_llamada_para_los_siete_agentes(self, swarm: MiroFishSwarm) -> None:
        """El diseño multi-persona existe para no hacer siete llamadas."""
        result = await swarm.run("¿Anomalías globales?", {"events": SAMPLE_EVENTS})

        assert swarm.llm.call_count == 1
        assert len(result.agent_votes) == 7

    async def test_presupuesto_de_tokens_escala_con_el_enjambre(
        self, swarm: MiroFishSwarm
    ) -> None:
        """384 tokens no dan para siete dictámenes: la respuesta se truncaría."""
        await swarm.run("¿Anomalías globales?")

        assert swarm.llm.calls[0]["max_tokens"] >= 512
        assert swarm.llm.calls[0]["json_mode"] is True

    async def test_reintenta_una_vez_con_json_malformado(self) -> None:
        llm = FakeLLM(["esto no es JSON en absoluto", swarm_payload()])
        swarm = MiroFishSwarm(build_agents(llm), llm)

        result = await swarm.run("¿Anomalías globales?")

        assert llm.call_count == 2
        assert result.confidence > 0
        # El segundo prompt le dice al modelo qué hizo mal.
        assert "anterior" in llm.calls[1]["prompt"]

    async def test_se_rinde_tras_el_segundo_fallo(self) -> None:
        llm = FakeLLM(["basura", "más basura", "y más"])
        swarm = MiroFishSwarm(build_agents(llm), llm)

        with pytest.raises(SwarmError, match="dos intentos"):
            await swarm.run("¿Anomalías globales?")

        assert llm.call_count == 2

    async def test_acepta_respuesta_sin_envoltorio_verdicts(self) -> None:
        """Los modelos pequeños se saltan la clave `verdicts` a menudo."""
        llm = FakeLLM(swarm_payload(wrap=False))
        swarm = MiroFishSwarm(build_agents(llm), llm)

        result = await swarm.run("¿Anomalías globales?")

        assert len(result.agent_votes) == 7

    async def test_descarta_agentes_inventados(self) -> None:
        payload = json.loads(swarm_payload())
        payload["verdicts"]["Astrologer"] = {
            "prediction": "Mercurio retrógrado",
            "confidence": 0.99,
            "reasoning": "",
            "sources_used": [],
        }
        llm = FakeLLM(json.dumps(payload))
        swarm = MiroFishSwarm(build_agents(llm), llm)

        result = await swarm.run("¿Anomalías globales?")

        assert "Astrologer" not in result.agent_votes
        assert len(result.agent_votes) == 7

    async def test_descarta_fuentes_que_no_estaban_en_el_contexto(self) -> None:
        """Un modelo pequeño copió literalmente el "…" del esquema de ejemplo.

        Observado en una ejecución real: `sources_used: ["…"]`. Citar una
        fuente inexistente es peor que no citar ninguna.
        """
        payload = json.loads(swarm_payload())
        for verdict in payload["verdicts"].values():
            verdict["sources_used"] = ["…", "USGS", "Inventada"]
        llm = FakeLLM(json.dumps(payload))
        swarm = MiroFishSwarm(build_agents(llm), llm)

        result = await swarm.run("¿Anomalías?", {"events": SAMPLE_EVENTS})

        assert result.sources_used == ["USGS"]

    async def test_sin_contexto_no_se_filtra_por_fuente(self) -> None:
        """Sin eventos no hay contra qué contrastar; sólo caen los marcadores."""
        payload = json.loads(swarm_payload())
        for verdict in payload["verdicts"].values():
            verdict["sources_used"] = ["…", "GDELT"]
        llm = FakeLLM(json.dumps(payload))
        swarm = MiroFishSwarm(build_agents(llm), llm)

        result = await swarm.run("¿Anomalías?", {"events": []})

        assert result.sources_used == ["GDELT"]

    async def test_enjambre_vacio_es_error_de_programacion(self) -> None:
        with pytest.raises(ValueError, match="al menos un agente"):
            MiroFishSwarm([], FakeLLM("{}"))


class TestConsensus:
    def test_mejor_brier_pesa_mas(self) -> None:
        """El núcleo del diseño: quien acierta más inclina más la balanza."""
        agents = build_agents()
        preciso, impreciso = agents[0], agents[1]
        preciso.brier_score = 0.05
        impreciso.brier_score = 0.90

        verdicts = {
            preciso.name: AgentVerdict(prediction="a", confidence=1.0),
            impreciso.name: AgentVerdict(prediction="b", confidence=0.0),
        }
        result = weighted_consensus(verdicts, agents)

        assert result.weights[preciso.name] > result.weights[impreciso.name]
        # Media plana daría 0.5; la ponderación empuja hacia el agente preciso.
        assert result.confidence > 0.5

    def test_sin_ponderacion_es_media_plana(self) -> None:
        agents = build_agents()
        agents[0].brier_score = 0.05
        agents[1].brier_score = 0.90

        verdicts = {
            agents[0].name: AgentVerdict(prediction="a", confidence=1.0),
            agents[1].name: AgentVerdict(prediction="b", confidence=0.0),
        }
        result = weighted_consensus(verdicts, agents, brier_weighted=False)

        assert result.confidence == pytest.approx(0.5)

    def test_agentes_ausentes_no_cuentan_en_el_denominador(self) -> None:
        """Si el modelo omite un agente, su peso no puede diluir la media."""
        agents = build_agents()
        verdicts = {agents[0].name: AgentVerdict(prediction="a", confidence=0.8)}

        result = weighted_consensus(verdicts, agents)

        assert result.confidence == pytest.approx(0.8)
        assert len(result.weights) == 1

    def test_dictamenes_desconocidos_son_error(self) -> None:
        verdicts = {"Nadie": AgentVerdict(prediction="a", confidence=0.5)}

        with pytest.raises(ValueError, match="Ningún dictamen"):
            weighted_consensus(verdicts, build_agents())

    def test_discrepancia_alta_cuando_los_agentes_chocan(self) -> None:
        agents = build_agents()
        acuerdo = weighted_consensus(
            {a.name: AgentVerdict(prediction="x", confidence=0.7) for a in agents}, agents
        )
        choque = weighted_consensus(
            {
                a.name: AgentVerdict(prediction="x", confidence=0.1 if i % 2 else 0.9)
                for i, a in enumerate(agents)
            },
            agents,
        )

        assert acuerdo.dissent == 0.0
        assert choque.dissent > 0.3

    def test_usa_la_sintesis_del_modelo_como_prediccion(self) -> None:
        agents = build_agents()
        verdicts = {a.name: AgentVerdict(prediction="parcial", confidence=0.5) for a in agents}

        result = weighted_consensus(verdicts, agents, synthesis="Visión conjunta.")

        assert result.prediction == "Visión conjunta."


class TestAgentCalibration:
    def test_actualiza_aciertos_y_no_solo_la_media(self) -> None:
        """La versión de la especificación nunca tocaba `correct_predictions`."""
        agent = build_agents()[0]

        agent.update_brier_score(0.9, 1.0)

        assert agent.predictions_made == 1
        assert agent.correct_predictions == 1
        assert agent.accuracy == 1.0
        assert agent.brier_score == pytest.approx(0.01)

    def test_una_prediccion_muy_errada_cuenta_como_fallo(self) -> None:
        agent = build_agents()[0]

        agent.update_brier_score(0.9, 0.0)

        assert agent.correct_predictions == 0
        assert agent.brier_score == pytest.approx(0.81)

    def test_arranca_en_brier_neutro(self) -> None:
        agent = build_agents()[0]

        assert agent.brier_score == NEUTRAL_BRIER
        assert agent.weight == pytest.approx(1 / 1.25)

    async def test_record_outcome_propaga_a_los_votantes(self, swarm: MiroFishSwarm) -> None:
        result = await swarm.run("¿Anomalías globales?")

        scores = swarm.record_outcome(result.agent_votes, actual=1.0)

        assert len(scores) == 7
        assert all(agent.predictions_made == 1 for agent in swarm.agents)


class TestSingleAgent:
    async def test_analyze_usa_el_camino_individual(self) -> None:
        """`/chat` habla con un solo agente, no con el enjambre."""
        llm = FakeLLM(agent_payload(0.72))
        agent = build_agents(llm)[0]

        verdict = await agent.analyze("¿Aguanta la red?", {"events": SAMPLE_EVENTS})

        assert verdict.confidence == pytest.approx(0.72)
        assert agent.name in llm.calls[0]["prompt"]

    async def test_analyze_sin_llm_falla_con_mensaje_util(self) -> None:
        agent = build_agents()[0]

        with pytest.raises(RuntimeError, match="no tiene cliente LLM"):
            await agent.analyze("¿Aguanta la red?")


class TestJSONExtraction:
    @pytest.mark.parametrize(
        "raw",
        [
            '{"a": 1}',
            '```json\n{"a": 1}\n```',
            '```\n{"a": 1}\n```',
            'Claro, aquí tienes:\n{"a": 1}\nEspero que sirva.',
        ],
    )
    def test_rescata_json_envuelto(self, raw: str) -> None:
        assert extract_json(raw) == {"a": 1}

    @pytest.mark.parametrize("raw", ["sin json", "", "[1, 2, 3]", "{roto"])
    def test_rechaza_lo_irrecuperable(self, raw: str) -> None:
        with pytest.raises(MalformedResponseError):
            extract_json(raw)

    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [(0.78, 0.78), ("0.78", 0.78), (78, 0.78), ("78%", 0.78), (1, 1.0)],
    )
    def test_normaliza_confianza_en_porcentaje(self, entrada: object, esperado: float) -> None:
        """Los modelos pequeños confunden probabilidad con porcentaje."""
        verdict = AgentVerdict(prediction="x", confidence=entrada)

        assert verdict.confidence == pytest.approx(esperado)

    def test_sources_used_admite_cadena(self) -> None:
        verdict = AgentVerdict(prediction="x", confidence=0.5, sources_used="USGS, CAISO")

        assert verdict.sources_used == ["USGS", "CAISO"]
