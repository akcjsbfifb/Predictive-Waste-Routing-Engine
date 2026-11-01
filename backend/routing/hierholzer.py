"""Circuito euleriano. El multigrafo tiene que ser conexo y de grados pares."""

from __future__ import annotations

from collections import defaultdict


def hierholzer(aristas: list[tuple[int, int]]) -> list[int]:
    """Devuelve los nodos del circuito, con el inicio repetido al final.

    Cada arista es no dirigida y se recorre una vez. Dos pares iguales son
    dos copias de la misma calle.
    """
    if not aristas:
        raise ValueError("no hay aristas para recorrer")

    adyacencia: dict[int, list[int]] = defaultdict(list)
    for indice, (u, v) in enumerate(aristas):
        adyacencia[u].append(indice)
        adyacencia[v].append(indice)

    usada = [False] * len(aristas)
    inicio = aristas[0][0]
    pila = [inicio]
    circuito: list[int] = []

    while pila:
        nodo = pila[-1]
        while adyacencia[nodo] and usada[adyacencia[nodo][-1]]:
            adyacencia[nodo].pop()
        if not adyacencia[nodo]:
            circuito.append(pila.pop())
            continue
        indice = adyacencia[nodo].pop()
        usada[indice] = True
        u, v = aristas[indice]
        pila.append(v if u == nodo else u)

    circuito.reverse()
    if len(circuito) != len(aristas) + 1 or circuito[0] != circuito[-1] or not all(usada):
        raise RuntimeError("el multigrafo no tiene circuito euleriano")
    return circuito
