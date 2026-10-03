"""Localización del XLSX DANE sin transformación de negocio."""

from pathlib import Path


def extraer_dane(source_dir: Path) -> Path:
    paths = sorted(Path(source_dir).glob("anexo-proyecciones*.xlsx"))
    if len(paths) != 1:
        raise FileNotFoundError("Se requiere exactamente un XLSX DANE.")
    return paths[0]
