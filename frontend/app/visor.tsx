"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Button } from "@/components/ui/button";
import {
  ColorPicker,
  ColorPickerArea,
  ColorPickerAreaThumb,
  ColorPickerContent,
  ColorPickerControl,
  ColorPickerEyeDropperTrigger,
  ColorPickerInput,
  ColorPickerSlider,
  ColorPickerSwatchPreview,
  ColorPickerTransparencyGrid,
  ColorPickerTrigger,
  ColorPickerView,
  parseColor,
} from "@/components/ui/color-picker";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { CAMPOS, type Edicion, type Prioridad, type Recorrido, type Tramo } from "./tipos";

const Mapa = dynamic(() => import("@/components/mapa-caba"), {
  ssr: false,
  loading: () => <div className="mapa-vacio">Cargando mapa…</div>,
});

const ZONAS = ["residencial", "comercial", "industrial"];
const CIRCUITO_INICIAL = "#1d4ed8";
const REPETIDOS_INICIAL = "#7c3aed";
const DIAS_SORTEO_MAX = 10;
const CONTENEDORES_SORTEO_MAX = 7;
const QUEJAS_SORTEO_MAX = 20;

function metros(valor: number): string {
  return `${new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 }).format(valor)} m`;
}

function metrosAgrupados(valor: number): string {
  const entero = Math.round(valor);
  const texto = new Intl.NumberFormat("es-AR", {
    useGrouping: true,
    maximumFractionDigits: 0,
  }).format(entero);
  return texto.replaceAll(".", " ");
}

