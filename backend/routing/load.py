"""Lee el grafo de calles ya generado en data/processed."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd

from backend.routing.postman import Calle

PRIORIDADES = ("alta", "media")
COLUMNA_PRIORIDAD = "prioridad_recoleccion"


def repo_root() -> Path:
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / "data/processed/tramos.csv").is_file():
            return candidate
    raise FileNotFoundError("no está data/processed/tramos.csv")


def cargar(
    root: Path | None = None,
) -> tuple[list[Calle], pd.DataFrame, dict[int, tuple[float, float]], dict[int, list[tuple[float, float]]]]:
    """Calles, tabla de tramos, coordenadas (lat, lon) y geometría de cada tramo."""
    root = repo_root() if root is None else root
    frame = pd.read_csv(root / "data/processed/tramos.csv")
    graph = nx.read_graphml(root / "data/processed/grafo.graphml")
    coordenadas = {
        int(nodo): (float(data["y"]), float(data["x"]))
        for nodo, data in graph.nodes(data=True)
    }
    geometria: dict[int, list[tuple[float, float]]] = {}
    for u, v, data in graph.edges(data=True):
        tramo_id = int(float(data["tramo_id"]))
        crudo = data.get("geometry")
        if isinstance(crudo, str) and crudo.startswith("LINESTRING"):
            geometria[tramo_id] = _linestring(crudo)
        else:
            a, b = int(u), int(v)
            geometria[tramo_id] = [coordenadas[a], coordenadas[b]]
    calles = [
        Calle(
            tramo_id=int(row.tramo_id),
            u=int(row.u),
            v=int(row.v),
            distancia_m=float(row.distancia_m),
        )
        for row in frame.itertuples(index=False)
    ]
    return calles, frame, coordenadas, geometria


def a_cubrir(frame: pd.DataFrame, columna: str, prioridades: tuple[str, ...]) -> set[int]:
    marcas = set(prioridades)
    desconocidas = marcas - set(frame[columna].astype(str).unique())
    if desconocidas:
        raise ValueError(f"no hay tramos con prioridad {sorted(desconocidas)} en {columna}")
    elegidos = frame[frame[columna].astype(str).isin(marcas)]
    return set(elegidos["tramo_id"].astype(int))


def _linestring(texto: str) -> list[tuple[float, float]]:
    interior = texto[texto.find("(") + 1 : texto.rfind(")")]
    puntos: list[tuple[float, float]] = []
    for parte in interior.split(","):
        lon, lat = parte.split()
        puntos.append((float(lat), float(lon)))
    return puntos
