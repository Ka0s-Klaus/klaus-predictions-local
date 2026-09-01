"""Brier score, persistencia de predicciones y resolución."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from engine.database import session_scope
from engine.mirofish import MiroFishSwarm, build_agents
from engine.models import AgentScore, AuditLog, Prediction
from engine.prediction import (
    UNINFORMED_BRIER,
    Predictor,
    brier_score,
    brier_skill_score,
    calibration,
    mean_brier,
    resolve,
)
from engine.prediction.brier import running_update
from tests.fixtures import AGENT_NAMES, SAMPLE_EVENTS, FakeLLM, swarm_payload


class TestBrier:
    def test_prediccion_perfecta_puntua_cero(self) -> None:
        assert brier_score(1.0, 1.0) == 0.0

    def test_prediccion_pesima_puntua_uno(self) -> None:
        assert brier_score(0.0, 1.0) == 1.0

    def test_ignorancia_declarada_puntua_un_cuarto(self) -> None:
        """0.5 siempre da 0.25. Es la referencia contra la que se mide todo."""
        assert brier_score(0.5, 1.0) == UNINFORMED_BRIER
        assert brier_score(0.5, 0.0) == UNINFORMED_BRIER

    @pytest.mark.parametrize(("prob", "outcome"), [(1.5, 1.0), (-0.1, 0.0), (0.5, 2.0)])
    def test_rechaza_valores_fuera_de_rango(self, prob: float, outcome: float) -> None:
        with pytest.raises(ValueError, match="entre 0 y 1"):
            brier_score(prob, outcome)

    def test_skill_positivo_cuando_aporta_informacion(self) -> None:
        bueno = [(0.9, 1.0), (0.1, 0.0), (0.85, 1.0)]
        malo = [(0.1, 1.0), (0.9, 0.0)]

        assert brier_skill_score(bueno) > 0
        assert brier_skill_score(malo) < 0

    def test_sin_muestras_devuelve_la_referencia(self) -> None:
        assert mean_brier([]) == UNINFORMED_BRIER
        assert brier_skill_score([]) == 0.0

    def test_media_incremental_coincide_con_la_completa(self) -> None:
        pares = [(0.8, 1.0), (0.3, 0.0), (0.6, 1.0)]

        acumulado = 0.0
        for i, (p, o) in enumerate(pares):
            acumulado = running_update(acumulado, i, p, o)

        assert acumulado == pytest.approx(mean_brier(pares))

    def test_calibracion_detecta_exceso_de_confianza(self) -> None:
        # Dice 0.9 constantemente pero sólo acierta la mitad.
        pares = [(0.9, 1.0), (0.9, 0.0), (0.9, 1.0), (0.9, 0.0)]

        cal = calibration(pares)

        assert cal.avg_predicted_confidence == pytest.approx(0.9)
        assert cal.actual_accuracy == pytest.approx(0.5)
        assert cal.calibration_ratio > 1.0

    def test_calibracion_sin_muestras_no_divide_por_cero(self) -> None:
        assert calibration([]).calibration_ratio == 0.0


class TestPredictor:
    @pytest.fixture
    def predictor(self) -> Predictor:
        llm = FakeLLM(swarm_payload(dict.fromkeys(AGENT_NAMES, 0.8)))
        agents = build_agents(llm)
        return Predictor(
            MiroFishSwarm(agents, llm),
            context_provider=lambda _query, _limit: SAMPLE_EVENTS,
        )

    async def test_guarda_la_prediccion_y_devuelve_su_id(
        self, db: None, predictor: Predictor
    ) -> None:
        result = await predictor.predict("¿Riesgo de red?", horizon="24h")

        assert result["prediction_id"] is not None
        with session_scope() as session:
            row = session.get(Prediction, result["prediction_id"])
            assert row is not None
            assert row.horizon == "24h"
            assert row.resolved is False
            assert 0.0 <= row.probability <= 1.0

    async def test_registra_auditoria(self, db: None, predictor: Predictor) -> None:
        await predictor.predict("¿Riesgo de red?")

        with session_scope() as session:
            assert session.scalars(select(AuditLog)).all()

    async def test_persist_false_no_toca_la_base_de_datos(
        self, db: None, predictor: Predictor
    ) -> None:
        result = await predictor.predict("¿Riesgo de red?", persist=False)

        assert result["prediction_id"] is None
        with session_scope() as session:
            assert session.scalars(select(Prediction)).all() == []

    async def test_horizonte_desconocido_falla_pronto(self, predictor: Predictor) -> None:
        with pytest.raises(ValueError, match="no soportado"):
            await predictor.predict("¿Riesgo?", horizon="decade")

    async def test_pasa_los_eventos_al_prompt(self, db: None, predictor: Predictor) -> None:
        await predictor.predict("¿Riesgo de red?")

        prompt = predictor.swarm.llm.calls[0]["prompt"]
        assert "USGS" in prompt
        assert "CAISO" in prompt

    async def test_marca_si_alcanza_el_umbral(self, db: None) -> None:
        llm = FakeLLM(swarm_payload(dict.fromkeys(AGENT_NAMES, 0.3)))
        predictor = Predictor(MiroFishSwarm(build_agents(llm), llm), confidence_min=0.55)

        result = await predictor.predict("¿Riesgo?")

        assert result["meets_threshold"] is False

    async def test_el_historial_sobrevive_al_reinicio(self, db: None) -> None:
        """Sin esto, el voto ponderado se reinicia con cada arranque."""
        llm = FakeLLM(swarm_payload())
        primero = Predictor(MiroFishSwarm(build_agents(llm), llm))
        primero.swarm.agents[0].update_brier_score(0.9, 1.0)
        primero.save_agent_scores()

        segundo = Predictor(MiroFishSwarm(build_agents(llm), llm))
        segundo.load_agent_scores()

        assert segundo.swarm.agents[0].brier_score == pytest.approx(0.01)
        assert segundo.swarm.agents[0].predictions_made == 1


class TestResolution:
    async def _crear_prediccion(self, confidence: float = 0.8) -> int:
        llm = FakeLLM(swarm_payload(dict.fromkeys(AGENT_NAMES, confidence)))
        predictor = Predictor(MiroFishSwarm(build_agents(llm), llm))
        result = await predictor.predict("¿Ocurrirá?")
        return result["prediction_id"]

    async def test_resolver_calcula_el_brier_y_cierra_la_fila(self, db: None) -> None:
        pid = await self._crear_prediccion()

        score = resolve(pid, outcome=1.0, notes="Ocurrió")

        with session_scope() as session:
            row = session.get(Prediction, pid)
            assert row.resolved is True
            assert row.outcome_value == 1.0
            assert row.actual_outcome == "Ocurrió"
            assert row.brier_score == pytest.approx(score)
            assert row.resolution_time is not None

    async def test_resolver_actualiza_el_marcador_de_cada_agente(self, db: None) -> None:
        pid = await self._crear_prediccion()

        resolve(pid, outcome=1.0)

        with session_scope() as session:
            scores = {r.agent_name: r for r in session.scalars(select(AgentScore))}
        assert len(scores) == 7
        assert all(r.predictions_made == 1 for r in scores.values())
        assert all(r.accuracy == 1.0 for r in scores.values())

    async def test_no_se_resuelve_dos_veces(self, db: None) -> None:
        pid = await self._crear_prediccion()
        resolve(pid, outcome=1.0)

        with pytest.raises(ValueError, match="ya estaba resuelta"):
            resolve(pid, outcome=0.0)

    def test_prediccion_inexistente(self, db: None) -> None:
        with pytest.raises(LookupError, match="no existe"):
            resolve(9999, outcome=1.0)

    async def test_desenlace_fuera_de_rango(self, db: None) -> None:
        pid = await self._crear_prediccion()

        with pytest.raises(ValueError, match="entre 0 y 1"):
            resolve(pid, outcome=1.5)
