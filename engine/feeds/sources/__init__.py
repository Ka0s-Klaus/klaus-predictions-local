"""Fuentes implementadas.

`IMPLEMENTATIONS` es la tabla que consulta el registro para saber qué entradas
de `catalog.yaml` tienen código detrás.
"""

from engine.feeds.sources.base import FeedError, FeedSource
from engine.feeds.sources.ai_regulation_tracker import AIRegulationTracker
from engine.feeds.sources.ai_security_vulnerabilities import AISafetyVulnerabilities
from engine.feeds.sources.anthropic_research import AnthropicResearch
from engine.feeds.sources.arxiv_ml import ArxivML
from engine.feeds.sources.cdc_wastewater import CDCWastewater
from engine.feeds.sources.cisa_kev import CISAKEVulnerabilities
from engine.feeds.sources.copernicus_ems import CopernicusEMS
from engine.feeds.sources.crypto import CryptoPrices
from engine.feeds.sources.drought_monitor import DroughtMonitor
from engine.feeds.sources.edgar_insider import EDGARInsider
from engine.feeds.sources.elexon_bmrs import ElexonBMRS
from engine.feeds.sources.eonet import EONET
from engine.feeds.sources.ercot_grid import ERCOTGrid
from engine.feeds.sources.equity_indices import EquityIndices
from engine.feeds.sources.enso_index import ENSOIndex
from engine.feeds.sources.eu_sanctions import EUSanctions
from engine.feeds.sources.flight_tracking import OpenSkyFlights
from engine.feeds.sources.forex import ForexRates
from engine.feeds.sources.gdacs import GDACSDisasters
from engine.feeds.sources.gdelt import GDELT
from engine.feeds.sources.glofas_floods import GloFASFloods
from engine.feeds.sources.hacker_news import HackerNews
from engine.feeds.sources.huggingface_models import HuggingFaceModels
from engine.feeds.sources.ioda_outages import IODAOutages
from engine.feeds.sources.llm_leaderboards import LLMLeaderboards
from engine.feeds.sources.llm_safety_alignment import LLMSafetyAlignment
from engine.feeds.sources.model_releases import ModelReleases
from engine.feeds.sources.nhc import NHCStorms
from engine.feeds.sources.nsidc_sea_ice import NSIDCSeaIce
from engine.feeds.sources.nws import NWSAlerts
from engine.feeds.sources.nvd_cve import NVDVulnerabilities
from engine.feeds.sources.ofac_sanctions import OFACSanctions
from engine.feeds.sources.oil_prices import OilPrices
from engine.feeds.sources.open_meteo import OpenMeteoWeather
from engine.feeds.sources.openai_announcements import OpenAIAnnouncements
from engine.feeds.sources.papers_with_code import PapersWithCode
from engine.feeds.sources.polymarket import Polymarket
from engine.feeds.sources.ptwc_tsunami import PTWCTsunami
from engine.feeds.sources.reliefweb import ReliefWebSituations
from engine.feeds.sources.smithsonian_volcano import SmithsonianVolcano
from engine.feeds.sources.swpc import SWPCAlerts
from engine.feeds.sources.treasury_yields import TreasuryYields
from engine.feeds.sources.ucdp_conflicts import UCDPConflicts
from engine.feeds.sources.un_sanctions import UNSanctions
from engine.feeds.sources.unhcr_displacement import UNHCRDisplacement
from engine.feeds.sources.usgs import USGSEarthquakes
from engine.feeds.sources.usgs_volcano import USGSVolcano
from engine.feeds.sources.usgs_water import USGSWater
from engine.feeds.sources.who_outbreaks import WHOOutbreaks
from engine.feeds.sources.worldbank_indicators import WorldBankIndicators

