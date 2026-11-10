"""Comandos generales: menú, ayuda, ping y saludo por privado."""

from __future__ import annotations

import time

from licha_bot import ErrorUsuario, comando, escuchar
from licha_bot.comandos import Comando
from licha_bot.contexto import Contexto
from licha_bot.mensajes import media_de

# --------------------------------------------------------------------------- #
# !menu
# --------------------------------------------------------------------------- #

SALUDO_PRIMERA_VEZ = "Elegí bien la foto que después te la mandan a vos jajaj"
SALUDOS_MENU = (
    "Acá está todo. Elegí tranquilo.",
    "A ver, ¿qué necesitás?",
    "Yo tiro la moneda. Después se arreglan ustedes.",
    "Si venías por una excusa, está un poquito más abajo.",
    "Abriste el menú. Yo también entro a mirar y después pido lo mismo.",
)

# (comando, lo que va después del nombre, descripción). Un comando que no esté
# cargado no aparece; los comandos nuevos que no están acá van a "Otros".
SECCIONES_MENU: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    ("🖼️ *Stickers*", (
        ("sticker", "", "Pasá una foto, video o GIF a sticker."),
        ("imagen", "", "Convertí un sticker en foto."),
    )),
    ("🎲 *Para jugar*", (
        ("dado", "", "Tirá uno o varios dados."),
        ("moneda", "", "Cara o cruz. Después bancate lo que salga."),
        ("8ball", "", "Haceme una pregunta de sí o no."),
        ("elegir", "", "Pasame las opciones que ya sé que no se ponen de acuerdo."),
        ("top5", "", "Armo el ranking del grupo. Los reclamos van al que lo pidió."),
    )),
    ("🍕 *Para grupos*", (
        ("confirmo", "armar <plan>", "Abrí la lista. Cada uno pone voy, capaz o me bajo."),
        ("decreto", "<regla>", "Proponé una regla y que el grupo la vote."),
        ("excusa", "", "Te doy una excusa para bajarte del plan. Mandarla te toca a vos."),
    )),
    ("⚙️ *General*", (
        ("menu", "", "Volvé a ver los comandos."),
        ("ping", "", "Fijate si sigo vivo."),
        ("ayuda", "<comando>", "Te muestro cómo se usa."),
    )),
)  # fmt: skip
SECCION_DUENO = (
    ("reiniciar", "", "Me apagás y me prendés."),
    ("apagar", "", "Hasta acá llegué."),
)
EXTRAS_DUENO = (
    ("autorizar", "<código>", "Me dejás quedarme en un grupo que me agregaron."),
    ("rechazar", "<código>", "Me saco de ese grupo."),
    ("grupos", "", "Grupos donde estoy y los que esperan tu permiso."),
)


def puede_ver(ctx: Contexto, cmd: Comando) -> bool:
    return not cmd.solo_dueno or ctx.es_dueno


def linea_menu(ctx: Contexto, cmd: Comando, args: str, texto: str) -> str:
    nombre = f"{ctx.prefijo}{cmd.nombre}" + (f" {args}" if args else "")
    if cmd.solo_grupos and not ctx.es_grupo:
        nombre += " (solo grupos)"
    return f"• {nombre} — {texto}"


def armar_menu(ctx: Contexto, saludo: str) -> str:
    p = ctx.prefijo
    registro = ctx.bot.registro
    mostrados: set[str] = set()
    lineas = [f"🤖 *{ctx.config.nombre}*", "", "Mandame una foto, video o GIF y te lo hago sticker.", saludo]

    for titulo, comandos in SECCIONES_MENU:
        filas = []
        for nombre, args, texto in comandos:
            cmd = registro.buscar(nombre)
            if cmd is not None and puede_ver(ctx, cmd) and cmd.nombre not in mostrados:
                mostrados.add(cmd.nombre)
                filas.append(linea_menu(ctx, cmd, args, texto))
        if filas:
            lineas += ["", titulo, *filas]

    dueno = [(registro.buscar(n), a, t) for n, a, t in SECCION_DUENO]
    if ctx.es_dueno and all(cmd is not None for cmd, _, _ in dueno):
        extras = [(registro.buscar(n), a, t) for n, a, t in EXTRAS_DUENO]
        filas = [linea_menu(ctx, cmd, a, t) for cmd, a, t in dueno + extras if cmd is not None]
        mostrados.update(cmd.nombre for cmd, _, _ in dueno + extras if cmd is not None)
        lineas += ["", "🔒 *Solo Licha*", *filas]

    otros = [
        c for c in registro.todos()
        if c.nombre not in mostrados and not c.oculto and puede_ver(ctx, c)
    ]  # fmt: skip
    if otros:
        filas = [
            linea_menu(ctx, c, "", c.descripcion or "Mirá cómo se usa con " + f"{p}ayuda {c.nombre}") for c in otros
        ]
        lineas += ["", "➕ *Otros*", *filas]

    lineas.append("")
    if ctx.es_grupo and registro.buscar("confirmo"):
        lineas.append(f"¿Armamos algo? Probá con *{p}confirmo armar previa del sábado*.")
    elif registro.buscar("elegir"):
        lineas.append(f"¿Lo dejamos a la suerte? Probá con *{p}elegir bondi o Uber*.")
    lineas.append(f"Para ver cómo se usa uno, mandá *{p}ayuda sticker*.")
    return "\n".join(lineas)


