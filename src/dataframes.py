"""API pública para obtener DataFrames pandas de la ejecución terminada.

`cargar_dataframes` solo lee los resultados existentes. `ejecutar_etl` reconstruye
las capas y después carga los resultados. Ninguna función rellena ausencias con 0.
"""

import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
TABLES = {
    "df_icfes": "silver/icfes_municipio_periodo.csv",
    "df_crc": "silver/crc_municipio_trimestre.csv",
    "df_dane": "silver/dane_municipio_anio.csv",
    "df_unificado": "gold/df_unificado.csv",
    "df_final": "gold/panel_municipio_anio.csv",
    "df_resumen_anual": "gold/resumen_anual.csv",
    "df_cobertura": "quality/cobertura_cruces.csv",
    "df_balance": "quality/balance_fuentes.csv",
}
INTEGER_COLUMNS = {
    "anio", "trimestre", "estudiantes", "periodos_icfes", "trimestres_crc",
    "hogares", "fila_excel", "municipios", "municipios_cobertura_completa",
    "leidos", "rechazados", "validos",
}
BOOLEAN_COLUMNS = {
    "tiene_icfes", "tiene_crc", "tiene_dane", "integrado",
    "cobertura_temporal_completa", "tasa_mayor_100",
}


def cargar_dataframes(output_dir=None, *, run_dir=None) -> dict[str, pd.DataFrame]:
    """Carga tablas unificadas y conserva códigos, enteros nulos y booleanos.

    Sin argumentos lee `data/latest.json` del proyecto. Para una entrega trasladada
    puede usarse `run_dir="resultados"`, sin depender de rutas del equipo original.
    Bronze se expone como catálogo de archivos, no como una tabla que mezcle
    estudiantes, conexiones y hogares de granularidades incompatibles.
    """
    if run_dir is None:
        root = Path(output_dir) if output_dir is not None else PROJECT / "data"
        pointer = json.loads((root / "latest.json").read_text(encoding="utf-8"))
        run = root / "runs" / pointer["run_id"]
    else:
        run = Path(run_dir)
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    if report["status"] != "completed":
        raise ValueError("La ejecución seleccionada no terminó correctamente.")
    frames = {}
    for name, relative in TABLES.items():
        path = run / relative
        if not path.exists():
            raise FileNotFoundError(f"Falta {path}. Ejecute nuevamente el ETL actualizado.")
        header = pd.read_csv(path, nrows=0).columns
        types = {col: "Int64" for col in header if col in INTEGER_COLUMNS}
        types.update({col: "boolean" for col in header if col in BOOLEAN_COLUMNS})
        types.update({col: "string" for col in header if col in {"codigo_municipio", "periodo"}})
        frames[name] = pd.read_csv(path, dtype=types)
    frames["df_bronze_catalogo"] = pd.DataFrame(
        json.loads((run / "manifest.json").read_text(encoding="utf-8")))
    return frames


def ejecutar_etl(config_path=None) -> dict[str, pd.DataFrame]:
    """Ejecuta Bronze → Silver → Gold y devuelve las tablas listas para trabajar.

    Usa el mismo intérprete de Python del llamador. Una falla produce una excepción
    y no devuelve silenciosamente resultados anteriores. Las rutas relativas de
    configuración se interpretan desde la raíz del proyecto.
    """
    config = Path(config_path) if config_path is not None else PROJECT / "config/local.json"
    if not config.is_absolute():
        config = PROJECT / config
    settings = json.loads(config.read_text(encoding="utf-8"))
    subprocess.run([sys.executable, "-m", "etl_medallon", "--config", str(config)],
                   cwd=PROJECT, check=True)
    output = Path(settings["output_dir"]).expanduser()
    if not output.is_absolute():
        output = PROJECT / output
    return cargar_dataframes(output)
