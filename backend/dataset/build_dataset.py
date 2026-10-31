"""Arma tramos.csv, nodos.csv y grafo.graphml.

Correr desde la raíz del repo: ``python -m backend.dataset.build_dataset``.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd

from backend.dataset.assign_zone_type import assign_zone_types
from backend.dataset.download_graph import download_drive_graph, osm_xml_path, report
from backend.dataset.load_containers import containers_file, count_containers_per_edge
from backend.dataset.synthesize import synthesize


def build() -> None:
    containers_file()
    graph = download_drive_graph()
    report(graph)
    zones = assign_zone_types(graph, osm_xml_path())
    counts = count_containers_per_edge(graph)
    frame = _edge_frame(graph, zones, counts)
    frame = synthesize(frame)
    _attach_tramo_id(graph, frame)
    out = Path("data/processed")
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "tramos.csv", index=False)
    _nodes_frame(graph).to_csv(out / "nodos.csv", index=False)
    nx.write_graphml(graph, out / "grafo.graphml")
    print(f"tramos: {len(frame)} -> {out / 'tramos.csv'}")
    print(f"nodos: {graph.number_of_nodes()} -> {out / 'nodos.csv'}")
    print(f"grafo -> {out / 'grafo.graphml'}")
    print(frame["tipo_zona"].value_counts().to_string())
    print(frame["prioridad_recoleccion"].value_counts(normalize=True).round(3).to_string())


def _edge_frame(graph: nx.Graph, zones: pd.Series, counts: pd.Series) -> pd.DataFrame:
    zone_by_edge = zones.to_dict()
    rows = []
    for u, v, data in graph.edges(data=True):
        key = (u, v) if u < v else (v, u)
        rows.append(
            {
                "u": key[0],
                "v": key[1],
                "distancia_m": round(float(data["length"]), 2),
                "highway": data.get("highway") or "",
                "nombre_calle": data.get("name") or "",
                "tipo_zona": zone_by_edge[key],
                "cantidad_contenedores": int(counts.get(key, 0)),
            }
        )
    frame = pd.DataFrame(rows)
    frame = frame.sort_values(["u", "v"], kind="mergesort").reset_index(drop=True)
    frame.insert(0, "tramo_id", frame.index + 1)
    return frame


def _attach_tramo_id(graph: nx.Graph, frame: pd.DataFrame) -> None:
    lookup = {(int(row.u), int(row.v)): int(row.tramo_id) for row in frame.itertuples(index=False)}
    for u, v, data in graph.edges(data=True):
        key = (u, v) if u < v else (v, u)
        data["tramo_id"] = lookup[key]
        data["length"] = round(float(data["length"]), 2)


def _nodes_frame(graph: nx.Graph) -> pd.DataFrame:
    rows = [
        {"node_id": node, "lat": float(data["y"]), "lon": float(data["x"])}
        for node, data in graph.nodes(data=True)
    ]
    return pd.DataFrame(rows).sort_values("node_id").reset_index(drop=True)


def main() -> None:
    build()


if __name__ == "__main__":
    main()
