"""Suma todos los tanques y compara el resultado con el dato oficial de la EIA.

Para que la comparación sea honesta, la recta que convierte "volumen medido desde el
satélite" en "millones de barriles de la EIA" se ajusta solo con las imágenes anteriores
a 2022. Los números que se dan como resultado son los de 2022 en adelante, que el
ajuste no ha visto.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data"
RESULTADOS = RAIZ / "resultados"

ALTURA_M = 14.6            # altura de pared típica (48 pies)
BARRILES_POR_M3 = 6.2898
CORTE = "2022-01-01"       # antes: calibración; después: prueba

AZUL, NARANJA = "#2a78d6", "#eb6834"
TINTA, TINTA_2, TENUE, FONDO = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"


def volumen_satelite():
    z = np.load(DATOS / "medidas.npz")
    tanques = pd.read_csv(DATOS / "tanques_medidos.csv")
    fechas = pd.to_datetime(z["fechas"])
    area = np.pi * (tanques.diametro_m.values / 2) ** 2

    # tanques que se han podido medir al menos la mitad de las veces
    usable = z["valida"].mean(axis=0) >= 0.5
    bajada = np.where(z["valida"], np.clip(z["bajada_m"], 0, ALTURA_M), np.nan)[:, usable]
    # los huecos (una nube sobre ese tanque ese día) se rellenan con las fechas vecinas
    bajada = pd.DataFrame(bajada, index=fechas).interpolate(method="time", limit_direction="both").values

    millones = (area[usable] * (ALTURA_M - bajada)).sum(axis=1) * BARRILES_POR_M3 / 1e6
    capacidad = (area[usable] * ALTURA_M).sum() * BARRILES_POR_M3 / 1e6
    return pd.Series(millones, index=fechas), int(usable.sum()), capacidad


def eia_en(fechas):
    e = pd.read_csv(DATOS / "eia_cushing.csv", parse_dates=["fecha"]).set_index("fecha").miles_barriles / 1000
    en_fechas = np.interp(fechas.astype("int64"), e.index.astype("int64"), e.values)
    return pd.Series(en_fechas, index=fechas), e


def resumen(nombre, sat, eia):
    err = sat - eia
    print(f"  {nombre:<28} n={len(sat):>3}  correlación {np.corrcoef(sat, eia)[0, 1]:.3f}  "
          f"error típico {np.sqrt((err**2).mean()):.1f} M  sesgo {err.mean():+.1f} M")


def cambios(sat, eia, minimo, maximo):
    """Cambio entre cada imagen y la primera que haya entre `minimo` y `maximo` días después."""
    d_sat, d_eia = [], []
    for i, fecha in enumerate(sat.index):
        despues = sat.index[i + 1:]
        dias = (despues - fecha).days
        cand = despues[(dias >= minimo) & (dias <= maximo)]
        if len(cand):
            d_sat.append(sat[cand[0]] - sat[fecha])
            d_eia.append(eia[cand[0]] - eia[fecha])
    return np.array(d_sat), np.array(d_eia)


def estilo(ax):
    ax.set_facecolor(FONDO)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(TENUE)
    ax.tick_params(colors=TINTA_2, labelsize=10)
    ax.grid(axis="y", color="#e6e5e0", lw=0.8)
    ax.set_axisbelow(True)


def main():
    RESULTADOS.mkdir(exist_ok=True)
    crudo, n_tanques, capacidad = volumen_satelite()
    eia, eia_semanal = eia_en(crudo.index)
    idx = pd.read_csv(DATOS / "parches_indice.csv")
    elev = pd.Series(idx.sol_elevacion.values, index=crudo.index)

    antes = crudo.index < CORTE
    pendiente, origen = np.polyfit(crudo[antes], eia[antes], 1)
    sat = pendiente * crudo + origen

    print(f"{n_tanques} tanques medidos, {capacidad:.0f} millones de barriles de capacidad")
    print(f"calibración con {antes.sum()} imágenes hasta {CORTE}: EIA = {pendiente:.2f} x satélite {origen:+.1f}")
    print("\nNivel total, imágenes de 2022 en adelante (no usadas para calibrar):")
    despues = ~antes
    resumen("todas", sat[despues], eia[despues])
    resumen("sol bajo (< 40°, invierno)", sat[despues & (elev < 40)], eia[despues & (elev < 40)])
    resumen("sol medio (40°-60°)", sat[despues & (elev >= 40) & (elev < 60)], eia[despues & (elev >= 40) & (elev < 60)])
    resumen("sol alto (> 60°, verano)", sat[despues & (elev >= 60)], eia[despues & (elev >= 60)])

    print("\nCambios entre dos imágenes, 2022 en adelante:")
    for nombre, lo, hi in [("a una semana (5-10 días)", 5, 10), ("a un mes (25-35 días)", 25, 35), ("a tres meses (80-100 días)", 80, 100)]:
        d_sat, d_eia = cambios(sat[despues], eia[despues], lo, hi)
        acierto = (np.sign(d_sat) == np.sign(d_eia)).mean()
        print(f"  {nombre:<28} n={len(d_sat):>3}  correlación {np.corrcoef(d_sat, d_eia)[0, 1]:.2f}  "
              f"acierta el sentido {acierto:.0%}  cambio real típico {np.abs(d_eia).mean():.1f} M  "
              f"error típico {np.sqrt(((d_sat - d_eia) ** 2).mean()):.1f} M")

    pd.DataFrame({
        "fecha": crudo.index.strftime("%Y-%m-%d"),
        "sol_elevacion": elev.values.round(1),
        "satelite_millones_barriles": sat.values.round(2),
        "eia_millones_barriles": eia.values.round(2),
    }).to_csv(RESULTADOS / "serie.csv", index=False)

    # serie temporal
    fig, ax = plt.subplots(figsize=(11, 4.6), facecolor=FONDO)
    estilo(ax)
    oficial = eia_semanal[crudo.index[0] - pd.Timedelta(days=30):]
    ax.plot(oficial.index, oficial.values, color=AZUL, lw=2, label="EIA (dato oficial semanal)")
    ax.scatter(sat.index, sat.values, s=22, color=NARANJA, edgecolor=FONDO, lw=0.6, zorder=3,
               label="Estimación desde Sentinel-2 (una por imagen despejada)")
    ax.axvline(pd.Timestamp(CORTE), color=TENUE, lw=1, ls=(0, (4, 3)))
    ax.text(pd.Timestamp(CORTE) - pd.Timedelta(days=20), 76, "calibración", ha="right", color=TINTA_2, fontsize=10)
    ax.text(pd.Timestamp(CORTE) + pd.Timedelta(days=20), 76, "prueba", ha="left", color=TINTA_2, fontsize=10)
    ax.set_ylim(0, 80)
    ax.set_ylabel("Millones de barriles", color=TINTA_2)
    ax.set_title("Crudo almacenado en Cushing, Oklahoma", loc="left", color=TINTA, fontsize=14, pad=12)
    ax.legend(frameon=False, loc="lower left", fontsize=10, labelcolor=TINTA_2)
    fig.tight_layout()
    fig.savefig(RESULTADOS / "serie.png", dpi=150)

    # dispersión
    fig, ax = plt.subplots(figsize=(5.6, 5.6), facecolor=FONDO)
    estilo(ax)
    ax.grid(axis="x", color="#e6e5e0", lw=0.8)
    ax.plot([15, 72], [15, 72], color=TENUE, lw=1)
    ax.scatter(eia[despues], sat[despues], s=26, color=NARANJA, edgecolor=FONDO, lw=0.6, zorder=3)
    ax.set_xlim(15, 72)
    ax.set_ylim(15, 72)
    ax.set_aspect("equal")
    ax.set_xlabel("EIA, millones de barriles", color=TINTA_2)
    ax.set_ylabel("Satélite, millones de barriles", color=TINTA_2)
    ax.set_title("Imágenes de 2022 a 2026", loc="left", color=TINTA, fontsize=13, pad=10)
    fig.tight_layout()
    fig.savefig(RESULTADOS / "dispersion.png", dpi=150)


if __name__ == "__main__":
    main()
