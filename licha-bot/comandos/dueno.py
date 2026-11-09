"""Comandos solo para los dueños del bot ([bot] duenos en config.toml)."""

from __future__ import annotations

from licha_bot import comando
from licha_bot.bot import SALIDA_OK, SALIDA_REINICIAR
from licha_bot.contexto import Contexto


@comando(
    "reiniciar",
    categoria="Dueño",
    descripcion="Reinicia el bot (por ejemplo, para cargar comandos nuevos)",
    solo_dueno=True,
)
async def reiniciar(ctx: Contexto) -> None:
    await ctx.responder("♻️ Reiniciando… vuelvo en unos segundos.")
    await ctx.bot.detener(SALIDA_REINICIAR)  # iniciar.bat lo vuelve a abrir


@comando("apagar", categoria="Dueño", descripcion="Apaga el bot", solo_dueno=True)
async def apagar(ctx: Contexto) -> None:
    await ctx.responder("👋 Apagando. Para prenderlo de nuevo, abrí iniciar.bat en la PC.")
    await ctx.bot.detener(SALIDA_OK)
