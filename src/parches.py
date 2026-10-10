"""Recorta cada tanque de cada imagen y lo gira para que el sol quede siempre arriba.

El resultado es un "parche" cuadrado por tanque y fecha, en coordenadas normalizadas:
el centro del tanque es (0, 0), el borde está a distancia 1 y el eje u apunta al sol.
Así la sombra interior cae siempre en el mismo sitio del parche (u > 0), sea cual sea
el tamaño del tanque o la época del año, y todos los tanques se pueden comparar.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import map_coordinates
from skimage.registration import phase_cross_correlation

from imagenes import marco

DATOS = Path(__file__).resolve().parent.parent / "data"
RECORTES = DATOS / "recortes"
PIXEL = 10.0

# rejilla del parche: de -1.5 a 1.5 radios, 25 x 25 puntos
EXTENSION = 1.5
LADO = 25
EJE = np.linspace(-EXTENSION, EXTENSION, LADO)


def cargar_indice():
    idx = pd.read_csv(DATOS / "imagenes.csv")
    idx = idx[idx.guardada.fillna(False).astype(bool)].reset_index(drop=True)
    return idx


def imagen_referencia(fechas, banda="nir", cuantas=60):
    """Mediana de unas cuantas imágenes repartidas en el tiempo: sirve de plantilla para alinear."""
    elegidas = fechas[:: max(1, len(fechas) // cuantas)]
    pila = np.stack([np.load(RECORTES / f"{f}.npz")[banda] for f in elegidas]).astype(np.float32)
    return np.median(pila, axis=0)


def desplazamiento(imagen, referencia):
    """Cuánto está corrida la imagen respecto a la referencia, en píxeles (fila, columna).

    La geolocalización de Sentinel-2 tiene errores de varios metros de una pasada a otra,
    y aquí unos metros son la señal entera, así que hay que corregirlo.
    """
    corr, _, _ = phase_cross_correlation(referencia, imagen, upsample_factor=20, normalization=None)
    return corr


def parches_de_imagen(imagen, tanques, sol_azimut, corr, limites):
    """Devuelve un array (n_tanques, LADO, LADO) con los parches girados hacia el sol."""
    oeste, _, _, norte = limites
    az = np.radians(sol_azimut)
    hacia_sol = np.array([np.sin(az), np.cos(az)])      # (este, norte)
    perpendicular = np.array([np.cos(az), -np.sin(az)])

    u, v = np.meshgrid(EJE, EJE, indexing="ij")  # eje 0 = u (hacia el sol), eje 1 = v
    radio = (tanques.diametro_m.values / 2)[:, None, None]
    x = tanques.x.values[:, None, None] + radio * (u * hacia_sol[0] + v * perpendicular[0])
    y = tanques.y.values[:, None, None] + radio * (u * hacia_sol[1] + v * perpendicular[1])

    # coordenadas de píxel (el centro del píxel [0, 0] está a medio píxel de la esquina)
    columna = (x - oeste) / PIXEL - 0.5 - corr[1]
    fila = (norte - y) / PIXEL - 0.5 - corr[0]
    return map_coordinates(imagen, [fila, columna], order=1, mode="nearest")


def main():
    tanques = pd.read_csv(DATOS / "tanques.csv")
    idx = cargar_indice()
    limites = marco()
    referencia = imagen_referencia(idx.fecha.tolist())

    nir = np.zeros((len(idx), len(tanques), LADO, LADO), dtype=np.float32)
    corrs = []
    for i, fila in idx.iterrows():
        img_nir = np.load(RECORTES / f"{fila.fecha}.npz")["nir"].astype(np.float32)
        corr = desplazamiento(img_nir, referencia)
        corrs.append(corr)
        nir[i] = parches_de_imagen(img_nir, tanques, fila.sol_azimut, corr, limites)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(idx)}", flush=True)

    corrs = np.array(corrs)
    idx["corr_fila"] = corrs[:, 0]
    idx["corr_columna"] = corrs[:, 1]
    idx.to_csv(DATOS / "parches_indice.csv", index=False)
    np.save(DATOS / "parches_nir.npy", nir)
    print(f"{len(idx)} fechas x {len(tanques)} tanques")
    print("desplazamiento típico (m):", (np.abs(corrs).mean(axis=0) * PIXEL).round(1),
          " máximo:", (np.abs(corrs).max(axis=0) * PIXEL).round(1))


if __name__ == "__main__":
    main()
