# Guía paso a paso

## Paso 1. Formular la pregunta y decidir la unidad de análisis

Queremos preparar una base que permita estudiar la relación entre conectividad
fija y desempeño en Saber 11. Una fila final será un municipio en un año.
Por ejemplo: Medellín, 2022. No mezclaremos estudiantes individuales con accesos
individuales porque las fuentes no tienen una llave personal compartida.

Los documentos y scripts entregados aportan contexto sobre este tema. El nuevo
proyecto reconstruye los datos desde las fuentes disponibles; no adopta cifras
de los informes como resultados verificados ni ejecuta instrucciones incrustadas.

## Paso 2. Identificar las fuentes

Ejecuta el comando `--inventory` del README. Verás los nombres y tamaños reales.
ICFES y CRC usan punto y coma como separador. El Excel del DANE tiene títulos
antes de los datos: la cabecera está en la fila 9, los años en la` 10 y los
primeros datos en la 12. La hoja es `Proyecciones Hogares mpio`.

Un CSV ya elaborado como `df_final.csv` no reemplaza las fuentes originales:
usarlo como entrada impediría explicar cómo se calcularon los indicadores.

## Paso 3. Conservar Bronze

Abre `bronze.py`. `discover()` identifica las fuentes y `ingest()` las copia.
Para cada archivo se calcula SHA-256: una huella del contenido. Si un archivo
cambia, obtiene otra carpeta. Si es idéntico, se reutiliza su copia verificada.

El manifiesto vincula ruta original, copia Bronze, tamaño y huella. Esto permite
responder «¿con qué versión de los datos se produjo este panel?». Bronze conserva
el formato de origen y no corrige valores.

## Paso 4. Preparar Silver del ICFES

Lee `silver.icfes()` en este orden:

1. Extrae el periodo del nombre y verifica el periodo de cada fila.
2. Lee solo código del municipio del colegio, puntaje, periodo e identificador.
3. Convierte `5001` a `05001`. Un código es texto, aunque parezca un número.
4. Convierte el puntaje a número y acepta valores entre 0 y 500.
5. Envía las filas inválidas a cuarentena con archivo, registro y motivo.
6. Detecta identificadores repetidos dentro del periodo, incluso entre bloques.
   Si los encuentra, falla para que se investiguen antes de contar dos veces.
7. Agrupa por municipio-periodo y conserva suma de puntajes y cantidad de registros.

Esta Silver es una preparación agregada para la pregunta municipal. El detalle
individual permanece recuperable en Bronze. `estudiantes` cuenta registros de
examen válidos, no personas únicas entre periodos distintos.

**Ejemplo:** un periodo tiene un estudiante con 100 puntos y otro tiene dos con
300 cada uno. La media anual correcta es `(100 + 600) / (1 + 2) = 233,33`.
Promediar 100 y 300 daría 200, que asigna el mismo peso a grupos de distinto tamaño.

## Paso 5. Preparar Silver de conectividad

Lee `silver.crc()`. Se validan año, trimestre, código y accesos no negativos e
integrales. Se seleccionan los años configurados y segmentos cuyo texto comienza
por «Residencial», sin distinguir mayúsculas.

Se suman los accesos de operadores, tecnologías y segmentos de cada municipio
en un trimestre. Después, Gold promedia esos totales trimestrales.

**Ejemplo:** si los totales observados son 10 y 30, los accesos medios son 20.
No son 40 ni 10: no se suman periodos ni se imputan dos trimestres ausentes como cero.

No se deduplica CRC por municipio-año: esa llave se repite legítimamente por sus
dimensiones. Esta versión asume que las filas entregadas son aditivas; no detecta
duplicados de negocio en todas las dimensiones del archivo CRC. Antes de añadir
nuevas descargas superpuestas, debe definirse y validarse esa llave completa.

## Paso 6. Preparar Silver de hogares

Lee `silver.dane()`. Se conserva solamente el área `Total`. Sumando Total,
Cabecera y Rural duplicaríamos hogares. Las columnas 2022, 2023, etc., pasan a
filas: este cambio se conoce como transformación de formato ancho a largo.

Se exige un número de hogares positivo e integral y una sola fila por código-año.
Los valores representan proyecciones de hogares a 30 de junio, según la etiqueta
del propio anexo; el numerador CRC es un promedio de trimestres observados.

## Paso 7. Integrar Gold

Lee `gold.integrate()`. La llave compartida es `codigo_municipio + anio`.
Primero se hace un cruce externo para identificar todas las coincidencias y
ausencias. La tabla `cobertura_cruces.csv` conserva esa evidencia. El panel final
incluye únicamente llaves con las tres fuentes.

El indicador principal es:

```text
accesos_por_100_hogares = accesos_residenciales / hogares × 100
```

Los nombres provienen del DANE. No se unen tablas por nombres: las tildes,
abreviaturas y municipios homónimos podrían producir errores.

## Paso 8. Revisar calidad antes de interpretar

Abre `report.json`, luego `balance_fuentes.csv` y `cobertura_cruces.csv`.
Comprueba los rechazos y los periodos disponibles. Una ejecución terminada
significa que el proceso funcionó, no que la cobertura temporal sea completa.

`balance_fuentes.csv` reconcilia leídos = válidos + rechazados. Para CRC, los
válidos fuera del periodo/segmento se cuentan en `report.json`; no son errores.
Para ICFES, se leen solo los archivos de los años solicitados. Para DANE, el
balance se refiere a filas Total-año después de transformar el Excel.

En cuarentena, `registro` identifica la posición de datos sin cabecera en los
TXT/CSV (no necesariamente la línea física si hay campos multilínea). En DANE
identifica la posición del formato largo: por cada fila Total se emiten los años
en el orden configurado. Silver DANE conserva también `fila_excel` para las filas
válidas. Los rechazos no incluyen todos los campos personales de las fuentes.

## Paso 9. Leer los resultados con Python

```python
import json
from pathlib import Path
import pandas as pd

