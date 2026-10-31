"""Chequeos del dataset de tramos. Sale con código distinto de 0 si algo estructural falla."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import networkx as nx
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from backend import config
from backend.dataset.synthesize import synthesize

REQUIRED = [
    "tramo_id",
    "tipo_zona",
    "cantidad_contenedores",
    "dias_desde_ultima_recoleccion",
    "historico_quejas_vecinales",
    "prioridad_recoleccion",
    "u",
    "v",
    "distancia_m",
]
FEATURES = [
    "tipo_zona",
    "cantidad_contenedores",
    "dias_desde_ultima_recoleccion",
    "historico_quejas_vecinales",
]
LABEL = "prioridad_recoleccion"
SHARE_TOLERANCE = 0.05

errors: list[str] = []
warnings: list[str] = []


def main() -> None:
    tramos_path = Path("data/processed/tramos.csv")
    graph_path = Path("data/processed/grafo.graphml")
    if not tramos_path.is_file() or not graph_path.is_file():
        print("Faltan data/processed/tramos.csv o grafo.graphml. Corré build_dataset primero.")
        sys.exit(1)
    frame = pd.read_csv(tramos_path)
    graph = nx.read_graphml(graph_path)
    _check_nulls(frame)
    _check_ids_and_edges(frame, graph)
    _check_graph(graph)
    _check_priority_shares(frame)
    _check_zones(frame)
    _check_numeric(frame)
    _sanity_model(frame)
    _check_reproducible(frame)
    print("\n".join(warnings) if warnings else "sin advertencias")
    if errors:
        print("ERRORES:")
        print("\n".join(errors))
        sys.exit(1)
    print("validación ok")


def _check_nulls(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED if column not in frame.columns]
    if missing:
        errors.append(f"faltan columnas: {missing}")
        return
    nulls = frame[REQUIRED].isna().sum()
    bad = nulls[nulls > 0]
    if not bad.empty:
        errors.append(f"nulos en columnas obligatorias:\n{bad.to_string()}")
    else:
        print("nulos en columnas obligatorias: 0")


def _check_ids_and_edges(frame: pd.DataFrame, graph: nx.Graph) -> None:
    if frame["tramo_id"].duplicated().any():
        errors.append("tramo_id repetido")
    else:
        print(f"tramo_id únicos: {frame['tramo_id'].nunique()}")
    csv_edges = {(int(min(u, v)), int(max(u, v))) for u, v in zip(frame["u"], frame["v"], strict=True)}
    graph_edges = set()
    graph_ids = {}
    for u, v, data in graph.edges(data=True):
        key = (int(u), int(v)) if int(u) < int(v) else (int(v), int(u))
        graph_edges.add(key)
        graph_ids[key] = int(float(data.get("tramo_id", -1)))
    if csv_edges != graph_edges:
        errors.append(
            f"aristas csv vs grafo no coinciden (solo csv {len(csv_edges - graph_edges)}, "
            f"solo grafo {len(graph_edges - csv_edges)})"
        )
    else:
        print(f"aristas csv y grafo: {len(csv_edges)}")
    mismatched = [
        row.tramo_id
        for row in frame.itertuples(index=False)
        if graph_ids.get((int(min(row.u, row.v)), int(max(row.u, row.v)))) != int(row.tramo_id)
    ]
    if mismatched:
        errors.append(f"tramo_id distinto entre csv y grafo: {len(mismatched)}")


def _check_graph(graph: nx.Graph) -> None:
    if graph.is_directed():
        errors.append("el grafo es dirigido")
    if any(u == v for u, v in graph.edges()):
        errors.append("hay self-loops")
    if isinstance(graph, nx.MultiGraph):
        errors.append("hay aristas paralelas (MultiGraph)")
    if not nx.is_connected(graph):
        errors.append(f"el grafo no es conexo ({nx.number_connected_components(graph)} componentes)")
    else:
        print("grafo: no dirigido, simple, conexo")
    odd = sum(1 for _, degree in graph.degree if degree % 2 == 1)
    print(f"nodos de grado impar: {odd}")
    print(f"nodos: {graph.number_of_nodes()}  aristas: {graph.number_of_edges()}")


def _check_priority_shares(frame: pd.DataFrame) -> None:
    shares = frame[LABEL].value_counts(normalize=True)
    print("prioridad:")
    print(shares.round(3).to_string())
    for name, target in config.PRIORITY_SHARES.items():
        got = float(shares.get(name, 0.0))
        if abs(got - target) > SHARE_TOLERANCE:
            errors.append(f"prioridad {name}: {got:.3f}, esperada {target:.2f} ± {SHARE_TOLERANCE}")


def _check_zones(frame: pd.DataFrame) -> None:
    shares = frame["tipo_zona"].value_counts(normalize=True)
    print("tipo_zona:")
    print(shares.round(3).to_string())
    unknown = set(shares.index) - set(config.ZONE_TYPES)
    if unknown:
        errors.append(f"tipo_zona fuera de {config.ZONE_TYPES}: {unknown}")
    for name in config.ZONE_TYPES:
        got = float(shares.get(name, 0.0))
        if got < config.ZONE_MIN_SHARE_WARN:
            warnings.append(f"advertencia: tipo_zona={name} es {got:.1%} (< {config.ZONE_MIN_SHARE_WARN:.0%})")


def _check_numeric(frame: pd.DataFrame) -> None:
    columns = [
        "cantidad_contenedores",
        "dias_desde_ultima_recoleccion",
        "historico_quejas_vecinales",
        "distancia_m",
    ]
    print(frame[columns].describe().round(2).to_string())
    if (frame["dias_desde_ultima_recoleccion"] < 0).any() or (frame["dias_desde_ultima_recoleccion"] > config.DAYS_MAX).any():
        errors.append(f"dias_desde_ultima_recoleccion fuera de 0–{config.DAYS_MAX}")
    if (frame["historico_quejas_vecinales"] < 0).any() or (frame["cantidad_contenedores"] < 0).any():
        errors.append("conteos negativos")
    if (frame["distancia_m"] <= 0).any():
        errors.append("hay tramos con distancia <= 0")


def _sanity_model(frame: pd.DataFrame) -> None:
    model_frame = frame[FEATURES + [LABEL]].dropna()
    transformer = ColumnTransformer(
        [("zona", OneHotEncoder(handle_unknown="ignore"), ["tipo_zona"])],
        remainder="passthrough",
    )
    clf = Pipeline(
        [
            ("prep", transformer),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=config.VALIDATION_RF_TREES,
                    random_state=config.SEED,
                    n_jobs=1,
                ),
            ),
        ]
    )
    train, test = train_test_split(
        model_frame,
        test_size=config.VALIDATION_TEST_SIZE,
        random_state=config.SEED,
        stratify=model_frame[LABEL],
    )
    clf.fit(train[FEATURES], train[LABEL])
    predicted = clf.predict(test[FEATURES])
    accuracy = float((predicted == test[LABEL].to_numpy()).mean())
    labels = ["alta", "media", "baja"]
    matrix = pd.crosstab(
        pd.Series(test[LABEL].to_numpy(), name="real"),
        pd.Series(predicted, name="predicho"),
    ).reindex(index=labels, columns=labels, fill_value=0)
    print(f"sanity RandomForest accuracy: {accuracy:.3f}")
    print(matrix.to_string())
    if accuracy > config.VALIDATION_ACCURACY_WARN_HIGH:
        warnings.append(f"advertencia: accuracy {accuracy:.3f} > {config.VALIDATION_ACCURACY_WARN_HIGH} (etiqueta demasiado determinística)")
    if accuracy < config.VALIDATION_ACCURACY_WARN_LOW:
        warnings.append(f"advertencia: accuracy {accuracy:.3f} < {config.VALIDATION_ACCURACY_WARN_LOW} (demasiado ruido)")


def _check_reproducible(frame: pd.DataFrame) -> None:
    base = frame.drop(columns=["dias_desde_ultima_recoleccion", "historico_quejas_vecinales", LABEL])
    first = synthesize(base, seed=config.SEED)
    second = synthesize(base, seed=config.SEED)
    same = first[FEATURES[1:] + [LABEL]].equals(second[FEATURES[1:] + [LABEL]])
    if not same:
        errors.append("la parte sintética no es reproducible con la misma semilla")
    else:
        print(f"reproducible con SEED={config.SEED}")


if __name__ == "__main__":
    main()
