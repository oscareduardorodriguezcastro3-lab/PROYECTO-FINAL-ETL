"""Bronze: descubrimiento y copia exacta, versionada por contenido."""

import logging
import shutil
from pathlib import Path

from .common import sha256, save_json


def discover(source: Path) -> dict[str, list[Path]]:
    """Selecciona fuentes originales. df_final.csv es referencia, no entrada."""
    files = {
        "icfes": sorted((source / "Datos ICFES").glob("Examen_Saber_11_*.txt")),
        "crc": sorted(source.glob("ACCESOS_INTERNET*.csv")),
        "dane": sorted(source.glob("anexo-proyecciones*.xlsx")),
    }
    if not files["icfes"] or len(files["crc"]) != 1 or len(files["dane"]) != 1:
        raise ValueError("Se requieren TXT ICFES, un CSV de accesos y un XLSX DANE.")
    return files


def ingest(source: Path, output: Path, run: Path) -> dict[str, list[Path]]:
    """Copia cada versión una vez y verifica su SHA-256 antes de procesarla.

    Los archivos de origen nunca se modifican. Las copias se reutilizan cuando
    el contenido no cambia. El manifiesto de cada ejecución conserva el linaje.
    """
    result, manifest = {}, []
    for kind, paths in discover(source).items():
        result[kind] = []
        for path in paths:
            logging.info("Bronze | %s", path.name)
            digest = sha256(path)
            target = output / "bronze" / kind / digest / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                # El temporal es propio de esta ejecución: no publica copias parciales.
                temporary = target.with_name(path.name + f".{run.name}.tmp")
                shutil.copyfile(path, temporary)
                if sha256(temporary) != digest:
                    raise ValueError(f"El origen cambió durante la copia: {path.name}")
                temporary.replace(target)
            elif sha256(target) != digest:
                raise ValueError(f"Copia Bronze alterada: {target}")
            result[kind].append(target)
            manifest.append({"source": str(path), "bronze": str(target),
                             "type": kind, "sha256": digest,
                             "bytes": target.stat().st_size})
    save_json(run / "manifest.json", manifest)
    return result
