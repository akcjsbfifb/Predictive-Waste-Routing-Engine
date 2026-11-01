"""Camino mínimo desde un origen. Los pesos son distancias, siempre >= 0."""

from __future__ import annotations

import heapq
from collections.abc import Iterable

# vecino, distancia
Adyacencia = dict[int, list[tuple[int, float]]]


def dijkstra(
    adj: Adyacencia,
    origen: int,
    destinos: Iterable[int] | None = None,
) -> tuple[dict[int, float], dict[int, int | None]]:
    """Distancias y predecesor de cada nodo alcanzado.

    Si `destinos` está, corta cuando todos quedaron asentados. El predecesor
    del origen es None.
    """
    pendientes = None if destinos is None else {nodo for nodo in destinos if nodo != origen}
    dist: dict[int, float] = {origen: 0.0}
    prev: dict[int, int | None] = {origen: None}
    heap: list[tuple[float, int]] = [(0.0, origen)]
    vistos: set[int] = set()

    while heap:
        acumulado, nodo = heapq.heappop(heap)
        if nodo in vistos:
            continue
        vistos.add(nodo)
        if pendientes is not None:
            pendientes.discard(nodo)
            if not pendientes:
                break
        for vecino, peso in adj[nodo]:
            propuesta = acumulado + peso
            if propuesta < dist.get(vecino, float("inf")):
                dist[vecino] = propuesta
                prev[vecino] = nodo
                heapq.heappush(heap, (propuesta, vecino))
    return dist, prev


def dijkstra_multi(
    adj: Adyacencia,
    origenes: Iterable[int],
) -> tuple[dict[int, float], dict[int, int | None]]:
    """Igual que Dijkstra, con varios orígenes a distancia 0."""
    dist: dict[int, float] = {}
    prev: dict[int, int | None] = {}
    heap: list[tuple[float, int]] = []
    for origen in origenes:
        if origen not in dist:
            dist[origen] = 0.0
            prev[origen] = None
            heapq.heappush(heap, (0.0, origen))
    vistos: set[int] = set()

    while heap:
        acumulado, nodo = heapq.heappop(heap)
        if nodo in vistos:
            continue
        vistos.add(nodo)
        for vecino, peso in adj[nodo]:
            propuesta = acumulado + peso
            if propuesta < dist.get(vecino, float("inf")):
                dist[vecino] = propuesta
                prev[vecino] = nodo
                heapq.heappush(heap, (propuesta, vecino))
    return dist, prev


def reconstruir(prev: dict[int, int | None], destino: int) -> list[int]:
    """Nodos desde la raíz (predecesor None) hasta `destino`, inclusive."""
    nodos: list[int] = []
    actual: int | None = destino
    vistos: set[int] = set()
    while actual is not None:
        if actual in vistos:
            raise RuntimeError(f"ciclo de predecesores en {actual}")
        vistos.add(actual)
        nodos.append(actual)
        actual = prev.get(actual)
    nodos.reverse()
    if not nodos or destino not in prev:
        raise RuntimeError(f"no hay camino hasta {destino}")
    return nodos
