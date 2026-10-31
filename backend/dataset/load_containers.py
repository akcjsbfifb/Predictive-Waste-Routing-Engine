"""Contenedores del GCBA y join a la arista más cercana."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
import requests
from shapely import wkt
from shapely.geometry import Point, shape

from backend import config

_LAT_COLUMNS = ("lat", "latitude", "latitud", "y")
_LON_COLUMNS = ("lon", "lng", "longitude", "longitud", "x")


def containers_file() -> Path:
    """Devuelve el CSV de contenedores, descargándolo si todavía no está."""
    raw = Path("data/raw")
    raw.mkdir(parents=True, exist_ok=True)
    path = raw / config.CONTAINERS_FILENAME
    if path.is_file() and path.stat().st_size > 0:
        return path
    print(f"descargando {config.CONTAINERS_CSV_URL}")
    response = requests.get(
        config.CONTAINERS_CSV_URL,
        headers={"User-Agent": config.OSM_USER_AGENT},
        timeout=120,
    )
    response.raise_for_status()
    path.write_bytes(response.content)
    if path.stat().st_size == 0:
        raise SystemExit(f"La descarga quedó vacía: {config.CONTAINERS_CSV_URL}")
    return path


def count_containers_per_edge(graph: nx.Graph, path: Path | None = None) -> pd.Series:
    """Cuenta contenedores asignados a cada arista, dentro del umbral en metros.

    El índice es `(min(u, v), max(u, v))`. Las aristas sin contenedor no aparecen.
    """
    path = containers_file() if path is None else path
    points = load_container_points(path)
    edges = _edges_projected(graph)
    points = points.to_crs(edges.crs)
    joined = gpd.sjoin_nearest(
        points,
        edges,
        how="left",
        distance_col="distancia_m",
        max_distance=config.MAX_CONTAINER_DISTANCE_M,
    )
    joined = joined.sort_values("distancia_m")
    joined = joined.loc[~joined.index.duplicated(keep="first")]
    kept = joined.dropna(subset=["edge_key"])
    discarded = len(joined) - len(kept)
    print(f"contenedores leídos: {len(points)}")
    print(f"contenedores asignados (≤ {config.MAX_CONTAINER_DISTANCE_M:.0f} m): {len(kept)}")
    print(f"contenedores descartados por distancia: {discarded}")
    if kept.empty:
        return pd.Series(dtype="int64", name="cantidad_contenedores")
    counts = kept.groupby("edge_key").size()
    counts.name = "cantidad_contenedores"
    return counts.astype(int)


def load_container_points(path: Path) -> gpd.GeoDataFrame:
    """Lee puntos desde GeoJSON o CSV. Falla si no hay coordenadas."""
    if path.suffix.lower() in {".geojson", ".json"}:
        frame = gpd.read_file(path)
    else:
        frame = _points_from_csv(path)
    if frame.empty or frame.geometry.isna().all():
        raise SystemExit(f"{path} no tiene geometrías de punto utilizables.")
    points = frame.loc[frame.geometry.notna() & frame.geometry.geom_type.isin(["Point", "MultiPoint"])].copy()
    if points.empty:
        kinds = sorted(set(frame.geometry.geom_type.dropna().astype(str)))
        raise SystemExit(
            f"{path} no trae puntos (tipos encontrados: {kinds or 'ninguno'}). "
            "Hace falta un punto por contenedor."
        )
    if points.crs is None:
        points = points.set_crs("EPSG:4326")
    return points[["geometry"]]


def _points_from_csv(path: Path) -> gpd.GeoDataFrame:
    table = _read_table(path)
    columns = {column.lower(): column for column in table.columns}
    lat = _first(columns, _LAT_COLUMNS)
    lon = _first(columns, _LON_COLUMNS)
    if lat and lon:
        latitudes = table[lat].map(lambda value: _rescale_geographic(value, 90))
        longitudes = table[lon].map(lambda value: _rescale_geographic(value, 180))
        geometry = [Point(xy) for xy in zip(longitudes, latitudes, strict=True)]
        return gpd.GeoDataFrame(table, geometry=geometry, crs="EPSG:4326")
    geo_column = _first(columns, ("geojson", "geometry", "geom", "the_geom"))
    if geo_column:
        geometry = table[geo_column].map(_parse_geo_cell)
        return gpd.GeoDataFrame(table, geometry=geometry, crs="EPSG:4326")
    raise SystemExit(
        f"{path.name} no tiene lat/lon ni una columna geojson/geometry.\n"
        f"Columnas: {list(table.columns)}"
    )


def _edges_projected(graph: nx.Graph) -> gpd.GeoDataFrame:
    rows = []
    for u, v, data in graph.edges(data=True):
        key = (u, v) if u < v else (v, u)
        rows.append({"edge_key": key, "geometry": wkt.loads(data["geometry"])})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs(config.ZONE_UTM_EPSG)


def _read_table(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
        except Exception as error:  # noqa: BLE001 — el siguiente encoding puede andar
            last_error = error
    raise SystemExit(f"No pude leer {path.name}: {last_error}")


def _rescale_geographic(value: object, limit: float) -> float:
    """El CSV de CABA a veces guarda -34.61 como -3461 o -3461477."""
    number = float(value)
    for _ in range(8):
        if abs(number) <= limit:
            return number
        number /= 10
    return number


def _first(columns: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in columns:
            return columns[name]
    return None


def _parse_geo_cell(value: object):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("{"):
        import json

        return shape(json.loads(text))
    return wkt.loads(text)
