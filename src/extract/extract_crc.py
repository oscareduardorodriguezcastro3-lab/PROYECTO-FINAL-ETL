"""Localización del CSV CRC sin transformación de negocio."""

from pathlib import Path


def extraer_crc(source_dir: Path) -> Path:
    paths = sorted(Path(source_dir).glob("ACCESOS_INTERNET*.csv"))
    if len(paths) != 1:
        raise FileNotFoundError("Se requiere exactamente un CSV CRC.")
    return paths[0]
