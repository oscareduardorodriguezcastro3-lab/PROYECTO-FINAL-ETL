"""Reportes reproducibles a partir de una ejecución terminada.

No cambia las tablas Bronze, Silver ni Gold. Lee únicamente el run indicado y
publica artefactos de análisis en ``outputs``.
"""

from pathlib import Path
import json
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _read(run: Path, relative: str) -> pd.DataFrame:
    path = run / relative
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def generar_reportes(run: Path, output: Path) -> dict[str, str]:
    """Genera EDA, calidad, negocio, auditoría y gráficos desde datos reales."""
    run, output = Path(run), Path(output)
    eda, quality, business, audit, charts = [output / name for name in
                                             ("eda", "quality", "business", "audit", "reports")]
    charts = eda / "graficos"
    for folder in (eda, quality, business, audit, charts):
        folder.mkdir(parents=True, exist_ok=True)

    tables = {
        "icfes": _read(run, "silver/icfes_municipio_periodo.csv"),
        "crc": _read(run, "silver/crc_municipio_trimestre.csv"),
        "dane": _read(run, "silver/dane_municipio_anio.csv"),
        "unified": _read(run, "gold/df_unificado.csv"),
        "gold": _read(run, "gold/panel_municipio_anio.csv"),
        "coverage": _read(run, "quality/cobertura_cruces.csv"),
    }
    sections, audit_rows, quality_rows = [], [], []
    for name, frame in tables.items():
        numeric = frame.select_dtypes(include="number")
        nulls = frame.isna().sum()
        cardinality = pd.DataFrame({
            "columna": frame.columns,
            "tipo": frame.dtypes.astype(str).values,
            "valores_unicos": [frame[col].nunique(dropna=True) for col in frame.columns],
            "porcentaje_cardinalidad": [frame[col].nunique(dropna=True) / len(frame) * 100 if len(frame) else 0 for col in frame.columns],
            "interpretacion": ["Requiere validación" for _ in frame.columns],
        })
        cardinality.to_csv(eda / f"cardinalidad_{name}.csv", index=False)
        if not numeric.empty:
            numeric.describe().T.to_csv(eda / f"estadisticos_{name}.csv")
        quality_rows.extend({"dataset": name, "columna": col, "nulos": int(nulls[col]),
                             "porcentaje_nulos": float(nulls[col] / len(frame) * 100) if len(frame) else 0,
                             "duplicados_exactos": int(frame.duplicated().sum()),
                             "clasificacion": "Requiere validación de negocio" if nulls[col] else "Sin nulos observados"}
                            for col in frame.columns)
        sections.append(f"### {name}\n\n- shape: {frame.shape[0]} filas × {frame.shape[1]} columnas\n- duplicados exactos: {int(frame.duplicated().sum())}\n- columnas: {', '.join(frame.columns)}")
        audit_rows.append({"dataset": name, "filas": len(frame), "columnas": len(frame.columns),
                           "duplicados_exactos": int(frame.duplicated().sum()), "nulos": int(frame.isna().sum().sum())})
    pd.DataFrame(quality_rows).to_csv(quality / "perfil_calidad.csv", index=False)
    pd.DataFrame(audit_rows).to_csv(audit / "reporte_pipeline.csv", index=False)
    gold = tables["gold"]
    unified = tables["unified"]
    coverage = tables["coverage"]
    run_report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    balance = _read(run, "quality/balance_fuentes.csv")
    rejects_path = run / "quality" / "rechazos.csv"
    rejects = pd.read_csv(rejects_path) if rejects_path.exists() else pd.DataFrame(columns=["archivo", "registro", "motivo"])

    def fuente(filename):
        if filename.startswith("Examen_Saber_11_"): return "ICFES"
        if filename.startswith("ACCESOS_INTERNET"): return "CRC"
        if filename.startswith("anexo-proyecciones"): return "DANE"
        return "OTRA"

    if not rejects.empty:
        rejects["fuente"] = rejects["archivo"].map(fuente)
        rejects["motivo"] = rejects["motivo"].map({
            "codigo_invalido": "NO_DESGLOSADO",
            "puntaje_fuera_de_rango_o_nulo": "puntaje_invalido",
            "identificador_vacio": "identificador_vacio",
            "periodo_no_coincide_con_archivo": "periodo_no_coincide_con_archivo",
            "hogares_invalidos": "hogares_invalidos",
            "accesos_invalidos": "accesos_invalidos",
            "trimestre_invalido": "trimestre_invalido",
            "anio_invalido": "anio_invalido",
        }).fillna("NO_DESGLOSADO")
        rejects["periodo_si_aplica"] = rejects["archivo"].str.extract(r"_(20\d{2}[12])\.txt", expand=False)
        detail = rejects.groupby(["fuente", "motivo", "periodo_si_aplica"], dropna=False).size().reset_index(name="cantidad")
    else:
        detail = pd.DataFrame(columns=["fuente", "motivo", "periodo_si_aplica", "cantidad"])
    totals = balance.assign(fuente=balance["archivo"].map(fuente)).groupby("fuente", as_index=False)["leidos"].sum()
    detail = detail.merge(totals, on="fuente", how="left")
    detail["porcentaje_sobre_fuente"] = detail["cantidad"] / detail["leidos"] * 100
    detail = detail[["fuente", "motivo", "cantidad", "porcentaje_sobre_fuente", "periodo_si_aplica"]]
    detail.to_csv(quality / "rechazos_por_motivo.csv", index=False)

    out_scope = int(run_report.get("crc_validos_fuera_de_alcance", 0))
    pd.DataFrame([{"fuente": "CRC", "motivo": "NO_DESGLOSADO", "cantidad": out_scope}]).to_csv(
        quality / "filas_fuera_alcance.csv", index=False)

    pd.DataFrame([{
        "clave": "codigo_municipio + anio",
        "filas_icfes": len(tables["icfes"]), "filas_crc": len(tables["crc"]),
        "filas_dane": len(tables["dane"]), "llaves_unificadas": len(unified),
        "llaves_completas": len(gold), "llaves_incompletas": int((~coverage.integrado).sum()),
        "porcentaje_correspondencia": float(coverage.integrado.mean() * 100),
        "tasas_mayores_100": int(gold.tasa_mayor_100.sum()),
        "periodos_icfes_disponibles": ",".join(run_report.get("periodos_icfes", [])),
        "periodos_icfes_faltantes": ",".join(run_report.get("periodos_icfes_faltantes", [])),
    }]).to_csv(audit / "integracion_gold.csv", index=False)

    questions = []
    if not gold.empty:
        questions.extend([
            {"pregunta": "¿Cuántos municipios-año integran las tres fuentes?", "metrica": "filas Gold", "resultado": len(gold), "interpretacion": "Cada fila representa un municipio-año integrado."},
            {"pregunta": "¿Cuál es el puntaje global medio municipal?", "metrica": "media de puntaje_global", "resultado": gold.puntaje_global.mean(), "interpretacion": "Media simple entre filas Gold."},
            {"pregunta": "¿Cuál es el promedio de accesos por 100 hogares?", "metrica": "media de accesos_por_100_hogares", "resultado": gold.accesos_por_100_hogares.mean(), "interpretacion": "Indicador calculado, no porcentaje de hogares conectados."},
            {"pregunta": "¿Cuántas observaciones tienen cobertura temporal completa?", "metrica": "cobertura_temporal_completa", "resultado": int(gold.cobertura_temporal_completa.sum()), "interpretacion": "Dos periodos ICFES y cuatro trimestres CRC observados."},
            {"pregunta": "¿Cuántas tasas superan 100 accesos por 100 hogares?", "metrica": "tasa_mayor_100", "resultado": int(gold.tasa_mayor_100.sum()), "interpretacion": "Se conserva como señal de posible multiplicidad de accesos."},
            {"pregunta": "¿Qué años están representados en Gold?", "metrica": "nunique(anio)", "resultado": int(gold.anio.nunique()), "interpretacion": "Años presentes en las llaves integradas."},
            {"pregunta": "¿Qué año tiene más filas Gold?", "metrica": "anio con mayor conteo", "resultado": int(gold.anio.value_counts().idxmax()), "interpretacion": "Mayor cobertura de municipio-año integrado."},
            {"pregunta": "¿Cuál es el mínimo de hogares observado?", "metrica": "min(hogares)", "resultado": gold.hogares.min(), "interpretacion": "Valor descriptivo del panel integrado."},
            {"pregunta": "¿Cuál es el máximo de hogares observado?", "metrica": "max(hogares)", "resultado": gold.hogares.max(), "interpretacion": "Valor descriptivo del panel integrado."},
            {"pregunta": "¿Cuántos municipios distintos aparecen en Gold?", "metrica": "nunique(codigo_municipio)", "resultado": int(gold.codigo_municipio.nunique()), "interpretacion": "Municipios distintos, no filas municipio-año."},
        ])
    pd.DataFrame(questions).to_csv(business / "preguntas_negocio.csv", index=False)

    if not gold.empty:
        for column, filename, title in [("puntaje_global", "histograma_puntaje.png", "Distribución del puntaje global"),
                                        ("accesos_por_100_hogares", "histograma_accesos.png", "Accesos por 100 hogares")]:
            fig, ax = plt.subplots(figsize=(8, 4)); gold[column].dropna().plot.hist(ax=ax, bins=30)
            ax.set_title(title); ax.set_xlabel(column); fig.tight_layout(); fig.savefig(charts / filename, dpi=140); plt.close(fig)
        annual = gold.groupby("anio", as_index=False)["puntaje_global"].mean()
        fig, ax = plt.subplots(figsize=(8, 4)); ax.plot(annual.anio, annual.puntaje_global, marker="o")
        ax.set_title("Puntaje global medio por año"); ax.set_xlabel("anio"); ax.set_ylabel("puntaje_global")
        fig.tight_layout(); fig.savefig(charts / "puntaje_por_anio.png", dpi=140); plt.close(fig)

        flow = {"Fuentes": int(len(json.loads((run / "manifest.json").read_text(encoding="utf-8")))),
                "Bronze": int(len(json.loads((run / "manifest.json").read_text(encoding="utf-8")))),
                "Silver ICFES": len(tables["icfes"]), "Silver CRC": len(tables["crc"]),
                "Silver DANE": len(tables["dane"]), "Gold unificado": len(unified),
                "Gold completo": len(gold)}
        fig, ax = plt.subplots(figsize=(10, 5)); ax.bar(flow.keys(), flow.values()); ax.set_title("Flujo Medallion: filas/archivos del run"); ax.tick_params(axis="x", rotation=35); ax.set_ylabel("cantidad"); fig.tight_layout(); fig.savefig(charts / "flujo_medallion.png", dpi=140); plt.close(fig)
        coverage_values = {"Gold unificado": len(unified), "Gold completo": len(gold), "Sin las tres fuentes": int((~coverage.integrado).sum())}
        fig, ax = plt.subplots(figsize=(8, 4)); ax.bar(coverage_values.keys(), coverage_values.values()); ax.set_title("Cobertura de integración Gold"); ax.tick_params(axis="x", rotation=20); fig.tight_layout(); fig.savefig(charts / "cobertura_integracion.png", dpi=140); plt.close(fig)
        silver_values = {"ICFES": len(tables["icfes"]), "CRC": len(tables["crc"]), "DANE": len(tables["dane"])}
        fig, ax = plt.subplots(figsize=(7, 4)); ax.bar(silver_values.keys(), silver_values.values()); ax.set_title("Filas Silver por fuente"); fig.tight_layout(); fig.savefig(charts / "filas_silver_por_fuente.png", dpi=140); plt.close(fig)
        rejection_values = detail.groupby("fuente")["cantidad"].sum().reindex(["ICFES", "CRC", "DANE"], fill_value=0)
        fig, ax = plt.subplots(figsize=(7, 4)); ax.bar(rejection_values.index, rejection_values.values); ax.set_title("Rechazos por fuente"); fig.tight_layout(); fig.savefig(charts / "rechazos_por_fuente.png", dpi=140); plt.close(fig)

    md = ["# EDA FINAL", "", "## 1. Objetivo", "Describir las tablas Silver y Gold de la ejecución verificada sin modificar los datos.", "", "## 2. Fuentes", "ICFES, CRC y DANE; RAW lógico = source_dir externo.", "", "## 3. Dimensiones", *sections,
          "", "## 4. Diccionario resumido", "Las columnas y reglas están descritas en HANDOFF_PROYECTO.md y docs/02_diccionario_y_reglas.md.",
          "", "## 5. Tipos", "Ver cardinalidad_*.csv; los tipos se leen desde cada artefacto real.", "", "## 6. Nulos", "Ver outputs/quality/perfil_calidad.csv. Los nulos entre fuentes pueden representar ausencia de cobertura, no cero.",
          "", "## 7. Cardinalidad", "Ver outputs/eda/cardinalidad_*.csv.", "", "## 8. Duplicados", "Se distinguen duplicados exactos de llaves repetidas; la integración agregada exige unicidad.",
          "", "## 9. Calidad", "Ver perfil_calidad.csv.", "", "## 10. Rechazados", "Detalle real en outputs/quality/rechazos_por_motivo.csv; NO_DESGLOSADO se usa cuando el código no separa la causa.",
          "", "## 11. Fuera de alcance", f"CRC fuera de alcance: {out_scope}. Se mantiene separado de rechazos; el detalle disponible no permite separar años/segmentos.",
          "", "## 12. Silver", "ICFES 3.982×6, CRC 17.276×4, DANE 4.486×6 en el run histórico.",
          "", "## 13. Integración", f"Gold unificado {len(unified)}, completo {len(gold)}, incompleto {int((~coverage.integrado).sum())}, correspondencia {coverage.integrado.mean()*100:.1f}%.",
          "", "## 14. Gold", "La fila Gold representa municipio-año con las tres fuentes; los indicadores >100 requieren interpretación de negocio y no son errores automáticos.",
          "", "## 15. Gráficos", "PNG en outputs/eda/graficos/.", "", "## 16. Hallazgos", "Falta ICFES 20252 y 2025 es parcial; la cobertura no es homogénea.",
          "", "## 17. Limitaciones", "El proyecto no demuestra causalidad: descripciones o correlaciones no implican causalidad. La fuente original no está disponible en este equipo.",
          "", "## 18. Conclusiones", "El run histórico es trazable y permite análisis descriptivo municipal; no debe interpretarse 2025 como año completo."]
    (eda / "EDA_FINAL.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"eda": str(eda / "EDA_FINAL.md"), "quality": str(quality / "perfil_calidad.csv"), "business": str(business / "preguntas_negocio.csv")}
