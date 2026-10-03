"""Pruebas con cifras pequeñas cuyo resultado se calcula a mano.

Ejecutar: python -m unittest discover -s tests -v
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from src.transform.common import municipality
from src.load.gold import integrate, unify
from src.transform.silver import Audit, crc, icfes


class PipelineTests(unittest.TestCase):
    def test_divipola(self):
        codes = municipality(pd.Series(["5001", " 05001 ", "abc", "123456", ""]))
        self.assertEqual(codes.iloc[:2].tolist(), ["05001", "05001"])
        self.assertTrue(codes.iloc[2:].isna().all())

    def inputs(self):
        # Tres alumnos: (100 + 300 + 300)/3, no (100 + 300)/2.
        exam = pd.DataFrame({"codigo_municipio": ["05001", "05001"],
            "anio": [2022, 2022], "periodo": ["20221", "20222"],
            "suma_puntaje": [100, 600], "estudiantes": [1, 2]})
        internet = pd.DataFrame({"codigo_municipio": ["05001"] * 2,
            "anio": [2022] * 2, "trimestre": [1, 2], "accesos": [10, 30]})
        homes = pd.DataFrame({"codigo_municipio": ["05001", "05002"],
            "anio": [2022, 2022], "hogares": [10, 50]})
        return exam, internet, homes

    def test_weighted_mean_quarters_unmatched_and_rate(self):
        panel, coverage = integrate(*self.inputs())
        self.assertEqual(len(panel), 1)
        self.assertAlmostEqual(panel.iloc[0].puntaje_global, 700 / 3)
        self.assertEqual(panel.iloc[0].accesos_residenciales, 20)
        self.assertEqual(panel.iloc[0].accesos_por_100_hogares, 200)
        self.assertTrue(panel.iloc[0].tasa_mayor_100)
        self.assertFalse(panel.iloc[0].cobertura_temporal_completa)
        self.assertEqual(int((~coverage.integrado).sum()), 1)

    def test_duplicate_household_key_fails(self):
        exam, internet, homes = self.inputs()
        with self.assertRaisesRegex(ValueError, "duplicada"):
            integrate(exam, internet, pd.concat([homes, homes]))

    def test_unified_preserves_missing_values(self):
        unified, _ = unify(*self.inputs())
        self.assertEqual(len(unified), 2)
        unmatched = unified.loc[unified.codigo_municipio.eq("05002")].iloc[0]
        self.assertFalse(unmatched.integrado)
        self.assertTrue(unmatched.tiene_dane)
        self.assertTrue(pd.isna(unmatched.puntaje_global))
        self.assertTrue(pd.isna(unmatched.accesos_por_100_hogares))
        self.assertTrue(pd.isna(unmatched.tasa_mayor_100))

    def test_zero_denominator_fails(self):
        exam, internet, homes = self.inputs()
        homes.loc[0, "hogares"] = 0
        with self.assertRaisesRegex(ValueError, "positivos"):
            integrate(exam, internet, homes)

    def test_icfes_quarantine_and_chunk_invariance(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "Examen_Saber_11_20221.txt"
            source.write_text("periodo;estu_consecutivo;cole_cod_mcpio_ubicacion;punt_global\n"
                "20221;a;5001;100\n20221;b;05001;300\n20221;c;5001;999\n"
                "20222;d;5001;200\n", encoding="utf-8")
            small, _ = icfes([source], [2022], 1, Audit(root / "small"))
            large, _ = icfes([source], [2022], 10, Audit(root / "large"))
            pd.testing.assert_frame_equal(small, large)
            self.assertEqual(small.iloc[0].estudiantes, 2)
            self.assertEqual(small.iloc[0].puntaje_promedio, 200)
            rejects = pd.read_csv(root / "small/quality/rechazos.csv")
            self.assertEqual(rejects.registro.tolist(), [3, 4])

    def test_duplicate_icfes_across_chunks_fails(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "Examen_Saber_11_20221.txt"
            source.write_text("periodo;estu_consecutivo;cole_cod_mcpio_ubicacion;punt_global\n"
                              "20221;a;5001;100\n20221;a;5001;200\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicado"):
                icfes([source], [2022], 1, Audit(root))

    def test_crc_filter_and_sum(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "crc.csv"
            source.write_text("ANNO;TRIMESTRE;ID_MUNICIPIO;SEGMENTO;ACCESOS\n"
                "2022;1;5001;Residencial - Estrato 1;10\n"
                "2022;1;5001;Residencial - Estrato 2;20\n"
                "2022;1;5001;Corporativo;90\n"
                "2021;1;5001;Residencial;70\n"
                "2022;1;5001;Residencial;-5\n", encoding="utf-8")
            result, excluded = crc(source, [2022], 2, Audit(root))
            self.assertEqual(result.iloc[0].accesos, 30)
            self.assertEqual(excluded, 2)
            self.assertEqual(len(pd.read_csv(root / "quality/rechazos.csv")), 1)


if __name__ == "__main__":
    unittest.main()
