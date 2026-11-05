"""Ediciones del usuario. Una fila por tramo, solo las seis columnas del modelo."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.model.pipeline import COLUMNAS

_CREAR = """
CREATE TABLE IF NOT EXISTS overrides (
    tramo_id INTEGER PRIMARY KEY,
    dias_desde_ultima_recoleccion INTEGER NOT NULL,
    cantidad_contenedores INTEGER NOT NULL,
    historico_quejas_vecinales INTEGER NOT NULL,
    tipo_zona TEXT NOT NULL,
    cerca_escuela_hospital INTEGER NOT NULL,
    feria_o_evento INTEGER NOT NULL
)
"""


def conectar(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_CREAR)
    return conn


def leer(path: Path) -> dict[int, dict[str, object]]:
    with conectar(path) as conn:
        filas = conn.execute(f"SELECT tramo_id, {', '.join(COLUMNAS)} FROM overrides").fetchall()
    return {int(fila["tramo_id"]): {columna: fila[columna] for columna in COLUMNAS} for fila in filas}


def guardar(path: Path, tramo_id: int, valores: dict[str, object]) -> None:
    columnas = ", ".join(COLUMNAS)
    marcas = ", ".join("?" for _ in COLUMNAS)
    actualiza = ", ".join(f"{columna} = excluded.{columna}" for columna in COLUMNAS)
    with conectar(path) as conn:
        conn.execute(
            f"""
            INSERT INTO overrides (tramo_id, {columnas})
            VALUES (?, {marcas})
            ON CONFLICT(tramo_id) DO UPDATE SET {actualiza}
            """,
            [tramo_id, *[valores[columna] for columna in COLUMNAS]],
        )
