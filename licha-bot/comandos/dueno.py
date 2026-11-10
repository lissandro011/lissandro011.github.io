"""Comandos solo para los dueños del bot ([bot] duenos en config.toml).

El permiso se revisa antes de correr el comando (en licha_bot/bot.py): si no
sos dueño, el bot contesta y no hace nada.
"""

from __future__ import annotations

from licha_bot import ErrorUsuario, comando
from licha_bot.bot import SALIDA_OK, SALIDA_REINICIAR
from licha_bot.contexto import Contexto

REINICIANDO = (
    "Dale, me reinicio.",
    "Reiniciando. Ahí vamos.",
    "Recibido. Arranco de nuevo.",
    "Bueno, aplicamos la vieja confiable. Reiniciando.",
)
APAGANDO = (
    "Dale, me apago.",
    "Hasta acá llegué por hoy.",
    "Bajo la persiana. Nos vemos.",
    "Me retiro del grupo en espíritu. Apagando.",
)


@comando(
    "reiniciar",
    categoria="Dueño",
    descripcion="Me apagás y me prendés.",
    uso="{p}reiniciar → por ejemplo, para cargar comandos nuevos",
    solo_dueno=True,
)
async def reiniciar(ctx: Contexto) -> None:
    await ctx.responder(ctx.frase("reiniciar", REINICIANDO))
    await ctx.bot.detener(SALIDA_REINICIAR)  # iniciar.bat lo vuelve a abrir


@comando(
    "apagar",
    categoria="Dueño",
    descripcion="Hasta acá llegué.",
    uso="{p}apagar → para prenderlo de nuevo, abrí iniciar.bat en la PC",
    solo_dueno=True,
)
async def apagar(ctx: Contexto) -> None:
    await ctx.responder(ctx.frase("apagar", APAGANDO))
    await ctx.bot.detener(SALIDA_OK)


# --------------------------------------------------------------------------- #
# Grupos: solo el dueño decide dónde se queda el bot (ver licha_bot/guardia.py)
# --------------------------------------------------------------------------- #


def elegir_pendiente(ctx: Contexto, accion: str) -> str:
    """El grupo sobre el que actúa !autorizar / !rechazar: el de este chat, el del código o el único pendiente."""
    guardia = ctx.bot.guardia
    p = ctx.prefijo
    if ctx.es_grupo and not ctx.args:
        return ctx.clave_chat
    pendientes = ctx.bot.almacen.pendientes()
    if ctx.args:
        chat = guardia.buscar_pendiente(ctx.args[0])
        if chat is None:
            raise ErrorUsuario(
                f"No hay ningún grupo esperando con el código {ctx.args[0]}. Mirá cuáles hay con {p}grupos"
            )
        return chat
    if not pendientes:
        raise ErrorUsuario(f"No hay grupos esperando tu permiso. Mirá dónde estoy con {p}grupos")
    if len(pendientes) > 1:
        lista = "\n".join(f"• «{g.nombre or 'sin nombre'}» → {p}{accion} {g.codigo}" for g in pendientes)
        raise ErrorUsuario(f"Hay varios grupos esperando. Decime cuál:\n{lista}")
    return pendientes[0].chat


@comando(
    "autorizar", "permitir",
    categoria="Dueño",
    descripcion="Me dejás quedarme en un grupo que me agregaron.",
    uso=(
        "{p}autorizar 1234 → con el código que te mandé por privado\n"
        "{p}autorizar → dentro del grupo, o si hay un solo grupo esperando"
    ),
    solo_dueno=True,
)  # fmt: skip
async def autorizar(ctx: Contexto) -> None:
    chat = elegir_pendiente(ctx, "autorizar")
    en_este_grupo = chat == ctx.clave_chat
    await ctx.bot.guardia.autorizar(chat, avisar_en_grupo=not en_este_grupo)
    await ctx.responder("✅ Listo, me quedo en este grupo." if en_este_grupo else "✅ Listo, me quedo en ese grupo.")


@comando(
    "rechazar", "salir",
    categoria="Dueño",
    descripcion="Me saco de ese grupo.",
    uso=(
        "{p}rechazar 1234 → con el código que te mandé por privado\n"
        "{p}salir → dentro de un grupo, me voy de ahí"
    ),
    solo_dueno=True,
)  # fmt: skip
async def rechazar(ctx: Contexto) -> None:
    chat = elegir_pendiente(ctx, "rechazar")
    if chat == ctx.clave_chat:
        await ctx.bot.guardia.salir(chat, "👋 Me voy. ¡Chau!")
        return
    await ctx.bot.guardia.salir(chat, "👋 Me voy: el dueño no me dejó quedarme en este grupo.")
    await ctx.responder("👋 Listo, me fui de ese grupo.")


@comando(
    "grupos",
    categoria="Dueño",
    descripcion="Grupos donde estoy y los que esperan tu permiso.",
    uso="{p}grupos",
    solo_dueno=True,
)
async def grupos(ctx: Contexto) -> None:
    almacen = ctx.bot.almacen
    p = ctx.prefijo
    autorizados = almacen.autorizados()
    pendientes = almacen.pendientes()
    plural = "" if len(autorizados) == 1 else "s"
    lineas = [f"👥 Estoy en {len(autorizados)} grupo{plural} autorizado{plural}."]
    nombres = sorted(n for _, n in autorizados if n)
    if nombres:
        lineas += [f"• {n}" for n in nombres[:30]]
        if len(nombres) > 30:
            lineas.append(f"… y {len(nombres) - 30} más")
    if pendientes:
        lineas += ["", "⏳ Esperando tu permiso:"]
        for g in pendientes:
            lineas.append(f"• «{g.nombre or 'sin nombre'}» (me agregó {g.agregado_por})")
            if not g.avisado:
                lineas.append("  ⚠️ No te pude avisar por privado cuando pasó.")
            lineas.append(f"  {p}autorizar {g.codigo} o {p}rechazar {g.codigo}")
    if not ctx.bot.guardia.activa:
        lineas += [
            "",
            "Ojo: cualquiera puede agregarme a grupos ([grupos] solo_el_dueno_agrega está apagado o no hay duenos).",
        ]
    await ctx.responder("\n".join(lineas))