IMPLEMENTATIONS: dict[str, type[FeedSource]] = {
    # Desastres naturales
    "usgs_earthquakes": USGSEarthquakes,
    "eonet": EONET,
    "gdacs": GDACSDisasters,
    "smithsonian_volcano": SmithsonianVolcano,
    "usgs_volcano": USGSVolcano,
    "ptwc_tsunami": PTWCTsunami,
    "usgs_water": USGSWater,
    "copernicus_ems": CopernicusEMS,
    "glofas_floods": GloFASFloods,
    # Meteorología y clima
    "nws_alerts": NWSAlerts,
    "nhc_storms": NHCStorms,
    "noaa_swpc": SWPCAlerts,
    "open_meteo": OpenMeteoWeather,
    "enso_index": ENSOIndex,
    "nsidc_sea_ice": NSIDCSeaIce,
    "drought_monitor": DroughtMonitor,
    # Energía y red eléctrica
    "ercot": ERCOTGrid,
    "oil_prices": OilPrices,
    "elexon_bmrs": ElexonBMRS,
    # Mercados financieros
    "forex_ecb": ForexRates,
    "crypto_prices": CryptoPrices,
    "equity_indices": EquityIndices,
    "treasury_yields": TreasuryYields,
    "worldbank_indicators": WorldBankIndicators,
    "polymarket": Polymarket,
    "edgar_insider": EDGARInsider,
    # Geopolítica, conflicto y sanciones
    "gdelt": GDELT,
    "ofac_sanctions": OFACSanctions,
    "eu_sanctions": EUSanctions,
    "un_sanctions": UNSanctions,
    "ucdp": UCDPConflicts,
    # Ciberseguridad e infraestructura digital
    "cisa_kev": CISAKEVulnerabilities,
    "nvd_cve": NVDVulnerabilities,
    "ioda_outages": IODAOutages,
    "hacker_news": HackerNews,
    # Humanitario y salud pública
    "who_outbreaks": WHOOutbreaks,
    "unhcr_displacement": UNHCRDisplacement,
    "reliefweb": ReliefWebSituations,
    "cdc_wastewater": CDCWastewater,
    # Transporte y logística
    "flight_tracking": OpenSkyFlights,
    # Inteligencia Artificial y Machine Learning
    "openai_announcements": OpenAIAnnouncements,
    "huggingface_models": HuggingFaceModels,
    "arxiv_ml": ArxivML,
    "anthropic_research": AnthropicResearch,
    "papers_with_code": PapersWithCode,
    "llm_safety_alignment": LLMSafetyAlignment,
    "ai_regulation_tracker": AIRegulationTracker,
    "llm_leaderboards": LLMLeaderboards,
    "ai_security_vulnerabilities": AISafetyVulnerabilities,
    "model_releases": ModelReleases,
}

__all__ = [
    "AIRegulationTracker",
    "AISafetyVulnerabilities",
    "AnthropicResearch",
    "ArxivML",
    "CDCWastewater",
    "CISAKEVulnerabilities",
    "CopernicusEMS",
    "CryptoPrices",
    "DroughtMonitor",
    "EDGARInsider",
    "ElexonBMRS",
    "EONET",
    "EquityIndices",
    "ENSOIndex",
    "ERCOTGrid",
    "EUSanctions",
    "FeedError",
    "FeedSource",
    "ForexRates",
    "GDELT",
    "GDACSDisasters",
    "GloFASFloods",
    "HackerNews",
    "HuggingFaceModels",
    "IMPLEMENTATIONS",
    "IODAOutages",
    "LLMLeaderboards",
    "LLMSafetyAlignment",
    "ModelReleases",
    "NHCStorms",
    "NSIDCSeaIce",
    "NWSAlerts",
    "NVDVulnerabilities",
    "OFACSanctions",
    "OilPrices",
    "OpenAIAnnouncements",
    "OpenMeteoWeather",
    "OpenSkyFlights",
    "PapersWithCode",
    "Polymarket",
    "PTWCTsunami",
    "ReliefWebSituations",
    "SmithsonianVolcano",
    "SWPCAlerts",
    "TreasuryYields",
    "UCDPConflicts",
    "UNSanctions",
    "UNHCRDisplacement",
    "USGSEarthquakes",
    "USGSVolcano",
    "USGSWater",
    "WHOOutbreaks",
    "WorldBankIndicators",
]
