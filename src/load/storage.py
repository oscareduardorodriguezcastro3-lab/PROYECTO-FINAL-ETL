"""Utilidades de almacenamiento compartidas por las cargas."""

import shutil
from ..transform.common import write_csv, save_json
from pathlib import Path


def publicar_ultima_version(run: Path, output: Path) -> None:
    """Publica Silver/Gold del run sin mover ni borrar el histórico.

    Copia primero a staging y reemplaza solo los CSV presentes en el run. Si
    algo falla, restaura los archivos anteriores y deja intacta la publicación.
    """
    run, output = Path(run), Path(output)
    staging = output / f".publish_{run.name}"
    backup = output / f".backup_{run.name}"
    mappings = {
        "silver": sorted((run / "silver").glob("*.csv")),
        "gold": sorted((run / "gold").glob("*.csv")),
    }
    if not any(mappings.values()):
        raise FileNotFoundError(f"El run no contiene artefactos Silver/Gold: {run}")
    try:
        for layer, files in mappings.items():
            target_dir = staging / layer
            target_dir.mkdir(parents=True, exist_ok=True)
            for source in files:
                shutil.copy2(source, target_dir / source.name)
        for layer, files in mappings.items():
            target_dir = output / layer
            target_dir.mkdir(parents=True, exist_ok=True)
            for source in files:
                target = target_dir / source.name
                old = backup / layer / source.name
                if target.exists():
                    old.parent.mkdir(parents=True, exist_ok=True)
                    target.replace(old)
                (staging / layer / source.name).replace(target)
    except Exception:
        for layer, files in mappings.items():
            target_dir = output / layer
            for source in files:
                target = target_dir / source.name
                if target.exists():
                    target.unlink()
                old = backup / layer / source.name
                if old.exists():
                    old.replace(target)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


__all__ = ["write_csv", "save_json", "publicar_ultima_version"]
