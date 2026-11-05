"""FastAPI: prioridades del SVM y circuito de las calles altas.

Al arrancar carga el grafo, el CSV, el joblib y el SQLite. El CSV no se
reescribe. Si no hay una fila en SQLite, vale el CSV.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.api.db import guardar, leer
from backend.model.pipeline import COLUMNAS, NUMERICAS
from backend.routing.load import cargar
from backend.routing.postman import circuito
from backend.routing.view import _orientar

RAIZ = Path(__file__).resolve().parents[2]
MODELO = RAIZ / "data" / "processed" / "svm.joblib"
PRIORIDAD_CIRCUITO = "alta"


class Edicion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dias_desde_ultima_recoleccion: int = Field(ge=0, le=3650)
    cantidad_contenedores: int = Field(ge=0, le=10000)
    historico_quejas_vecinales: int = Field(ge=0, le=100000)
    tipo_zona: Literal["residencial", "comercial", "industrial"]
    cerca_escuela_hospital: Literal[0, 1]
    feria_o_evento: Literal[0, 1]


class Servicio:
    def __init__(self, calles, frame, coordenadas, geometria, modelo, sqlite: Path) -> None:
        self.calles = calles
        self.frame = frame
        self.coordenadas = coordenadas
        self.geometria = geometria
        self.modelo = modelo
        self.sqlite = sqlite
        self.nombres = {
            int(fila.tramo_id): _texto(fila.nombre_calle) for fila in frame.itertuples(index=False)
        }

    @classmethod
    def cargar(cls) -> Servicio:
        if not MODELO.is_file():
            raise FileNotFoundError(f"no está {MODELO}. Entrenarlo con: python -m backend.model.train")
        calles, frame, coordenadas, geometria = cargar(RAIZ)
        faltan = set(frame["tramo_id"].astype(int)) - set(geometria)
        if faltan:
            raise RuntimeError(f"hay tramos sin geometría: {len(faltan)}")
        return cls(calles, frame, coordenadas, geometria, joblib.load(MODELO), _ruta_sqlite())

    def filas(self) -> tuple[list[dict], dict[int, str]]:
        frame = _aplicar(self.frame, leer(self.sqlite))
        predicciones = self.modelo.predict(_matriz(frame))
        tramos: list[dict] = []
        por_id: dict[int, str] = {}
        for fila, marca in zip(frame.itertuples(index=False), predicciones, strict=True):
            tramo_id = int(fila.tramo_id)
            prioridad = str(marca)
            por_id[tramo_id] = prioridad
            tramos.append(_tramo(fila, prioridad, self.geometria[tramo_id]))
        return tramos, por_id

    def uno(self, tramo_id: int) -> dict:
        for tramo in self.filas()[0]:
            if tramo["tramo_id"] == tramo_id:
                return tramo
        raise HTTPException(status_code=404, detail="no está ese tramo")

    def recorrido(self) -> dict:
        _, por_id = self.filas()
        cubrir = {tramo_id for tramo_id, prioridad in por_id.items() if prioridad == PRIORIDAD_CIRCUITO}
        if not cubrir:
            raise HTTPException(status_code=400, detail="no hay tramos de prioridad alta")
        resultado = circuito(self.calles, cubrir)
        visitas: dict[int, int] = {}
        pasos = []
        for paso in resultado.pasos:
            visitas[paso.tramo_id] = visitas.get(paso.tramo_id, 0) + 1
            puntos = _orientar(self.geometria[paso.tramo_id], self.coordenadas, paso.u)
            pasos.append(
                {
                    "tramo_id": paso.tramo_id,
                    "sentido": {"desde": paso.u, "hasta": paso.v},
                    "agregado": paso.agregado,
                    "distancia_m": paso.distancia_m,
                    "visita": visitas[paso.tramo_id],
                    "nombre_calle": self.nombres.get(paso.tramo_id, ""),
                    "geometria": _redondear(puntos),
                }
            )
        conteo = Counter(paso["tramo_id"] for paso in pasos)
        return {
            "prioridades": [
                {"tramo_id": tramo_id, "prioridad": prioridad} for tramo_id, prioridad in por_id.items()
            ],
            "pasos": pasos,
            "costo_m": resultado.costo_m,
            "repetidos": sorted(tramo_id for tramo_id, cantidad in conteo.items() if cantidad > 1),
        }


async def _sin_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.servicio = Servicio.cargar()
        yield

    app = FastAPI(title="Recolección", lifespan=lifespan)
    app.middleware("http")(_sin_cache)

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/tramos")
    def tramos() -> list[dict]:
        return app.state.servicio.filas()[0]

    @app.patch("/tramos/{tramo_id}")
    def editar(tramo_id: int, edicion: Edicion) -> dict:
        servicio: Servicio = app.state.servicio
        if tramo_id not in servicio.nombres:
            raise HTTPException(status_code=404, detail="no está ese tramo")
        guardar(servicio.sqlite, tramo_id, edicion.model_dump())
        return servicio.uno(tramo_id)

    @app.post("/recorrido")
    def recorrido() -> dict:
        return app.state.servicio.recorrido()

    return app


app = create_app()


def _ruta_sqlite() -> Path:
    crudo = os.environ.get("SQLITE_PATH")
    path = Path(crudo) if crudo else RAIZ / "data" / "overrides.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _aplicar(frame: pd.DataFrame, overrides: dict[int, dict[str, object]]) -> pd.DataFrame:
    if not overrides:
        return frame
    out = frame.copy()
    posiciones = {int(tramo_id): i for i, tramo_id in enumerate(out["tramo_id"].to_numpy())}
    for tramo_id, valores in overrides.items():
        i = posiciones.get(int(tramo_id))
        if i is None:
            continue
        for columna, valor in valores.items():
            out.iat[i, out.columns.get_loc(columna)] = valor
    return out


def _matriz(frame: pd.DataFrame) -> pd.DataFrame:
    datos = frame.loc[:, COLUMNAS].copy()
    for columna in NUMERICAS:
        datos[columna] = pd.to_numeric(datos[columna])
    return datos


def _tramo(fila, prioridad: str, geometria: list[tuple[float, float]]) -> dict:
    return {
        "tramo_id": int(fila.tramo_id),
        "nombre_calle": _texto(fila.nombre_calle),
        "distancia_m": float(fila.distancia_m),
        "geometria": _redondear(geometria),
        "dias_desde_ultima_recoleccion": int(fila.dias_desde_ultima_recoleccion),
        "cantidad_contenedores": int(fila.cantidad_contenedores),
        "historico_quejas_vecinales": int(fila.historico_quejas_vecinales),
        "tipo_zona": str(fila.tipo_zona),
        "cerca_escuela_hospital": int(fila.cerca_escuela_hospital),
        "feria_o_evento": int(fila.feria_o_evento),
        "prioridad": prioridad,
    }


def _redondear(puntos: list[tuple[float, float]]) -> list[list[float]]:
    return [[round(lat, 6), round(lon, 6)] for lat, lon in puntos]


def _texto(valor: object) -> str:
    try:
        if pd.isna(valor):
            return ""
    except TypeError:
        pass
    if isinstance(valor, float) and math.isnan(valor):
        return ""
    return str(valor)
