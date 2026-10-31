"""tipo_zona a partir de tags OSM alrededor de cada tramo."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd
from shapely import wkt

from backend import config


def assign_zone_types(graph: nx.Graph, osm_xml: Path) -> pd.Series:
    """Clasifica cada arista en residencial, comercial o industrial.

    En el microcentro el `landuse` de manzana casi no está mapeado. Se usa un buffer
    y un puntaje con shops, amenities y buildings. Si no hay señal, el tramo
    queda residencial: es el tejido por defecto del centro.
    """
    edges = _edges_gdf(graph).to_crs(config.ZONE_UTM_EPSG)
    buffers = edges.copy()
    buffers["geometry"] = buffers.geometry.buffer(config.ZONE_BUFFER_M)
    features = _load_features(osm_xml)

    commercial = _score(buffers, features, _commercial_weight)
    industrial = _score(buffers, features, _industrial_weight)
    residential = _score(buffers, features, _residential_weight)

    labels: list[str] = []
    for key in edges["edge_key"]:
        scores = {
            "comercial": float(commercial.get(key, 0.0)),
            "industrial": float(industrial.get(key, 0.0)),
            "residencial": float(residential.get(key, 0.0)),
        }
        labels.append(_pick(scores))
    return pd.Series(labels, index=pd.Index(edges["edge_key"], name="edge_key"), name="tipo_zona")


def _edges_gdf(graph: nx.Graph) -> gpd.GeoDataFrame:
    rows = []
    for u, v, data in graph.edges(data=True):
        key = (u, v) if u < v else (v, u)
        rows.append({"edge_key": key, "geometry": wkt.loads(data["geometry"])})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def _load_features(osm_xml: Path) -> gpd.GeoDataFrame:
    features = ox.features.features_from_xml(
        osm_xml,
        tags={"landuse": True, "shop": True, "amenity": True, "building": True},
    )
    if features.empty:
        return features
    features = features.reset_index(drop=True)
    return features.to_crs(config.ZONE_UTM_EPSG)


def _score(buffers: gpd.GeoDataFrame, features: gpd.GeoDataFrame, weight) -> dict[tuple[int, int], float]:
    if features.empty:
        return {}
    pieces = []
    for column in ("landuse", "shop", "amenity", "building"):
        if column not in features.columns:
            continue
        subset = features.loc[features[column].notna(), ["geometry", column]].copy()
        if subset.empty:
            continue
        subset["w"] = subset[column].map(lambda value, column=column: weight(column, value))
        subset = subset.loc[subset["w"] > 0, ["geometry", "w"]]
        if not subset.empty:
            pieces.append(subset)
    if not pieces:
        return {}
    weighted = gpd.GeoDataFrame(pd.concat(pieces, ignore_index=True), geometry="geometry", crs=buffers.crs)
    joined = gpd.sjoin(buffers, weighted, how="left", predicate="intersects")
    grouped = joined.groupby("edge_key")["w"].sum(min_count=1)
    return {key: float(value) for key, value in grouped.dropna().items()}


def _commercial_weight(column: str, value: object) -> float:
    text = str(value)
    if column == "shop" and text and text != "vacant":
        return 1.0
    if column == "landuse" and text in {"commercial", "retail"}:
        return 2.0
    if column == "amenity" and text in config.COMMERCIAL_AMENITIES:
        return 0.5
    if column == "building" and text in config.COMMERCIAL_BUILDINGS:
        return 1.5
    return 0.0


def _industrial_weight(column: str, value: object) -> float:
    text = str(value)
    if column == "landuse" and text == "industrial":
        return 3.0
    if column == "building" and text in config.INDUSTRIAL_BUILDINGS:
        return 2.0
    return 0.0


def _residential_weight(column: str, value: object) -> float:
    text = str(value)
    if column == "landuse" and text == "residential":
        return 1.0
    if column == "building" and text in config.RESIDENTIAL_BUILDINGS:
        return 0.4
    return 0.0


def _pick(scores: dict[str, float]) -> str:
    industrial = scores["industrial"]
    commercial = scores["comercial"]
    if industrial >= config.ZONE_INDUSTRIAL_MIN_SCORE and industrial >= commercial:
        return "industrial"
    if commercial >= config.ZONE_COMMERCIAL_MIN_SCORE and commercial >= industrial:
        return "comercial"
    return "residencial"
