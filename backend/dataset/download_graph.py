"""Red vial de OpenStreetMap a un networkx.Graph simple y conexo."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import osmnx as ox
import requests
from shapely.geometry import LineString

from backend import config

def download_drive_graph(bbox: tuple[float, float, float, float] | None = None) -> nx.Graph:
    """Descarga calles transitables y devuelve un grafo no dirigido simple.

    Overpass público suele estar saturado. Para esta bounding box chica se usa
    la API de mapa de OSM (``/api/0.6/map``), que devuelve el mismo extracto,
    y después se filtra al conjunto de vías de ``network_type="drive"``.
    """
    bbox = config.BBOX if bbox is None else bbox
    xml_path = _download_osm_xml(bbox)
    raw = ox.graph_from_xml(xml_path, simplify=True, retain_all=True)
    drive = _keep_drive_edges(raw)
    clipped = ox.truncate.truncate_graph_bbox(drive, bbox, truncate_by_edge=False)
    clipped = _largest_weak_component(clipped)
    undirected = ox.convert.to_undirected(clipped)
    simple = _to_simple_graph(undirected)
    simple = _largest_component(simple)
    simple.graph["crs"] = "EPSG:4326"
    simple.graph["bbox"] = ",".join(str(v) for v in bbox)
    return simple


def report(graph: nx.Graph) -> None:
    """Imprime nodos, aristas y grados impares."""
    odd = sum(1 for _, degree in graph.degree if degree % 2 == 1)
    low, high = config.TARGET_EDGES
    print(f"nodos: {graph.number_of_nodes()}")
    print(f"aristas: {graph.number_of_edges()}")
    print(f"nodos de grado impar: {odd}")
    if not (low <= graph.number_of_edges() <= high):
        print(
            f"aviso: las aristas están fuera de {low}–{high}. "
            "Ajustá config.BBOX; no se recortan aristas al azar."
        )


def _download_osm_xml(bbox: tuple[float, float, float, float]) -> Path:
    west, south, east, north = bbox
    path = osm_xml_path(bbox)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        print(f"OSM cache: {path}")
        return path
    url = (
        "https://api.openstreetmap.org/api/0.6/map"
        f"?bbox={west},{south},{east},{north}"
    )
    print(f"descargando {url}")
    response = requests.get(
        url,
        headers={"User-Agent": config.OSM_USER_AGENT},
        timeout=120,
    )
    response.raise_for_status()
    path.write_bytes(response.content)
    print(f"guardado {path} ({path.stat().st_size} bytes)")
    return path


def _highway_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else None
    return str(value)


def _is_drive_edge(data: dict) -> bool:
    highway = _highway_value(data.get("highway"))
    if highway is None or highway in config.DRIVE_EXCLUDED_HIGHWAYS:
        return False
    if str(data.get("area", "")).lower() == "yes":
        return False
    if str(data.get("access", "")).lower() == "private":
        return False
    if str(data.get("motor_vehicle", "")).lower() == "no":
        return False
    if str(data.get("motorcar", "")).lower() == "no":
        return False
    service = _highway_value(data.get("service"))
    if service in config.DRIVE_EXCLUDED_SERVICE:
        return False
    return True


def _keep_drive_edges(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    kept = graph.copy()
    drop = [
        (u, v, key)
        for u, v, key, data in kept.edges(keys=True, data=True)
        if not _is_drive_edge(data)
    ]
    kept.remove_edges_from(drop)
    kept.remove_nodes_from([node for node, degree in kept.degree if degree == 0])
    return kept


def _largest_weak_component(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    nodes = max(nx.weakly_connected_components(graph), key=len)
    return graph.subgraph(nodes).copy()


def _largest_component(graph: nx.Graph) -> nx.Graph:
    nodes = max(nx.connected_components(graph), key=len)
    return graph.subgraph(nodes).copy()


def _to_simple_graph(multigraph: nx.MultiGraph) -> nx.Graph:
    """Quita self-loops y, si hay paralelas, se queda con la más corta."""
    simple = nx.Graph()
    simple.graph.update(multigraph.graph)
    simple.add_nodes_from(multigraph.nodes(data=True))
    best: dict[tuple[int, int], dict] = {}
    for u, v, data in multigraph.edges(data=True):
        if u == v:
            continue
        length = float(data.get("length", 0.0))
        key = (u, v) if u < v else (v, u)
        current = best.get(key)
        if current is None or length < current["length"]:
            attrs = {
                "length": length,
                "highway": _as_scalar(data.get("highway")),
                "name": _as_scalar(data.get("name")),
                "osmid": _as_scalar(data.get("osmid")),
                "geometry": _geometry_wkt(multigraph, u, v, data),
            }
            best[key] = attrs
    for (u, v), attrs in best.items():
        simple.add_edge(u, v, **attrs)
    return simple


def osm_xml_path(bbox: tuple[float, float, float, float] | None = None) -> Path:
    """Ruta del extracto OSM ya descargado para esta bounding box."""
    west, south, east, north = config.BBOX if bbox is None else bbox
    return Path("data/cache") / f"calles_{west}_{south}_{east}_{north}.osm"


def _geometry_wkt(graph: nx.MultiGraph, u: int, v: int, data: dict) -> str:
    geometry = data.get("geometry")
    if geometry is not None and hasattr(geometry, "wkt"):
        return geometry.wkt
    line = LineString(
        [(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])]
    )
    return line.wkt


def _as_scalar(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else ""
    return str(value)


def main() -> None:
    graph = download_drive_graph()
    report(graph)


if __name__ == "__main__":
    main()
