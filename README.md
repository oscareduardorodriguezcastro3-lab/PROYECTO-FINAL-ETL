# ETL en Python con arquitectura Medallón


```text
TXT ICFES ─┐
CSV CRC   ─┼─> Bronze ─> Silver ─> Gold ─> Reporting
XLSX DANE ─┘
```

RAW es lógico: corresponde a `source_dir`, externo al repositorio. La primera
capa física gobernada es Bronze, con copias verificadas por SHA-256, tamaño,
origen, destino y `manifest.json`.

Proyecto educativo y ejecutable para integrar **Saber 11 (ICFES), accesos
residenciales a Internet fijo (CRC) y proyecciones de hogares (DANE)**.
La unidad final de análisis es **municipio del colegio y año**.

## Entrega completa: DataFrames listos

Abre `proyecto_medallon.ipynb` para recorrer el proyecto por celdas, o ejecuta:

```bash
python ejecutar_proyecto.py
```

Para cargar los resultados ya generados sin volver a procesar los originales:

```python
from src.dataframes import cargar_dataframes

datos = cargar_dataframes()
df_icfes = datos["df_icfes"]
df_crc = datos["df_crc"]
df_dane = datos["df_dane"]
df_unificado = datos["df_unificado"]  # Unión externa; conserva ausencias.
df_final = datos["df_final"]          # Coincidencias de las tres fuentes.
```

Para reconstruir todo desde Python: `from src.dataframes import ejecutar_etl`,
seguido de `datos = ejecutar_etl()`. Los códigos se cargan como texto, los
conteos como enteros que admiten nulos y las señales como booleanos.

| Capa | DataFrame | Unidad de cada fila |
| --- | --- | --- |
| Bronze | `df_bronze_catalogo` | Archivo original y su copia verificada |
| Silver | `df_icfes` | Municipio-periodo, todos los TXT seleccionados reunidos |
| Silver | `df_crc` | Municipio-año-trimestre, accesos residenciales sumados |
| Silver | `df_dane` | Municipio-año, proyección de hogares |
| Gold | `df_unificado` | Municipio-año presente en al menos una fuente |
| Gold | `df_final` | Municipio-año con las tres fuentes |
| Gold | `df_resumen_anual` | Año, medias municipales y cobertura |
| Calidad | `df_cobertura`, `df_balance` | Cobertura del cruce y balance por archivo |

Bronze conserva los datos originales como archivos. El catálogo es su DataFrame
de trazabilidad; no mezcla en una misma tabla registros de estudiantes y conexiones.

La entrega ZIP incluye código, guía, cuaderno y resultados en `resultados/`.
Después de descomprimirla puedes usar `cargar_dataframes(run_dir="resultados")`.
Los originales Bronze (aproximadamente 1,8 GB) permanecen fuera del repositorio.
Para reconstruir desde otro equipo, configura `fuentes.source_dir` en
`config/config.yaml` o usa la variable `ETL_SOURCE_DIR`.

Empieza por [la guía paso a paso](docs/01_paso_a_paso.md). Las reglas y campos
están en [el diccionario](docs/02_diccionario_y_reglas.md).
Consulta también [los resultados verificados con tus fuentes](docs/03_resultados_verificados.md).

## 1. Qué significa Medallón

## Etapas ETL

```text
src/
├── extract/   # lectura y localización de fuentes
├── transform/ # reglas de limpieza y Silver
├── load/      # persistencia Bronze/Silver/Gold e integración
└── analysis/  # EDA, calidad, negocio y gráficos
```

EXTRACT obtiene las fuentes; TRANSFORM valida y construye Silver; LOAD conserva
evidencia y produce Gold; ANALYSIS documenta resultados. Esta separación no
duplica la arquitectura Medallion: RAW, Bronze, Silver y Gold siguen siendo
capas de datos, mientras `src/` organiza responsabilidades del código.

| Capa | Qué hacemos | Producto |
| --- | --- | --- |
| Bronze | Conservar copias exactas y registrar su procedencia | TXT, CSV y XLSX originales con huellas SHA-256 |
| Silver | Validar, normalizar y preparar cada fuente | ICFES municipio-periodo, CRC municipio-trimestre, DANE municipio-año |
| Gold | Integrar fuentes y calcular indicadores | Panel municipio-año y resumen anual |

```mermaid
flowchart LR
    A[TXT ICFES] --> B[Bronze: originales versionados]
    C[CSV CRC] --> B
    D[Excel DANE] --> B
    B --> S[Silver: validación y preparación]
    S --> Q[Calidad: rechazos y cobertura]
    S --> G[Gold: panel municipio-año]
    G --> R[Resumen anual]
```

Es una implementación local por lotes, con pandas y archivos CSV; no requiere
Spark ni servicios en la nube. Medallón organiza responsabilidades y niveles
de calidad. No exige una herramienta particular.

## 2. Instalar

Requiere Python 3.10 o posterior. Abre una terminal en la carpeta del proyecto:

