"""Arma el circuito y escribe un mapa para revisarlo.

Correr desde la raíz del repo: ``python -m backend.routing.build_route``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backend.routing.load import COLUMNA_PRIORIDAD, PRIORIDADES, a_cubrir, cargar
from backend.routing.postman import circuito
from backend.routing.view import escribir_mapa


def main() -> None:
    parser = argparse.ArgumentParser(description="Circuito del camión sobre los tramos prioritarios")
    parser.add_argument("--columna", default=COLUMNA_PRIORIDAD)
    parser.add_argument("--prioridades", nargs="+", default=list(PRIORIDADES))
    parser.add_argument("--html", type=Path, default=Path("output/recorrido.html"))
    parser.add_argument("--csv", type=Path, default=Path("output/recorrido.csv"))
    args = parser.parse_args()
    prioridades = tuple(args.prioridades)

    calles, frame, coordenadas, geometria = cargar()
    cubrir = a_cubrir(frame, args.columna, prioridades)
    resultado = circuito(calles, cubrir)
    _escribir_csv(args.csv, resultado, frame, args.columna)
    escribir_mapa(args.html, resultado, frame, coordenadas, geometria, args.columna, prioridades)
    _informe(args.columna, prioridades, len(cubrir), resultado, args.html, args.csv)


def _escribir_csv(path: Path, resultado, frame: pd.DataFrame, columna: str) -> None:
    tabla = frame.set_index("tramo_id")
    visitas: dict[int, int] = {}
    filas = []
    for indice, paso in enumerate(resultado.pasos, start=1):
        visitas[paso.tramo_id] = visitas.get(paso.tramo_id, 0) + 1
        fila = tabla.loc[paso.tramo_id]
        filas.append(
            {
                "paso": indice,
                "tramo_id": paso.tramo_id,
                "desde": paso.u,
                "hasta": paso.v,
                "distancia_m": paso.distancia_m,
                "nombre_calle": fila["nombre_calle"],
                "tipo_zona": fila["tipo_zona"],
                columna: fila[columna],
                "agregado": paso.agregado,
                "visita": visitas[paso.tramo_id],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas).to_csv(path, index=False)


def _informe(columna: str, prioridades: tuple[str, ...], tramos: int, resultado, html: Path, csv: Path) -> None:
    print(f"columna: {columna}")
    print(f"prioridades a cubrir: {', '.join(prioridades)}")
    print(f"tramos a cubrir: {tramos}")
    print(f"componentes de ese subgrafo: {resultado.componentes}")
    print(f"vértices de grado impar: {resultado.impares}")
    print("emparejamiento: networkx.min_weight_matching")
    print(f"componentes después de emparejar: {resultado.componentes_tras_emparejar}")
    print(f"copias agregadas: {resultado.agregadas}")
    print(f"metros de los tramos a cubrir: {resultado.costo_cubrir_m:.1f}")
    print(f"metros del circuito: {resultado.costo_m:.1f}")
    print(f"metros de más: {resultado.costo_m - resultado.costo_cubrir_m:.1f}")
    print(f"pasos: {len(resultado.pasos)}")
    print(f"tramos recorridos más de una vez: {resultado.repetidos}")
    print(f"csv: {csv}")
    print(f"mapa: {html}")


if __name__ == "__main__":
    main()
