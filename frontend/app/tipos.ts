export type Prioridad = "alta" | "media" | "baja";

export type Tramo = {
  tramo_id: number;
  nombre_calle: string;
  distancia_m: number;
  geometria: [number, number][];
  dias_desde_ultima_recoleccion: number;
  cantidad_contenedores: number;
  historico_quejas_vecinales: number;
  tipo_zona: string;
  cerca_escuela_hospital: 0 | 1;
  feria_o_evento: 0 | 1;
  prioridad: Prioridad;
};

export type Edicion = {
  dias_desde_ultima_recoleccion: number;
  cantidad_contenedores: number;
  historico_quejas_vecinales: number;
  tipo_zona: string;
  cerca_escuela_hospital: 0 | 1;
  feria_o_evento: 0 | 1;
};

export type Paso = {
  tramo_id: number;
  sentido: { desde: number; hasta: number };
  agregado: boolean;
  distancia_m: number;
  visita: number;
  nombre_calle: string;
  geometria: [number, number][];
};

export type Recorrido = {
  prioridades: { tramo_id: number; prioridad: Prioridad }[];
  pasos: Paso[];
  costo_m: number;
  repetidos: number[];
};

export const CAMPOS: (keyof Edicion)[] = [
  "dias_desde_ultima_recoleccion",
  "cantidad_contenedores",
  "historico_quejas_vecinales",
  "tipo_zona",
  "cerca_escuela_hospital",
  "feria_o_evento",
];
