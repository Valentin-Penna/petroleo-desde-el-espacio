"""Saca de OpenStreetMap los tanques de almacenamiento de Cushing (Oklahoma).

Cada tanque está dibujado en OSM como un polígono. De ahí salen el centro y el
diámetro, que es todo lo que hace falta para saber dónde mirar en la imagen.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer

DATOS = Path(__file__).resolve().parent.parent / "data"

# sur, oeste, norte, este
ZONA = (35.88, -96.83, 36.07, -96.67)
# Cushing cae en la zona UTM 14N, la misma proyección que usan las imágenes de Sentinel-2
UTM = "EPSG:32614"

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
CONSULTA = f"""
[out:json][timeout:120];
way["man_made"="storage_tank"]({ZONA[0]},{ZONA[1]},{ZONA[2]},{ZONA[3]});
out geom;
"""

# Por debajo de 3 píxeles de radio no hay techo suficiente que medir a 10 m/píxel
DIAMETRO_MINIMO = 30.0


def descargar():
    ultimo_error = None
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": CONSULTA}, timeout=180,
                              headers={"User-Agent": "petroleo-desde-el-espacio"})
            r.raise_for_status()
            return r.json()["elements"]
        except Exception as e:  # probar con el siguiente servidor
            ultimo_error = e
    raise ultimo_error


def a_tabla(elementos):
    a_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    filas = []
    for el in elementos:
        geom = el.get("geometry")
        if not geom or len(geom) < 6:
            continue
        lon = np.array([p["lon"] for p in geom])
        lat = np.array([p["lat"] for p in geom])
        x, y = a_utm.transform(lon, lat)
        x, y = np.asarray(x), np.asarray(y)

        # área y centroide del polígono (fórmula del cordón de zapato)
        cruz = x[:-1] * y[1:] - x[1:] * y[:-1]
        area = cruz.sum() / 2
        if abs(area) < 1:
            continue
        cx = ((x[:-1] + x[1:]) * cruz).sum() / (6 * area)
        cy = ((y[:-1] + y[1:]) * cruz).sum() / (6 * area)
        area = abs(area)

        # un tanque es redondo: su área tiene que parecerse a la del círculo que lo envuelve
        radio_max = np.hypot(x - cx, y - cy).max()
        redondez = area / (np.pi * radio_max**2)
        diametro = 2 * np.sqrt(area / np.pi)

        etiquetas = el.get("tags", {})
        filas.append({
            "id": el["id"],
            "x": round(cx, 2),
            "y": round(cy, 2),
            "diametro_m": round(diametro, 2),
            "redondez": round(redondez, 3),
            "contenido": etiquetas.get("content", ""),
            "operador": etiquetas.get("operator", ""),
        })
    return pd.DataFrame(filas)


def main():
    DATOS.mkdir(exist_ok=True)
    tabla = a_tabla(descargar())
    print(f"OSM devuelve {len(tabla)} tanques en la zona")
    tabla = tabla[(tabla.redondez > 0.85) & (tabla.diametro_m >= DIAMETRO_MINIMO)]
    tabla = tabla.sort_values("id").reset_index(drop=True)
    tabla.to_csv(DATOS / "tanques.csv", index=False)
    print(f"{len(tabla)} son redondos y de al menos {DIAMETRO_MINIMO:.0f} m de diámetro")
    print(tabla.diametro_m.describe().round(1).to_string())


if __name__ == "__main__":
    main()
