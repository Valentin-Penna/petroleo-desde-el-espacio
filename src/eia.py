"""Descarga las existencias semanales de crudo en Cushing que publica la EIA.

Es el dato oficial contra el que se compara la estimación hecha desde el satélite.
La serie (W_EPC0_SAX_YCUOK_MBBL) da los miles de barriles almacenados cada viernes
y se publica el miércoles siguiente.
"""
import io
from pathlib import Path

import pandas as pd
import requests

DATOS = Path(__file__).resolve().parent.parent / "data"
URL = "https://www.eia.gov/dnav/pet/hist_xls/W_EPC0_SAX_YCUOK_MBBLw.xls"


def main():
    DATOS.mkdir(exist_ok=True)
    r = requests.get(URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    hoja = pd.read_excel(io.BytesIO(r.content), sheet_name="Data 1", skiprows=2)
    hoja.columns = ["fecha", "miles_barriles"]
    hoja = hoja.dropna()
    hoja["fecha"] = pd.to_datetime(hoja.fecha).dt.strftime("%Y-%m-%d")
    hoja["miles_barriles"] = hoja.miles_barriles.astype(int)
    hoja.to_csv(DATOS / "eia_cushing.csv", index=False)
    print(f"{len(hoja)} semanas, de {hoja.fecha.iloc[0]} a {hoja.fecha.iloc[-1]}")
    print(hoja.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
