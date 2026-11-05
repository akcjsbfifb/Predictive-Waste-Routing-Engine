"""El API predice con el SVM guardado y no reescribe el CSV."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CSV = ROOT / "data" / "processed" / "tramos.csv"


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._dir = tempfile.TemporaryDirectory()
        os.environ["SQLITE_PATH"] = str(Path(cls._dir.name) / "overrides.sqlite")
        cls._csv = hashlib.sha256(CSV.read_bytes()).hexdigest()
        from fastapi.testclient import TestClient

        from backend.api.main import app

        cls._cm = TestClient(app)
        cls.client = cls._cm.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._cm.__exit__(None, None, None)
        cls._dir.cleanup()
        os.environ.pop("SQLITE_PATH", None)

    def test_tramos_edicion_y_circuito(self) -> None:
        lista = self.client.get("/tramos")
        self.assertEqual(lista.status_code, 200)
        tramos = lista.json()
        self.assertEqual(len(tramos), 1257)
        primero = tramos[0]
        self.assertIn(primero["prioridad"], {"alta", "media", "baja"})
        self.assertGreaterEqual(len(primero["geometria"]), 2)
        self.assertEqual(len(primero["geometria"][0]), 2)

        malo = self.client.patch("/tramos/999999", json=_cuerpo(primero))
        self.assertEqual(malo.status_code, 404)

        invalido = _cuerpo(primero)
        invalido["tipo_zona"] = "rural"
        self.assertEqual(self.client.patch(f"/tramos/{primero['tramo_id']}", json=invalido).status_code, 422)

        de_mas = _cuerpo(primero)
        de_mas["distancia_m"] = 1
        self.assertEqual(self.client.patch(f"/tramos/{primero['tramo_id']}", json=de_mas).status_code, 422)

        editado = _cuerpo(primero)
        editado["dias_desde_ultima_recoleccion"] = 9
        editado["cantidad_contenedores"] = 4
        editado["historico_quejas_vecinales"] = 3
        editado["tipo_zona"] = "comercial"
        editado["cerca_escuela_hospital"] = 1
        editado["feria_o_evento"] = 1
        guardado = self.client.patch(f"/tramos/{primero['tramo_id']}", json=editado)
        self.assertEqual(guardado.status_code, 200)
        cuerpo = guardado.json()
        self.assertEqual(cuerpo["dias_desde_ultima_recoleccion"], 9)
        self.assertEqual(cuerpo["feria_o_evento"], 1)
        self.assertEqual(cuerpo["distancia_m"], primero["distancia_m"])

        otra = self.client.get("/tramos")
        fila = next(item for item in otra.json() if item["tramo_id"] == primero["tramo_id"])
        self.assertEqual(fila["dias_desde_ultima_recoleccion"], 9)
        self.assertEqual(fila["tipo_zona"], "comercial")

        recorrido = self.client.post("/recorrido")
        self.assertEqual(recorrido.status_code, 200)
        data = recorrido.json()
        self.assertEqual(len(data["prioridades"]), 1257)
        self.assertGreater(data["costo_m"], 0)
        self.assertAlmostEqual(
            data["costo_m"],
            sum(paso["distancia_m"] for paso in data["pasos"]),
            places=2,
        )
        conteo = Counter(paso["tramo_id"] for paso in data["pasos"])
        self.assertEqual(set(data["repetidos"]), {tramo_id for tramo_id, n in conteo.items() if n > 1})
        altas = {item["tramo_id"] for item in data["prioridades"] if item["prioridad"] == "alta"}
        self.assertTrue(altas)
        self.assertTrue(altas <= set(conteo))
        for paso in data["pasos"]:
            self.assertEqual(set(paso["sentido"]), {"desde", "hasta"})
            self.assertIsInstance(paso["agregado"], bool)
            self.assertGreater(paso["distancia_m"], 0)
            self.assertGreaterEqual(len(paso["geometria"]), 2)

        self.assertEqual(hashlib.sha256(CSV.read_bytes()).hexdigest(), self._csv)


def _cuerpo(tramo: dict) -> dict:
    return {
        "dias_desde_ultima_recoleccion": tramo["dias_desde_ultima_recoleccion"],
        "cantidad_contenedores": tramo["cantidad_contenedores"],
        "historico_quejas_vecinales": tramo["historico_quejas_vecinales"],
        "tipo_zona": tramo["tipo_zona"],
        "cerca_escuela_hospital": tramo["cerca_escuela_hospital"],
        "feria_o_evento": tramo["feria_o_evento"],
    }


if __name__ == "__main__":
    unittest.main()
