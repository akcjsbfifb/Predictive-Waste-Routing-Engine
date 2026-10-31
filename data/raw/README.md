# Descargas originales

Esta carpeta no se versiona (salvo este archivo). El script la llena solo.

## Contenedores

Gobierno de la Ciudad de Buenos Aires, licencia CC-BY.

- Ficha: https://data.buenosaires.gob.ar/dataset/infraestructura-gestion-residuos
- Archivo que usa el generador: `caba_humedos_zona_1.csv`
- URL: https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-espacio-publico-e-higiene-urbana/infraestructura-gestion-residuos/zona_1_cont_humedos_clean.csv

Son los contenedores de residuos húmedos de la zona 1 (negros y grises). Si el archivo no está, `python -m backend.dataset.build_dataset` lo baja.

Rosario quedó afuera: el dataset municipal de contenedores no se pudo descargar porque `datosabiertos.rosario.gob.ar` no respondía. La Plata no publica un inventario equivalente con coordenadas.

## Red vial

OpenStreetMap se baja solo, a `data/cache/`, vía `https://api.openstreetmap.org/api/0.6/map`. © OpenStreetMap contributors, ODbL.
