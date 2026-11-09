"""Comandos generales: menú de ayuda, ping y saludo por privado."""

from __future__ import annotations

import time

from licha_bot import ErrorUsuario, comando, escuchar
from licha_bot.comandos import Comando
from licha_bot.contexto import Contexto
from licha_bot.mensajes import media_de

# Orden de las categorías en el menú: las que no están acá van primero, por orden alfabético.
ORDEN_CATEGORIAS = {"General": 1, "Dueño": 2}


def puede_ver(ctx: Contexto, cmd: Comando) -> bool:
    return not cmd.solo_dueno or ctx.es_dueno


def detalle(ctx: Contexto, cmd: Comando) -> str:
    p = ctx.prefijo
    lineas = [f"*{p}{cmd.nombre}*", cmd.descripcion, "", ctx.uso(cmd)]
    if cmd.alias:
        lineas += ["", "También: " + ", ".join(f"{p}{a}" for a in cmd.alias)]
    return "\n".join(lineas).strip()


@comando(
    "menu", "ayuda", "help", "comandos",
    descripcion="Muestra la lista de comandos",
    uso="{p}menu → lista de comandos\n{p}ayuda sticker → cómo se usa un comando",
)  # fmt: skip
async def menu(ctx: Contexto) -> None:
    p = ctx.prefijo
    registro = ctx.bot.registro

    if ctx.args:
        buscado = ctx.args[0].lstrip("".join(ctx.config.prefijos))
        cmd = registro.buscar(buscado)
        if cmd is None or not puede_ver(ctx, cmd):
            raise ErrorUsuario(f"No conozco el comando {p}{buscado}. Escribí {p}menu para ver la lista.")
        await ctx.responder(detalle(ctx, cmd))
        return

    lineas = [f"🤖 *{ctx.config.nombre}*", ""]
    if not ctx.es_grupo and ctx.config.stickers.automatico_en_privado:
        lineas += ["Por acá, mandame una foto, video o GIF y te lo devuelvo como sticker.", ""]

    grupos = registro.por_categoria()
    for categoria in sorted(grupos, key=lambda c: (ORDEN_CATEGORIAS.get(c, 0), c)):
        visibles = [c for c in grupos[categoria] if puede_ver(ctx, c)]
        if not visibles:
            continue
        lineas.append(f"*{categoria}*")
        lineas += [f"• {p}{c.nombre} — {c.descripcion}" if c.descripcion else f"• {p}{c.nombre}" for c in visibles]
        lineas.append("")
    lineas.append(f"Para ver cómo se usa uno: {p}ayuda sticker")
    await ctx.responder("\n".join(lineas))


def duracion_legible(segundos: float) -> str:
    segundos = int(segundos)
    dias, segundos = divmod(segundos, 86400)
    horas, segundos = divmod(segundos, 3600)
    minutos, segundos = divmod(segundos, 60)
    partes = [f"{dias} d"] if dias else []
    if horas or dias:
        partes.append(f"{horas} h")
    if minutos or horas or dias:
        partes.append(f"{minutos} min")
    if not dias:
        partes.append(f"{segundos} s")
    return " ".join(partes)


@comando("ping", "estado", descripcion="Muestra si el bot está funcionando")
async def ping(ctx: Contexto) -> None:
    await ctx.responder(
        f"🏓 ¡Pong! {ctx.config.nombre} está funcionando hace {duracion_legible(ctx.bot.segundos_activo)}."
    )


SEGUNDOS_ENTRE_SALUDOS = 6 * 3600
_ultimo_saludo: dict[str, float] = {}


@escuchar
async def saludo(ctx: Contexto) -> bool:
    """Por privado, a quien escribe algo que no es un comando le explica cómo usar el bot."""
    if ctx.es_grupo or not ctx.config.saludar_por_privado or not ctx.texto.strip():
        return False
    if media_de(ctx.mensaje) is not None:
        return False  # las fotos y videos los atiende el sticker automático
    quien = ctx.numero or ctx.remitente.User
    ahora = time.monotonic()
    if ahora - _ultimo_saludo.get(quien, -SEGUNDOS_ENTRE_SALUDOS) < SEGUNDOS_ENTRE_SALUDOS:
        return False
    _ultimo_saludo[quien] = ahora
    p = ctx.prefijo
    lineas = [f"👋 ¡Hola! Soy *{ctx.config.nombre}*."]
    if ctx.config.stickers.automatico_en_privado:
        lineas.append("Mandame una foto, video o GIF y te lo devuelvo como sticker.")
    else:
        lineas.append(f"Mandame una foto, video o GIF con el texto {p}s y te lo devuelvo como sticker.")
    lineas.append(f"Escribí {p}menu para ver todo lo que sé hacer.")
    await ctx.responder("\n".join(lineas))
    return True
