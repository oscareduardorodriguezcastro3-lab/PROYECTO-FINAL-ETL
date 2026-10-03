import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.transform.common import sha256
from src.load.load_bronze import discover
from src.load.storage import publicar_ultima_version
from src.pipeline import cargar_configuracion
from src.analysis.reporting import generar_reportes


ROOT = Path(__file__).resolve().parents[1]


class FinalAdjustmentTests(unittest.TestCase):
    def test_yaml_configuration_is_loadable(self):
        config = cargar_configuracion(ROOT / "config" / "config.yaml")
        self.assertEqual(config["years"], [2022, 2023, 2024, 2025])
        self.assertEqual(config["chunksize"], 50000)

    def test_invalid_configuration_fails_clearly(self):
        with self.assertRaises(FileNotFoundError):
            cargar_configuracion(ROOT / "config" / "does_not_exist.yaml")

    def test_bronze_hash_is_preserved(self):
        sample = ROOT / "data" / "bronze" / "icfes"
        files = list(sample.glob("*/*.txt"))
        self.assertTrue(files)
        self.assertEqual(len(sha256(files[0])), 64)

    def test_empty_raw_uses_existing_bronze_snapshot(self):
        files = discover(ROOT / "data" / "raw")
        self.assertTrue(files["icfes"])
        self.assertEqual(len(files["crc"]), 1)
        self.assertEqual(len(files["dane"]), 1)

    def test_reporting_historical_run(self):
        run = ROOT / "data" / "runs" / "20260922T164653_d3e80760"
        with TemporaryDirectory() as folder:
            result = generar_reportes(run, Path(folder))
            self.assertTrue(Path(result["eda"]).exists())
            self.assertTrue((Path(folder) / "quality" / "rechazos_por_motivo.csv").exists())
            self.assertTrue((Path(folder) / "audit" / "integracion_gold.csv").exists())

    def test_publication_keeps_history_and_updates_current_layers(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            run = root / "runs" / "run-1"
            (run / "silver").mkdir(parents=True)
            (run / "gold").mkdir(parents=True)
            (run / "silver" / "icfes_municipio_periodo.csv").write_text("v1", encoding="utf-8")
            (run / "gold" / "panel_municipio_anio.csv").write_text("v1", encoding="utf-8")
            publicar_ultima_version(run, root)
            self.assertTrue((run / "silver" / "icfes_municipio_periodo.csv").exists())
            self.assertEqual((root / "silver" / "icfes_municipio_periodo.csv").read_text(), "v1")
            self.assertEqual((root / "gold" / "panel_municipio_anio.csv").read_text(), "v1")

            failed_run = root / "runs" / "run-failed"
            (failed_run / "silver").mkdir(parents=True)
            with self.assertRaises(FileNotFoundError):
                publicar_ultima_version(failed_run, root)
            self.assertEqual((root / "gold" / "panel_municipio_anio.csv").read_text(), "v1")

    def test_latest_pointer_describes_current_publication(self):
        pointer = json.loads((ROOT / "data" / "latest.json").read_text(encoding="utf-8"))
        for key in ("run_id", "status", "fecha", "silver_path", "gold_path", "historical_run_path"):
            self.assertIn(key, pointer)
        self.assertEqual(pointer["status"], "completed")
        self.assertTrue((ROOT / "data" / "silver").exists())
        self.assertTrue((ROOT / "data" / "gold").exists())

if __name__ == "__main__":
    unittest.main()
