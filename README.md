# Petróleo desde el espacio

¿Se puede sacar ventaja en bolsa mirando fotos gratis de un satélite?

Los fondos de inversión lo hacen desde hace años: pagan por imágenes de alta resolución para contar coches en aparcamientos o medir depósitos de petróleo, y así saben cómo va una empresa o un mercado antes de que salga el dato oficial. Este proyecto comprueba hasta dónde se llega con lo que tiene cualquiera: las imágenes públicas de Sentinel-2, donde cada píxel mide 10 metros.

El objetivo es Cushing, Oklahoma. Sus más de 400 tanques guardan el crudo de referencia del mercado americano (el WTI). Cada miércoles el gobierno publica cuánto hay dentro, y ese número mueve el precio del petróleo y de las empresas del sector. Quien lo supiera unos días antes operaría con ventaja.

![Los mismos tanques con Cushing lleno y medio vacío](resultados/sombras.png)

## La idea

Un tanque de crudo no tiene tapa fija. El techo flota sobre el petróleo y sube y baja con él. Cuando el tanque se vacía, el techo se hunde y la pared proyecta sobre él una sombra con forma de media luna. Cuanto más larga la sombra, menos petróleo.

Si el sol está a una altura `a` sobre el horizonte y la sombra mide `L`, el techo ha bajado `d = L · tan(a)`. Con el diámetro del tanque, eso son barriles.

El problema es que la sombra mide entre 2 y 25 metros y el píxel mide 10. No se puede ver, pero sí se puede deducir: la sombra oscurece un poco los píxeles del borde, y ese poco se puede medir.

## ¿Se puede medir Cushing desde el espacio?

Sí.

![Estimación desde el satélite frente al dato oficial](resultados/serie.png)

La línea azul es el dato oficial de la EIA. Cada punto naranja es una imagen de satélite.

Entre noviembre de 2020 y noviembre de 2025, Cushing pasó de 60 a 22 millones de barriles: una caída del 63 %. Desde el satélite sale un 60 %.

En las imágenes de 2022 a 2026, que no se usaron para calibrar, el error típico es de 3,7 millones de barriles sobre unas existencias de entre 19 y 43 millones. La correlación con el dato oficial en los nueve años es de 0,96.

## ¿Y eso da ventaja para operar?

Con imágenes gratuitas, todavía no.

Para adelantarse al dato del miércoles hay que acertar el cambio de una semana, y de una semana a otra Cushing cambia menos de un millón de barriles. El error entre dos imágenes consecutivas es de 2,4 millones: la señal es más pequeña que el ruido. El método acierta si las existencias suben o bajan el 62 % de las veces a una semana y el 71 % a un mes, pero a un mes el dato oficial ya se ha publicado cuatro veces.

Hay tres cosas que lo limitan:

- **Resolución.** En verano el sol está a 70° y las sombras miden menos de 5 metros, medio píxel.
- **Nubes.** De 670 pasadas del satélite, 320 están despejadas. Algunos meses solo hay una o dos imágenes.
- **Tanques pequeños.** Los 52 de menos de unos 36 metros de diámetro no dan píxeles suficientes y se quedan fuera. Los otros 355 suman el 94 % de la capacidad.

Las tres tienen arreglo con mejores datos: el radar de Sentinel-1 ve a través de las nubes y también es gratuito, y las imágenes comerciales de 3 metros resolverían la sombra directamente. Eso es lo que compran los fondos.

## Cómo funciona

1. **Tanques.** La posición y el diámetro de los 407 tanques salen de OpenStreetMap. Con una altura de pared estándar suman 95 millones de barriles de capacidad; la cifra real de Cushing ronda los 94.
2. **Imágenes.** Todas las pasadas de Sentinel-2 sobre Cushing desde 2017 (una cada 5 días). Están en abierto en AWS en un formato que deja descargar solo el recorte de 5 × 11 km en vez de la imagen entera, así que no hace falta cuenta ni clave.
3. **Alineado.** Las imágenes están corridas entre sí hasta 13 metros, más que la sombra que se busca. Se alinean todas contra una de referencia con precisión de medio metro.
4. **Girar hacia el sol.** Cada tanque se recorta y se gira para que el sol quede siempre arriba. Así la sombra cae en el mismo sitio en todos los tanques y todas las fechas.
5. **Ajuste.** Para cada tanque y fecha se dibuja cómo se vería con cada longitud de sombra posible, se emborrona como lo hace la óptica del satélite, y se elige la que más se parece a la imagen real.
6. **Punto cero.** La sombra tiene que ser proporcional a `1/tan(a)` y desaparecer con el sol en lo más alto. Si para un tanque no es así, lo que sobra es el error de posición de ese tanque, y se le resta. Este paso es el que hace que funcione también en verano.

Nada de lo anterior usa el dato oficial. Solo al final se ajusta una recta para pasar de volumen medido a barriles, usando únicamente las imágenes anteriores a 2022.

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

Esto es un proyecto de programación y análisis de datos, no una recomendación de inversión.
