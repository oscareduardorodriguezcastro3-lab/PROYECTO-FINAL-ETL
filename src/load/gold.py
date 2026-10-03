"""Gold: producto analítico municipio-año y evidencia de cobertura."""

import pandas as pd

from .common import unique, write_csv

KEYS = ["codigo_municipio", "anio"]


def unify(exam, internet, households):
    """Integra con unión externa para que ninguna ausencia quede oculta.

    Un promedio anual ICFES pondera por registros válidos. Accesos CRC es el
    promedio de totales trimestrales observados, nunca la suma de trimestres.
    """
    scores = exam.groupby(KEYS, as_index=False).agg(
        suma_puntaje=("suma_puntaje", "sum"), estudiantes=("estudiantes", "sum"),
        periodos_icfes=("periodo", "nunique"))
    scores["puntaje_global"] = scores.suma_puntaje / scores.estudiantes
    scores = scores.drop(columns="suma_puntaje")
    access = internet.groupby(KEYS, as_index=False).agg(
        accesos_residenciales=("accesos", "mean"), trimestres_crc=("trimestre", "nunique"))
    household = households.drop(columns="fila_excel", errors="ignore")
    for label, table in [("ICFES", scores), ("CRC", access), ("DANE", household)]:
        unique(table, KEYS, label)
        table[f"tiene_{label.lower()}"] = True
    merged = scores.merge(access, on=KEYS, how="outer", validate="one_to_one").merge(
        household, on=KEYS, how="outer", validate="one_to_one")
    flags = ["tiene_icfes", "tiene_crc", "tiene_dane"]
    for col in flags:
        merged[col] = merged[col].eq(True)
    matched = merged[flags].all(axis=1)
    coverage = merged[KEYS + flags].copy()
    coverage["integrado"] = matched
    merged["integrado"] = matched
    merged["accesos_por_100_hogares"] = (
        merged.accesos_residenciales / merged.hogares.where(merged.hogares.gt(0)) * 100
    )
    merged["cobertura_temporal_completa"] = merged.periodos_icfes.eq(2) & merged.trimestres_crc.eq(4)
    merged["tasa_mayor_100"] = merged.accesos_por_100_hogares.gt(100).astype("boolean")
    merged.loc[merged.accesos_por_100_hogares.isna(), "tasa_mayor_100"] = pd.NA
    return merged.sort_values(KEYS).reset_index(drop=True), coverage.sort_values(KEYS)


def integrate(exam, internet, households):
    """Entrega el panel con tres fuentes y el reporte de todas las llaves."""
    merged, coverage = unify(exam, internet, households)
    panel = merged.loc[merged.integrado].drop(
        columns=["tiene_icfes", "tiene_crc", "tiene_dane", "integrado"]).copy()
    if panel.empty:
        raise ValueError("No hay municipios-año con las tres fuentes.")
    if not panel.hogares.gt(0).all():
        raise ValueError("Gold requiere hogares positivos.")
    panel["accesos_por_100_hogares"] = panel.accesos_residenciales / panel.hogares * 100
    panel["cobertura_temporal_completa"] = panel.periodos_icfes.eq(2) & panel.trimestres_crc.eq(4)
    panel["tasa_mayor_100"] = panel.accesos_por_100_hogares.gt(100)
    # Más de 100 accesos/100 hogares se señala, no se recorta artificialmente.
    return panel.sort_values(KEYS), coverage.sort_values(KEYS)


def build(exam, internet, households, run):
    """Publica panel, cobertura y resumen anual con tamaño de muestra visible."""
    panel, coverage = integrate(exam, internet, households)
    unified, _ = unify(exam, internet, households)
    write_csv(unified, run / "gold" / "df_unificado.csv")
    write_csv(panel, run / "gold" / "panel_municipio_anio.csv")
    write_csv(coverage, run / "quality" / "cobertura_cruces.csv")
    summary = panel.groupby("anio", as_index=False).agg(
        municipios=("codigo_municipio", "nunique"),
        puntaje_medio_municipal=("puntaje_global", "mean"),
        accesos_por_100_hogares_media_municipal=("accesos_por_100_hogares", "mean"),
        municipios_cobertura_completa=("cobertura_temporal_completa", "sum"))
    write_csv(summary, run / "gold" / "resumen_anual.csv")
    return {"filas_gold": len(panel), "municipios_gold": panel.codigo_municipio.nunique(),
        "municipios_anio_no_integrados": int((~coverage.integrado).sum()),
        "filas_cobertura_incompleta": int((~panel.cobertura_temporal_completa).sum()),
        "tasas_mayores_100": int(panel.tasa_mayor_100.sum())}
