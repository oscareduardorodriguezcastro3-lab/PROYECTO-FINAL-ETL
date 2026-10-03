"""Punto de entrada didáctico: python ejecutar_proyecto.py [--solo-cargar]."""

import argparse

from src.dataframes import cargar_dataframes, ejecutar_etl


def main():
    parser = argparse.ArgumentParser(description="Obtener los DataFrames del ETL Medallón")
    parser.add_argument("--solo-cargar", action="store_true",
                        help="Reutiliza los resultados existentes sin reprocesar fuentes")
    args = parser.parse_args()
    frames = cargar_dataframes() if args.solo_cargar else ejecutar_etl()

    # Silver: cada fuente ya está unificada con su propia granularidad.
    df_icfes = frames["df_icfes"]
    df_crc = frames["df_crc"]
    df_dane = frames["df_dane"]

    # Gold: todas las llaves, incluso si alguna fuente falta.
    df_unificado = frames["df_unificado"]
    # Gold: solamente municipio-año con las tres fuentes presentes.
    df_final = frames["df_final"]

    for name, frame in frames.items():
        print(f"{name}: {len(frame):,} filas × {len(frame.columns)} columnas")
    print("\nPrimeras filas del DataFrame final:")
    print(df_final.head().to_string(index=False))
    return frames


if __name__ == "__main__":
    main()