```bash
cd /ETL
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Las versiones de las dependencias están fijadas en `requirements.txt`.
este proyecto. En Windows, activa el entorno con `.venv\Scripts\activate`.

## 3. Configurar las fuentes

La fuente principal de configuración es `config/config.yaml`. Define proyecto,
fuentes, años, chunksize, rutas y scheduler sin credenciales. Define
`fuentes.source_dir` o usa `ETL_SOURCE_DIR` como override local. `config/local.json`
se conserva solo como fallback temporal compatible y está ignorado por Git.

```text
Archivos-Datos/
  Datos ICFES/
    Examen_Saber_11_20221.txt
    ...
  ACCESOS_INTERNET_FIJO_2_8.csv
  anexo-proyecciones-hogares-dptal-mpal-2018-2042.xlsx
```

`years` selecciona años; `chunksize` controla filas leídas por bloque. Las
columnas y la estructura del Excel se validan según los archivos entregados.

## 4. Revisar y ejecutar

```bash
python main.py
python -m unittest discover -s tests -v
python main.py
```

La primera ejecución copia aproximadamente 1,8 GB a Bronze. Las siguientes
reutilizan las copias de contenido idéntico y recalculan Silver/Gold. El diseño
es de reconstrucción completa, no de actualización incremental de registros.

## 5. Encontrar los resultados

`data/latest.json` indica la última ejecución terminada correctamente.

La persistencia tiene dos niveles:

- `data/runs/<run_id>/`: histórico versionado e inmutable de cada ejecución.
- `data/silver/`: última publicación Silver exitosa, lista para reutilización.
- `data/gold/`: última publicación Gold exitosa, lista para consumo.

El pipeline copia los artefactos sin moverlos. Si una ejecución falla, conserva
el histórico fallido para diagnóstico, pero no reemplaza `data/silver/`,
`data/gold/` ni `data/latest.json`.

```text
data/
  bronze/<fuente>/<sha256>/<archivo_original>
  latest.json
  runs/<ejecucion>/
    manifest.json
    report.json
    pipeline.log
    silver/
      icfes_municipio_periodo.csv
      crc_municipio_trimestre.csv
      dane_municipio_anio.csv
    gold/
      df_unificado.csv
      panel_municipio_anio.csv
      resumen_anual.csv
    quality/
      balance_fuentes.csv
      cobertura_cruces.csv
      rechazos.csv  (solo si hay rechazos)
  silver/          (última versión publicada)
    icfes_municipio_periodo.csv
    crc_municipio_trimestre.csv
    dane_municipio_anio.csv
  gold/            (última versión publicada)
    df_unificado.csv
    panel_municipio_anio.csv
    resumen_anual.csv
```

`latest.json` contiene `run_id`, `status`, `fecha`, `silver_path`, `gold_path`
y `historical_run_path`.

Cada ejecución tiene una carpeta nueva. Una ejecución fallida queda registrada
y no reemplaza el puntero a la última ejecución correcta. Las salidas parciales
de una ejecución fallida no deben usarse para análisis.

Los rechazos están en `outputs/quality/rechazos_por_motivo.csv` y las filas
fuera de alcance en `outputs/quality/filas_fuera_alcance.csv`; no se mezclan.
La integración está en `outputs/audit/integracion_gold.csv` y los gráficos en
`outputs/eda/graficos/`. 2025 es parcial porque falta ICFES 20252. El proyecto
no demuestra causalidad; los nulos entre fuentes pueden representar ausencia de
cobertura, no cero.

## 6. Decisiones que debes conocer

- Se encontraron siete TXT ICFES: 20221, 20222, 20231, 20232, 20241, 20242 y 20251.
  Falta 20252. Su ausencia se registra, sin inventar ni sustituir observaciones.
- El archivo `df_final.csv` existente es un resultado anterior. No se usa como
  fuente del nuevo panel ni se exige reproducir sus 4.361 filas.
- El puntaje anual pondera por registros válidos de los periodos disponibles.
- Los accesos anuales promedian los totales trimestrales disponibles. Un trimestre
  ausente no se considera cero. La cobertura se muestra en cada fila.
- `accesos_por_100_hogares` cuenta accesos por cada cien hogares; no equivale al
  porcentaje de hogares conectados. Puede superar 100 y se conserva con una señal.
- La cobertura temporal completa significa dos periodos ICFES y cuatro trimestres
  CRC observados en ese municipio-año. No certifica la exhaustividad de cada fuente.
- Un año parcial, especialmente 2025, puede representar una población diferente.
  No debe interpretarse automáticamente como una tendencia anual comparable.

## 7. Archivos para aprender el código

1. `src/pipeline.py`: configuración y orquestación.
2. `src/extract/`: localización de fuentes.
3. `src/load/load_bronze.py`: copias y huellas de integridad.
4. `src/transform/silver.py`: lectura por bloques y reglas por fuente.
5. `src/load/gold.py`: promedios, cruces e indicadores.
6. `src/analysis/reporting.py`: reportes y gráficos.
6. `tests/test_pipeline.py`: ejemplos pequeños con resultados calculables a mano.

Los comentarios y docstrings están en español. Los originales y resultados de
datos están excluidos de Git. Las copias Bronze contienen todos los campos de
origen; para compartir el proyecto basta con el código y la documentación.
