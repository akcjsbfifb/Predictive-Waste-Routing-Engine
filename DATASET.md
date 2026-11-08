# Dataset de tramos

Zona: microcentro de la Ciudad Autónoma de Buenos Aires. Bounding box en `backend/config.py` (`BBOX`), de oeste a este y de sur a norte:

`-58.393, -34.6105, -58.3705, -34.5925`

Son unas 2 km por lado: San Nicolás y el borde de Retiro y Monserrat. La zona 1 de contenedores húmedos llega también a Constitución, San Telmo y Puerto Madero. Ese polígono entero se iba de las ~1500 aristas.

## Por qué no es Rosario

El trabajo arrancó con Rosario. El dataset "Contenedores de residuos domiciliarios" figura en Datos Abiertos de la Municipalidad (`https://datosabiertos.rosario.gob.ar/dataset/contenedores-de-residuos-domiciliarios`), pero el 30 de octubre de 2026 el portal no respondía: el nombre no resolvía por el DNS local y el sitio daba timeout o 504. Tampoco cargó en el navegador. No había un CSV espejo con coordenadas. Las papeleras de OpenStreetMap en el centro eran 57 puntos y cubrían el 3 % de las aristas. La Plata no publica un inventario de contenedores con latitud y longitud (hay un dataset genérico "Residuos" de 2020, sin geometría usable, y un mapa de focos de basura que es otra cosa).

La fuente que sí está publicada, actualizada y con coordenadas es la del GCBA.

## Columnas

| Columna | Origen | Cómo se obtiene |
| --- | --- | --- |
| `tramo_id` | derivado | Entero desde 1, después de ordenar las aristas por `(min(u, v), max(u, v))`. El mismo id va en el GraphML. |
| `u`, `v` | real | Nodos extremos. Siempre `u < v`, porque el grafo no tiene dirección. |
| `distancia_m` | real | Largo de la arista en metros, calculado por osmnx. |
| `highway` | real | Tag OSM de tipo de vía. Vacío si no vino. |
| `nombre_calle` | real | Tag `name`. Vacío si la calle no tiene nombre en OSM. |
| `tipo_zona` | derivado de OSM | Buffer de 40 m alrededor del tramo. Ver abajo. |
| `cantidad_contenedores` | real | Contenedores húmedos del GCBA asignados a la arista más cercana, hasta 50 m. El resto se descarta. 0 si no hay ninguno. |
| `dias_desde_ultima_recoleccion` | sintético | Poisson. La media depende de `tipo_zona` y sube con la cantidad de contenedores. Recortado a 0–10. |
| `historico_quejas_vecinales` | sintético | Poisson. La tasa crece con contenedores, con los días sin recolección y en zona comercial. |
| `prioridad_recoleccion` | sintético | Corte por ranking de un score con ruido. No es una regla cerrada sobre las otras columnas. |

`nodos.csv` tiene `node_id`, `lat`, `lon` de los cruces. Esos datos salen de OSM.

En esta corrida el grafo tiene 986 nodos y 1257 aristas. De los 2292 contenedores de la zona 1, 887 caen a menos de 50 m de alguna arista del recorte. El 32 % de los tramos tiene al menos uno. El máximo en un tramo es 9.

## Calles

La red se pide con el filtro de calles de `network_type="drive"` de osmnx (sin peatonales, ciclovías ni service). Overpass público estaba saturado, así que el extracto sale de `https://api.openstreetmap.org/api/0.6/map` y el filtro se aplica localmente. El grafo pasa a no dirigido, se tiran los self-loops y, si quedan dos aristas entre el mismo par de nodos, se conserva la más corta. Después se deja solo la componente conexa más grande.

## Contenedores

Archivo: `zona_1_cont_humedos_clean.csv`, "Contenedores para residuos húmedos - Zona 1", dataset Infraestructura de gestión de residuos.

https://data.buenosaires.gob.ar/dataset/infraestructura-gestion-residuos

El CSV separa columnas con `;`. `latitud` y `longitud` a veces vienen sin punto decimal (`-3461477` en vez de `-34.61477`). El loader las divide por 10 hasta que la latitud queda en [-90, 90] y la longitud en [-180, 180]. La columna `wkt_geom` está en coordenadas planas del GCBA y no se usa.

## Tipo de zona

En esta zona OSM casi no marca `landuse=industrial`. El tipo sale de un puntaje en un buffer de 40 m: locales, `landuse` commercial/retail, amenities de comercio y edificios commercial/retail. Hace falta un puntaje de al menos 6 para comercial. Industrial exige `landuse=industrial` o edificio industrial/depósito. Si no hay señal, el tramo queda residencial.

Sobre las 1257 aristas: residencial 859 (68 %) y comercial 398 (32 %). Industrial es 0 %. Es una limitación del microcentro, no un relleno. La validación lo avisa.

## Fórmulas sintéticas

Semilla: `SEED` en `backend/config.py`. Se usa `numpy.random.default_rng`. Nada de esto está medido en la calle.

Días, con media por zona `DAYS_POISSON_LAM` (residencial 3,2, comercial 2,0, industrial 4,5):

```text
lambda_dias = media(zona) + 0,15 * cantidad_contenedores
dias = clip(Poisson(lambda_dias), 0, 10)
```

Quejas:

```text
lambda_quejas = exp(-0,4 + 0,35 * log1p(contenedores) + 0,12 * dias + bonus_zona)
bonus_zona: residencial 0, comercial 0,55, industrial 0,15
quejas = Poisson(lambda_quejas)
```

Score, y después ruido normal de desvío `PRIORITY_NOISE_SIGMA` (0,40):

```text
score = 0,55 * dias
      + 0,70 * log1p(contenedores)
      + 0,45 * log1p(quejas)
      + bonus_zona_prioridad
      + 0,18 * dias * log1p(contenedores)
      + Normal(0, 0,40)
```

`bonus_zona_prioridad`: residencial 0, comercial 0,40, industrial 0,20.

La etiqueta no usa umbrales fijos sobre el score. Se ordenan los tramos por score y se corta para acercarse a alta 20 %, media 35 %, baja 45 % (`PRIORITY_SHARES`). El desvío 0,40 se eligió para que un Random Forest de diagnóstico, con split 80/20 y la misma semilla, quede cerca del 80 % de accuracy: aprende la estructura, pero no reconstruye la clase. Esas proporciones son una decisión de diseño, no una estadística del GCBA.

El Random Forest de `backend/dataset/validate_dataset.py` no es el modelo del práctico. Para volver a generar solo días, quejas y prioridad sin bajar OSM de nuevo: `.venv/bin/python backend/dataset/resynthesize.py`.

## Fuentes y licencias

- Calles, nombres, tipo de vía y tags de zona: © OpenStreetMap contributors, licencia ODbL. https://www.openstreetmap.org/copyright
- Contenedores: Gobierno de la Ciudad Autónoma de Buenos Aires, Buenos Aires Data, dataset "Infraestructura de gestión de residuos", recurso "Contenedores para residuos húmedos - Zona 1". Licencia Creative Commons Attribution (CC-BY). https://data.buenosaires.gob.ar/dataset/infraestructura-gestion-residuos

## Limitaciones

- El recorte es el microcentro, no toda la Ciudad de Buenos Aires ni la zona 1 completa.
- No hay tramos industriales. Un clasificador no va a ver esa clase.
- Los contenedores de la zona 1 que quedan a más de 50 m de una calle del recorte no entran (1405 de 2292 en esta corrida).
- Días sin recolección, quejas y la prioridad no salen del GCBA. El modelo va a aprender las reglas de este archivo.
