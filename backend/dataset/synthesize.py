"""Variables sintéticas y etiqueta de prioridad. Toda fórmula está en config."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend import config


def synthesize(frame: pd.DataFrame, seed: int | None = None) -> pd.DataFrame:
    """Agrega días, quejas y prioridad. No modifica las columnas reales.

    La etiqueta sale de un score con ruido y un corte por cantidad de filas,
    así las proporciones quedan cerca de `PRIORITY_SHARES` y no hay una regla
    cerrada que reconstruya la clase.
    """
    seed = config.SEED if seed is None else seed
    rng = np.random.default_rng(seed)
    out = frame.copy()
    zones = out["tipo_zona"].astype(str)
    containers = out["cantidad_contenedores"].to_numpy(dtype=float)

    day_lambda = np.array([config.DAYS_POISSON_LAM[zone] for zone in zones])
    day_lambda = day_lambda + config.DAYS_CONTAINER_BUMP * containers
    days = rng.poisson(day_lambda)
    days = np.clip(days, 0, config.DAYS_MAX).astype(int)
    # Dominio: sin contenedor mapeado no hay "días desde última recolección" medible aquí.
    days = np.where(containers > 0, days, 0).astype(int)
    has_container = containers > 0

    complaint_lambda = np.exp(
        config.COMPLAINTS_INTERCEPT
        + config.COMPLAINTS_COEF_CONTAINERS * np.log1p(containers)
        + config.COMPLAINTS_COEF_DAYS * days
        + np.array([config.COMPLAINTS_ZONE[zone] for zone in zones])
    )
    # Dominio: quejas vecinales solo sobre tramos con al menos un contenedor mapeado.
    # Sin esto, intercept + días + zona bastan para Poisson > 0 con contenedores = 0.
    complaint_lambda = np.where(has_container, complaint_lambda, 0.0)
    complaints = rng.poisson(complaint_lambda).astype(int)
    # Con contenedor, días y quejas no pueden quedar en 0 tras Poisson.
    days = np.where(has_container & (days < 1), 1, days).astype(int)
    complaints = np.where(has_container & (complaints < 1), 1, complaints).astype(int)

    zone_weight = np.array([config.PRIORITY_WEIGHTS["zona"][zone] for zone in zones])
    log_containers = np.log1p(containers)
    signal = (
        config.PRIORITY_WEIGHTS["dias"] * days
        + config.PRIORITY_WEIGHTS["contenedores"] * log_containers
        + config.PRIORITY_WEIGHTS["quejas"] * np.log1p(complaints)
        + zone_weight
        + config.PRIORITY_WEIGHTS["interaccion_dias_contenedores"] * days * log_containers
    )
    noise = rng.normal(0.0, config.PRIORITY_NOISE_SIGMA, size=len(out))
    priority = _priority_from_score(signal + noise)

    out["dias_desde_ultima_recoleccion"] = days
    out["historico_quejas_vecinales"] = complaints
    out["prioridad_recoleccion"] = priority
    return out


def _priority_from_score(score: np.ndarray) -> np.ndarray:
    n = len(score)
    n_alta = int(round(config.PRIORITY_SHARES["alta"] * n))
    n_media = int(round(config.PRIORITY_SHARES["media"] * n))
    if n_alta + n_media > n:
        n_media = n - n_alta
    order = np.argsort(-score, kind="mergesort")
    labels = np.empty(n, dtype=object)
    labels[order[:n_alta]] = "alta"
    labels[order[n_alta : n_alta + n_media]] = "media"
    labels[order[n_alta + n_media :]] = "baja"
    return labels
