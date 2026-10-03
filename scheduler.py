"""Programador opcional; nunca inicia el bucle al importar el módulo."""

import schedule
import time

from src.pipeline import cargar_configuracion, ejecutar_pipeline


def programar(config_path="config/config.yaml"):
    config = cargar_configuracion(config_path)
    settings = config.get("scheduler", {})
    if settings.get("enabled", True) is False:
        return schedule
    hora = settings.get("hora", "02:00")
    schedule.every().day.at(hora).do(ejecutar_pipeline, config_path)
    return schedule


if __name__ == "__main__":
    programar()
    while True:
        schedule.run_pending()
        time.sleep(30)
