"use client";

import { memo, useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { parseColor } from "@/components/ui/color-picker";
import type { Paso, Prioridad, Recorrido, Tramo } from "./tipos";

const COLOR: Record<Prioridad, string> = {
  alta: "#111111",
  media: "#ff7a00",
  baja: "#8a847c",
};

const ALREDEDOR = L.latLngBounds([
  [-34.62, -58.41],
  [-34.582, -58.355],
]);

const Calles = memo(function Calles({
  tramos,
  onSelect,
}: {
  tramos: Tramo[];
  onSelect: (tramoId: number) => void;
}) {
  return (
    <>
      {tramos.map((tramo) => (
        <Polyline
          key={tramo.tramo_id}
          positions={tramo.geometria}
          smoothFactor={0}
          pathOptions={{
            color: COLOR[tramo.prioridad] ?? COLOR.baja,
            weight: tramo.prioridad === "alta" ? 5.5 : 4.5,
            opacity: 1,
            className: "calle",
          }}
          eventHandlers={{ click: () => onSelect(tramo.tramo_id) }}
        />
      ))}
    </>
  );
});

const Vertices = memo(function Vertices({ tramos }: { tramos: Tramo[] }) {
  const puntos = useMemo(() => {
    const vistos = new Set<string>();
    const lista: [number, number][] = [];
    for (const tramo of tramos) {
      const extremos = [tramo.geometria[0], tramo.geometria[tramo.geometria.length - 1]];
      for (const punto of extremos) {
        if (!punto) continue;
        const clave = `${punto[0].toFixed(6)},${punto[1].toFixed(6)}`;
        if (vistos.has(clave)) continue;
        vistos.add(clave);
        lista.push(punto);
      }
    }
    return lista;
  }, [tramos]);

  return (
    <>
      {puntos.map((punto) => (
        <CircleMarker
          key={`${punto[0]},${punto[1]}`}
          center={punto}
          radius={2.5}
          interactive={false}
          pathOptions={{ color: "#ffffff", weight: 1.5, fillColor: "#111111", fillOpacity: 1 }}
        />
      ))}
    </>
  );
});

function opcionesCircuito(colorCircuito: string): { color: string; opacity: number; weight: number } {
  try {
    const c = parseColor(colorCircuito);
    const alpha = c.getChannelValue("alpha");
    return {
      color: c.toString("hex"),
      opacity: typeof alpha === "number" && Number.isFinite(alpha) ? alpha : 1,
      weight: 2.5,
    };
  } catch {
    return { color: "#1d4ed8", opacity: 0.95, weight: 2.5 };
  }
}

const CircuitoCapa = memo(function CircuitoCapa({
  pasos,
  colorCircuito,
}: {
  pasos: Paso[];
  colorCircuito: string;
}) {
  const pathOptions = useMemo(() => opcionesCircuito(colorCircuito), [colorCircuito]);
  return (
    <>
      {pasos.map((paso, indice) => (
        <Polyline
          key={`${indice}-${paso.tramo_id}`}
          positions={paso.geometria}
          smoothFactor={0}
          interactive={false}
          pathOptions={pathOptions}
        />
      ))}
    </>
  );
});

const RepetidosCapa = memo(function RepetidosCapa({
  pasos,
  repetidos,
}: {
  pasos: Paso[];
  repetidos: number[];
}) {
  const lineas = useMemo(() => {
    const marca = new Set(repetidos);
    const vistos = new Set<number>();
    const unicos: Paso[] = [];
    for (const paso of pasos) {
      if (!marca.has(paso.tramo_id) || vistos.has(paso.tramo_id)) continue;
      vistos.add(paso.tramo_id);
      unicos.push(paso);
    }
    return unicos;
  }, [pasos, repetidos]);
  return (
    <>
      {lineas.map((paso) => (
        <Polyline
          key={paso.tramo_id}
          positions={paso.geometria}
          smoothFactor={0}
          interactive={false}
          pathOptions={{ color: "#7c3aed", weight: 6, opacity: 1 }}
        />
      ))}
    </>
  );
});

function caja(tramos: Tramo[]): L.LatLngBounds {
  const bounds = L.latLngBounds(tramos[0].geometria);
  for (const tramo of tramos) {
    for (const punto of tramo.geometria) bounds.extend(punto);
  }
  return bounds;
}

function Limites({ tramos }: { tramos: Tramo[] }) {
  const map = useMap();
  const listo = useRef(false);
  useEffect(() => {
    if (listo.current || tramos.length === 0) return;
    const aplicar = () => {
      if (map.getSize().y < 40) return;
      const zona = caja(tramos);
      const alrededor = zona.pad(0.4);
      map.setMaxBounds(alrededor);
      map.fitBounds(zona, { padding: [20, 20], animate: false });
      map.setMinZoom(map.getZoom());
      listo.current = true;
    };
    aplicar();
    if (!listo.current) map.once("resize", aplicar);
  }, [map, tramos]);
  return null;
}

export default function Mapa({
  tramos,
  seleccionado,
  recorrido,
  paso,
  verCircuito,
  verRepetidos,
  colorCircuito,
  onSelect,
}: {
  tramos: Tramo[];
  seleccionado: number | null;
  recorrido: Recorrido | null;
  paso: number;
  verCircuito: boolean;
  verRepetidos: boolean;
  colorCircuito: string;
  onSelect: (tramoId: number) => void;
}) {
  const limites = useMemo(
    () => (tramos.length === 0 ? ALREDEDOR : caja(tramos).pad(0.4)),
    [tramos],
  );
  const elegido = tramos.find((item) => item.tramo_id === seleccionado) ?? null;
  const actual = recorrido?.pasos[paso];

  return (
    <MapContainer
      center={[-34.6015, -58.3818]}
      zoom={15}
      minZoom={14}
      maxZoom={18}
      maxBounds={ALREDEDOR}
      maxBoundsViscosity={1}
      zoomControl
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        noWrap
        bounds={limites}
      />
      <Limites tramos={tramos} />
      <Calles tramos={tramos} onSelect={onSelect} />
      {recorrido && verCircuito && (
        <CircuitoCapa pasos={recorrido.pasos} colorCircuito={colorCircuito} />
      )}
      {recorrido && verRepetidos && <RepetidosCapa pasos={recorrido.pasos} repetidos={recorrido.repetidos} />}
      <Vertices tramos={tramos} />
      {elegido && (
        <>
          <Polyline
            positions={elegido.geometria}
            smoothFactor={0}
            interactive={false}
            pathOptions={{ color: "#ffffff", weight: 11, opacity: 1 }}
          />
          <Polyline
            positions={elegido.geometria}
            smoothFactor={0}
            interactive={false}
            pathOptions={{ color: COLOR[elegido.prioridad] ?? COLOR.baja, weight: 6.5, opacity: 1 }}
          />
        </>
      )}
      {actual && (
        <>
          <Polyline
            positions={actual.geometria}
            smoothFactor={0}
            interactive={false}
            pathOptions={{ color: "#111111", weight: 12, opacity: 1 }}
          />
          <Polyline
            positions={actual.geometria}
            smoothFactor={0}
            interactive={false}
            pathOptions={{ color: "#ffffff", weight: 5, opacity: 1 }}
          />
        </>
      )}
    </MapContainer>
  );
}
