"""Persistencia explícita de las tablas Silver."""

from pathlib import Path

from ..transform.common import write_csv


def guardar_silver(tables: dict, run: Path) -> None:
    names = {
        "icfes": "icfes_municipio_periodo.csv",
        "crc": "crc_municipio_trimestre.csv",
        "dane": "dane_municipio_anio.csv",
    }
    for key, name in names.items():
        write_csv(tables[key], Path(run) / "silver" / name)
