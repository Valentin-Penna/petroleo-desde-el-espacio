"""Descarga los recortes de Sentinel-2 sobre Cushing.

Las imágenes están en abierto en AWS como Cloud Optimized GeoTIFF: se puede pedir
solo el trozo que interesa (unos 5 x 11 km) en vez de la imagen entera de 110 x 110 km.
No hace falta cuenta ni clave.

Uso:  python src/imagenes.py [fecha_inicio] [fecha_fin]
"""
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pystac_client import Client
from rasterio.windows import from_bounds

warnings.filterwarnings("ignore", module="pystac")

DATOS = Path(__file__).resolve().parent.parent / "data"
RECORTES = DATOS / "recortes"
CATALOGO = "https://earth-search.aws.element84.com/v1"
COLECCION = "sentinel-2-l2a"
TESELA = "MGRS-14SPE"
CUSHING = {"type": "Point", "coordinates": [-96.745, 35.955]}
MARGEN = 300  # metros alrededor de los tanques

# Clases de la capa SCL que cuentan como "se ve el suelo":
# 4 vegetación, 5 suelo desnudo, 6 agua, 7 sin clasificar, 11 nieve.
# Fuera quedan nubes (8, 9, 10), sombras de nube (3), zonas oscuras (2) y píxeles malos (0, 1).
# Ojo: los techos blancos de los tanques a veces salen como nube, por eso la decisión
# de aceptar la imagen se toma con el entorno y no tanque a tanque.
SCL_DESPEJADO = (4, 5, 6, 7, 11)
DESPEJADO_MINIMO = 0.80

GDAL = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_HTTP_MAX_RETRY="5",
    GDAL_HTTP_RETRY_DELAY="2",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    VSI_CACHE="TRUE",
)


def marco():
    """Rectángulo (oeste, sur, este, norte) en UTM que cubre todos los tanques, ajustado a la rejilla de 20 m."""
    t = pd.read_csv(DATOS / "tanques.csv")
    oeste = np.floor((t.x.min() - MARGEN) / 20) * 20
    sur = np.floor((t.y.min() - MARGEN) / 20) * 20
    este = np.ceil((t.x.max() + MARGEN) / 20) * 20
    norte = np.ceil((t.y.max() + MARGEN) / 20) * 20
    return float(oeste), float(sur), float(este), float(norte)


def buscar(inicio, fin):
    cat = Client.open(CATALOGO)
    items = cat.search(
        collections=[COLECCION],
        intersects=CUSHING,
        datetime=f"{inicio}/{fin}",
        query={"grid:code": {"eq": TESELA}},
        max_items=None,
    ).items()
    # Algunas fechas están dos veces (la misma toma reprocesada): me quedo con la versión más nueva
    por_fecha = {}
    for it in items:
        dia = it.datetime.strftime("%Y-%m-%d")
        clave = (it.properties.get("s2:processing_baseline", ""), it.properties.get("created", ""))
        if dia not in por_fecha or clave > por_fecha[dia][0]:
            por_fecha[dia] = (clave, it)
    return [por_fecha[d][1] for d in sorted(por_fecha)]


def leer(href, limites):
    with rasterio.open(href) as f:
        return f.read(1, window=from_bounds(*limites, transform=f.transform))


def bajar(item, limites):
    dia = item.datetime.strftime("%Y-%m-%d")
    destino = RECORTES / f"{dia}.npz"
    p = item.properties
    fila = {
        "fecha": dia,
        "hora_utc": item.datetime.strftime("%H:%M:%S"),
        "satelite": p.get("platform"),
        "version": p.get("s2:processing_baseline"),
        "sol_elevacion": p.get("view:sun_elevation"),
        "sol_azimut": p.get("view:sun_azimuth"),
    }
    try:
        with rasterio.Env(**GDAL):
            scl = leer(item.assets["scl"].href, limites)
            fila["despejado"] = float(np.isin(scl, SCL_DESPEJADO).mean())
            fila["nieve"] = float((scl == 11).mean())
            if fila["despejado"] >= DESPEJADO_MINIMO and not destino.exists():
                # banda del infrarrojo cercano: es donde más contrastan las sombras
                nir = leer(item.assets["nir"].href, limites)
                np.savez_compressed(destino, nir=nir, scl=scl)
        fila["guardada"] = destino.exists()
    except Exception as e:
        fila["error"] = str(e)[:200]
    return fila


def main():
    inicio = sys.argv[1] if len(sys.argv) > 1 else "2015-06-01"
    fin = sys.argv[2] if len(sys.argv) > 2 else pd.Timestamp.now().strftime("%Y-%m-%d")
    RECORTES.mkdir(parents=True, exist_ok=True)
    limites = marco()
    items = buscar(inicio, fin)
    print(f"{len(items)} fechas entre {inicio} y {fin}", flush=True)

    filas = []
    with ThreadPoolExecutor(8) as hilos:
        for n, fila in enumerate(hilos.map(lambda it: bajar(it, limites), items), 1):
            filas.append(fila)
            if n % 25 == 0:
                print(f"  {n}/{len(items)}", flush=True)

    nuevo = pd.DataFrame(filas)
    indice = DATOS / "imagenes.csv"
    if indice.exists():
        viejo = pd.read_csv(indice)
        nuevo = pd.concat([viejo[~viejo.fecha.isin(nuevo.fecha)], nuevo])
    nuevo = nuevo.sort_values("fecha")
    nuevo.to_csv(indice, index=False)
    print(f"{int(nuevo.guardada.fillna(False).sum())} imágenes despejadas guardadas en total")
    if "error" in nuevo and nuevo.error.notna().any():
        print(f"{int(nuevo.error.notna().sum())} fechas con error (se pueden reintentar volviendo a ejecutar)")


if __name__ == "__main__":
    main()
