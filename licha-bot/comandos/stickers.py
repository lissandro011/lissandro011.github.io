"""Stickers: foto/video/GIF -> sticker, sticker -> foto y stickers automáticos por privado."""

from __future__ import annotations

from licha_bot import ErrorUsuario, comando, escuchar
from licha_bot.comandos import normalizar
from licha_bot.contexto import Contexto
from licha_bot.conversor import OpcionesSticker, crear_sticker, sticker_a_imagen
from licha_bot.mensajes import Media, media_de

PALABRAS_RECORTAR = {"recortar", "recortado", "r", "cuadrado", "crop"}
LARGO_MAXIMO_NOMBRE = 60

STICKER_SIN_MEDIA = (
    "Pasame una foto, video o GIF y te lo hago sticker.",
    "¿Qué convertimos? Respondé a la foto, video o GIF con {p}sticker.",
    "Materia prima, amigo. Mandame una foto, video o GIF.",
    "El sticker lo pongo yo. La foto, el video o el GIF los ponés vos.",
)
STICKER_YA_ES = (
    "Ya es sticker. Impecable el trabajo que me dejaste.",
    "Lo miré bien. Te me adelantaste, ya es sticker.",
)
IMAGEN_SIN_STICKER = (
    "Respondé a un sticker con {p}imagen y te lo paso a foto.",
    "¿Cuál sticker? Respondelo con {p}imagen.",
    "Te falta elegir la víctima. Citá el sticker con {p}imagen.",
)
IMAGEN_LISTA = (
    "Ahí tenés la foto.",
    "Listo, volvió a imagen.",
)


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
    descripcion="Pasá una foto, video o GIF a sticker.",
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
        texto = ctx.frase("sticker.falta", STICKER_SIN_MEDIA)
        if f"{ctx.prefijo}sticker" not in texto:  # que siempre quede claro cómo se usa
            texto += f"\nMandala con {ctx.prefijo}sticker de pie de foto, o respondé a una con {ctx.prefijo}sticker."
        raise ErrorUsuario(texto)
    if media.tipo == "sticker" and not ctx.args:
        # Sin "recortar" ni "Mi pack | Mi nombre" no hay nada que cambiarle.
        ya_es = ctx.frase("sticker.ya_es", STICKER_YA_ES)
        raise ErrorUsuario(f"{ya_es} Si querés ponerle tu nombre: {ctx.prefijo}s Mi pack | Mi nombre")
    await hacer_sticker(ctx, media, opciones_del_pedido(ctx))


@comando(
    "imagen", "toimg", "img", "foto",
    categoria="Stickers",
    descripcion="Convertí un sticker en foto.",
    uso="Respondé a un sticker con {p}imagen.",
)  # fmt: skip
async def imagen(ctx: Contexto) -> None:
    media = ctx.media()
    if media is None or media.tipo != "sticker":
        raise ErrorUsuario(ctx.frase("imagen.falta", IMAGEN_SIN_STICKER))
    datos = await ctx.descargar(media)
    jpeg, animado = await ctx.en_segundo_plano(sticker_a_imagen, datos)
    pie = "Es un sticker animado: te mando el primer cuadro." if animado else ctx.frase("imagen.lista", IMAGEN_LISTA)
    await ctx.enviar_imagen(jpeg, pie)


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
