"""Localización/lectura de archivos ICFES; las reglas viven en transform."""

from pathlib import Path


def extraer_icfes(source_dir: Path) -> list[Path]:
    paths = sorted((Path(source_dir) / "Datos ICFES").glob("Examen_Saber_11_*.txt"))
    if not paths:
        raise FileNotFoundError("No se encontraron archivos TXT ICFES.")
    return paths
