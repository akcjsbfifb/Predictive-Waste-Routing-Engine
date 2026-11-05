"""Entrena el SVM una vez y lo guarda en data/processed/svm.joblib.

Mismo corte que el notebook: 20 % de test, stratify, random_state=42.
Se ajusta solo con el train. El test se mira para comprobar que el
archivo coincide con el notebook (accuracy 0,829 y F1 macro 0,821).

Correr desde la raíz, con el venv ya instalado:

    python -m backend.model.train
"""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from backend.model.pipeline import COLUMNAS, OBJETIVO, pipeline_svm

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "processed" / "svm.joblib"


def main() -> None:
    tramos = pd.read_csv(RAIZ / "data" / "processed" / "tramos.csv")
    X = tramos[COLUMNAS].copy()
    y = tramos[OBJETIVO].copy()
    if X.isna().any().any():
        raise SystemExit("Hay nulos en las columnas del modelo y no imputamos.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )
    modelo = pipeline_svm()
    modelo.fit(X_train, y_train)
    predicho = modelo.predict(X_test)
    accuracy = accuracy_score(y_test, predicho)
    f1 = f1_score(y_test, predicho, average="macro")
    if round(accuracy, 3) != 0.829 or round(f1, 3) != 0.821:
        raise SystemExit(
            f"el test no coincide con el notebook: accuracy {accuracy:.3f} f1 {f1:.3f}"
        )

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, SALIDA)
    conteo = pd.Series(modelo.predict(X)).value_counts().to_dict()
    print(f"train: {len(X_train)}  test: {len(X_test)}")
    print(f"test accuracy {accuracy:.3f}  f1 macro {f1:.3f}")
    print(f"predicción sobre el CSV: {conteo}")
    print(f"modelo: {SALIDA}")


if __name__ == "__main__":
    main()
