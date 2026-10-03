"""Fachada de calidad; el coordinador publica los CSV auditables."""

from .reporting import generar_reportes

__all__ = ["generar_reportes"]
