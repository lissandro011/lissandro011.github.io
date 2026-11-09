"""Licha Bot: bot de WhatsApp de stickers al que se le pueden sumar comandos.

Para crear comandos nuevos, mirá comandos/_plantilla.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .comandos import REGISTRO, Comando, comando, escuchar
from .errores import ErrorUsuario

if TYPE_CHECKING:
    from .contexto import Contexto

NOMBRE = "Licha Bot"
__version__ = "1.0.0"

__all__ = ["NOMBRE", "REGISTRO", "Comando", "Contexto", "ErrorUsuario", "comando", "escuchar", "__version__"]


def __getattr__(nombre: str) -> Any:
    # Contexto se importa recién cuando se usa: carga la librería de WhatsApp,
    # que no hace falta para probar el conversor de stickers por consola.
    if nombre == "Contexto":
        from .contexto import Contexto

        return Contexto
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")
