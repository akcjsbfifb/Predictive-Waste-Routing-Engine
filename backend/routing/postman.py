"""Circuito que cubre un subconjunto de calles.

Si esas calles forman un subgrafo conexo, el largo que se agrega es el mínimo
del cartero chino: vértices de grado impar, caminos mínimos con Dijkstra,
emparejamiento de costo mínimo y duplicación de esos caminos. El
emparejamiento lo resuelve ``networkx.min_weight_matching``.

Si el subgrafo no es conexo, el mismo emparejamiento puede unir componentes
cuando conviene cruzar de una a otra por el grafo completo. Las que siguen
separadas (también las que ya tenían todos los grados pares) se unen con el
camino mínimo entre ellas, puesto dos veces para no dejar grados impares.
Ese empalme sigue un árbol de componentes: alcanza para armar un circuito y,
si el subgrafo ya era conexo, no agrega nada. No es el óptimo del cartero
rural, que es otro problema.

Hierholzer arma el circuito sobre el multigrafo que queda.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import networkx as nx

from backend.routing.dijkstra import dijkstra, dijkstra_multi, reconstruir
from backend.routing.hierholzer import hierholzer


@dataclass(frozen=True)
class Calle:
    tramo_id: int
    u: int
    v: int
    distancia_m: float


@dataclass(frozen=True)
class Paso:
    tramo_id: int
    u: int
    v: int
    distancia_m: float
    agregado: bool


@dataclass(frozen=True)
class Circuito:
    pasos: list[Paso]
    costo_m: float
    costo_cubrir_m: float
    impares: int
    componentes: int
    componentes_tras_emparejar: int
    agregadas: int
    repetidos: int


@dataclass(frozen=True)
class _Copia:
    tramo_id: int
    u: int
    v: int
    distancia_m: float
    agregado: bool


def circuito(calles: list[Calle], cubrir: set[int]) -> Circuito:
    """Circuito cerrado que pasa por cada tramo de `cubrir` al menos una vez."""
    if not cubrir:
        raise ValueError("no hay tramos para cubrir")
    por_id = {calle.tramo_id: calle for calle in calles}
    faltan = cubrir - por_id.keys()
    if faltan:
        raise ValueError(f"tramos que no están en el grafo: {len(faltan)}")

    requeridas = [por_id[tramo_id] for tramo_id in sorted(cubrir)]
    adyacencia = _adyacencia(calles)
    por_punta = {_punta(calle.u, calle.v): calle for calle in calles}
    impares = _impares(requeridas)
    componentes = _componentes(requeridas)

    copias = [_copia(calle, agregado=False) for calle in requeridas]
    if impares:
        copias.extend(_copias_del_emparejamiento(adyacencia, por_punta, impares))
    componentes_tras_emparejar = len(_componentes_de_copias(copias))
    copias.extend(_copias_para_conectar(adyacencia, por_punta, copias))
    _grados_pares(copias)

    nodos = hierholzer([(copia.u, copia.v) for copia in copias])
    pasos = _pasos(nodos, copias)
    _cubre(pasos, cubrir)

    conteo = Counter(paso.tramo_id for paso in pasos)
    costo_cubrir = sum(calle.distancia_m for calle in requeridas)
    return Circuito(
        pasos=pasos,
        costo_m=sum(paso.distancia_m for paso in pasos),
        costo_cubrir_m=costo_cubrir,
        impares=len(impares),
        componentes=len(componentes),
        componentes_tras_emparejar=componentes_tras_emparejar,
        agregadas=sum(1 for copia in copias if copia.agregado),
        repetidos=sum(1 for cantidad in conteo.values() if cantidad > 1),
    )


def _adyacencia(calles: list[Calle]) -> dict[int, list[tuple[int, float]]]:
    adyacencia: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for calle in calles:
        adyacencia[calle.u].append((calle.v, calle.distancia_m))
        adyacencia[calle.v].append((calle.u, calle.distancia_m))
    return adyacencia


def _punta(u: int, v: int) -> tuple[int, int]:
    return (u, v) if u < v else (v, u)


def _copia(calle: Calle, agregado: bool) -> _Copia:
    return _Copia(calle.tramo_id, calle.u, calle.v, calle.distancia_m, agregado)


def _impares(calles: list[Calle]) -> list[int]:
    grado: dict[int, int] = defaultdict(int)
    for calle in calles:
        grado[calle.u] += 1
        grado[calle.v] += 1
    return [nodo for nodo, cantidad in grado.items() if cantidad % 2 == 1]


def _componentes(calles: list[Calle]) -> list[set[int]]:
    return _componentes_de_copias([_copia(calle, False) for calle in calles])


def _componentes_de_copias(copias: list[_Copia]) -> list[set[int]]:
    adyacencia: dict[int, set[int]] = defaultdict(set)
    for copia in copias:
        adyacencia[copia.u].add(copia.v)
        adyacencia[copia.v].add(copia.u)
    vistos: set[int] = set()
    componentes: list[set[int]] = []
    for inicio in adyacencia:
        if inicio in vistos:
            continue
        pila = [inicio]
        componente: set[int] = set()
        while pila:
            nodo = pila.pop()
            if nodo in vistos:
                continue
            vistos.add(nodo)
            componente.add(nodo)
            pila.extend(adyacencia[nodo] - vistos)
        componentes.append(componente)
    return componentes


def _copias_del_emparejamiento(
    adyacencia: dict[int, list[tuple[int, float]]],
    por_punta: dict[tuple[int, int], Calle],
    impares: list[int],
) -> list[_Copia]:
    if len(impares) % 2 == 1:
        raise RuntimeError("cantidad impar de vértices de grado impar")
    distancias = _distancias(adyacencia, impares)
    parejas = _emparejar(impares, distancias)
    copias: list[_Copia] = []
    for origen, destino in parejas:
        _, prev = dijkstra(adyacencia, origen, [destino])
        copias.extend(_copias_del_camino(por_punta, reconstruir(prev, destino), veces=1))
    return copias


def _distancias(
    adyacencia: dict[int, list[tuple[int, float]]],
    nodos: list[int],
) -> dict[tuple[int, int], float]:
    distancias: dict[tuple[int, int], float] = {}
    objetivos = set(nodos)
    for origen in nodos:
        dist, _ = dijkstra(adyacencia, origen, objetivos)
        for destino in nodos:
            if origen < destino:
                if destino not in dist:
                    raise RuntimeError(f"no hay camino de {origen} a {destino}")
                distancias[(origen, destino)] = dist[destino]
    return distancias


def _emparejar(nodos: list[int], distancias: dict[tuple[int, int], float]) -> list[tuple[int, int]]:
    """Emparejamiento de costo mínimo. Lo calcula networkx.min_weight_matching."""
    grafo = nx.Graph()
    grafo.add_nodes_from(nodos)
    for (u, v), distancia in distancias.items():
        grafo.add_edge(u, v, weight=distancia)
    parejas = nx.min_weight_matching(grafo, weight="weight")
    if len(parejas) != len(nodos) // 2:
        raise RuntimeError("el emparejamiento no cubre todos los vértices de grado impar")
    return [(u, v) if u < v else (v, u) for u, v in parejas]


def _copias_para_conectar(
    adyacencia: dict[int, list[tuple[int, float]]],
    por_punta: dict[tuple[int, int], Calle],
    copias: list[_Copia],
) -> list[_Copia]:
    componentes = _componentes_de_copias(copias)
    if len(componentes) <= 1:
        return []

    nodo_componente: dict[int, int] = {}
    for indice, componente in enumerate(componentes):
        for nodo in componente:
            nodo_componente[nodo] = indice

    aristas: list[tuple[float, int, int]] = []
    for i, componente in enumerate(componentes):
        dist, _ = dijkstra_multi(adyacencia, componente)
        for j in range(i + 1, len(componentes)):
            distancia = min(dist.get(nodo, float("inf")) for nodo in componentes[j])
            if distancia == float("inf"):
                raise RuntimeError("el grafo de calles no conecta dos componentes")
            aristas.append((distancia, i, j))
    aristas.sort()

    padre = list(range(len(componentes)))

    def encontrar(indice: int) -> int:
        while padre[indice] != indice:
            padre[indice] = padre[padre[indice]]
            indice = padre[indice]
        return indice

    def unir(a: int, b: int) -> None:
        padre[encontrar(a)] = encontrar(b)

    agregadas: list[_Copia] = []
    for _, i, j in aristas:
        if encontrar(i) == encontrar(j):
            continue
        dist, prev = dijkstra_multi(adyacencia, componentes[i])
        destino = min(componentes[j], key=lambda nodo: dist.get(nodo, float("inf")))
        camino = reconstruir(prev, destino)
        agregadas.extend(_copias_del_camino(por_punta, camino, veces=2))
        for nodo in camino:
            if nodo in nodo_componente:
                unir(i, nodo_componente[nodo])
    if len({encontrar(indice) for indice in range(len(componentes))}) != 1:
        raise RuntimeError("las componentes no quedaron unidas")
    return agregadas


def _copias_del_camino(
    por_punta: dict[tuple[int, int], Calle],
    nodos: list[int],
    veces: int,
) -> list[_Copia]:
    tramo: list[_Copia] = []
    for u, v in zip(nodos, nodos[1:]):
        calle = por_punta[_punta(u, v)]
        tramo.append(_copia(calle, agregado=True))
    return tramo * veces


def _grados_pares(copias: list[_Copia]) -> None:
    grado: dict[int, int] = defaultdict(int)
    for copia in copias:
        grado[copia.u] += 1
        grado[copia.v] += 1
    impares = [nodo for nodo, cantidad in grado.items() if cantidad % 2 == 1]
    if impares:
        raise RuntimeError(f"quedaron {len(impares)} vértices de grado impar")
    if len(_componentes_de_copias(copias)) != 1:
        raise RuntimeError("el multigrafo del circuito no es conexo")


def _pasos(nodos: list[int], copias: list[_Copia]) -> list[Paso]:
    bolsa: dict[tuple[int, int], list[_Copia]] = defaultdict(list)
    for copia in copias:
        bolsa[_punta(copia.u, copia.v)].append(copia)
    pasos: list[Paso] = []
    for u, v in zip(nodos, nodos[1:]):
        copia = bolsa[_punta(u, v)].pop()
        pasos.append(Paso(copia.tramo_id, u, v, copia.distancia_m, copia.agregado))
    if any(bolsa.values()):
        raise RuntimeError("quedaron copias de aristas sin usar")
    return pasos


def _cubre(pasos: list[Paso], cubrir: set[int]) -> None:
    recorridos = {paso.tramo_id for paso in pasos}
    faltan = cubrir - recorridos
    if faltan:
        raise RuntimeError(f"el circuito no cubre {len(faltan)} tramos")
