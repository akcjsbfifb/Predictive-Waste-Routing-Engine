"""Parámetros del dataset de recolección de residuos (microcentro de CABA).

La bounding box, la semilla, los umbrales y los pesos de la etiqueta viven
acá y en ningún otro lado. El generador solo lee este módulo.
"""

from __future__ import annotations

# Semilla de numpy. Toda variable sintética sale de un Generator derivado de esta.
SEED = 42

# (oeste, sur, este, norte) en EPSG:4326.
# Microcentro de la Ciudad Autónoma de Buenos Aires, unas 2 km por lado:
# San Nicolás y el borde de Retiro y Monserrat. La zona 1 de contenedores
# húmedos cubre más barrios; este recorte entra en el tope de aristas.
BBOX: tuple[float, float, float, float] = (-58.393, -34.6105, -58.3705, -34.5925)

# Tope blando. Si el grafo se pasa, achicar BBOX (no recortar aristas al azar).
TARGET_EDGES = (300, 1500)

# Contenedores a más de esta distancia (metros) de cualquier arista se descartan.
MAX_CONTAINER_DISTANCE_M = 50.0

# Contenedores húmedos de la zona 1 (GCBA). CSV con latitud y longitud.
# El portal de Rosario no publicó un archivo accesible; ver README.
CONTAINERS_FILENAME = "caba_humedos_zona_1.csv"
CONTAINERS_CSV_URL = (
    "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/"
    "ministerio-de-espacio-publico-e-higiene-urbana/"
    "infraestructura-gestion-residuos/zona_1_cont_humedos_clean.csv"
)
CONTAINERS_DATASET_URL = (
    "https://data.buenosaires.gob.ar/dataset/infraestructura-gestion-residuos"
)

# User-Agent exigido por la política de uso de la API de OpenStreetMap.
OSM_USER_AGENT = "tp-logica-grafos/0.1 (academic; caba waste collection dataset)"

# Tipos de vía que osmnx excluye con network_type="drive".
DRIVE_EXCLUDED_HIGHWAYS = frozenset(
    {
        "abandoned",
        "bridleway",
        "bus_guideway",
        "construction",
        "corridor",
        "cycleway",
        "elevator",
        "escalator",
        "footway",
        "no",
        "path",
        "pedestrian",
        "planned",
        "platform",
        "proposed",
        "raceway",
        "razed",
        "rest_area",
        "service",
        "services",
        "steps",
        "track",
    }
)
DRIVE_EXCLUDED_SERVICE = frozenset(
    {"alley", "driveway", "emergency_access", "parking", "parking_aisle", "private"}
)

# --- Etiqueta sintética (se usa cuando haya contenedores reales) ---
# Score latente, antes del ruido:
#   score = w_dias * dias
#         + w_cont * log1p(contenedores)
#         + w_quejas * log1p(quejas)
#         + w_zona[tipo_zona]
#         + w_inter * dias * log1p(contenedores)   # interacción no lineal
# El ruido gaussiano se suma después. Los cortes son cuantiles del score ruidoso.
ZONE_TYPES = ("residencial", "comercial", "industrial")

# Poisson de días desde la última recolección, por tipo de zona.
# La media sube un poco si el tramo tiene más contenedores (ver synthesize).
DAYS_POISSON_LAM: dict[str, float] = {
    "residencial": 3.2,
    "comercial": 2.0,
    "industrial": 4.5,
}
DAYS_CONTAINER_BUMP = 0.15  # se suma a lambda por cada contenedor, con tope
DAYS_MAX = 10

# Quejas ~ Poisson(lambda).
# lambda = exp(a + b*log1p(cont) + c*dias + d_zona)
COMPLAINTS_INTERCEPT = -0.4
COMPLAINTS_COEF_CONTAINERS = 0.35
COMPLAINTS_COEF_DAYS = 0.12
COMPLAINTS_ZONE: dict[str, float] = {
    "residencial": 0.0,
    "comercial": 0.55,
    "industrial": 0.15,
}

PRIORITY_WEIGHTS = {
    "dias": 0.55,
    "contenedores": 0.70,
    "quejas": 0.45,
    "interaccion_dias_contenedores": 0.18,
    "zona": {"residencial": 0.0, "comercial": 0.40, "industrial": 0.20},
}
# Desvío del ruido gaussiano, en las mismas unidades del score.
# Tiene que ser grande para que la etiqueta no sea una regla determinística.
PRIORITY_NOISE_SIGMA = 0.40

# Proporciones objetivo, de mayor a menor prioridad. Suman 1.
# Los cortes son cuantiles: alta = cola superior, baja = cola inferior.
PRIORITY_SHARES = {"alta": 0.20, "media": 0.35, "baja": 0.45}

# Sanity check (no es el modelo del TP).
VALIDATION_TEST_SIZE = 0.20
VALIDATION_RF_TREES = 200
VALIDATION_ACCURACY_WARN_HIGH = 0.95
VALIDATION_ACCURACY_WARN_LOW = 0.60
ZONE_MIN_SHARE_WARN = 0.05

# Buffer alrededor del tramo para mirar tags OSM (metros, UTM 20S).
ZONE_BUFFER_M = 40.0
# UTM 21S. Cubre el microcentro de CABA.
ZONE_UTM_EPSG = "EPSG:32721"

# Un local suelto no alcanza: el centro tiene comercios en casi todas las cuadras.
# 6 puntos ≈ seis locales, o menos si hay landuse commercial/retail en el buffer.
ZONE_COMMERCIAL_MIN_SCORE = 6.0
ZONE_INDUSTRIAL_MIN_SCORE = 2.0

COMMERCIAL_AMENITIES = frozenset(
    {
        "restaurant",
        "cafe",
        "pharmacy",
        "fast_food",
        "bank",
        "bar",
        "marketplace",
        "ice_cream",
        "pub",
        "biergarten",
        "food_court",
    }
)
COMMERCIAL_BUILDINGS = frozenset({"commercial", "retail", "supermarket"})
INDUSTRIAL_BUILDINGS = frozenset({"industrial", "warehouse"})
RESIDENTIAL_BUILDINGS = frozenset(
    {"residential", "apartments", "house", "detached", "semidetached_house", "terrace"}
)