@comando(
    "menu", "comandos",
    categoria="General",
    descripcion="Volvé a ver los comandos.",
    uso="{p}menu",
)  # fmt: skip
async def menu(ctx: Contexto) -> None:
    if ctx.args:  # "!menu sticker" funciona como "!ayuda sticker"
        await ayuda(ctx)
        return
    if ctx.bot.almacen.primera_vez_menu(ctx.clave_chat):
        saludo = SALUDO_PRIMERA_VEZ
    else:
        saludo = ctx.frase("menu.saludo", SALUDOS_MENU)
    await ctx.responder(armar_menu(ctx, saludo))


# --------------------------------------------------------------------------- #
# !ayuda
# --------------------------------------------------------------------------- #

AYUDA_FALTA = (
    "Probá con {p}ayuda sticker. Cambiá “sticker” por el comando que quieras.",
    "¿De cuál? Por ejemplo: {p}ayuda decreto",
)
AYUDA_DESCONOCIDO = "Ese no lo tengo. Fijate en {p}menu o probá con {p}ayuda confirmo."


def detalle(ctx: Contexto, cmd: Comando) -> str:
    p = ctx.prefijo
    lineas = [f"*{p}{cmd.nombre}*", cmd.descripcion, "", ctx.uso(cmd)]
    if cmd.alias:
        lineas += ["", "También: " + ", ".join(f"{p}{a}" for a in cmd.alias)]
    return "\n".join(lineas).strip()


@comando(
    "ayuda", "help",
    categoria="General",
    descripcion="Te muestro cómo se usa.",
    uso="{p}ayuda sticker\n{p}ayuda confirmo\n{p}ayuda decreto",
)  # fmt: skip
async def ayuda(ctx: Contexto) -> None:
    if not ctx.args:
        raise ErrorUsuario(ctx.frase("ayuda.falta", AYUDA_FALTA))
    buscado = ctx.args[0].lstrip("".join(ctx.config.prefijos))
    cmd = ctx.bot.registro.buscar(buscado)
    if cmd is None or not puede_ver(ctx, cmd):
        raise ErrorUsuario(AYUDA_DESCONOCIDO.format(p=ctx.prefijo))
    await ctx.responder(detalle(ctx, cmd))


# --------------------------------------------------------------------------- #
# !ping
# --------------------------------------------------------------------------- #

PING_PRIMERO = (
    "Pong 🏓",
    "Acá estoy 🏓",
    "Te leo.",
    "Presente.",
    "🏓 Volvió.",
)
PING_SEGUNDO = (
    "Sigo acá.",
    "Sí, amigo. Te leo.",
    "Dos de dos 🏓",
    "Acá también en la segunda.",
    "Te llegó el pong de vuelta.",
)
PING_RACHA = (
    "Sigo acá, amigo. ¿Qué pasó?",
    "Si querías charlar podías decir hola jajaj",
    "Me tenés haciendo pretemporada 🏓",
    "Te leo desde el primero. Contame.",
    "Decime, ¿qué estamos midiendo?",
    "¿Pruebas técnicas o estás al pedo?",
    "¿Qué pasó, te encariñaste con el pong?",
    "Mientras vos pongas ping, yo sigo laburando.",
    "Acá. Ahora te toca sacar a vos 🏓",
)


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


@comando(
    "ping", "estado",
    categoria="General",
    descripcion="Fijate si sigo vivo.",
    uso="{p}ping\n{p}estado → también te digo hace cuánto estoy prendido",
)  # fmt: skip
async def ping(ctx: Contexto) -> None:
    # La racha es por chat y persona; cualquier otro comando de esa persona la corta.
    racha = ctx.bot.memoria.racha(ctx.clave_chat, ctx.persona, "ping", cortar=ctx.anterior not in (None, "ping"))
    if racha.numero == 1:
        texto = ctx.frase("ping.1", PING_PRIMERO)
    elif racha.numero == 2:
        texto = ctx.frase("ping.2", PING_SEGUNDO)
    else:
        texto = ctx.frase("ping.3", PING_RACHA)
    if ctx.comando.casefold() == "estado":
        texto += f"\nPrendido hace {duracion_legible(ctx.bot.segundos_activo)}."
    await ctx.responder(texto)


# --------------------------------------------------------------------------- #
# Saludo por privado
# --------------------------------------------------------------------------- #

SEGUNDOS_ENTRE_SALUDOS = 6 * 3600
_ultimo_saludo: dict[str, float] = {}


@escuchar
async def saludo(ctx: Contexto) -> bool:
    """Por privado, a quien escribe algo que no es un comando (o manda una foto sin !s) le explica cómo usar el bot."""
    if ctx.es_grupo or not ctx.config.saludar_por_privado:
        return False
    tiene_media = media_de(ctx.mensaje) is not None
    if tiene_media and ctx.config.stickers.automatico_en_privado:
        return False  # las fotos y videos los atiende el sticker automático
    if not tiene_media and not ctx.texto.strip():
        return False
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
