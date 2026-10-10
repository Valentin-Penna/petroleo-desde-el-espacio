# Petróleo desde el espacio

¿Se puede saber cuánto petróleo hay almacenado en Estados Unidos mirando fotos gratis de un satélite?

En Cushing, Oklahoma, hay más de 400 tanques que guardan el crudo de referencia del mercado americano (el WTI). Cada miércoles el gobierno publica cuánto hay dentro, y ese número mueve el precio del petróleo. Los fondos de inversión pagan por imágenes de satélite de alta resolución para adelantarse a ese dato.

Este proyecto intenta lo mismo con las imágenes públicas de Sentinel-2, donde cada píxel mide 10 metros y un tanque entero ocupa unos 6 píxeles de ancho.

![Los mismos tanques con Cushing lleno y medio vacío](resultados/sombras.png)

## La idea

Un tanque de crudo no tiene tapa fija. El techo flota sobre el petróleo y sube y baja con él. Cuando el tanque se vacía, el techo se hunde y la pared proyecta sobre él una sombra con forma de media luna. Cuanto más larga la sombra, menos petróleo.

Si el sol está a una altura `a` sobre el horizonte y la sombra mide `L`, el techo ha bajado `d = L · tan(a)`. Con el diámetro del tanque, eso son barriles.

El problema es que la sombra mide entre 2 y 25 metros y el píxel mide 10. No se puede ver, pero sí se puede deducir: la sombra oscurece un poco los píxeles del borde, y ese poco se puede medir.

## Cómo funciona

1. **Tanques.** La posición y el diámetro de los 407 tanques salen de OpenStreetMap. Con una altura de pared estándar suman 95 millones de barriles de capacidad; la cifra real de Cushing ronda los 94.
2. **Imágenes.** Todas las pasadas de Sentinel-2 sobre Cushing desde 2017 (una cada 5 días). Están en abierto en AWS en un formato que deja descargar solo el recorte de 5 × 11 km en vez de la imagen entera, así que no hace falta cuenta ni clave. De 670 fechas, 320 están despejadas.
3. **Alineado.** Las imágenes están corridas entre sí hasta 13 metros, más que la sombra que se busca. Se alinean todas contra una de referencia con precisión de medio metro.
4. **Girar hacia el sol.** Cada tanque se recorta y se gira para que el sol quede siempre arriba. Así la sombra cae en el mismo sitio en todos los tanques y todas las fechas.
5. **Ajuste.** Para cada tanque y fecha se dibuja cómo se vería con cada longitud de sombra posible, se emborrona como lo hace la óptica del satélite, y se elige la que más se parece a la imagen real.
6. **Punto cero.** La sombra tiene que ser proporcional a `1/tan(a)` y desaparecer con el sol en lo más alto. Si para un tanque no es así, lo que sobra es el error de posición de ese tanque, y se le resta. Este paso es el que hace que funcione también en verano.

Nada de lo anterior usa el dato oficial. Solo al final se ajusta una recta para pasar de volumen medido a barriles, usando únicamente las imágenes anteriores a 2022.

## Resultado

![Estimación desde el satélite frente al dato oficial](resultados/serie.png)

La línea azul es el dato oficial de la EIA. Cada punto naranja es una imagen.

Entre noviembre de 2020 y noviembre de 2025, Cushing pasó de 60 a 22 millones de barriles: una caída del 63 %. Desde el satélite sale un 60 %.

En las imágenes de 2022 a 2026, que no se usaron para calibrar, el error típico es de 3,7 millones de barriles sobre unas existencias de entre 19 y 43 millones. La correlación con el dato oficial en los nueve años es de 0,96.

## Lo que no funciona

No sirve para adelantarse al dato semanal. De una semana a otra Cushing cambia menos de un millón de barriles, y el error entre dos imágenes consecutivas es de 2,4 millones. El método acierta si las existencias suben o bajan el 62 % de las veces a una semana y el 71 % a un mes.

En verano el sol está a 70° y las sombras miden menos de 5 metros, así que el error es mayor que en invierno. Y con nubes no hay imagen: algunos meses solo hay una o dos.

Los 52 tanques más pequeños (menos de unos 36 metros de diámetro) no dan píxeles suficientes y se quedan fuera. Los otros 355 suman el 94 % de la capacidad.

## Ejecutarlo

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python src/tanques.py     # tanques desde OpenStreetMap
.venv/bin/python src/eia.py         # dato oficial de la EIA
.venv/bin/python src/imagenes.py    # recortes de Sentinel-2 (unos 300 MB)
.venv/bin/python src/parches.py     # alinear y recortar cada tanque
.venv/bin/python src/medir.py       # medir la sombra de cada tanque
.venv/bin/python src/comparar.py    # comparar con la EIA y dibujar las gráficas
```

Las medidas ya calculadas están en `data/medidas.npz`, así que el último paso se puede ejecutar sin descargar nada.

## Datos

- Imágenes: Copernicus Sentinel-2 (ESA), a través de [Earth Search](https://earth-search.aws.element84.com/v1) en AWS.
- Tanques: © colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright), licencia ODbL.
- Existencias de crudo: [U.S. Energy Information Administration](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=W_EPC0_SAX_YCUOK_MBBL&f=W).

La idea de medir Cushing con Sentinel-2 viene de [este vídeo de LosingLoonies](https://www.youtube.com/watch?v=VJm9BBJwMDY). El código y el método de este repositorio son propios.
