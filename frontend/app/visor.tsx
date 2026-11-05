"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CAMPOS, type Edicion, type Prioridad, type Recorrido, type Tramo } from "./tipos";

const Mapa = dynamic(() => import("./mapa"), {
  ssr: false,
  loading: () => <div className="mapa-vacio">Cargando mapa…</div>,
});

const ZONAS = ["residencial", "comercial", "industrial"];

function metros(valor: number): string {
  return `${new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 }).format(valor)} m`;
}

function edicionDe(tramo: Tramo): Edicion {
  return {
    dias_desde_ultima_recoleccion: tramo.dias_desde_ultima_recoleccion,
    cantidad_contenedores: tramo.cantidad_contenedores,
    historico_quejas_vecinales: tramo.historico_quejas_vecinales,
    tipo_zona: tramo.tipo_zona,
    cerca_escuela_hospital: tramo.cerca_escuela_hospital,
    feria_o_evento: tramo.feria_o_evento,
  };
}

async function mensaje(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
  } catch {
    /* el cuerpo no era JSON */
  }
  return "No se pudo completar la operación.";
}

export function Visor() {
  const [tramos, setTramos] = useState<Tramo[]>([]);
  const [seleccionado, setSeleccionado] = useState<number | null>(null);
  const [form, setForm] = useState<Edicion | null>(null);
  const [recorrido, setRecorrido] = useState<Recorrido | null>(null);
  const [paso, setPaso] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [calculando, setCalculando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verCircuito, setVerCircuito] = useState(false);
  const [verRepetidos, setVerRepetidos] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const res = await fetch("/api/tramos", { cache: "no-store" });
      if (!res.ok) throw new Error(await mensaje(res));
      setTramos(await res.json());
    } catch (causa) {
      setError(causa instanceof Error ? causa.message : "No se pudieron cargar las calles.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const tramosRef = useRef(tramos);
  tramosRef.current = tramos;

  const tramo = useMemo(
    () => tramos.find((item) => item.tramo_id === seleccionado) ?? null,
    [tramos, seleccionado],
  );

  const elegir = useCallback((tramoId: number) => {
    const elegido = tramosRef.current.find((item) => item.tramo_id === tramoId);
    setSeleccionado(tramoId);
    if (elegido) setForm(edicionDe(elegido));
  }, []);

  const maxPaso = recorrido ? recorrido.pasos.length - 1 : 0;

  useEffect(() => {
    function tecla(evento: KeyboardEvent) {
      if (!recorrido) return;
      const tag = (evento.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (evento.key === "ArrowRight") setPaso((actual) => Math.min(actual + 1, maxPaso));
      if (evento.key === "ArrowLeft") setPaso((actual) => Math.max(actual - 1, 0));
    }
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [recorrido, maxPaso]);

  const calculandoRef = useRef(false);

  async function recalcular() {
    if (calculandoRef.current) return;
    calculandoRef.current = true;
    setCalculando(true);
    setError(null);
    try {
      if (seleccionado !== null && form) {
        const res = await fetch(`/api/tramos/${seleccionado}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
          body: JSON.stringify(form),
        });
        if (!res.ok) throw new Error(await mensaje(res));
      }
      const res = await fetch("/api/recorrido", { method: "POST", cache: "no-store" });
      if (!res.ok) throw new Error(await mensaje(res));
      const data = (await res.json()) as Recorrido;
      const prioridades = new Map(data.prioridades.map((item) => [item.tramo_id, item.prioridad]));
      setTramos((actuales) =>
        actuales.map((item) => {
          const prioridad = (prioridades.get(item.tramo_id) ?? item.prioridad) as Prioridad;
          if (item.tramo_id === seleccionado && form) return { ...item, ...form, prioridad };
          return { ...item, prioridad };
        }),
      );
      setRecorrido(data);
      setPaso(0);
    } catch (causa) {
      setError(causa instanceof Error ? causa.message : "No se pudo recalcular.");
    } finally {
      calculandoRef.current = false;
      setCalculando(false);
    }
  }

  function alternarCapa(capa: "circuito" | "repetidos") {
    if (capa === "circuito") {
      const siguiente = !verCircuito;
      setVerCircuito(siguiente);
      if (siguiente && !recorrido) void recalcular();
      return;
    }
    const siguiente = !verRepetidos;
    setVerRepetidos(siguiente);
    if (siguiente && !recorrido) void recalcular();
  }

  const actual = recorrido?.pasos[paso];
  const altas = recorrido?.prioridades.filter((item) => item.prioridad === "alta").length ?? 0;
  const repetidos = useMemo(() => new Set(recorrido?.repetidos ?? []), [recorrido]);

  return (
    <main className="app">
      <aside className="panel">
        <h1>Recolección</h1>
        <p className="subtitulo">Microcentro de Buenos Aires. El circuito cubre solo prioridad alta.</p>
        <ul className="leyenda">
          <li><i className="muestra alta" /> alta</li>
          <li><i className="muestra media" /> media</li>
          <li><i className="muestra baja" /> baja</li>
          <li><i className="muestra actual" /> paso actual</li>
        </ul>

        {cargando && <p className="vacio">Cargando calles…</p>}
        {error && (
          <p className="error">
            {error}{" "}
            {tramos.length === 0 && (
              <button type="button" className="secundario" onClick={() => void cargar()}>
                Reintentar
              </button>
            )}
          </p>
        )}

        {!cargando && !tramo && <p className="vacio">Elegí una calle en el mapa para cambiar sus datos.</p>}

        {tramo && form && (
          <form
            onSubmit={(evento) => {
              evento.preventDefault();
              void recalcular();
            }}
          >
            <p className="calle-titulo">{tramo.nombre_calle || `Tramo ${tramo.tramo_id}`}</p>
            <p className="meta">
              {tramo.prioridad} · {metros(tramo.distancia_m)} · la distancia no se edita
            </p>
            <label htmlFor="dias">Días desde la última recolección</label>
            <input
              id="dias"
              type="number"
              min={0}
              step={1}
              value={form.dias_desde_ultima_recoleccion}
              onChange={(evento) =>
                setForm({
                  ...form,
                  dias_desde_ultima_recoleccion: numero(evento.target.value, form.dias_desde_ultima_recoleccion),
                })
              }
            />
            <label htmlFor="contenedores">Contenedores</label>
            <input
              id="contenedores"
              type="number"
              min={0}
              step={1}
              value={form.cantidad_contenedores}
              onChange={(evento) =>
                setForm({
                  ...form,
                  cantidad_contenedores: numero(evento.target.value, form.cantidad_contenedores),
                })
              }
            />
            <label htmlFor="quejas">Quejas vecinales</label>
            <input
              id="quejas"
              type="number"
              min={0}
              step={1}
              value={form.historico_quejas_vecinales}
              onChange={(evento) =>
                setForm({
                  ...form,
                  historico_quejas_vecinales: numero(evento.target.value, form.historico_quejas_vecinales),
                })
              }
            />
            <label htmlFor="zona">Tipo de zona</label>
            <select
              id="zona"
              value={form.tipo_zona}
              onChange={(evento) => setForm({ ...form, tipo_zona: evento.target.value })}
            >
              {ZONAS.map((zona) => (
                <option key={zona} value={zona}>
                  {zona}
                </option>
              ))}
            </select>
            <div className="chequeos">
              <label>
                <input
                  type="checkbox"
                  checked={form.cerca_escuela_hospital === 1}
                  onChange={(evento) =>
                    setForm({ ...form, cerca_escuela_hospital: evento.target.checked ? 1 : 0 })
                  }
                />
                Cerca de escuela u hospital
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={form.feria_o_evento === 1}
                  onChange={(evento) =>
                    setForm({ ...form, feria_o_evento: evento.target.checked ? 1 : 0 })
                  }
                />
                Feria o evento
              </label>
            </div>
            <div className="acciones">
              <button type="submit" disabled={calculando || !entero(form)}>
                {calculando ? "Calculando circuito…" : "Recalcular"}
              </button>
            </div>
          </form>
        )}

        {!tramo && (
          <div className="acciones">
            <button type="button" disabled={calculando || tramos.length === 0} onClick={() => void recalcular()}>
              {calculando ? "Calculando circuito…" : "Recalcular"}
            </button>
          </div>
        )}

        {recorrido && actual && (
          <section className="resultado">
            <h2>Circuito</h2>
            <p className="costo">{metros(recorrido.costo_m)}</p>
            <p className="meta">
              {altas} calles altas · {recorrido.pasos.length} pasos · {recorrido.repetidos.length} tramos
              más de una vez
            </p>
            <div className="paso-ctrl">
              <label htmlFor="paso">
                Paso {paso + 1} de {recorrido.pasos.length}
              </label>
              <input
                id="paso"
                type="range"
                min={0}
                max={maxPaso}
                value={paso}
                onChange={(evento) => setPaso(Number(evento.target.value))}
              />
              <div className="botones">
                <button
                  type="button"
                  className="secundario"
                  onClick={() => setPaso((actualPaso) => Math.max(actualPaso - 1, 0))}
                >
                  Anterior
                </button>
                <button
                  type="button"
                  className="secundario"
                  onClick={() => setPaso((actualPaso) => Math.min(actualPaso + 1, maxPaso))}
                >
                  Siguiente
                </button>
              </div>
              <p className="detalle">
                {actual.nombre_calle || `Tramo ${actual.tramo_id}`} · {metros(actual.distancia_m)}
                {actual.agregado ? " · copia agregada" : ""}
                {repetidos.has(actual.tramo_id) ? " · se recorre más de una vez" : ""}
              </p>
            </div>
          </section>
        )}
      </aside>
      <div className="mapa">
        <Mapa
          tramos={tramos}
          seleccionado={seleccionado}
          recorrido={recorrido}
          paso={paso}
          verCircuito={verCircuito}
          verRepetidos={verRepetidos}
          onSelect={elegir}
        />
        <div className="controles-mapa">
          <button
            type="button"
            className={verCircuito ? "on" : ""}
            onClick={() => alternarCapa("circuito")}
          >
            <i className="muestra circuito" />
            Ver circuito
          </button>
          <button
            type="button"
            className={verRepetidos ? "on" : ""}
            onClick={() => alternarCapa("repetidos")}
          >
            <i className="muestra repite" />
            Más de una vez
          </button>
        </div>
      </div>
    </main>
  );
}

function numero(valor: string, anterior: number): number {
  if (valor.trim() === "") return anterior;
  const n = Number(valor);
  return Number.isInteger(n) && n >= 0 ? n : anterior;
}

function entero(form: Edicion): boolean {
  return CAMPOS.every((campo) => {
    const valor = form[campo];
    if (campo === "tipo_zona") return ZONAS.includes(String(valor));
    return Number.isInteger(valor) && Number(valor) >= 0;
  });
}
