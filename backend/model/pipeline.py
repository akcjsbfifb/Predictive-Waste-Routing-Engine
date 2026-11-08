"""Pipeline de regresión logística (ganador en notebooks/modelos.ipynb).

Seis columnas. Las cinco numéricas se escalan. `tipo_zona` pasa a
ceros y unos dentro del pipeline. LogisticRegression(max_iter=5000), sin grilla.
"""

from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

COLUMNAS = [
    "dias_desde_ultima_recoleccion",
    "cantidad_contenedores",
    "historico_quejas_vecinales",
    "cerca_escuela_hospital",
    "feria_o_evento",
    "tipo_zona",
]
NUMERICAS = COLUMNAS[:-1]
ZONA = ["tipo_zona"]
OBJETIVO = "prioridad_recoleccion"


def pipeline_logistic() -> Pipeline:
    preparacion = ColumnTransformer(
        [
            ("numeros", StandardScaler(), NUMERICAS),
            ("zona", OneHotEncoder(handle_unknown="ignore"), ZONA),
        ]
    )
    return Pipeline(
        [
            ("prep", preparacion),
            ("modelo", LogisticRegression(max_iter=5000)),
        ]
    )
