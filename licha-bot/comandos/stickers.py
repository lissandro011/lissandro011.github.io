"""Stickers: foto/video/GIF -> sticker, sticker -> foto y stickers automáticos por privado."""

from __future__ import annotations

from licha_bot import ErrorUsuario, comando, escuchar
from licha_bot.comandos import normalizar
from licha_bot.contexto import Contexto
from licha_bot.conversor import OpcionesSticker, crear_sticker, sticker_a_imagen
from licha_bot.mensajes import Media, media_de

PALABRAS_RECORTAR = {"recortar", "recortado", "r", "cuadrado", "crop"}
LARGO_MAXIMO_NOMBRE = 60


def opciones_del_pedido(ctx: Contexto) -> OpcionesSticker:
    """Lee los extras del comando: '!s recortar Mi pack | Mi nombre'."""
    recortar = False
    resto = []
    for palabra in ctx.args:
        if not recortar and normalizar(palabra) in PALABRAS_RECORTAR:
            recortar = True
        else:
            resto.append(palabra)
    cambios: dict = {"recortar": recortar}
    texto = " ".join(resto).strip()
    if texto:
        paquete, _, autor = texto.partition("|")
        if paquete.strip():
            cambios["paquete"] = paquete.strip()[:LARGO_MAXIMO_NOMBRE]
        if autor.strip():
            cambios["autor"] = autor.strip()[:LARGO_MAXIMO_NOMBRE]
    return ctx.config.stickers.opciones(**cambios)


async def hacer_sticker(ctx: Contexto, media: Media, opciones: OpcionesSticker) -> None:
    lento = media.animado  # los videos tardan unos segundos: avisamos con una reacción
    if lento:
        await ctx.reaccionar("⏳")
    try:
        datos = await ctx.descargar(media)
        sticker = await ctx.en_segundo_plano(crear_sticker, datos, opciones)
        await ctx.enviar_sticker(sticker.datos, sticker.animado)
    finally:
        if lento:
            await ctx.reaccionar("")


@comando(
    "sticker", "s", "stiker", "fig",
    categoria="Stickers",
    descripcion="Convierte una foto, video o GIF en sticker",
    uso=(
        "Mandá una foto, video o GIF con el texto {p}sticker, o respondé a uno (o a un sticker) con {p}sticker.\n"
        "• {p}s recortar → lo recorta cuadrado, sin bordes\n"
        "• {p}s Mi pack | Mi nombre → cambia el nombre del paquete y el autor\n"
        "Los videos se cortan a los primeros 10 segundos."
    ),
)  # fmt: skip
async def sticker(ctx: Contexto) -> None:
    media = ctx.media()
    if media is None:
        raise ErrorUsuario(ctx.uso())
    await hacer_sticker(ctx, media, opciones_del_pedido(ctx))


@comando(
    "imagen", "toimg", "img", "foto",
    categoria="Stickers",
    descripcion="Convierte un sticker en foto",
    uso="Respondé a un sticker con {p}imagen.",
)  # fmt: skip
async def imagen(ctx: Contexto) -> None:
    media = ctx.media()
    if media is None or media.tipo != "sticker":
        raise ErrorUsuario(ctx.uso())
    datos = await ctx.descargar(media)
    jpeg, animado = await ctx.en_segundo_plano(sticker_a_imagen, datos)
    await ctx.enviar_imagen(jpeg, "Es un sticker animado: te mando el primer cuadro." if animado else "")


@escuchar
async def sticker_automatico(ctx: Contexto) -> bool:
    """Por privado, cualquier foto, video o GIF que le manden vuelve como sticker."""
    if ctx.es_grupo or not ctx.config.stickers.automatico_en_privado:
        return False
    media = media_de(ctx.mensaje)
    if media is None or media.tipo == "sticker" or media.ver_una_vez:
        return False
    if ctx.evento.IsViewOnce or ctx.evento.IsViewOnceV2 or ctx.evento.IsViewOnceV2Extension:
        return False
    await hacer_sticker(ctx, media, ctx.config.stickers.opciones())
    return True
