"""¿Saber cuánto petróleo hay en Cushing sirve para ganar dinero?

Se prueba una regla muy simple, semana a semana, con tres niveles de información:

  adelantado  Se conoce el dato oficial el mismo viernes al que se refiere, cinco días
              antes de que se publique. Es el techo: lo que daría un satélite perfecto.
  publicado   Se usa el mismo dato pero después de que salga (jueves siguiente).
              No hace falta satélite; es el control.
  satélite    Se usa la estimación de este proyecto, con las imágenes que había.

La regla, para las empresas dueñas de tanques: si las existencias suben, se compra y se
mantiene una semana; si bajan, se está fuera. Para el crudo es al revés (menos petróleo
almacenado, precio más alto).

Ganar más que "comprar y aguantar" no demuestra nada, porque una regla que está fuera
la mitad del tiempo ya se comporta distinto por sí sola. La comparación justa es contra
la misma regla con las semanas barajadas al azar: mismas semanas dentro, elegidas sin
información. Si la regla de verdad no gana a la gran mayoría de esas, es suerte.
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

INICIO = "2015-10-01"
BARAJADAS = 5000
NOMBRES = {"USO": "Crudo WTI (USO)", "PAA": "Plains", "EPD": "Enterprise", "ENB": "Enbridge", "OKE": "ONEOK"}
# con qué signo del cambio de existencias se compra cada cosa
SENTIDO = {"USO": -1, "PAA": 1, "EPD": 1, "ENB": 1, "OKE": 1}

AZUL, NARANJA, VERDE = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA_2, TENUE, FONDO = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"


def cargar():
    eia = pd.read_csv(DATOS / "eia_cushing.csv", parse_dates=["fecha"]).set_index("fecha").miles_barriles / 1000
    precios = pd.read_csv(DATOS / "precios.csv", parse_dates=["fecha"]).set_index("fecha")
    sat = pd.read_csv(RESULTADOS / "serie.csv", parse_dates=["fecha"]).set_index("fecha").satelite_millones_barriles
    return eia[INICIO:], precios, sat


def rentabilidad(precios, desde, dias=7):
    """Rentabilidad de cada valor entre el cierre de cada fecha y el de `dias` después."""
    antes = precios.reindex(desde, method="ffill")
    despues = precios.reindex(desde + pd.Timedelta(days=dias), method="ffill")
    return pd.DataFrame(despues.values / antes.values - 1, index=desde, columns=precios.columns)


def señal_satelite(viernes, sat):
    """Cambio entre las dos últimas imágenes, solo si ha llegado una nueva esa semana.

    Solo cuentan las imágenes de antes del viernes: el dato procesado tarda unas horas.
    """
    cambio = pd.Series(np.nan, index=viernes)
    for v in viernes:
        vistas = sat[sat.index < v]
        if len(vistas) >= 2 and vistas.index[-1] > v - pd.Timedelta(days=7):
            cambio[v] = vistas.iloc[-1] - vistas.iloc[-2]
    return cambio


def probar(cambio, rent, sentido, rng):
    """Devuelve la ganancia de la regla y qué porcentaje de barajadas al azar supera."""
    ok = cambio.notna() & rent.notna()
    dentro = (np.sign(cambio[ok]) == sentido).to_numpy(copy=True)
    r = np.log1p(rent[ok].values)
    total = r[dentro].sum()
    azar = np.array([r[rng.permutation(dentro)].sum() for _ in range(BARAJADAS)])
    return {
        "semanas": int(ok.sum()),
        "dentro": dentro.mean(),
        "regla": np.expm1(total),
        "aguantar": np.expm1(r.sum()),
        "supera_al_azar": (azar < total).mean(),
    }


def main():
    eia, precios, sat = cargar()
    cambio = eia.diff().dropna()
    viernes = cambio.index
    jueves = viernes + pd.Timedelta(days=6)   # el dato sale el miércoles; el jueves si hay festivo

    variantes = {
        "adelantado": (cambio, rentabilidad(precios, viernes)),
        "publicado": (cambio, rentabilidad(precios, jueves).set_axis(viernes)),
        "satélite": (señal_satelite(viernes, sat), rentabilidad(precios, viernes)),
    }

    rng = np.random.default_rng(0)
    filas = []
    for nombre, (señal, rent) in variantes.items():
        for valor in NOMBRES:
            filas.append({"información": nombre, "valor": valor, **probar(señal, rent[valor], SENTIDO[valor], rng)})
    tabla = pd.DataFrame(filas)
    tabla.round(4).to_csv(RESULTADOS / "backtest.csv", index=False)

    for nombre in variantes:
        print(f"\n{nombre}")
        for _, f in tabla[tabla.información == nombre].iterrows():
            print(f"  {NOMBRES[f.valor]:<18} {f.semanas:>3} semanas, dentro el {f.dentro:.0%}   "
                  f"regla {f.regla:+7.0%}   dentro todas esas semanas {f.aguantar:+7.0%}   "
                  f"supera al {f.supera_al_azar:.0%} del azar")

    # ¿acierta el satélite el signo del cambio semanal oficial?
    s = variantes["satélite"][0].dropna()
    print(f"\nEl satélite da señal {len(s)} de {len(viernes[viernes >= sat.index[0]])} semanas "
          f"y coincide con el signo oficial el {(np.sign(s) == np.sign(cambio[s.index])).mean():.0%} de las veces")

    # ¿Es robusto lo que sale con el dato ya publicado?
    print("\nDato publicado, % del azar que supera según el periodo:")
    señal, rent = variantes["publicado"]
    for nombre, m in [("2015-2020", viernes < "2021"), ("2021-2026", viernes >= "2021"), ("sin 2020", viernes.year != 2020)]:
        print(f"  {nombre:<10} " + "  ".join(
            f"{NOMBRES[v]} {probar(señal[m], rent[v][m], SENTIDO[v], rng)['supera_al_azar']:.0%}" for v in NOMBRES))

    # Si fuera la publicación lo que mueve el precio, entrar antes debería ser aún mejor.
    print("\n% del azar que supera según el día de entrada (días desde el viernes del dato; se publica el día 5):")
    for dias in (-7, 0, 2, 4, 6, 9, 14):
        rent = rentabilidad(precios, viernes + pd.Timedelta(days=dias)).set_axis(viernes)
        print(f"  {dias:>3}  " + "  ".join(
            f"{NOMBRES[v]} {probar(cambio, rent[v], SENTIDO[v], rng)['supera_al_azar']:.0%}" for v in NOMBRES))

    # figura: porcentaje del azar que supera cada regla
    fig, ax = plt.subplots(figsize=(10, 4.6), facecolor=FONDO)
    ax.set_facecolor(FONDO)
    ancho = 0.26
    for k, (nombre, color) in enumerate(zip(variantes, (AZUL, NARANJA, VERDE))):
        sub = tabla[tabla.información == nombre]
        ax.bar(np.arange(len(sub)) + (k - 1) * ancho, sub.supera_al_azar * 100, ancho - 0.03,
               color=color, label={"adelantado": "Dato oficial 5 días antes", "publicado": "Dato oficial ya publicado",
                                   "satélite": "Estimación del satélite"}[nombre])
    ax.axhline(95, color=TENUE, lw=1, ls=(0, (4, 3)))
    ax.text(len(NOMBRES) - 0.42, 95, "95 %: difícil que\nsea suerte", va="center", color=TINTA_2, fontsize=9.5)
    ax.axhline(50, color=TENUE, lw=1)
    ax.text(len(NOMBRES) - 0.42, 50, "50 %: como elegir\nal azar", va="center", color=TINTA_2, fontsize=9.5)
    ax.set_xlim(-0.6, len(NOMBRES) - 0.5)
    ax.set_xticks(np.arange(len(NOMBRES)), list(NOMBRES.values()))
    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("% de reglas al azar que supera", color=TINTA_2)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(TENUE)
    ax.tick_params(colors=TINTA_2, labelsize=10, length=0)
    ax.set_title("¿Gana la regla a elegir las semanas al azar?", loc="left", color=TINTA, fontsize=14, pad=30)
    ax.legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=10, labelcolor=TINTA_2)
    fig.tight_layout(rect=(0, 0, 0.87, 1))
    fig.savefig(RESULTADOS / "backtest.png", dpi=150)


if __name__ == "__main__":
    main()
