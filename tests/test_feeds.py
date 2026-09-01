"""Catálogo, parsers, ingesta concurrente y caché."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from sqlalchemy import select

from engine.database import session_scope
from engine.feeds import (
    IMPLEMENTATIONS,
    CatalogError,
    FeedError,
    FeedIngestor,
    FeedSource,
    NormalizedEvent,
    TTLCache,
    build_sources,
    dedupe,
    event_counts,
    implemented_entries,
    load_catalog,
    planned_entries,
    prune_old_events,
    recent_events,
    summary,
)
from engine.feeds.normalizer import clamp, parse_timestamp, truncate
from engine.feeds.sources import (
    EONET,
    GDELT,
    CryptoPrices,
    ForexRates,
    NHCStorms,
    NWSAlerts,
    SWPCAlerts,
    USGSEarthquakes,
)
from engine.models import FeedEvent

# Número de fuentes que piden los documentos de partida.
TARGET_SOURCES = 48

# ---------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------


class StubSource(FeedSource):
    """Fuente que devuelve lo que se le diga, o revienta a propósito."""

    name: ClassVar[str] = "Stub"
    domain: ClassVar[str] = "test"
    event_type: ClassVar[str] = "stub"
    endpoint: ClassVar[str] = "https://example.invalid/stub"

    def __init__(
        self,
        events: list[NormalizedEvent] | None = None,
        error: Exception | None = None,
        name: str = "Stub",
    ):
        super().__init__()
        # Atributo de instancia: sobreescribir el ClassVar filtraría el nombre
        # a los demás tests.
        self.name = name
        self._events = events or []
        self._error = error

    def parse(self, payload: Any) -> list[NormalizedEvent]:  # pragma: no cover
        return self._events

    async def fetch(self, session: Any) -> list[NormalizedEvent]:
        if self._error is not None:
            raise self._error
        return self._events


def make_stub(nombre: str, **kwargs: Any) -> StubSource:
    return StubSource(name=nombre, **kwargs)


def evento(source: str = "Stub", external_id: str | None = "1", **kwargs: Any) -> NormalizedEvent:
    return NormalizedEvent(source=source, title="evento", external_id=external_id, **kwargs)


# ---------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------


class TestCatalog:
    def test_cubre_el_objetivo_documentado(self) -> None:
        """Los documentos de partida piden 48 fuentes; el catálogo no baja de ahí."""
        assert len(load_catalog()) >= TARGET_SOURCES

    def test_todas_las_implementadas_tienen_clase(self) -> None:
        """Si no, el fallo aparecería al arrancar la ingesta, no aquí."""
        for entry in implemented_entries():
            assert entry.key in IMPLEMENTATIONS

    def test_todas_las_clases_estan_en_el_catalogo(self) -> None:
        claves = {entry.key for entry in load_catalog()}
        assert set(IMPLEMENTATIONS) <= claves

    def test_implementadas_y_pendientes_suman_el_total(self) -> None:
        total = len(load_catalog())

        assert len(implemented_entries()) == 11
        assert len(implemented_entries()) + len(planned_entries()) == total

    def test_las_pendientes_no_inventan_endpoint(self) -> None:
        """El endpoint vive en la clase; una pendiente no tiene ninguno."""
        for entry in planned_entries():
            assert entry.homepage, f"{entry.key} debería al menos indicar su homepage"

    def test_las_que_necesitan_clave_estan_marcadas(self) -> None:
        con_clave = {e.key for e in load_catalog() if e.requires_key}
        assert "firms_wildfire" in con_clave
        assert "acled" in con_clave

    def test_resumen(self) -> None:
        datos = summary()

        total = len(load_catalog())

        assert datos["total"] == total >= TARGET_SOURCES
        assert datos["implemented"] + datos["planned"] == total
        assert sum(datos["by_domain"].values()) == total

    def test_catalogo_inexistente(self) -> None:
        load_catalog.cache_clear()
        with pytest.raises(CatalogError, match="no se encuentra"):
            load_catalog("/no/existe.yaml")
        load_catalog.cache_clear()

    def test_build_sources_filtra_por_clave(self) -> None:
        fuentes = build_sources(["usgs_earthquakes", "eonet"])

        assert {s.name for s in fuentes} == {"USGS", "EONET"}

    def test_build_sources_rechaza_claves_desconocidas(self) -> None:
        with pytest.raises(CatalogError, match="desconocidas"):
            build_sources(["no_existe"])

    def test_build_sources_ignora_las_pendientes(self) -> None:
        """Pedir una pendiente no es un error: simplemente no hay nada que crear."""
        assert build_sources(["caiso"]) == []


# ---------------------------------------------------------------------
# Normalizador
# ---------------------------------------------------------------------


class TestNormalizer:
    def test_recorta_titulos_largos(self) -> None:
        largo = "x" * 900

        assert len(NormalizedEvent(source="s", title=largo).title) == 500

    def test_descarta_coordenadas_imposibles(self) -> None:
        """Un CHECK violado aborta la transacción entera, no solo esa fila."""
        e = NormalizedEvent(source="s", title="t", latitude=999.0, longitude=-500.0)

        assert e.latitude is None
        assert e.longitude is None

    def test_acota_la_relevancia(self) -> None:
        assert NormalizedEvent(source="s", title="t", salience=5.0).salience == 1.0
        assert NormalizedEvent(source="s", title="t", salience=-2.0).salience == 0.0

    def test_titulo_vacio_tiene_relleno(self) -> None:
        assert NormalizedEvent(source="s", title="   ").title == "(sin título)"

    @pytest.mark.parametrize(
        "valor",
        [1788258977000, 1788258977, "2026-09-01T07:37:17Z", "2026-09-01T07:37:17+00:00"],
    )
    def test_interpreta_los_formatos_de_fecha_habituales(self, valor: Any) -> None:
        assert parse_timestamp(valor) is not None

    @pytest.mark.parametrize("valor", [None, "", "ayer", {}, []])
    def test_fechas_ilegibles_dan_none(self, valor: Any) -> None:
        assert parse_timestamp(valor) is None

    def test_epoch_en_milisegundos_no_se_va_al_ano_33000(self) -> None:
        ms = parse_timestamp(1788258977000)
        s = parse_timestamp(1788258977)

        assert ms is not None and s is not None
        assert ms.year == s.year

    def test_dedupe_conserva_el_primero(self) -> None:
        eventos = [evento(external_id="a"), evento(external_id="a"), evento(external_id="b")]

        assert len(dedupe(eventos)) == 2

    def test_dedupe_respeta_los_eventos_sin_id(self) -> None:
        """Sin clave natural no se puede afirmar que sean el mismo evento."""
        assert len(dedupe([evento(external_id=None), evento(external_id=None)])) == 2

    def test_truncate_normaliza_espacios(self) -> None:
        assert truncate("  hola   mundo \n ", 100) == "hola mundo"

    def test_clamp(self) -> None:
        assert clamp(1.5) == 1.0
        assert clamp(-1) == 0.0
        assert clamp(0.3) == 0.3


# ---------------------------------------------------------------------
# Parsers, contra respuestas reales recortadas
# ---------------------------------------------------------------------


class TestParsers:
    def test_usgs(self) -> None:
        payload = {
            "features": [
                {
                    "id": "us7000abcd",
                    "properties": {
                        "mag": 6.4,
                        "place": "120 km SE of Tokyo",
                        "title": "M 6.4 - 120 km SE of Tokyo",
                        "time": 1788258977000,
                        "url": "https://earthquake.usgs.gov/x",
                        "tsunami": 1,
                    },
                    "geometry": {"coordinates": [140.9, 35.1, 30.0]},
                },
                # Por debajo del umbral: ruido sísmico de fondo.
                {"id": "small", "properties": {"mag": 2.1}, "geometry": {"coordinates": [0, 0, 5]}},
            ]
        }

        eventos = USGSEarthquakes().parse(payload)

        assert len(eventos) == 1
        e = eventos[0]
        assert e.magnitude == 6.4
        assert (e.latitude, e.longitude) == (35.1, 140.9)
        # Tsunami y foco somero elevan la relevancia por encima de la base.
        assert e.salience > 0.6

    def test_usgs_geometria_incompleta(self) -> None:
        payload = {"features": [{"id": "x", "properties": {"mag": 5.0}, "geometry": {}}]}

        eventos = USGSEarthquakes().parse(payload)

        assert eventos[0].latitude is None

    def test_eonet_usa_la_ultima_posicion(self) -> None:
        payload = {
            "events": [
                {
                    "id": "EONET_1",
                    "title": "Volcán X",
                    "link": "https://eonet.gsfc.nasa.gov/x",
                    "categories": [{"id": "volcanoes"}],
                    "geometry": [
                        {"date": "2026-08-01T00:00:00Z", "coordinates": [10.0, 20.0]},
                        {"date": "2026-09-01T00:00:00Z", "coordinates": [11.0, 21.0]},
                    ],
                }
            ]
        }

        e = EONET().parse(payload)[0]

        assert (e.latitude, e.longitude) == (21.0, 11.0)
        assert e.salience == 0.80

    def test_eonet_ignora_poligonos(self) -> None:
        payload = {
            "events": [
                {
                    "id": "E2",
                    "title": "Incendio",
                    "categories": [{"id": "wildfires"}],
                    "geometry": [
                        {"date": "2026-09-01T00:00:00Z", "coordinates": [[[1, 2], [3, 4]]]}
                    ],
                }
            ]
        }

        e = EONET().parse(payload)[0]

        assert e.latitude is None
        assert e.event_time is not None

    def test_nws_escala_por_severidad(self) -> None:
        payload = {
            "features": [
                {
                    "properties": {
                        "id": "urn:oid:1",
                        "event": "Tornado Warning",
                        "headline": "Tornado Warning issued",
                        "severity": "Extreme",
                        "urgency": "Immediate",
                        "sent": "2026-09-01T07:00:00Z",
                    }
                }
            ]
        }

        e = NWSAlerts().parse(payload)[0]

        assert e.salience == 1.0

    def test_nhc(self) -> None:
        payload = {
            "activeStorms": [
                {
                    "id": "al052026",
                    "name": "Erin",
                    "classification": "MH",
                    "intensity": "115",
                    "latitudeNumeric": 25.3,
                    "longitudeNumeric": -70.1,
                    "lastUpdate": "2026-09-01T06:00:00Z",
                }
            ]
        }

        e = NHCStorms().parse(payload)[0]

        assert e.magnitude == 115.0
        assert e.salience >= 0.95
        assert "Erin" in e.title

    def test_nhc_intensidad_no_numerica(self) -> None:
        payload = {"activeStorms": [{"id": "x", "name": "Y", "intensity": "n/a"}]}

        assert NHCStorms().parse(payload)[0].magnitude is None

    def test_swpc_salta_la_cabecera_del_boletin(self) -> None:
        payload = [
            {
                "product_id": "EF3A",
                "issue_datetime": "2026-09-01 07:37:17.493",
                "message": (
                    "Space Weather Message Code: ALTEF3\r\n"
                    "Serial Number: 3732\r\n"
                    "Issue Time: 2026 Sep 01 0737 UTC\r\n\r\n"
                    "ALERT: Geomagnetic G4 conditions observed"
                ),
            }
        ]

        e = SWPCAlerts().parse(payload)[0]

        assert e.title == "ALERT: Geomagnetic G4 conditions observed"
        # G4 sobre 5 → 0.4 + 3*0.15
        assert e.salience == pytest.approx(0.85)

    def test_swpc_mensaje_solo_cabecera_se_descarta(self) -> None:
        payload = [{"product_id": "X", "message": "Serial Number: 1\r\n"}]

        assert SWPCAlerts().parse(payload) == []

    def test_gdelt_pondera_por_lexico(self) -> None:
        payload = {
            "articles": [
                {
                    "url": "https://x.test/1",
                    "title": "Airstrike causes casualties near border",
                    "seendate": "20260901T050000Z",
                    "domain": "x.test",
                    "sourcecountry": "Testland",
                },
                {
                    "url": "https://x.test/2",
                    "title": "Ceasefire agreement holds after peace talks",
                    "seendate": "20260901T050000Z",
                    "domain": "x.test",
                    "sourcecountry": "Testland",
                },
            ]
        }

        escalada, distension = GDELT().parse(payload)

        assert escalada.salience > distension.salience
        assert escalada.event_time is not None

    def test_gdelt_descarta_titulares_vacios(self) -> None:
        assert GDELT().parse({"articles": [{"url": "u", "title": "  "}]}) == []

    def test_forex_solo_divisas_vigiladas(self) -> None:
        payload = {
            "base": "USD",
            "date": "2026-08-31",
            "rates": {"EUR": 0.92, "JPY": 147.1, "XYZ": 1.0},
        }

        eventos = ForexRates().parse(payload)

        assert {e.raw["quote"] for e in eventos} == {"EUR", "JPY"}
        # Un tipo de cambio es contexto, no un suceso: no debe desplazar eventos.
        assert all(e.salience < 0.5 for e in eventos)

    def test_crypto_relevancia_por_volatilidad(self) -> None:
        payload = {
            "bitcoin": {"usd": 78130.0, "usd_24h_change": -0.44},
            "solana": {"usd": 130.0, "usd_24h_change": -22.0},
        }

        estable, desplome = CryptoPrices().parse(payload)

        assert desplome.salience > estable.salience
        assert "-22.00%" in desplome.title

    def test_crypto_sin_precio_se_omite(self) -> None:
        assert CryptoPrices().parse({"x": {"usd_24h_change": 1.0}}) == []

    def test_cisa_kev(self) -> None:
        from engine.feeds.sources.cisa_kev import CISAKEVulnerabilities

        payload = {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2024-1234",
                    "vulnDescription": "Remote code execution in XYZ",
                    "dateAdded": "2026-09-01T00:00:00Z",
                },
                {
                    "cveID": "CVE-2024-5678",
                    "vulnDescription": "Buffer overflow in ABC",
                    "dateAdded": "2026-08-31T00:00:00Z",
                },
            ]
        }

        eventos = CISAKEVulnerabilities().parse(payload)

        assert len(eventos) == 2
        assert all(e.event_type == "kev_exploit" for e in eventos)
        assert all(e.salience == 0.9 for e in eventos)
        assert eventos[0].external_id == "CVE-2024-1234"

    def test_cisa_kev_sin_cve_id_se_omite(self) -> None:
        from engine.feeds.sources.cisa_kev import CISAKEVulnerabilities

        payload = {
            "vulnerabilities": [
                {"vulnDescription": "Sin CVE"},
                {"cveID": "CVE-2024-1234", "vulnDescription": "Válido"},
            ]
        }

        eventos = CISAKEVulnerabilities().parse(payload)

        assert len(eventos) == 1
        assert eventos[0].external_id == "CVE-2024-1234"

    def test_reliefweb(self) -> None:
        from engine.feeds.sources.reliefweb import ReliefWebSituations

        payload = {
            "data": [
                {
                    "id": "rw1",
                    "fields": {
                        "title": "Flooding in Kenya",
                        "body": "Heavy rains causing displacement",
                        "primary_country": [{"name": "Kenya"}],
                        "disaster": [{"name": "Floods"}],
                        "date": {"original": "2026-09-01T00:00:00Z"},
                    },
                },
                {
                    "id": "rw2",
                    "fields": {
                        "title": "Conflict",
                        "primary_country": [{"name": "A"}, {"name": "B"}],
                        "disaster": [{"name": "X"}, {"name": "Y"}, {"name": "Z"}],
                        "date": {"original": "2026-09-01T00:00:00Z"},
                    },
                },
            ]
        }

        eventos = ReliefWebSituations().parse(payload)

        assert len(eventos) == 2
        assert eventos[0].salience > 0.4
        assert eventos[1].salience > eventos[0].salience  # Más desastres/países

    def test_reliefweb_sin_titulo_se_omite(self) -> None:
        from engine.feeds.sources.reliefweb import ReliefWebSituations

        payload = {"data": [{"id": "rw1", "fields": {"title": "", "primary_country": []}}]}

        assert ReliefWebSituations().parse(payload) == []

    def test_open_meteo(self) -> None:
        from engine.feeds.sources.open_meteo import OpenMeteoWeather

        # Open-Meteo devuelve arrays horarios; aquí simulamos 6 horas de datos
        payload = {
            "hourly": [
                {
                    "temperature_2m": [20.0, 21.0, 22.0, 25.0, 28.0, 32.0],
                    "precipitation": [0.0, 0.0, 1.0, 2.0, 3.0, 15.0],
                }
            ]
        }

        eventos = OpenMeteoWeather().parse(payload)

        assert len(eventos) == 1
        assert eventos[0].source == "Open-Meteo"
        # Lluvia intensa y temperatura elevada
        assert eventos[0].salience > 0.65


# ---------------------------------------------------------------------
# Ingestor
# ---------------------------------------------------------------------


class TestIngestor:
    async def test_una_fuente_rota_no_contamina_el_resultado(self) -> None:
        """Regresión: `if r is not None` dejaba pasar el objeto excepción."""
        buena = make_stub("Buena", events=[evento(source="Buena")])
        mala = StubSource(error=FeedError("la fuente se cayó"))

        report = await FeedIngestor([buena, mala], concurrency=2).ingest_all()

        assert report.succeeded == ["Buena"]
        assert "Stub" in report.failed
        assert len(report.events) == 1
        assert all(isinstance(e, NormalizedEvent) for e in report.events)

    async def test_sin_fuentes_no_falla(self) -> None:
        report = await FeedIngestor([]).ingest_all()

        assert report.events == []
        assert report.attempted == 0

    async def test_respeta_el_limite_de_concurrencia(self) -> None:
        import asyncio

        activos = 0
        pico = 0

        class Lenta(StubSource):
            async def fetch(self, session: Any) -> list[NormalizedEvent]:
                nonlocal activos, pico
                activos += 1
                pico = max(pico, activos)
                await asyncio.sleep(0.02)
                activos -= 1
                return []

        await FeedIngestor([Lenta() for _ in range(8)], concurrency=2).ingest_all()

        assert pico <= 2

    async def test_el_timeout_se_convierte_en_fallo_de_la_fuente(self) -> None:
        import asyncio

        class Colgada(StubSource):
            async def fetch(self, session: Any) -> list[NormalizedEvent]:
                await asyncio.sleep(5)
                return []

        report = await FeedIngestor([Colgada()], timeout=1).ingest_all()

        assert "Stub" in report.failed
        assert "sin respuesta" in report.failed["Stub"]

    async def test_deduplica_entre_fuentes(self) -> None:
        a = make_stub("A", events=[evento(source="A", external_id="1")])
        b = make_stub("B", events=[evento(source="A", external_id="1")])

        report = await FeedIngestor([a, b]).ingest_all()

        assert len(report.events) == 1

    async def test_la_cache_evita_repetir_la_descarga(self) -> None:
        cache = TTLCache(ttl_seconds=600)
        fuente = make_stub("Cacheada", events=[evento(source="Cacheada")])
        ingestor = FeedIngestor([fuente], cache=cache)

        primera = await ingestor.ingest_all()
        segunda = await ingestor.ingest_all()

        assert primera.succeeded == ["Cacheada"]
        assert segunda.from_cache == ["Cacheada"]

    async def test_persiste_y_deduplica_contra_la_base_de_datos(self, db: None) -> None:
        fuente = make_stub("P", events=[evento(source="P", external_id="1")])
        ingestor = FeedIngestor([fuente], cache=TTLCache(0))

        primera = await ingestor.run_once()
        segunda = await ingestor.run_once()

        assert primera.persisted == 1
        assert segunda.persisted == 0, "reingerir lo mismo no debe duplicar filas"
        with session_scope() as session:
            assert len(session.scalars(select(FeedEvent)).all()) == 1

    async def test_los_eventos_sin_id_siempre_se_insertan(self, db: None) -> None:
        fuente = make_stub("S", events=[evento(source="S", external_id=None)])
        ingestor = FeedIngestor([fuente], cache=TTLCache(0))

        await ingestor.run_once()
        await ingestor.run_once()

        with session_scope() as session:
            assert len(session.scalars(select(FeedEvent)).all()) == 2

    def test_persist_sin_eventos(self, db: None) -> None:
        assert FeedIngestor([]).persist([]) == 0


# ---------------------------------------------------------------------
# Caché y retención
# ---------------------------------------------------------------------


class TestCache:
    def test_devuelve_lo_guardado(self) -> None:
        cache = TTLCache(600)
        cache.set("k", [1, 2])

        assert cache.get("k") == [1, 2]
        assert "k" in cache

    def test_caduca(self) -> None:
        reloj = [0.0]
        cache = TTLCache(10, clock=lambda: reloj[0])
        cache.set("k", "v")

        reloj[0] = 11.0

        assert cache.get("k") is None
        assert len(cache) == 0

    def test_clave_ausente(self) -> None:
        assert TTLCache(10).get("nada") is None

    def test_invalidar_e_vaciar(self) -> None:
        cache = TTLCache(600)
        cache.set("a", 1)
        cache.set("b", 2)

        cache.invalidate("a")
        assert len(cache) == 1
        cache.clear()
        assert len(cache) == 0

    def test_ttl_negativo(self) -> None:
        with pytest.raises(ValueError, match="negativo"):
            TTLCache(-1)

    def test_retencion_ilimitada_no_borra(self, db: None) -> None:
        assert prune_old_events(0) == 0
        assert prune_old_events(-5) == 0

    def test_purga_lo_antiguo_y_conserva_lo_reciente(self, db: None) -> None:
        from datetime import timedelta

        from engine.models import utcnow

        with session_scope() as session:
            session.add(
                FeedEvent(source="viejo", title="v", ingestion_time=utcnow() - timedelta(days=90))
            )
            session.add(FeedEvent(source="nuevo", title="n", ingestion_time=utcnow()))

        borrados = prune_old_events(30)

        assert borrados == 1
        assert event_counts() == {"nuevo": 1}


class TestRecentEvents:
    def test_ordena_por_relevancia_y_filtra(self, db: None) -> None:
        with session_scope() as session:
            session.add(FeedEvent(source="A", title="poco", salience=0.2))
            session.add(FeedEvent(source="B", title="mucho", salience=0.9))
            session.add(FeedEvent(source="C", title="medio", salience=0.6))

        todos = recent_events(limit=10)
        relevantes = recent_events(limit=10, min_salience=0.5)

        assert [e["title"] for e in todos] == ["mucho", "medio", "poco"]
        assert len(relevantes) == 2

    def test_respeta_el_limite(self, db: None) -> None:
        with session_scope() as session:
            for i in range(10):
                session.add(FeedEvent(source="A", title=f"e{i}", salience=0.5))

        assert len(recent_events(limit=3)) == 3

    def test_colapsa_titulos_repetidos(self, db: None) -> None:
        """NWS emite el mismo aviso por zona: en el prompt sobra con uno."""
        with session_scope() as session:
            for zona in range(3):
                session.add(
                    FeedEvent(
                        source="NWS",
                        title="Storm Surge Warning issued by NWS Lake Charles",
                        external_id=f"zona-{zona}",
                        salience=0.9,
                    )
                )
            session.add(FeedEvent(source="USGS", title="M 6.1 Tokyo", salience=0.8))

        eventos = recent_events(limit=10)

        assert len(eventos) == 2
        assert {e["source"] for e in eventos} == {"NWS", "USGS"}

    def test_el_colapso_ignora_mayusculas_y_espacios(self, db: None) -> None:
        with session_scope() as session:
            session.add(FeedEvent(source="A", title="Alerta Roja", salience=0.9))
            session.add(FeedEvent(source="B", title="  alerta roja  ", salience=0.8))

        assert len(recent_events(limit=10)) == 1

    def test_una_fuente_ruidosa_no_acapara_el_contexto(self, db: None) -> None:
        """NWS publica un aviso por zona; sin reparto copaba los 10 huecos."""
        with session_scope() as session:
            for i in range(30):
                session.add(FeedEvent(source="NWS", title=f"aviso {i}", salience=0.9))
            session.add(FeedEvent(source="USGS", title="M 6.1 Tokyo", salience=0.5))
            session.add(FeedEvent(source="GDELT", title="Sanciones", salience=0.4))

        eventos = recent_events(limit=8, per_source_quota=3)

        fuentes = [e["source"] for e in eventos]
        # Sin reparto, las 8 plazas serían de NWS y las otras dos fuentes,
        # menos relevantes pero de otro dominio, no llegarían al prompt.
        assert "USGS" in fuentes
        assert "GDELT" in fuentes

    def test_rellena_los_huecos_si_faltan_fuentes(self, db: None) -> None:
        """Con una sola fuente, el cupo no puede dejar el contexto medio vacío."""
        with session_scope() as session:
            for i in range(10):
                session.add(FeedEvent(source="NWS", title=f"aviso {i}", salience=0.9))

        assert len(recent_events(limit=8, per_source_quota=2)) == 8

    def test_una_fuente_de_saliencia_baja_llega_a_competir(self, db: None) -> None:
        """El reparto tiene que empezar en la consulta, no solo en memoria.

        Pidiendo las N filas más relevantes, las 100 alertas de NWS llenaban la
        ventana de candidatos y Crypto no entraba ni a ser descartada.
        """
        with session_scope() as session:
            for i in range(100):
                session.add(FeedEvent(source="NWS", title=f"aviso {i}", salience=0.9))
            session.add(FeedEvent(source="Crypto", title="SOL -22% 24h", salience=0.3))

        fuentes = {e["source"] for e in recent_events(limit=10)}

        assert "Crypto" in fuentes

    def test_el_resultado_sigue_ordenado_por_relevancia(self, db: None) -> None:
        with session_scope() as session:
            session.add(FeedEvent(source="A", title="baja", salience=0.2))
            session.add(FeedEvent(source="B", title="alta", salience=0.9))
            session.add(FeedEvent(source="C", title="media", salience=0.5))

        saliencias = [e["salience"] for e in recent_events(limit=10)]

        assert saliencias == sorted(saliencias, reverse=True)
