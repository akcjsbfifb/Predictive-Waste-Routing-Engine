"""Mapa estático para mirar el circuito. No es el frontend del trabajo."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from backend.routing.postman import Circuito

_ANCHO = 1100.0


def escribir_mapa(
    path: Path,
    circuito: Circuito,
    frame: pd.DataFrame,
    coordenadas: dict[int, tuple[float, float]],
    geometria: dict[int, list[tuple[float, float]]],
    columna: str,
    prioridades: tuple[str, ...],
) -> None:
    tabla = frame.set_index("tramo_id")
    proyectar, ancho, alto = _proyector(geometria)
    calles = []
    for tramo_id, puntos in geometria.items():
        fila = tabla.loc[tramo_id]
        calles.append(
            {
                "id": int(tramo_id),
                "prioridad": str(fila[columna]),
                "nombre": _texto(fila["nombre_calle"]),
                "zona": str(fila["tipo_zona"]),
                "puntos": [proyectar(lat, lon) for lat, lon in puntos],
            }
        )
    visitas: dict[int, int] = {}
    pasos = []
    for paso in circuito.pasos:
        visitas[paso.tramo_id] = visitas.get(paso.tramo_id, 0) + 1
        fila = tabla.loc[paso.tramo_id]
        puntos = _orientar(geometria[paso.tramo_id], coordenadas, paso.u)
        nombre = _texto(fila["nombre_calle"])
        pasos.append(
            {
                "id": paso.tramo_id,
                "nombre": nombre or "sin nombre",
                "prioridad": str(fila[columna]),
                "zona": str(fila["tipo_zona"]),
                "metros": round(paso.distancia_m, 2),
                "agregado": paso.agregado,
                "visita": visitas[paso.tramo_id],
                "puntos": [proyectar(lat, lon) for lat, lon in puntos],
            }
        )
    repetidos = sorted(tramo_id for tramo_id, cantidad in visitas.items() if cantidad > 1)
    datos = {
        "calles": calles,
        "pasos": pasos,
        "repetidos": repetidos,
        "prioridades": list(prioridades),
        "costo": round(circuito.costo_m, 1),
        "extra": round(circuito.costo_m - circuito.costo_cubrir_m, 1),
        "cubrir": round(circuito.costo_cubrir_m, 1),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_html(datos, ancho, alto), encoding="utf-8")


def _proyector(geometria: dict[int, list[tuple[float, float]]]):
    puntos = [punto for trazo in geometria.values() for punto in trazo]
    lats = [lat for lat, _ in puntos]
    lons = [lon for _, lon in puntos]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    coseno = math.cos(math.radians((min_lat + max_lat) / 2))
    span_x = max((max_lon - min_lon) * coseno, 1e-9)
    span_y = max(max_lat - min_lat, 1e-9)
    escala = _ANCHO / span_x
    alto = span_y * escala

    def proyectar(lat: float, lon: float) -> list[float]:
        x = (lon - min_lon) * coseno * escala
        y = (max_lat - lat) * escala
        return [round(x, 1), round(y, 1)]

    return proyectar, _ANCHO, alto


def _texto(valor: object) -> str:
    if valor is None or pd.isna(valor):
        return ""
    return str(valor)


def _orientar(
    puntos: list[tuple[float, float]],
    coordenadas: dict[int, tuple[float, float]],
    origen: int,
) -> list[tuple[float, float]]:
    """La geometría queda en el sentido de marcha, desde `origen`."""
    lat, lon = coordenadas[origen]
    primero, ultimo = puntos[0], puntos[-1]
    if (primero[0] - lat) ** 2 + (primero[1] - lon) ** 2 <= (ultimo[0] - lat) ** 2 + (ultimo[1] - lon) ** 2:
        return list(puntos)
    return list(reversed(puntos))


def _html(datos: dict, ancho: float, alto: float) -> str:
    payload = json.dumps(datos, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Recorrido</title>
<style>
  body {{ margin: 0; font: 15px/1.4 system-ui, sans-serif; color: #1c1917; background: #f6f4ef; }}
  main {{ display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; }}
  aside {{ padding: 20px 18px; border-right: 1px solid #e4dfd6; }}
  h1 {{ font-size: 18px; font-weight: 600; margin: 0 0 8px; }}
  p {{ margin: 0 0 10px; }}
  .numero {{ font-variant-numeric: tabular-nums; }}
  ul {{ list-style: none; padding: 0; margin: 12px 0; }}
  li {{ display: flex; gap: 8px; align-items: center; margin: 4px 0; }}
  i {{ width: 18px; height: 4px; display: inline-block; }}
  .alta {{ background: #d4532b; }}
  .media {{ background: #e09a3e; }}
  .baja {{ background: #c4c1bb; }}
  .repite {{ background: #6d28d9; }}
  .actual {{ background: #1c1917; }}
  label {{ display: block; margin: 14px 0 6px; }}
  input[type=range] {{ width: 100%; }}
  .botones {{ display: flex; gap: 8px; margin-top: 8px; }}
  button {{ font: inherit; padding: 4px 10px; }}
  svg {{ width: 100%; height: calc(100vh - 16px); margin: 8px 0; background: #fbfaf7; }}
</style>
</head>
<body>
<main>
  <aside>
    <h1>Recorrido</h1>
    <p>Vista para revisar el circuito. No es el frontend.</p>
    <p>A cubrir <span class="numero" id="cubrir"></span> m</p>
    <p>Circuito <span class="numero" id="costo"></span> m</p>
    <p>De más <span class="numero" id="extra"></span> m</p>
    <ul>
      <li><i class="alta"></i> alta</li>
      <li><i class="media"></i> media</li>
      <li><i class="baja"></i> baja</li>
      <li><i class="repite"></i> más de una vez</li>
      <li><i class="actual"></i> paso actual</li>
    </ul>
    <label for="paso">Paso <span class="numero" id="indice"></span></label>
    <input id="paso" type="range" min="0" value="0">
    <div class="botones">
      <button type="button" id="atras">Anterior</button>
      <button type="button" id="adelante">Siguiente</button>
    </div>
    <p id="detalle"></p>
  </aside>
  <svg id="mapa" viewBox="0 0 {ancho:.1f} {alto:.1f}" xmlns="http://www.w3.org/2000/svg"></svg>
</main>
<script id="datos" type="application/json">{payload}</script>
<script>
const datos = JSON.parse(document.getElementById("datos").textContent);
const svg = document.getElementById("mapa");
const ns = "http://www.w3.org/2000/svg";
const color = {{ alta: "#d4532b", media: "#e09a3e", baja: "#c4c1bb" }};
const repetidos = new Set(datos.repetidos);

function trazo(puntos, ancho, tinta) {{
  const linea = document.createElementNS(ns, "polyline");
  linea.setAttribute("points", puntos.map(p => p.join(",")).join(" "));
  linea.setAttribute("fill", "none");
  linea.setAttribute("stroke", tinta);
  linea.setAttribute("stroke-width", ancho);
  linea.setAttribute("stroke-linecap", "round");
  linea.setAttribute("stroke-linejoin", "round");
  svg.appendChild(linea);
  return linea;
}}

for (const calle of datos.calles) {{
  trazo(calle.puntos, calle.prioridad === "baja" ? 1.4 : 2.2, color[calle.prioridad] || "#a8a29e");
}}
for (const calle of datos.calles) {{
  if (repetidos.has(calle.id)) trazo(calle.puntos, 3.2, "#6d28d9");
}}
const cursor = trazo(datos.pasos[0].puntos, 4.4, "#1c1917");

const rango = document.getElementById("paso");
rango.max = String(datos.pasos.length - 1);
document.getElementById("cubrir").textContent = datos.cubrir.toLocaleString("es-AR");
document.getElementById("costo").textContent = datos.costo.toLocaleString("es-AR");
document.getElementById("extra").textContent = datos.extra.toLocaleString("es-AR");

function mostrar(indice) {{
  const paso = datos.pasos[indice];
  cursor.setAttribute("points", paso.puntos.map(p => p.join(",")).join(" "));
  document.getElementById("indice").textContent = (indice + 1) + " / " + datos.pasos.length;
  const extra = paso.agregado ? ", copia agregada" : "";
  document.getElementById("detalle").textContent =
    paso.nombre + " · " + paso.prioridad + " · " + paso.zona +
    " · " + paso.metros + " m · visita " + paso.visita + extra;
}}

rango.addEventListener("input", () => mostrar(Number(rango.value)));
document.getElementById("atras").addEventListener("click", () => {{
  rango.value = String(Math.max(0, Number(rango.value) - 1));
  mostrar(Number(rango.value));
}});
document.getElementById("adelante").addEventListener("click", () => {{
  rango.value = String(Math.min(datos.pasos.length - 1, Number(rango.value) + 1));
  mostrar(Number(rango.value));
}});
document.addEventListener("keydown", (evento) => {{
  if (evento.key === "ArrowRight") document.getElementById("adelante").click();
  if (evento.key === "ArrowLeft") document.getElementById("atras").click();
}});
mostrar(0);
</script>
</body>
</html>
"""
