"""Invariantes de dominio sintético: quejas > 0 y días > 0 solo si hay contenedor en el tramo."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.dataset.synthesize import synthesize


class SynthesizeInvariantTest(unittest.TestCase):
    def test_quejas_cero_si_cero_contenedores(self) -> None:
        """Poisson(0) en tramos sin contenedor; filas con contenedor pueden tener quejas."""
        n = 500
        rng = np.random.default_rng(0)
        zones = rng.choice(["residencial", "comercial", "industrial"], size=n)
        frame = pd.DataFrame(
            {
                "tipo_zona": zones,
                "cantidad_contenedores": np.zeros(n, dtype=int),
            }
        )
        out = synthesize(frame, seed=123)
        self.assertTrue((out["historico_quejas_vecinales"] == 0).all())

    def test_dias_cero_si_cero_contenedores(self) -> None:
        n = 500
        rng = np.random.default_rng(0)
        zones = rng.choice(["residencial", "comercial", "industrial"], size=n)
        frame = pd.DataFrame(
            {
                "tipo_zona": zones,
                "cantidad_contenedores": np.zeros(n, dtype=int),
            }
        )
        out = synthesize(frame, seed=123)
        self.assertTrue((out["dias_desde_ultima_recoleccion"] == 0).all())

    def test_dias_al_menos_uno_si_hay_contenedores(self) -> None:
        n = 500
        rng = np.random.default_rng(1)
        zones = rng.choice(["residencial", "comercial", "industrial"], size=n)
        frame = pd.DataFrame(
            {
                "tipo_zona": zones,
                "cantidad_contenedores": rng.integers(1, 8, size=n),
            }
        )
        out = synthesize(frame, seed=123)
        mask = out["cantidad_contenedores"] > 0
        self.assertTrue((out.loc[mask, "dias_desde_ultima_recoleccion"] >= 1).all())

    def test_quejas_al_menos_uno_si_hay_contenedores(self) -> None:
        n = 500
        rng = np.random.default_rng(2)
        zones = rng.choice(["residencial", "comercial", "industrial"], size=n)
        frame = pd.DataFrame(
            {
                "tipo_zona": zones,
                "cantidad_contenedores": rng.integers(1, 8, size=n),
            }
        )
        out = synthesize(frame, seed=123)
        mask = out["cantidad_contenedores"] > 0
        self.assertTrue((out.loc[mask, "historico_quejas_vecinales"] >= 1).all())

    def test_dataset_tramos_csv_si_existe(self) -> None:
        path = ROOT / "data" / "processed" / "tramos.csv"
        if not path.is_file():
            self.skipTest("sin tramos.csv")
        df = pd.read_csv(path)
        bad_q = (df["historico_quejas_vecinales"] > 0) & (df["cantidad_contenedores"] <= 0)
        self.assertEqual(int(bad_q.sum()), 0, msg=f"quejas sin contenedor: {int(bad_q.sum())}")
        bad_d = (df["dias_desde_ultima_recoleccion"] > 0) & (df["cantidad_contenedores"] <= 0)
        self.assertEqual(int(bad_d.sum()), 0, msg=f"dias sin contenedor: {int(bad_d.sum())}")


if __name__ == "__main__":
    unittest.main()
