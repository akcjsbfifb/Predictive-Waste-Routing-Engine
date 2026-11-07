"""Regenera días, quejas y prioridad en data/processed/tramos.csv con synthesize (SEED fijo).

No redescarga OSM ni corre build_dataset. No toca cerca_escuela_hospital ni feria_o_evento.

Desde la raíz del repo:

    .venv/bin/python scripts/resynthesize.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from backend import config
from backend.dataset.synthesize import synthesize

TRAMOS_PATH = ROOT / "data" / "processed" / "tramos.csv"
SYNTH_COLS = [
    "dias_desde_ultima_recoleccion",
    "historico_quejas_vecinales",
    "prioridad_recoleccion",
]
PRESERVE_COLS = ["cerca_escuela_hospital", "feria_o_evento"]


def _series_fingerprint(series: pd.Series) -> str:
    blob = series.to_csv(index=False).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _violations(frame: pd.DataFrame) -> tuple[int, int]:
    c = frame["cantidad_contenedores"]
    d = frame["dias_desde_ultima_recoleccion"]
    q = frame["historico_quejas_vecinales"]
    sin_contenedor = int(((c <= 0) & ((d > 0) | (q > 0))).sum())
    con_contenedor = int(((c > 0) & ((d < 1) | (q < 1))).sum())
    return sin_contenedor, con_contenedor


def main() -> None:
    if not TRAMOS_PATH.is_file():
        print(f"Falta {TRAMOS_PATH.relative_to(ROOT)}.")
        sys.exit(1)

    frame = pd.read_csv(TRAMOS_PATH)
    n = len(frame)
    preserve_hashes = {
        col: _series_fingerprint(frame[col])
        for col in PRESERVE_COLS
        if col in frame.columns
    }

    regenerated = synthesize(frame, seed=config.SEED)
    for col in SYNTH_COLS:
        frame[col] = regenerated[col]

    for col, digest in preserve_hashes.items():
        if _series_fingerprint(frame[col]) != digest:
            print(f"ERROR: columna {col} cambió (no debería).")
            sys.exit(1)

    frame.to_csv(TRAMOS_PATH, index=False)

    v0, v1 = _violations(frame)
    print(f"filas: {n}")
    print(f"violaciones sin contenedor (días>0 o quejas>0): {v0}")
    print(f"violaciones con contenedor (días<1 o quejas<1): {v1}")
    print("prioridad_recoleccion:")
    print(frame["prioridad_recoleccion"].value_counts().to_string())
    if preserve_hashes:
        print("columnas preservadas (hash ok): " + ", ".join(sorted(preserve_hashes)))

    if v0 + v1 > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