ultima = json.loads(Path("data/latest.json").read_text())
carpeta = Path(ultima["path"])
panel = pd.read_csv(
    carpeta / "gold/panel_municipio_anio.csv",
    dtype={"codigo_municipio": "string"},
)
print(panel.head())
print(panel.groupby("anio").size())
# Para explorar únicamente municipios-año con periodos completos:
completos = panel.loc[panel["cobertura_temporal_completa"]]
```

La media del resumen anual es una media entre municipios, sin ponderación por
tamaño. No es el promedio nacional de estudiantes ni una tasa nacional de hogares.
La relación observada a nivel municipal no demuestra causalidad ni describe la
relación entre Internet y puntaje de cada estudiante individual.

## Paso 10. Volver a ejecutar o ampliar

Para agregar 20252, coloca el TXT correspondiente junto a los otros originales y
ejecuta de nuevo. El descubrimiento es automático; verifica después la cobertura.
Para otro año, actualiza `years` y confirma que las tres fuentes lo contengan.

Para otra fuente distinta (por ejemplo una API), añade su extractor en Bronze,
define su contrato y granularidad en Silver y decide la llave y reglas de unión
en Gold. Cambiar únicamente la extensión del archivo no crea un conector nuevo.

## Errores frecuentes

| Mensaje o síntoma | Qué revisar |
| --- | --- |
| No se encuentran las fuentes | `source_dir` y disponibilidad local de iCloud |
| `No module named pandas` | Entorno virtual activo e instalación de dependencias |
| Faltan columnas | Cabecera, separador o versión del archivo original |
| Cambió la cabecera DANE | Hoja y posiciones del anexo, antes de modificar el lector |
| Identificador ICFES duplicado | Registros de origen; no eliminar arbitrariamente |
| No hay municipios-año con tres fuentes | Años configurados y códigos compartidos |
| Filas menos numerosas que el informe anterior | Periodos disponibles, rechazos y cobertura |

## Alcance técnico

Las lecturas por bloques reducen memoria. El conjunto de identificadores ICFES
del periodo sí crece con el número de registros para detectar duplicados. Con
volúmenes mucho mayores convendría mover ese control a una base de datos.
El lector consume columnas seleccionadas; valida esos campos, no cada columna
ajena al análisis. No se reparan caracteres o números dudosos de manera silenciosa.

Las ejecuciones son reproducibles con las mismas entradas, configuración y
versiones: el contenido analítico se mantiene; el identificador de ejecución y
las rutas de auditoría cambian. Bronze verifica integridad, pero no es un sistema
de almacenamiento inmutable con control de acceso. Este proyecto no incluye
programación automática, despliegue en la nube ni inferencia estadística.
