"""Mide cuánto ha bajado el techo flotante de cada tanque en cada imagen.

Un tanque de crudo no tiene tapa fija: el techo flota sobre el petróleo. Cuando el
tanque se vacía, el techo baja y la pared proyecta sobre él una sombra con forma de
media luna en el lado del sol. Si el techo está d metros por debajo del borde y el
sol tiene una elevación a, la sombra mide L = d / tan(a).

A 10 m por píxel esa sombra ocupa uno o dos píxeles como mucho, así que no se puede
medir con una regla. Se hace al revés: se dibuja cómo se vería el tanque para cada
longitud de sombra posible, se emborrona igual que lo hace el satélite y se elige la
longitud cuyo dibujo se parece más a la imagen real.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter
from scipy.optimize import minimize

from parches import EJE, LADO

DATOS = Path(__file__).resolve().parent.parent / "data"

# Parámetros del modelo, estimados solo con las imágenes (nunca con el dato de la EIA)
DESENFOQUE_M = 8.0     # sigma del emborronado total (óptica + remuestreo), en metros
BRILLO_SOMBRA = 0.08   # cuánto refleja el techo en sombra respecto al techo al sol

LAMBDAS = np.arange(0, 1.61, 0.02)   # longitud de sombra / radio del tanque
FINO = 8                             # cada celda del parche se subdivide en 8 x 8 para dibujar las máscaras

PASO = EJE[1] - EJE[0]
_fino = (np.arange(LADO * FINO) + 0.5) / FINO * PASO + EJE[0] - PASO / 2
_uf, _vf = np.meshgrid(_fino, _fino, indexing="ij")
_u, _v = np.meshgrid(EJE, EJE, indexing="ij")


def _reducir(mascara):
    return mascara.reshape(LADO, FINO, LADO, FINO).mean(axis=(1, 3))


# El eje u apunta al sol. Un punto del techo está en sombra si, yendo hacia el sol una
# distancia lambda, se sale del círculo: ahí el rayo ha chocado con la pared.
DISCO = _reducir(_uf**2 + _vf**2 < 1)
SOMBRAS = np.stack([_reducir((_uf**2 + _vf**2 < 1) & ((_uf + lam) ** 2 + _vf**2 > 1)) for lam in LAMBDAS])

# Solo se ajusta la mitad del parche que da al sol. Al otro lado está la sombra exterior
# del tanque sobre el suelo, que no dice nada del nivel y solo mete ruido.
ZONA = ((_u > -0.5) & (_u < 1.4) & (np.abs(_v) < 1.2)).ravel()


def medir_tanque(parches, radio):
    """parches: (n_fechas, lado, lado). Devuelve lambda, brillo del techo y R2 para cada fecha."""
    sigma = DESENFOQUE_M / (PASO * radio)
    t_disco = gaussian_filter(DISCO, sigma, mode="nearest").ravel()[ZONA]
    t_sombra = np.stack([gaussian_filter(m, sigma, mode="nearest") for m in SOMBRAS]).reshape(len(LAMBDAS), -1)[:, ZONA]
    t_suelo = 1 - t_disco
    y = parches.reshape(len(parches), -1)[:, ZONA].T.astype(np.float64)

    sse = np.empty((len(LAMBDAS), y.shape[1]))
    techo = np.empty_like(sse)
    for j in range(len(LAMBDAS)):
        # dos incógnitas por fecha: el brillo del techo y el del suelo
        A = np.stack([t_disco - (1 - BRILLO_SOMBRA) * t_sombra[j], t_suelo], axis=1)
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        sse[j] = ((y - A @ coef) ** 2).sum(axis=0)
        techo[j] = coef[0]

    j = sse.argmin(axis=0)
    f = np.arange(len(j))
    lam = LAMBDAS[j].copy()
    # afinar entre dos pasos de la rejilla con una parábola
    dentro = (j > 0) & (j < len(LAMBDAS) - 1)
    a, b, c = sse[j[dentro] - 1, f[dentro]], sse[j[dentro], f[dentro]], sse[j[dentro] + 1, f[dentro]]
    curv = a - 2 * b + c
    lam[dentro] += np.where(curv > 0, 0.5 * (a - c) / np.where(curv > 0, curv, 1), 0) * (LAMBDAS[1] - LAMBDAS[0])

    sst = ((y - y.mean(axis=0)) ** 2).sum(axis=0)
    return lam, techo[j, f], 1 - sse[j, f] / sst


def punto_cero(sombra_m, cotangente):
    """Error de posición de un tanque, en metros, sacado de sus propias medidas.

    La sombra tiene que ser L = d / tan(a): proporcional a la cotangente de la altura del
    sol y nula con el sol en el cénit. Si el contorno del tanque está corrido un par de
    metros respecto a la imagen, a todas sus sombras se les suma ese mismo error, y la
    recta L frente a cotangente deja de pasar por cero. Lo que corta en el origen es el error.

    Se usa una recta mediana (no de mínimos cuadrados) porque las sombras medidas no
    pueden bajar de cero y eso descoloca la media.
    """
    def perdida(p):
        return np.abs(sombra_m - (p[0] + p[1] * cotangente)).sum()

    inicio = np.polyfit(cotangente, sombra_m, 1)[::-1]
    return minimize(perdida, inicio, method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-3}).x[0]


def main():
    tanques = pd.read_csv(DATOS / "tanques.csv")
    idx = pd.read_csv(DATOS / "parches_indice.csv")
    parches = np.load(DATOS / "parches_nir.npy", mmap_mode="r")
    radios = tanques.diametro_m.values / 2
    tangente = np.tan(np.radians(idx.sol_elevacion.values))

    n_f, n_t = len(idx), len(tanques)
    lam, techo, r2 = np.empty((n_f, n_t)), np.empty((n_f, n_t)), np.empty((n_f, n_t))
    for i in range(n_t):
        lam[:, i], techo[:, i], r2[:, i] = medir_tanque(np.asarray(parches[:, i]), radios[i])
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{n_t}", flush=True)

    # Una medida vale si el modelo explica bien el parche y el techo tiene su brillo habitual
    # (si pasa una nube por encima sale más claro, y si le cae la sombra de una nube, más oscuro)
    habitual = np.median(techo, axis=0)
    valida = (r2 > 0.8) & (techo > 0.6 * habitual) & (techo < 1.5 * habitual)

    sombra_m = lam * radios[None, :]
    cero = np.zeros(n_t)
    for i in range(n_t):
        m = valida[:, i]
        if m.sum() >= 60:
            cero[i] = punto_cero(sombra_m[m, i], 1 / tangente[m])
    bajada_m = (sombra_m - cero[None, :]) * tangente[:, None]

    tanques["punto_cero_m"] = cero.round(2)
    tanques["fechas_validas"] = valida.sum(axis=0)
    tanques.to_csv(DATOS / "tanques_medidos.csv", index=False)
    np.savez_compressed(DATOS / "medidas.npz", fechas=np.array(idx.fecha.tolist(), dtype="U10"), ids=tanques.id.values,
                        bajada_m=bajada_m.astype(np.float32), valida=valida)
    print(f"medidas válidas: {valida.mean():.1%}   R2 mediano: {np.median(r2):.3f}")
    print(f"punto cero: mediana {np.median(cero):+.2f} m, la mitad de los tanques entre "
          f"{np.percentile(cero, 25):+.2f} y {np.percentile(cero, 75):+.2f} m")


if __name__ == "__main__":
    main()
