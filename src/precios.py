"""Descarga los precios diarios de cierre de lo que, en teoría, se mueve con Cushing.

- USO: fondo cotizado que sigue al crudo WTI. Se usa en vez del precio del barril porque
  es algo que se puede comprar de verdad (y porque el barril llegó a valer -37 $ en abril
  de 2020, cosa que rompe cualquier cálculo de rentabilidad).
- PAA, EPD, ENB, OKE: empresas dueñas de tanques en Cushing (Plains, Enterprise,
  Enbridge y ONEOK, que compró Magellan en 2023).

Son cierres ajustados: incluyen los dividendos, que en estas empresas son buena parte
de lo que gana el accionista.
"""
import time
from pathlib import Path

import pandas as pd
import requests

DATOS = Path(__file__).resolve().parent.parent / "data"
VALORES = ["USO", "PAA", "EPD", "ENB", "OKE"]
INICIO = "2015-01-01"


def descargar(valor):
    r = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{valor}",
        params={"period1": int(pd.Timestamp(INICIO).timestamp()), "period2": int(time.time()),
                "interval": "1d", "events": "div,splits"},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=30,
    )
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    fechas = pd.to_datetime(res["timestamp"], unit="s").normalize()
    return pd.Series(res["indicators"]["adjclose"][0]["adjclose"], index=fechas, name=valor)


def main():
    tabla = pd.concat([descargar(v) for v in VALORES], axis=1).dropna(how="all").round(4)
    tabla.index.name = "fecha"
    tabla.to_csv(DATOS / "precios.csv")
    print(f"{len(tabla)} días, de {tabla.index[0].date()} a {tabla.index[-1].date()}")
    print((tabla.iloc[-1] / tabla.iloc[0] - 1).map("{:+.0%}".format).to_string())


if __name__ == "__main__":
    main()