function costoTotalRecorrido(metrosTotal: number): string {
  const m = Math.round(metrosTotal);
  const linea = `${metrosAgrupados(m)} m`;
  if (m >= 1000) {
    const km = new Intl.NumberFormat("es-AR", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(m / 1000);
    return `${linea} (${km} km)`;
  }
  return linea;
}

function estiloMuestraColor(color: string, fallback: string): CSSProperties {
  try {
    return { background: parseColor(color).toString("hsla") };
  } catch {
    return { background: fallback };
  }
}

type FormEdicion = Omit<
  Edicion,
  "dias_desde_ultima_recoleccion" | "cantidad_contenedores" | "historico_quejas_vecinales"
> & {
  dias_desde_ultima_recoleccion: number | "";
  cantidad_contenedores: number | "";
  historico_quejas_vecinales: number | "";
};

function edicionDe(tramo: Tramo): FormEdicion {
  return {
    dias_desde_ultima_recoleccion: tramo.dias_desde_ultima_recoleccion,
    cantidad_contenedores: tramo.cantidad_contenedores,
    historico_quejas_vecinales: tramo.historico_quejas_vecinales,
    tipo_zona: tramo.tipo_zona,
    cerca_escuela_hospital: tramo.cerca_escuela_hospital,
    feria_o_evento: tramo.feria_o_evento,
  };
}

function enteroAleatorio(maximo: number): number {
  return Math.floor(Math.random() * (maximo + 1));
}

function edicionAleatoria(tramo: Tramo): Edicion {
  return {
    dias_desde_ultima_recoleccion: enteroAleatorio(DIAS_SORTEO_MAX),
    cantidad_contenedores: enteroAleatorio(CONTENEDORES_SORTEO_MAX),
    historico_quejas_vecinales: enteroAleatorio(QUEJAS_SORTEO_MAX),
    tipo_zona: ZONAS[Math.floor(Math.random() * ZONAS.length)],
    cerca_escuela_hospital: tramo.cerca_escuela_hospital,
    feria_o_evento: tramo.feria_o_evento,
  };
}

function elegirNDistintos(tramoIds: number[], cantidad: number): number[] {
  const restantes = [...tramoIds];
  const elegidos: number[] = [];
  const limite = Math.min(cantidad, restantes.length);
  for (let i = 0; i < limite; i += 1) {
    const indice = Math.floor(Math.random() * restantes.length);
    elegidos.push(restantes[indice]);
    restantes.splice(indice, 1);
  }
  return elegidos;
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
  const [form, setForm] = useState<FormEdicion | null>(null);
  const [recorrido, setRecorrido] = useState<Recorrido | null>(null);
  const [paso, setPaso] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [calculando, setCalculando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verCircuito, setVerCircuito] = useState(false);
  const [verRepetidos, setVerRepetidos] = useState(false);
  const [soloCircuito, setSoloCircuito] = useState(false);
  const [colorCircuito, setColorCircuito] = useState(CIRCUITO_INICIAL);
  const [colorRepetidos, setColorRepetidos] = useState(REPETIDOS_INICIAL);
  const [pickerListo, setPickerListo] = useState(false);
  const [nSorteo, setNSorteo] = useState<number | "">(1);
  const valorAlFocoRef = useRef({
    dias: 0,
    contenedores: 0,
    quejas: 0,
    nSorteo: 1,
  });

  useEffect(() => {
    setPickerListo(true);
  }, []);

  const muestraCircuito = useMemo(
    () => estiloMuestraColor(colorCircuito, CIRCUITO_INICIAL),
    [colorCircuito],
  );
  const muestraRepetidos = useMemo(
    () => estiloMuestraColor(colorRepetidos, REPETIDOS_INICIAL),
    [colorRepetidos],
  );

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
    if (elegido) {
      const siguiente = edicionDe(elegido);
      setForm(siguiente);
      valorAlFocoRef.current.dias = siguiente.dias_desde_ultima_recoleccion;
      valorAlFocoRef.current.contenedores = siguiente.cantidad_contenedores;
      valorAlFocoRef.current.quejas = siguiente.historico_quejas_vecinales;
    }
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

  async function aplicarRecorrido(
    ediciones: Map<number, Edicion>,
  ): Promise<void> {
    const res = await fetch("/api/recorrido", { method: "POST", cache: "no-store" });
    if (!res.ok) throw new Error(await mensaje(res));
    const data = (await res.json()) as Recorrido;
    const prioridades = new Map(data.prioridades.map((item) => [item.tramo_id, item.prioridad]));
    setTramos((actuales) =>
      actuales.map((item) => {
        const prioridad = (prioridades.get(item.tramo_id) ?? item.prioridad) as Prioridad;
        const edicion = ediciones.get(item.tramo_id);
        if (edicion) return { ...item, ...edicion, prioridad };
        return { ...item, prioridad };
      }),
    );
    if (seleccionado !== null) {
      const edicionSel = ediciones.get(seleccionado);
      if (edicionSel) {
        setForm(edicionSel);
        valorAlFocoRef.current.dias = edicionSel.dias_desde_ultima_recoleccion;
        valorAlFocoRef.current.contenedores = edicionSel.cantidad_contenedores;
        valorAlFocoRef.current.quejas = edicionSel.historico_quejas_vecinales;
      }
    }
    setRecorrido(data);
    setPaso(0);
  }

  async function patchTramo(tramoId: number, edicion: Edicion): Promise<void> {
    const res = await fetch(`/api/tramos/${tramoId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify(edicion),
    });
    if (!res.ok) throw new Error(await mensaje(res));
  }

  async function recalcular() {
    if (calculandoRef.current) return;
    calculandoRef.current = true;
    setCalculando(true);
    setError(null);
    try {
      const ediciones = new Map<number, Edicion>();
      if (seleccionado !== null && form) {
        const edicion = edicionConfirmada(form);
        if (edicion) {
          await patchTramo(seleccionado, edicion);
          ediciones.set(seleccionado, edicion);
        }
      }
      await aplicarRecorrido(ediciones);
    } catch (causa) {
      setError(causa instanceof Error ? causa.message : "No se pudo recalcular.");
    } finally {
      calculandoRef.current = false;
      setCalculando(false);
    }
  }

  async function sortearNCalles() {
    if (calculandoRef.current || tramos.length === 0 || nSorteo === "") return;
    const cantidad = Math.min(Math.max(1, nSorteo), tramos.length);
    calculandoRef.current = true;
    setCalculando(true);
    setError(null);
    try {
      const ids = elegirNDistintos(
        tramosRef.current.map((item) => item.tramo_id),
        cantidad,
      );
      const ediciones = new Map<number, Edicion>();
      for (const tramoId of ids) {
        const original = tramosRef.current.find((item) => item.tramo_id === tramoId);
        if (!original) continue;
        const edicion = edicionAleatoria(original);
        await patchTramo(tramoId, edicion);
        ediciones.set(tramoId, edicion);
      }
      await aplicarRecorrido(ediciones);
    } catch (causa) {
      setError(causa instanceof Error ? causa.message : "No se pudo sortear.");
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
      <div className="mapa">
        <Mapa
          tramos={tramos}
          seleccionado={seleccionado}
          recorrido={recorrido}
          paso={paso}
          verCircuito={verCircuito}
          verRepetidos={verRepetidos}
          soloCircuito={soloCircuito}
          colorCircuito={colorCircuito}
          colorRepetidos={colorRepetidos}
          onSelect={elegir}
        />
        <div className="controles-mapa">
          <div className="controles-mapa-fila">
            <button
              type="button"
              className={`capas ${verCircuito ? "on" : ""}`}
              onClick={() => alternarCapa("circuito")}
            >
              <i className="muestra" style={muestraCircuito} />
              Ver circuito
            </button>
            {pickerListo && (
            <ColorPicker
              className="picker-circuito w-full max-w-xs"
              value={colorCircuito}
              onValueChange={(details) => setColorCircuito(details.valueAsString)}
              format="hsla"
              positioning={{ placement: "bottom-start" }}
            >
              <ColorPickerControl>
                <InputGroup>
                  <ColorPickerTrigger asChild>
                    <InputGroupAddon>
                      <ColorPickerSwatchPreview />
                    </InputGroupAddon>
                  </ColorPickerTrigger>
                  <ColorPickerInput asChild channel="hex">
                    <InputGroupInput className="font-mono uppercase" />
                  </ColorPickerInput>
                </InputGroup>
              </ColorPickerControl>
              <ColorPickerContent>
                <ColorPickerArea>
                  <ColorPickerAreaThumb />
                </ColorPickerArea>
                <ColorPickerView format="hsla">
                  <div className="flex items-center gap-2">
                    <ColorPickerEyeDropperTrigger />
                    <div className="flex min-w-0 flex-1 flex-col gap-2">
                      <ColorPickerSlider channel="hue" />
                      <ColorPickerSlider channel="alpha">
                        <ColorPickerTransparencyGrid />
                      </ColorPickerSlider>
                    </div>
                  </div>
                </ColorPickerView>
              </ColorPickerContent>
            </ColorPicker>
            )}
          </div>
          <div className="controles-mapa-fila">
            <button
              type="button"
              className={`capas ${verRepetidos ? "on" : ""}`}
              onClick={() => alternarCapa("repetidos")}
            >
              <i className="muestra" style={muestraRepetidos} />
              Más de una vez
            </button>
            {pickerListo && (
              <ColorPicker
                className="picker-circuito w-full max-w-xs"
                value={colorRepetidos}
                onValueChange={(details) => setColorRepetidos(details.valueAsString)}
                format="hsla"
                positioning={{ placement: "bottom-start" }}
              >
                <ColorPickerControl>
                  <InputGroup>
                    <ColorPickerTrigger asChild>
                      <InputGroupAddon>
                        <ColorPickerSwatchPreview />
                      </InputGroupAddon>
                    </ColorPickerTrigger>
                    <ColorPickerInput asChild channel="hex">
                      <InputGroupInput className="font-mono uppercase" />
                    </ColorPickerInput>
                  </InputGroup>
                </ColorPickerControl>
                <ColorPickerContent>
                  <ColorPickerArea>
                    <ColorPickerAreaThumb />
                  </ColorPickerArea>
                  <ColorPickerView format="hsla">
                    <div className="flex items-center gap-2">
                      <ColorPickerEyeDropperTrigger />
                      <div className="flex min-w-0 flex-1 flex-col gap-2">
                        <ColorPickerSlider channel="hue" />
                        <ColorPickerSlider channel="alpha">
                          <ColorPickerTransparencyGrid />
                        </ColorPickerSlider>
                      </div>
                    </div>
                  </ColorPickerView>
                </ColorPickerContent>
              </ColorPicker>
            )}
          </div>
        </div>
      </div>

      <aside className="panel">
        <div className="visor-marca">
          <h1>Recolección</h1>
        </div>
        <p className="subtitulo">Microcentro de Buenos Aires. El circuito cubre solo prioridad alta.</p>
        <ul className="leyenda">
          <li>
            <i className="muestra alta" /> alta
          </li>
          <li>
            <i className="muestra media" /> media
          </li>
          <li>
            <i className="muestra baja" /> baja
          </li>
          <li>
            <i className="muestra" style={muestraCircuito} /> circuito
          </li>
          <li>
            <i className="muestra actual" /> paso actual
          </li>
        </ul>

        {cargando && (
          <p className="vacio flex items-center gap-2">
            <Spinner className="size-4" aria-label="Cargando" />
            Cargando calles…
          </p>
        )}
        {error && (
          <p className="error">
            {error}{" "}
            {tramos.length === 0 && (
              <Button type="button" variant="outline" onClick={() => void cargar()}>
                Reintentar
              </Button>
            )}
          </p>
        )}

        {!cargando && tramos.length > 0 && (
          <section className="sorteo-n" aria-labelledby="sorteo-n-titulo">
            <label id="sorteo-n-titulo" htmlFor="n-calles">
              Sortear calles al azar
            </label>
            <div className="sorteo-n-row">
              <input
                id="n-calles"
                className="visor-input-number"
                type="number"
                min={1}
                max={tramos.length}
                step={1}
                value={nSorteo}
                onFocus={() => {
                  if (nSorteo !== "") valorAlFocoRef.current.nSorteo = nSorteo;
                }}
                onChange={(evento) => {
                  const siguiente = cambioNumerico(evento.target.value);
                  if (siguiente !== null) setNSorteo(siguiente);
                }}
                onBlur={() => {
                  setNSorteo((actual) =>
                    actual === ""
                      ? valorAlFocoRef.current.nSorteo
                      : confirmarNSorteo(actual, tramos.length),
                  );
                }}
              />
              <Button
                type="button"
                variant="outline"
                disabled={calculando || nSorteo === ""}
                onClick={() => void sortearNCalles()}
              >
                {calculando ? (
                  <>
                    <Spinner />
                    Sorteando…
                  </>
                ) : nSorteo === "" ? (
                  "Sortear"
                ) : (
                  `Sortear ${Math.min(Math.max(1, nSorteo), tramos.length)}`
                )}
              </Button>
            </div>
            <p>
              Sortea tantas calles distintas como indiques y asigna a cada una al azar días desde la última
              recolección (0 a {DIAS_SORTEO_MAX}), contenedores (0 a {CONTENEDORES_SORTEO_MAX}), quejas (0 a{" "}
              {QUEJAS_SORTEO_MAX}) y tipo de zona. No cambia si hay escuela u hospital cerca ni feria o evento;
              al terminar recalcula el recorrido.
            </p>
          </section>
        )}

        {!cargando && !tramo && (
          <p className="vacio">Elegí una calle en el mapa para cambiar sus datos.</p>
        )}

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
              className="visor-input-number"
              type="number"
              min={0}
              max={DIAS_SORTEO_MAX}
              step={1}
              value={form.dias_desde_ultima_recoleccion}
              onFocus={() => {
                const v = form.dias_desde_ultima_recoleccion;
                if (v !== "") valorAlFocoRef.current.dias = v;
              }}
              onChange={(evento) => {
                const siguiente = cambioNumerico(evento.target.value);
                if (siguiente === null) return;
                setForm({ ...form, dias_desde_ultima_recoleccion: siguiente });
              }}
              onBlur={() => {
                setForm((actual) => {
                  if (!actual) return actual;
                  if (actual.dias_desde_ultima_recoleccion === "") {
                    return {
                      ...actual,
                      dias_desde_ultima_recoleccion: valorAlFocoRef.current.dias,
                    };
                  }
                  return {
                    ...actual,
                    dias_desde_ultima_recoleccion: confirmarDias(actual.dias_desde_ultima_recoleccion),
                  };
                });
              }}
            />
            <label htmlFor="contenedores">Contenedores</label>
            <input
              id="contenedores"
              className="visor-input-number"
              type="number"
              min={0}
              max={CONTENEDORES_SORTEO_MAX}
              step={1}
              value={form.cantidad_contenedores}
              onFocus={() => {
                const v = form.cantidad_contenedores;
                if (v !== "") valorAlFocoRef.current.contenedores = v;
              }}
              onChange={(evento) => {
                const siguiente = cambioNumerico(evento.target.value);
                if (siguiente === null) return;
                setForm({ ...form, cantidad_contenedores: siguiente });
              }}
              onBlur={() => {
                setForm((actual) => {
                  if (!actual) return actual;
                  if (actual.cantidad_contenedores === "") {
                    return {
                      ...actual,
                      cantidad_contenedores: valorAlFocoRef.current.contenedores,
                    };
                  }
                  return {
                    ...actual,
                    cantidad_contenedores: confirmarContenedores(actual.cantidad_contenedores),
                  };
                });
              }}
            />
            <label htmlFor="quejas">Quejas vecinales</label>
            <input
              id="quejas"
              className="visor-input-number"
              type="number"
              min={0}
              max={QUEJAS_SORTEO_MAX}
              step={1}
              value={form.historico_quejas_vecinales}
              onFocus={() => {
                const v = form.historico_quejas_vecinales;
                if (v !== "") valorAlFocoRef.current.quejas = v;
              }}
              onChange={(evento) => {
                const siguiente = cambioNumerico(evento.target.value);
                if (siguiente === null) return;
                setForm({ ...form, historico_quejas_vecinales: siguiente });
              }}
              onBlur={() => {
                setForm((actual) => {
                  if (!actual) return actual;
                  if (actual.historico_quejas_vecinales === "") {
                    return {
                      ...actual,
                      historico_quejas_vecinales: valorAlFocoRef.current.quejas,
                    };
                  }
                  return {
                    ...actual,
                    historico_quejas_vecinales: confirmarQuejas(actual.historico_quejas_vecinales),
                  };
                });
              }}
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
              <Button type="submit" disabled={calculando || !formularioValido(form)} className="w-full">
                {calculando ? (
                  <>
                    <Spinner />
                    Calculando circuito…
                  </>
                ) : (
                  "Recalcular"
                )}
              </Button>
            </div>
          </form>
        )}

        {!tramo && (
          <div className="acciones">
            <Button
              type="button"
              disabled={calculando || tramos.length === 0}
              className="w-full"
              onClick={() => void recalcular()}
            >
              {calculando ? (
                <>
                  <Spinner />
                  Calculando circuito…
                </>
              ) : (
                "Recalcular"
              )}
            </Button>
          </div>
        )}

        {recorrido && actual && (
          <section className="resultado">
            <h2>Circuito</h2>
            <p className="costo-total-etiqueta">Costo total del recorrido</p>
            <p className="costo">{costoTotalRecorrido(recorrido.costo_m)}</p>
            <p className="meta">
              {altas} calles altas · {recorrido.pasos.length} pasos · {recorrido.repetidos.length} tramos más de una
              vez
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
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setPaso((actualPaso) => Math.max(actualPaso - 1, 0))}
                >
                  Anterior
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setPaso((actualPaso) => Math.min(actualPaso + 1, maxPaso))}
                >
                  Siguiente
                </Button>
              </div>
              <p className="detalle">
                {actual.nombre_calle || `Tramo ${actual.tramo_id}`} · {metros(actual.distancia_m)}
                {actual.agregado ? " · copia agregada" : ""}
                {repetidos.has(actual.tramo_id) ? " · se recorre más de una vez" : ""}
              </p>
              {verCircuito && (
                <label className="solo-circuito">
                  <input
                    type="checkbox"
                    checked={soloCircuito}
                    onChange={(evento) => setSoloCircuito(evento.target.checked)}
                  />
                  Mostrar solo el circuito
                </label>
              )}
            </div>
          </section>
        )}
      </aside>
    </main>
  );
}

function cambioNumerico(valor: string): number | "" | null {
  if (valor === "") return "";
  if (!/^\d+$/.test(valor)) return null;
  return Number(valor);
}

function confirmarDias(valor: number | ""): number | "" {
  if (valor === "") return "";
  return Math.min(DIAS_SORTEO_MAX, Math.max(0, valor));
}

function confirmarContenedores(valor: number | ""): number | "" {
  if (valor === "") return "";
  return Math.min(CONTENEDORES_SORTEO_MAX, Math.max(0, valor));
}

function confirmarQuejas(valor: number | ""): number | "" {
  if (valor === "") return "";
  return Math.min(QUEJAS_SORTEO_MAX, Math.max(0, valor));
}

function confirmarNSorteo(valor: number, maximo: number): number {
  return Math.min(maximo, Math.max(1, valor));
}

function edicionConfirmada(form: FormEdicion): Edicion | null {
  const dias = confirmarDias(form.dias_desde_ultima_recoleccion);
  const contenedores = confirmarContenedores(form.cantidad_contenedores);
  const quejas = confirmarQuejas(form.historico_quejas_vecinales);
  if (dias === "" || contenedores === "" || quejas === "") return null;
  if (!ZONAS.includes(form.tipo_zona)) return null;
  return {
    dias_desde_ultima_recoleccion: dias,
    cantidad_contenedores: contenedores,
    historico_quejas_vecinales: quejas,
    tipo_zona: form.tipo_zona,
    cerca_escuela_hospital: form.cerca_escuela_hospital,
    feria_o_evento: form.feria_o_evento,
  };
}

function formularioValido(form: FormEdicion): boolean {
  return edicionConfirmada(form) !== null;
}
