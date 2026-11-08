# Recolección de residuos

Trabajo práctico de Lógica y Teoría de Grafos. Este repositorio es solo esa consigna (la última del enunciado). La lógica va en Python (`backend/`). El frontend es Next.js en `frontend/`.

## Consigna

El área de higiene urbana de un municipio quiere optimizar el recorrido de sus camiones. A diferencia de un problema de entregas, el camión tiene que recorrer calles completas, y no todas necesitan recolección con la misma urgencia. Hay que predecir qué tramos tienen más prioridad y usar esa predicción para calcular un recorrido que los cubra.

El sistema tiene que combinar un clasificador (prioridad de cada tramo) con algoritmos de grafos para un recorrido que pase por todos los tramos prioritarios.

La zona se modela como un grafo no dirigido: nodo = intersección, arista = tramo de calle con su distancia.

Dataset mínimo por tramo: `tramo_id`, `tipo_zona` (residencial / comercial / industrial), `cantidad_contenedores`, `dias_desde_ultima_recoleccion`, `historico_quejas_vecinales`, `prioridad_recoleccion` (alta / media / baja, variable a predecir).

1. Entrenar un clasificador y analizar accuracy, precisión, recall y matriz de confusión en un test separado. Los modelos de la cátedra son regresión logística, KNN, SVM o árbol de decisión.
2. Elegir qué tramos recorre el camión según la predicción (por ejemplo, prioridad media o alta).
3. Implementar Hierholzer. Si el subgrafo no es euleriano, resolver el cartero chino: vértices de grado impar, caminos mínimos con Dijkstra, emparejamiento de costo mínimo (se puede usar una librería, aclarándolo), duplicar esos caminos y construir el circuito.

El frontend tiene que mostrar el grafo de calles coloreado por prioridad, el recorrido paso a paso marcando los tramos que se recorren más de una vez, y el costo total.

## Ciudad

La consigna no fija la ciudad. Primero buscamos Rosario: el dataset "Contenedores de residuos domiciliarios" del portal de Datos Abiertos (`datosabiertos.rosario.gob.ar`). La página no cargaba (timeout y 504), tampoco desde el navegador, y no apareció un espejo con coordenadas. OpenStreetMap en el centro de Rosario solo tenía unas decenas de papeleras, insuficientes. La Plata tampoco publica contenedores georreferenciados.

Quedó la Ciudad Autónoma de Buenos Aires. El GCBA publica, con URL estable y licencia CC-BY, la ubicación de los contenedores de residuos húmedos. Usamos la zona 1 y un recorte del microcentro (San Nicolás y el borde de Retiro y Monserrat) para no pasar de ~1500 aristas. El detalle de columnas, fórmulas y limitaciones está en [DATASET.md](DATASET.md).

## Setup

Hace falta Python 3.12. Desde la raíz del repo:

```bash
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m backend.dataset.build_dataset
.venv/bin/python backend/dataset/validate_dataset.py
```

Para volver a calcular solo días, quejas y prioridad sin redescargar OSM: `.venv/bin/python backend/dataset/resynthesize.py`.

Eso baja las calles a `data/cache/` y los contenedores a `data/raw/` (ninguno se versiona) y escribe `data/processed/tramos.csv`, `nodos.csv` y `grafo.graphml`. La semilla está en `backend/config.py` (`SEED`). `cerca_escuela_hospital` y `feria_o_evento` no salen de ese comando: las agrega `notebooks/tramos.ipynb`. Si se vuelve a generar el CSV, hay que volver a correr ese notebook y después:

```bash
.venv/bin/python -m backend.model.train
```

Eso ajusta el clasificador con el corte del notebook y escribe `data/processed/model.joblib`. El API no reentrena.

El circuito, aparte, sobre el CSV que ya existe:

```bash
.venv/bin/python -m backend.routing.build_route --prioridades alta
```

Escribe `output/recorrido.csv` y `output/recorrido.html`. No es el servidor.

## Correr

El navegador habla solo con Next, en `/api/...`. Next reenvía eso a `http://api:8000`. En los dos compose el servicio se llama `api`.

```bash
docker compose -f compose.dev.yaml up --build
docker compose -f compose.yaml up --build
```

El primero es local: publica el `3000` y el `8000`, monta el código y recarga solo. El segundo es el de producción (Coolify). Solo publica `web`. Las ediciones van a un SQLite en el volume `overrides`.

## Estructura

```text
backend/          dataset, SVM, circuito y API
frontend/         Next.js
data/raw/         CSV de contenedores, no se versiona
data/cache/       extracto OSM, no se versiona
data/processed/   tramos, grafo y model.joblib
compose.yaml      producción (Coolify)
compose.dev.yaml  local, con recarga
```

## Dependencias

- `osmnx`: baja y simplifica la red de OpenStreetMap.
- `geopandas` y `shapely`: join espacial de contenedores y tipo de zona. Las trae osmnx.
- `pandas` y `numpy`: tabla de tramos y el muestreo Poisson de las columnas sintéticas.
- `scikit-learn`: el SVM que sirve el API, y el chequeo de `backend/dataset/validate_dataset.py`.
- `networkx`: grafo y GraphML. Lo trae osmnx.
- `fastapi` y `uvicorn`: el API. Las ediciones de las seis columnas van a SQLite.
