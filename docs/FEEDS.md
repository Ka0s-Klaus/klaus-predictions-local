<!-- Generado por scripts/gen_feeds_doc.py. No editar a mano. -->

# Catálogo de fuentes

**51 fuentes declaradas** · 8 implementadas · 43 pendientes · 8 requieren clave de API.

La fuente de verdad es [`engine/feeds/catalog.yaml`](../engine/feeds/catalog.yaml). Este fichero se genera a partir de él.

## Implementadas

Cada una tiene una clase en `engine/feeds/sources/` y su endpoint se ha
comprobado contra el servicio real.

| Fuente | Dominio | Qué aporta |
| ------ | ------- | ---------- |
| [USGS](https://earthquake.usgs.gov/earthquakes/feed/) | `disasters` | Sismos de magnitud 4.5+ en las últimas 24 horas. |
| [EONET](https://eonet.gsfc.nasa.gov/) | `disasters` | Agregador de la NASA de eventos naturales abiertos. |
| [NWS](https://www.weather.gov/documentation/services-web-api) | `weather` | Avisos meteorológicos activos de severidad extrema o alta. |
| [NHC](https://www.nhc.noaa.gov/) | `weather` | Ciclones tropicales activos en Atlántico y Pacífico oriental. |
| [SWPC](https://www.swpc.noaa.gov/) | `space-weather` | Alertas de clima espacial: tormentas geomagnéticas y radiación. |
| [Forex](https://frankfurter.dev/) | `markets` | Tipos de cambio de referencia del Banco Central Europeo. |
| [Crypto](https://www.coingecko.com/en/api) | `markets` | Precios y variación a 24 h de las principales criptomonedas. |
| [GDELT](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) | `geopolitical` | Cobertura mediática global de conflicto, sanciones y crisis. |

## Pendientes

Fuentes identificadas y sin implementar. **No llevan endpoint**: la ruta de
cada API vive en la clase que la consume, así que apuntarla aquí sólo
crearía un segundo sitio que mantener. Lo que sí llevan es el enlace al
servicio y, cuando lo hay, el obstáculo concreto que queda por resolver.

| Fuente | Dominio | Clave | Notas |
| ------ | ------- | ----- | ----- |
| [GDACS](https://www.gdacs.org/) | `disasters` | — | Sirve RSS/XML de ~1 MB. Requiere un parser XML resistente a XML bombs. |
| [FIRMS](https://firms.modaps.eosdis.nasa.gov/) | `disasters` | sí | Exige MAP_KEY. Sin ella la API responde 400 "Invalid MAP_KEY". |
| [GVP](https://volcano.si.edu/) | `disasters` | — | Informe semanal de actividad volcánica. |
| [USGS-Volcano](https://volcanoes.usgs.gov/) | `disasters` | — | Niveles de alerta de los volcanes de Estados Unidos. |
| [PTWC](https://www.tsunami.gov/) | `disasters` | — | Avisos de tsunami del Pacífico. |
| [USGS-Water](https://waterservices.usgs.gov/) | `disasters` | — | Caudales y niveles de inundación. |
| [Copernicus-EMS](https://emergency.copernicus.eu/) | `disasters` | — | Activaciones del servicio europeo de gestión de emergencias. |
| [GloFAS](https://global-flood.emergency.copernicus.eu/) | `disasters` | — | Sistema global de alerta temprana de inundaciones. |
| [Open-Meteo](https://open-meteo.com/) | `weather` | — | Endpoint verificado y sin clave. Es la siguiente más fácil de añadir. |
| [ENSO](https://www.cpc.ncep.noaa.gov/products/precip/CWlink/MJO/enso.shtml) | `climate` | — | Índice oceánico de El Niño / La Niña. |
| [NSIDC](https://nsidc.org/arcticseaicenews/) | `climate` | — | Extensión del hielo marino ártico y antártico. |
| [CAMS](https://atmosphere.copernicus.eu/) | `climate` | — | Calidad del aire y transporte de aerosoles. |
| [DroughtMonitor](https://droughtmonitor.unl.edu/) | `climate` | — | Severidad y extensión de la sequía. |
| [GHCN](https://www.ncei.noaa.gov/products/land-based-station/) | `climate` | — | Anomalías de temperatura de estaciones terrestres. |
| [CAISO](https://www.caiso.com/todays-outlook) | `energy` | — | El endpoint que aparece en la documentación de partida (caiso.com/outlook/SP/fuelsource.csv) devuelve 404. Hay que localizar la ruta pública vigente antes de implementarla. |
| [EIA](https://www.eia.gov/opendata/) | `energy` | sí | Datos horarios de la red eléctrica de Estados Unidos. |
| [ENTSO-E](https://transparency.entsoe.eu/) | `energy` | sí | Transparencia del sistema eléctrico europeo. |
| [Elexon](https://bmrs.elexon.co.uk/) | `energy` | — | Datos del mercado eléctrico británico. |
| [ERCOT](https://www.ercot.com/gridmktinfo) | `energy` | — | Condiciones de la red de Texas. |
| [Oil](https://www.eia.gov/petroleum/) | `commodities` | — | Precios de referencia del crudo Brent y WTI. |
| [Equities](https://stooq.com/) | `markets` | — | Stooq sirve CSV sin clave; falta decidir la cesta de índices. |
| [Treasury](https://home.treasury.gov/interest-rates-data-csv-archive) | `markets` | — | Curva de tipos del Tesoro estadounidense. |
| [WorldBank](https://datahelpdesk.worldbank.org/knowledgebase/topics/125589) | `macro` | — | Indicadores macroeconómicos por país. |
| [Polymarket](https://docs.polymarket.com/) | `markets` | — | Interesante como contraste: da una probabilidad de mercado con la que comparar la del enjambre. |
| [FRED](https://fred.stlouisfed.org/docs/api/fred/) | `macro` | sí | Series macroeconómicas de la Reserva Federal de San Luis. |
| [EDGAR](https://www.sec.gov/edgar/sec-api-documentation) | `markets` | — | Operaciones de iniciados registradas en la SEC. |
| [OFAC](https://sanctionslist.ofac.treas.gov/Home/SdnList) | `sanctions` | — | Lista de personas y entidades sancionadas por Estados Unidos. |
| [EU-Sanctions](https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions) | `sanctions` | — | Lista consolidada de sanciones financieras de la Unión Europea. |
| [UN-Sanctions](https://scsanctions.un.org/) | `sanctions` | — | Lista consolidada del Consejo de Seguridad de Naciones Unidas. |
| [ACLED](https://acleddata.com/data-export-tool/) | `conflict` | sí | Eventos de conflicto armado y protestas, georreferenciados. |
| [UCDP](https://ucdp.uu.se/apidocs/) | `conflict` | — | Base de datos de conflictos de la Universidad de Uppsala. |
| [CISA-KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) | `cyber` | — | JSON sin clave y de formato estable. Candidata clara para la siguiente tanda. |
| [NVD](https://nvd.nist.gov/developers/vulnerabilities) | `cyber` | — | Vulnerabilidades publicadas con su puntuación CVSS. |
| [IODA](https://ioda.inetintel.cc.gatech.edu/) | `infrastructure` | — | Detección de cortes de conectividad a internet por país. |
| [Cloudflare-Radar](https://developers.cloudflare.com/radar/) | `infrastructure` | sí | Tráfico de internet, ataques y anomalías de enrutamiento. |
| [HackerNews](https://hn.algolia.com/api) | `technology` | — | Señal temprana de incidentes técnicos y tecnología emergente. |
| [WHO](https://www.who.int/emergencies/disease-outbreak-news) | `health` | — | Noticias oficiales sobre brotes de enfermedades. |
| [UNHCR](https://api.unhcr.org/docs/) | `humanitarian` | — | Cifras de desplazamiento forzoso y refugiados. |
| [ReliefWeb](https://apidoc.reliefweb.int/) | `humanitarian` | — | API sin clave, bien documentada. Otra candidata fácil. |
| [CDC-Wastewater](https://data.cdc.gov/) | `health` | — | Vigilancia de patógenos en aguas residuales. |
| [Maritime](https://www.marinetraffic.com/en/ais-api-services) | `logistics` | sí | Tráfico marítimo y congestión de puertos y estrechos. |
| [Flights](https://openskynetwork.github.io/opensky-api/) | `logistics` | — | Tráfico aéreo, cierres de espacio aéreo y desvíos. |
| [NOTAM](https://api.faa.gov/) | `logistics` | sí | Avisos a la navegación aérea y restricciones de espacio aéreo. |

## Por dominio

| Dominio | Fuentes |
| ------- | ------- |
| `climate` | 5 |
| `commodities` | 1 |
| `conflict` | 2 |
| `cyber` | 2 |
| `disasters` | 10 |
| `energy` | 5 |
| `geopolitical` | 1 |
| `health` | 2 |
| `humanitarian` | 2 |
| `infrastructure` | 2 |
| `logistics` | 3 |
| `macro` | 2 |
| `markets` | 6 |
| `sanctions` | 3 |
| `space-weather` | 1 |
| `technology` | 1 |
| `weather` | 3 |

## Añadir una fuente

1. Crea la clase en `engine/feeds/sources/`, heredando de `FeedSource`.
   Sólo hay que definir `name`, `domain`, `event_type`, `endpoint` y
   `parse()`; la concurrencia, los tiempos de espera y la deduplicación
   los pone el ingestor.
2. Regístrala en `IMPLEMENTATIONS`, en `engine/feeds/sources/__init__.py`.
3. Cambia su `status` a `implemented` en `catalog.yaml`.
4. Añade un test del parser en `tests/test_feeds.py` con una respuesta
   real recortada del servicio.
5. Regenera este fichero: `python scripts/gen_feeds_doc.py`.

El registro valida el cruce al arrancar: declarar una fuente como
implementada sin clase detrás —o al revés— es un error inmediato, no un
fallo silencioso a mitad de la ingesta.

## Sobre la relevancia

Cada fuente calcula su propia `salience` entre 0 y 1, y es lo que decide
qué llega al contexto del enjambre. Los criterios son específicos de cada
una: magnitud y profundidad en un sismo, escala NOAA en una alerta de
clima espacial, léxico de escalada en un titular. Los tipos de cambio
puntúan bajo a propósito — son contexto, no sucesos, y no deben desplazar
a un terremoto.

## Términos de uso

Todas son APIs públicas de terceros con sus propios límites de peticiones
y condiciones. Consúltalas antes de desplegar nada en producción. GDELT en
particular limita con dureza y falla con cierta frecuencia; el ingestor
está diseñado para tolerarlo.
