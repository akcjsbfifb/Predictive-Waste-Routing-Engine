"""Casos chicos de Dijkstra, Hierholzer y el cartero chino."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.routing.dijkstra import dijkstra, reconstruir
from backend.routing.hierholzer import hierholzer
from backend.routing.postman import Calle, circuito


def _calle(tramo_id: int, u: int, v: int, distancia_m: float) -> Calle:
    return Calle(tramo_id, u, v, distancia_m)


class DijkstraTest(unittest.TestCase):
    def test_elige_el_camino_corto(self) -> None:
        adj = {
            1: [(2, 5.0), (3, 1.0)],
            2: [(1, 5.0), (4, 1.0)],
            3: [(1, 1.0), (4, 1.0)],
            4: [(2, 1.0), (3, 1.0)],
        }
        dist, prev = dijkstra(adj, 1, [4])
        self.assertEqual(dist[4], 2.0)
        self.assertEqual(reconstruir(prev, 4), [1, 3, 4])


class HierholzerTest(unittest.TestCase):
    def test_dos_triangulos_que_comparten_un_vertice(self) -> None:
        aristas = [(0, 1), (1, 2), (2, 0), (0, 3), (3, 4), (4, 0)]
        circuito = hierholzer(aristas)
        self.assertEqual(circuito[0], circuito[-1])
        self.assertEqual(len(circuito), len(aristas) + 1)
        usadas = {tuple(sorted(par)) for par in zip(circuito, circuito[1:])}
        self.assertEqual(usadas, {tuple(sorted(arista)) for arista in aristas})


class PostmanTest(unittest.TestCase):
    def test_triangulo_ya_euleriano(self) -> None:
        calles = [
            _calle(1, 0, 1, 3),
            _calle(2, 1, 2, 4),
            _calle(3, 2, 0, 5),
        ]
        resultado = circuito(calles, {1, 2, 3})
        self.assertEqual(resultado.impares, 0)
        self.assertEqual(resultado.componentes, 1)
        self.assertEqual(resultado.agregadas, 0)
        self.assertEqual(resultado.costo_m, 12)
        self.assertEqual(resultado.repetidos, 0)
        self.assertEqual(resultado.pasos[0].u, resultado.pasos[-1].v)

    def test_cuadrado_con_diagonal(self) -> None:
        # Grados impares en A y C. Se duplica la diagonal.
        calles = [
            _calle(1, 0, 1, 1),
            _calle(2, 1, 2, 1),
            _calle(3, 2, 3, 1),
            _calle(4, 3, 0, 1),
            _calle(5, 0, 2, 1),
        ]
        resultado = circuito(calles, {1, 2, 3, 4, 5})
        self.assertEqual(resultado.impares, 2)
        self.assertEqual(resultado.costo_m, 6)
        self.assertEqual(resultado.repetidos, 1)
        self.assertEqual(sum(1 for paso in resultado.pasos if paso.tramo_id == 5), 2)

    def test_dos_componentes_se_unen_por_el_atajo(self) -> None:
        # AB y CD hay que cubrirlas. AC y BD son más cortas que duplicar AB y CD.
        calles = [
            _calle(1, 0, 1, 10),
            _calle(2, 2, 3, 10),
            _calle(3, 0, 2, 1),
            _calle(4, 1, 3, 1),
        ]
        resultado = circuito(calles, {1, 2})
        self.assertEqual(resultado.componentes, 2)
        self.assertEqual(resultado.costo_m, 22)
        self.assertEqual(resultado.repetidos, 0)
        self.assertEqual({paso.tramo_id for paso in resultado.pasos}, {1, 2, 3, 4})

    def test_componente_euleriana_aislada_se_une_ida_y_vuelta(self) -> None:
        # Triángulo ya euleriano, más un tramo suelto DE. El enlace AD se recorre dos veces.
        calles = [
            _calle(1, 0, 1, 1),
            _calle(2, 1, 2, 1),
            _calle(3, 2, 0, 1),
            _calle(4, 3, 4, 5),
            _calle(5, 0, 3, 2),
        ]
        resultado = circuito(calles, {1, 2, 3, 4})
        self.assertEqual(resultado.componentes, 2)
        self.assertEqual(resultado.costo_m, 17)
        self.assertEqual(sum(1 for paso in resultado.pasos if paso.tramo_id == 5), 2)
        self.assertEqual(sum(1 for paso in resultado.pasos if paso.tramo_id == 4), 2)


if __name__ == "__main__":
    unittest.main()
