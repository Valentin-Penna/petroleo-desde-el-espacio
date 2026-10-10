"""Dibuja la misma zona de tanques con Cushing lleno y con Cushing medio vacío."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from imagenes import marco

RAIZ = Path(__file__).resolve().parent.parent
RECORTES = RAIZ / "data" / "recortes"
FONDO, TINTA = "#fcfcfb", "#0b0b0b"

FECHAS = [("2020-11-25", "25 nov 2020 · 60 millones de barriles"),
          ("2025-11-16", "16 nov 2025 · 22 millones de barriles")]
CENTRO = (704150, 3980250)   # UTM 14N
MEDIO_LADO = 420             # metros


def main():
    oeste, sur, este, norte = marco()
    fig, ejes = plt.subplots(1, 2, figsize=(11, 5.9), facecolor=FONDO)
    for ax, (fecha, titulo) in zip(ejes, FECHAS):
        nir = np.load(RECORTES / f"{fecha}.npz")["nir"]
        ax.imshow(nir, extent=(oeste, este, sur, norte), cmap="gray", vmin=0, vmax=6500, interpolation="nearest")
        ax.set_xlim(CENTRO[0] - MEDIO_LADO, CENTRO[0] + MEDIO_LADO)
        ax.set_ylim(CENTRO[1] - MEDIO_LADO, CENTRO[1] + MEDIO_LADO)
        ax.set_axis_off()
        ax.set_title(titulo, loc="left", color=TINTA, fontsize=12, pad=8)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    (RAIZ / "resultados").mkdir(exist_ok=True)
    fig.savefig(RAIZ / "resultados" / "sombras.png", dpi=150)


if __name__ == "__main__":
    main()
