# Recolección de residuos

La aplicación está en [https://paz-reyes.moloeznik.me/](https://paz-reyes.moloeznik.me/). El informe está en [informe/main.pdf](informe/main.pdf).

El texto de abajo es la consigna de recolección de residuos, tal como está en [enunciado.pdf](enunciado.pdf).

## Enunciado

### Contexto

El área de higiene urbana de un municipio quiere optimizar el recorrido de sus camiones recolectores. A diferencia de un problema de entregas, donde importa visitar puntos, acá el camión tiene que recorrer calles completas, y no todas las calles necesitan recolección con la misma urgencia. El municipio los contrata para construir un sistema que prediga qué tramos tienen más prioridad y use esa predicción para calcular un recorrido que los cubra a todos de forma eficiente.

### Objetivo

Construir un sistema que combine un modelo predictivo (para estimar la prioridad de recolección de cada tramo) con algoritmos de grafos para calcular un recorrido que pase por todos los tramos prioritarios.

### Datos

Se puede modelar la zona como un grafo no dirigido:

- Nodo: intersección.
- Arista: tramo de calle con su distancia o tiempo de recorrido.

El grupo debe generar (o conseguir) un dataset de tramos con, al menos, estas columnas:

| Campo | Tipo | Descripción |
| --- | --- | --- |
| tramo_id | id | identificador de la arista |
| tipo_zona | categórica | residencial / comercial / industrial |
| cantidad_contenedores | numérico | — |
| dias_desde_ultima_recoleccion | numérico | — |
| historico_quejas_vecinales | numérico | — |
| prioridad_recoleccion | categórica | alta / media / baja: variable a predecir |

### Requisitos

1. Modelo predictivo: entrenar un modelo de clasificación que, a partir de las características de un tramo, prediga su prioridad de recolección. Analizar métricas (accuracy, precisión, recall, matriz de confusión) sobre un conjunto de test separado.
2. Selección de tramos: definir un criterio (por ejemplo, prioridad media o alta) para decidir, según la predicción del modelo, qué tramos tiene que recorrer el camión.
3. Grafos: implementar el algoritmo de Hierholzer para construir un circuito que recorra todos los tramos seleccionados. Si el subgrafo no es euleriano, resolver el problema del cartero chino: encontrar los vértices de grado impar, calcular caminos mínimos entre ellos con Dijkstra, emparejarlos con costo mínimo, duplicar esos caminos y construir el circuito sobre el grafo resultante. Para el emparejamiento se puede usar una librería, aclarándolo en el informe.

### Frontend

- Visualización del grafo de calles, con los tramos coloreados según la prioridad predicha.
- Visualización paso a paso del recorrido calculado, marcando los tramos que se recorren más de una vez.
- Costo total del recorrido.

## Correr

El navegador habla solo con Next, en `/api/...`. Next reenvía eso a `http://api:8000`. En los dos compose el servicio se llama `api`.

```bash
docker compose -f compose.dev.yaml up --build
```

Ese es el de local: publica el `3000` y el `8000`, monta el código y recarga solo. La página queda en [http://localhost:3000](http://localhost:3000).

```bash
docker compose -f compose.yaml up --build
```

Ese es el de producción. Solo publica `web`. Las ediciones van a un SQLite en el volume `overrides`.

## Estructura

```text
backend/           dataset, regresión logística, circuito y API
frontend/          Next.js
notebooks/         comparación de modelos y columnas binarias
informe/           informe en LaTeX y el PDF
data/raw/          CSV de contenedores, no se versiona
data/cache/        extracto de OpenStreetMap, no se versiona
data/processed/    tramos, grafo y model.joblib
tests/             tests del dataset, del circuito y de la API
compose.dev.yaml   local, con recarga
compose.yaml       producción
Dockerfile.api     imagen de la API
Dockerfile.web     imagen del frontend
enunciado.pdf      enunciado de la cátedra
DATASET.md         columnas, fórmulas y fuentes
```
