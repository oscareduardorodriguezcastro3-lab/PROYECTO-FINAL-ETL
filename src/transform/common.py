"""Funciones pequeñas compartidas por las tres capas."""

import hashlib
import json
from pathlib import Path

import pandas as pd


def save_json(path: Path, value) -> None:
    """Escribe metadatos legibles; los datos tabulares se guardan en CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    """Calcula una huella sin cargar el archivo completo en memoria."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def municipality(values: pd.Series) -> pd.Series:
    """Conserva DIVIPOLA como texto de 5 dígitos; un formato inválido es nulo.

    Esto valida formato, no existencia oficial. El cruce DANE permite auditar
    códigos sin correspondencia. Nunca se usa el nombre como llave.
    """
    text = values.astype("string").str.strip()
    return text.where(text.str.fullmatch(r"[0-9]{1,5}", na=False)).str.zfill(5)


def unique(frame: pd.DataFrame, keys: list[str], label: str) -> None:
    """Impide que un cruce multiplique filas por llaves repetidas o nulas."""
    if frame[keys].isna().any().any() or frame.duplicated(keys).any():
        raise ValueError(f"{label}: llave nula o duplicada: {keys}")


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    """CSV UTF-8, sin índice artificial, con punto como separador decimal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8")
