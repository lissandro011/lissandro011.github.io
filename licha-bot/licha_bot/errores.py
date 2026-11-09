"""Errores esperados del bot."""

from __future__ import annotations


class ErrorUsuario(Exception):
    """Algo que no se puede hacer y hay que explicarle a quien escribió.

    Si un comando lanza este error, el bot responde `mensaje` en el chat y deja
    `detalle` (si lo hay) en el log. Sirve para cortar un comando en cualquier
    punto sin tener que manejar la respuesta a mano:

        if not ctx.args:
            raise ErrorUsuario("Decime qué buscar, por ejemplo: !buscar gatos")
    """

    def __init__(self, mensaje: str, detalle: str | None = None):
        super().__init__(detalle or mensaje)
        self.mensaje = mensaje
