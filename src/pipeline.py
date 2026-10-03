"""Orquestación pública del proyecto."""

from pathlib import Path
import json
import subprocess
import sys

import yaml

from .dataframes import cargar_dataframes
from .analysis.reporting import generar_reportes


def cargar_configuracion(config_path=None):
    """Carga YAML como fuente principal y conserva fallback JSON temporal."""
    root = Path(__file__).resolve().parents[1]
    config = Path(config_path) if config_path else root / "config" / "config.yaml"
    if not config.is_absolute():
        config = root / config
    if config.suffix.lower() in {".yaml", ".yml"}:
        raw = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        source = raw.get("fuentes", {}).get("source_dir") or ""
        override = __import__("os").environ.get("ETL_SOURCE_DIR")
        if override:
            source = override
        if source and not Path(source).expanduser().is_absolute():
            source = str((root / source).resolve())
        routes = raw.get("rutas", {})
        runs = Path(routes.get("runs", "data/runs"))
        base = runs.parent
        return {"source_dir": source, "output_dir": str(base),
                "years": raw.get("etl", {}).get("years", []),
                "chunksize": raw.get("etl", {}).get("chunksize", 0),
                "scheduler": raw.get("scheduler", {}), "project_config": raw}
    return json.loads(config.read_text(encoding="utf-8"))


def ejecutar_pipeline(config_path=None):
    """Ejecuta el ETL y genera reportes; devuelve los DataFrames publicados."""
    root = Path(__file__).resolve().parents[1]
    config = Path(config_path) if config_path else root / "config" / "config.yaml"
    if not config.is_absolute():
        config = root / config
    settings = cargar_configuracion(config)
    if not settings["source_dir"] or not Path(settings["source_dir"]).expanduser().exists():
        raise FileNotFoundError("source_dir no existe. Defina fuentes.source_dir en config.yaml o ETL_SOURCE_DIR.")
    subprocess.run([sys.executable, "-m", "src.cli", "--config", str(config)], cwd=root, check=True)
    output = Path(settings["output_dir"])
    if not output.is_absolute(): output = root / output
    frames = cargar_dataframes(output)
    pointer = json.loads((output / "latest.json").read_text(encoding="utf-8"))
    run = output / "runs" / pointer["run_id"]
    generar_reportes(run, root / "outputs")
    return frames
