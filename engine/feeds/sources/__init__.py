"""Fuentes implementadas.

`IMPLEMENTATIONS` es la tabla que consulta el registro para saber qué entradas
de `catalog.yaml` tienen código detrás.
"""

from engine.feeds.sources.base import FeedError, FeedSource
from engine.feeds.sources.crypto import CryptoPrices
from engine.feeds.sources.eonet import EONET
from engine.feeds.sources.forex import ForexRates
from engine.feeds.sources.gdelt import GDELT
from engine.feeds.sources.nhc import NHCStorms
from engine.feeds.sources.nws import NWSAlerts
from engine.feeds.sources.swpc import SWPCAlerts
from engine.feeds.sources.usgs import USGSEarthquakes

IMPLEMENTATIONS: dict[str, type[FeedSource]] = {
    "usgs_earthquakes": USGSEarthquakes,
    "eonet": EONET,
    "nws_alerts": NWSAlerts,
    "nhc_storms": NHCStorms,
    "noaa_swpc": SWPCAlerts,
    "gdelt": GDELT,
    "forex_ecb": ForexRates,
    "crypto_prices": CryptoPrices,
}

__all__ = [
    "EONET",
    "GDELT",
    "IMPLEMENTATIONS",
    "CryptoPrices",
    "FeedError",
    "FeedSource",
    "ForexRates",
    "NHCStorms",
    "NWSAlerts",
    "SWPCAlerts",
    "USGSEarthquakes",
]
