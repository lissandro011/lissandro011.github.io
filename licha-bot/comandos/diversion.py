"""Comandos de diversión: dado, moneda, bola 8, elegir entre opciones y top en broma."""

from __future__ import annotations

import random
import re

from licha_bot import ErrorUsuario, comando
from licha_bot.contexto import Contexto

# --------------------------------------------------------------------------- #
# !dado
# --------------------------------------------------------------------------- #

MAX_CARAS = 1000
MAX_DADOS = 10
FORMATO_DADOS = re.compile(r"(\d{1,2})?d(\d{1,4})", re.IGNORECASE)


def leer_dados(texto: str) -> tuple[int, int]:
    """'' -> (1, 6), '20' -> (1, 20), '2d6' -> (2, 6). Lanza ValueError si no se entiende."""
    texto = texto.strip()
    if not texto:
        return 1, 6
    if texto.isdigit():
        cantidad, caras = 1, int(texto)
    elif (m := FORMATO_DADOS.fullmatch(texto)) is not None:
        cantidad, caras = int(m.group(1) or 1), int(m.group(2))
    else:
        raise ValueError(texto)
    if not 2 <= caras <= MAX_CARAS or not 1 <= cantidad <= MAX_DADOS:
        raise ValueError(texto)
    return cantidad, caras


@comando(
    "dado", "dados",
    categoria="Diversión",
    descripcion="Tira uno o varios dados",
    uso="{p}dado → del 1 al 6\n{p}dado 20 → del 1 al 20\n{p}dado 2d6 → dos dados de 6",
)  # fmt: skip
async def dado(ctx: Contexto) -> None:
    try:
        cantidad, caras = leer_dados(ctx.texto_args)
    except ValueError:
        raise ErrorUsuario(
            f"No entendí 🤔 Probá con {ctx.prefijo}dado, {ctx.prefijo}dado 20 o {ctx.prefijo}dado 2d6 "
            f"(hasta {MAX_DADOS} dados de {MAX_CARAS} caras)."
        ) from None
    tiradas = [random.randint(1, caras) for _ in range(cantidad)]
    if cantidad == 1:
        await ctx.responder(f"🎲 Salió *{tiradas[0]}*")
    else:
        detalle = " + ".join(str(t) for t in tiradas)
        await ctx.responder(f"🎲 {detalle} = *{sum(tiradas)}*")


# --------------------------------------------------------------------------- #
# !moneda
# --------------------------------------------------------------------------- #


@comando("moneda", "caraocruz", "coin", categoria="Diversión", descripcion="Tira una moneda: cara o cruz")
async def moneda(ctx: Contexto) -> None:
    await ctx.responder(f"🪙 ¡Salió *{random.choice(('cara', 'cruz'))}*!")


# --------------------------------------------------------------------------- #
# !8ball
# --------------------------------------------------------------------------- #

RESPUESTAS_8BALL = (
    # sí
    "Sí, obvio 😎",
    "Sin ninguna duda.",
    "Todo indica que sí.",
    "Las señales dicen que sí ✨",
    "Puede ser… yo diría que sí.",
    "Dalo por hecho.",
    "Sí, pero no se lo cuentes a nadie 🤫",
    # dudosas
    "Preguntame más tarde 😴",
    "Mejor no te digo ahora…",
    "Ni idea, la bola está empañada 🌫️",
    "Concentrate y volvé a preguntar.",
    "Mmm… 50 y 50.",
    # no
    "No.",
    "Ni en tus sueños 😂",
    "Mis fuentes dicen que no.",
    "Muy difícil.",
    "Olvidate.",
)


@comando(
    "8ball", "bola8", "bola", "pregunta",
    categoria="Diversión",
    descripcion="La bola 8 mágica responde tu pregunta",
    uso="{p}8ball ¿Mañana llueve?",
)  # fmt: skip
async def bola8(ctx: Contexto) -> None:
    if not ctx.texto_args:
        raise ErrorUsuario(f"Hacele una pregunta a la bola. Ejemplo: {ctx.prefijo}8ball ¿Apruebo el examen?")
    await ctx.responder(f"🎱 {random.choice(RESPUESTAS_8BALL)}")


# --------------------------------------------------------------------------- #
# !elegir
# --------------------------------------------------------------------------- #

SEPARADORES = re.compile(r"\s*(?:,|\||;|\n|\s+o\s+|\s+u\s+)\s*", re.IGNORECASE)
MAX_OPCIONES = 50


def leer_opciones(texto: str) -> list[str]:
    """'pizza, empanadas o sushi' -> ['pizza', 'empanadas', 'sushi'].

    Separa por comas, "|", ";", saltos de línea o la palabra "o". Si no hay
    ninguno de esos, separa por espacios ("pizza sushi" -> ['pizza', 'sushi']).
    Saca las opciones repetidas (sin importar mayúsculas).
    """
    texto = texto.strip().rstrip("?¿").strip()
    partes = SEPARADORES.split(texto)
    if len(partes) == 1:
        partes = texto.split()
    opciones: list[str] = []
    vistas: set[str] = set()
    for parte in partes:
        parte = parte.strip(" ¿?¡!.")
        if parte and parte.casefold() not in vistas:
            vistas.add(parte.casefold())
            opciones.append(parte)
    return opciones


@comando(
    "elegir", "elige", "decidir", "decide", "cual",
    categoria="Diversión",
    descripcion="Elige al azar entre varias opciones para decidir",
    uso="{p}elegir pizza, empanadas o sushi\n{p}elegir ir | quedarse\n{p}elegir rojo azul verde",
)  # fmt: skip
async def elegir(ctx: Contexto) -> None:
    opciones = leer_opciones(ctx.texto_args)
    if len(opciones) < 2:
        raise ErrorUsuario(f"Dame al menos dos opciones. Ejemplo: {ctx.prefijo}elegir pizza, empanadas o sushi")
    if len(opciones) > MAX_OPCIONES:
        raise ErrorUsuario(f"Son demasiadas opciones 😅 (máximo {MAX_OPCIONES}).")
    await ctx.responder(f"🤔 Entre {len(opciones)} opciones, elijo… *{random.choice(opciones)}* ✨")


# --------------------------------------------------------------------------- #
# !top5
# --------------------------------------------------------------------------- #

PUESTOS = ("🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")


@comando(
    "top5", "top",
    categoria="Diversión",
    descripcion="Arma un ranking en broma con gente del grupo",
    uso="{p}top5 más dormilones\n{p}top 3 mejores cocineros (de 2 a 10 puestos)",
    solo_grupos=True,
)  # fmt: skip
async def top(ctx: Contexto) -> None:
    args = ctx.args
    puestos = 5
    if args and args[0].isdigit():
        puestos = int(args[0])
        args = args[1:]
        if not 2 <= puestos <= len(PUESTOS):
            raise ErrorUsuario(f"El top puede ser de 2 a {len(PUESTOS)} puestos.")
    titulo = " ".join(args)
    if not titulo:
        raise ErrorUsuario(f"Decime de qué es el top. Ejemplo: {ctx.prefijo}top5 más dormilones")

    integrantes = await ctx.integrantes()
    if not integrantes:
        raise ErrorUsuario("No encontré a nadie en el grupo para el top 🤷")
    elegidos = random.sample(integrantes, min(puestos, len(integrantes)))

    lineas = [f"🏆 *Top {len(elegidos)}: {titulo}*", ""]
    lineas += [f"{PUESTOS[i]} {ctx.mencion(jid)}" for i, jid in enumerate(elegidos)]
    await ctx.responder_mencionando("\n".join(lineas), elegidos)
