"""Comandos para jugar: dado, moneda, bola 8, elegir, top en broma y excusas.

Primero se resuelve el sorteo (siempre al azar e independiente) y después se
elige una frase que encaje con el resultado, sacándola de la bolsa del chat
(ver licha_bot/frases.py) para no repetir hasta usarlas todas.
"""

from __future__ import annotations

import random
import re

from licha_bot import ErrorUsuario, comando
from licha_bot.contexto import Contexto
from licha_bot.frases import texto_normalizado

# --------------------------------------------------------------------------- #
# !moneda
# --------------------------------------------------------------------------- #

MONEDA_PRIMERA = (
    "🪙 {lado}.",
    "🪙 Salió {lado}.",
    "🪙 {lado}. Quedó.",
    "🪙 {lado}. ¿Te sirve?",
    "🪙 {lado}. Ahí tenés.",
    "🪙 {lado}. Yo ya hice mi parte.",
)
MONEDA_IGUAL = (
    "🪙 {lado} otra vez. ¿Me creés ahora?",
    "🪙 {lado} de nuevo. La tiré, te juro.",
    "🪙 Otra vez {lado}. Qué querés que te diga.",
    "🪙 {lado}. Hasta la moneda te está diciendo «ya está».",
    "🪙 {lado} de nuevo. Probá soplar el celu.",
    "🪙 Sigue saliendo {lado}. ¿Querés hablar con la moneda?",
)
MONEDA_CAMBIO = (
    "🪙 {lado}. Ah, este te gustó más, ¿no?",
    "🪙 {lado}. ¿Cuál de las dos era la oficial?",
    "🪙 {lado}. Dale, yo hago de cuenta que la primera era de prueba.",
    "🪙 {lado}. Si frenás acá ya sé cuál querías jajaj",
    "🪙 {lado}. Con esta ya te salieron las dos. Te dejé como estabas.",
    "🪙 Ahora sí, {lado}. ¿Cerramos o vas al mejor de tres?",
)


@comando(
    "moneda", "caraocruz", "coin",
    categoria="Para jugar",
    descripcion="Cara o cruz. Después bancate lo que salga.",
    uso="{p}moneda",
)  # fmt: skip
async def moneda(ctx: Contexto) -> None:
    lado = random.choice(("Cara", "Cruz"))
    racha = ctx.bot.memoria.racha(ctx.clave_chat, ctx.persona, "moneda", dato=lado)
    if not racha.seguida:
        await ctx.responder(ctx.frase("moneda.primera", MONEDA_PRIMERA, lado=lado))
    elif racha.anterior == lado:
        await ctx.responder(ctx.frase("moneda.igual", MONEDA_IGUAL, lado=lado))
    else:
        await ctx.responder(ctx.frase("moneda.cambio", MONEDA_CAMBIO, lado=lado))


# --------------------------------------------------------------------------- #
# !elegir
# --------------------------------------------------------------------------- #

ELEGIR_GENERAL = (
    "{opcion}. Listo.",
    "Salió «{opcion}». ¿Te sirve o tiramos hasta que salga la que querés?",
    "Voy con «{opcion}».",
    "{opcion}. Si hiciste una cara rara, ya sabés que querías otra.",
    "{opcion}. El que preguntó se hace cargo.",
    "Quedó «{opcion}». Yo hasta acá llego.",
    "{opcion}. Fijate que antes de mandarlo te daba igual jajaj",
    "Salió «{opcion}». Ahora sí aparecen las opiniones.",
    "{opcion}. Cuando pregunten quién eligió, acordate de quién me metió en esto.",
)
ELEGIR_TODAS_IGUALES = (
    "{opcion}. Estuvo peleado.",
    "Me diste para elegir «{opcion}» o «{opcion}». Salió {opcion}, increíble.",
    "{opcion}. Gracias por la confianza en este momento tan difícil.",
)
ELEGIR_FALTAN = (
    "Pasame dos opciones por lo menos. Ejemplo: {p}elegir bondi o Uber",
    "¿Entre qué y qué? Probá con {p}elegir rojo, negro, azul",
)
# Solo si las dos opciones reales son exactamente esas y ganó la indicada.
ELEGIR_ESPECIFICOS: dict[tuple[frozenset[str], str], tuple[str, ...]] = {
    (frozenset({"pizza", "hamburguesa"}), "pizza"): (
        "Pizza. Ahora aparece el que quería hamburguesas.",
        "Pizza. Al de «me da igual» le toca elegir los gustos.",
    ),
    (frozenset({"pizza", "hamburguesa"}), "hamburguesa"): (
        "Hamburguesas. Ahora se van a pasar media hora eligiendo de dónde.",
    ),
    (frozenset({"bondi", "uber"}), "bondi"): ("Bondi. Andá saliendo entonces.",),
    (frozenset({"bondi", "uber"}), "uber"): ("Uber. Pasá la patente cuando lo pidas.",),
}

SEPARADORES_FUERTES = re.compile(r"\s*(?:,|\||;|\n)\s*")  # se priorizan: respetan opciones compuestas
CONJUNCION = re.compile(r"\s+(?:o|u)\s+", re.IGNORECASE)  # "o" / "u" como palabra entera
MAX_OPCIONES = 50


def partir_opciones(texto: str) -> list[str]:
    """Separa las opciones tal como se escribieron (sin sacar repetidas).

    - Si hay comas, "|", ";" o saltos de línea, se separa por eso, así
      "ir al cine o al teatro, quedarnos" son dos opciones. Con comas, el
      último tramo también se separa por "o" ("pizza, empanadas o sushi").
    - Si no, por la palabra "o" (o "u"): "bondi o Uber".
    - Si tampoco hay, por espacios: "rojo azul verde".
    """
    texto = texto.strip().strip("¿?¡!").strip()
    if SEPARADORES_FUERTES.search(texto):
        partes = SEPARADORES_FUERTES.split(texto)
        if "," in texto and "|" not in texto:
            partes = partes[:-1] + CONJUNCION.split(partes[-1])
    elif CONJUNCION.search(texto):
        partes = CONJUNCION.split(texto)
    else:
        partes = texto.split()
    limpias = (parte.strip(" ¿?¡!.") for parte in partes)
    return [parte for parte in limpias if parte]


def sin_repetir(opciones: list[str]) -> list[str]:
    """Saca repetidas sin distinguir mayúsculas; se queda con la primera escritura."""
    vistas: set[str] = set()
    unicas = []
    for opcion in opciones:
        clave = opcion.casefold()
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(opcion)
    return unicas


def canonica(opcion: str) -> str:
    """Para reconocer los casos específicos: 'Hamburguesas' -> 'hamburguesa', 'Pizzas' -> 'pizza'."""
    normal = texto_normalizado(opcion)
    return normal[:-1] if normal in {"pizzas", "hamburguesas"} else normal


@comando(
    "elegir", "elige", "decidir", "decide", "cual",
    categoria="Para jugar",
    descripcion="Pasame las opciones que ya sé que no se ponen de acuerdo.",
    uso=(
        "{p}elegir pizza, empanadas o sushi\n"
        "{p}elegir bondi o Uber\n"
        "{p}elegir ir al cine o al teatro | quedarnos\n"
        "Separá con comas, | o la palabra «o»."
    ),
)  # fmt: skip
async def elegir(ctx: Contexto) -> None:
    escritas = partir_opciones(ctx.texto_args)
    if len(escritas) < 2:
        raise ErrorUsuario(ctx.frase("elegir.faltan", ELEGIR_FALTAN))
    opciones = sin_repetir(escritas)
    if len(opciones) > MAX_OPCIONES:
        raise ErrorUsuario(
            f"Son demasiadas opciones (máximo {MAX_OPCIONES}). Ejemplo: {ctx.prefijo}elegir bondi o Uber"
        )
    elegida = random.choice(opciones)
    if len(opciones) == 1:
        await ctx.responder(ctx.frase("elegir.iguales", ELEGIR_TODAS_IGUALES, opcion=elegida))
        return
    especificas = ELEGIR_ESPECIFICOS.get((frozenset(canonica(o) for o in opciones), canonica(elegida)))
    if len(opciones) == 2 and especificas and random.random() < 0.5:
        await ctx.responder(ctx.frase(f"elegir.{canonica(elegida)}", especificas))
        return
    await ctx.responder(ctx.frase("elegir.general", ELEGIR_GENERAL, opcion=elegida))


# --------------------------------------------------------------------------- #
# !8ball
# --------------------------------------------------------------------------- #

BOLA_GENERAL = {
    "sí": (
        "🎱 La bola dice que sí.",
        "🎱 Para mí que sí, eh.",
        "🎱 Sí. Sacá captura por si esta vez le pego.",
        "🎱 Me sale que sí. Mirá vos.",
        "🎱 Hoy te tocó un sí.",
        "🎱 Sí. Hasta me sorprendió lo decidida que salió.",
        "🎱 Te salió que sí de una. Yo cerraría acá.",
    ),
    "no": (
        "🎱 La bola dice que no.",
        "🎱 Para mí que no, che.",
        "🎱 Me salió que no. Yo también miré dos veces.",
        "🎱 Hoy tocó un no.",
        "🎱 No. Cortita la respuesta de hoy.",
        "🎱 Dice que no. Los reclamos van a la bola.",
        "🎱 No. Si le erro, vení a gastarme después.",
    ),
    "dudoso": (
        "🎱 Todavía no está claro.",
        "🎱 Mmm. Hoy te debo esa.",
        "🎱 Puede ser. Mirá qué manera de no jugármela.",
        "🎱 Ni la bola se quiso meter.",
        "🎱 Está para un «vemos» de esos que no aclaran nada.",
        "🎱 Me dejó en visto hasta a mí.",
        "🎱 Volvé después. Hoy está en modo «qué sé yo».",
    ),
}
BOLA_LE_ESCRIBO = {
    "sí": (
        "🎱 Sí. Igual ya lo tenías escrito, te faltaba apretar enviar.",
        "🎱 Mandale. Ese «hola» ya pasó por suficientes borradores.",
        "🎱 Sí. Después contá qué te respondió, ahora me metiste en el tema.",
    ),
    "no": (
        "🎱 Hoy no. Guardá ese «che, tanto tiempo».",
        "🎱 No. Ahora decime la verdad, ¿lo mandaste antes de preguntarme?",
        "🎱 No. Salí del chat que te conozco jajaj",
    ),
    "dudoso": (
        "🎱 Depende. ¿Tenés algo para decirle o subió una historia?",
        "🎱 Mmm. ¿Qué hora es y qué tema estás escuchando?",
        "🎱 No sé. A ver ese borrador.",
    ),
}
# Para preguntas personales o delicadas: sin chistes.
BOLA_NEUTRAL = {"sí": "🎱 La bola dice que sí.", "no": "🎱 La bola dice que no.", "dudoso": "🎱 Todavía no está claro."}
BOLA_VACIA = (
    "🎱 Te falta un detalle. La pregunta. Ejemplo: {p}8ball ¿se arma?",
    "🎱 Preguntame algo de sí o no. Probá con {p}8ball ¿llego?",
)
BOLA_ABIERTA = "🎱 Dámela en versión sí o no. Si querés elegir entre opciones, usá {p}elegir."

# Mismo sorteo que antes: 7 respuestas de sí, 5 dudosas y 5 de no.
VEREDICTOS = ("sí", "no", "dudoso")
PESOS_VEREDICTOS = (7, 5, 5)

PREGUNTA_LE_ESCRIBO = re.compile(
    r"(?:y\s+|che\s+)?(?:(?:le|la|lo)\s+(?:escribo|hablo|mando\s+(?:un\s+)?(?:mensaje|mensajito|msj|wpp|wsp|whatsapp))"
    r"|(?:deberia|debo|tengo\s+que)\s+(?:escribirle|hablarle|mandarle\s+(?:un\s+)?(?:mensaje|mensajito|msj)))"
    r"(?:\s+(?:o\s+no|hoy|ahora|ya|de\s+nuevo|otra\s+vez|primero))*"
)
INTERROGATIVOS = {"quien", "quienes", "cual", "cuales", "donde", "cuando", "cuanto", "cuanta", "cuantos", "cuantas"}
PALABRAS_DELICADAS = re.compile(
    r"\b(?:muer\w*|morir\w*|cancer|tumor|enferm\w*|hospital\w*|operaci\w*|diagnostic\w*|embaraz\w*|"
    r"aborto|suicid\w*|depresi\w*|ansiedad|terapia|divorci\w*|separ\w*|despid\w*|duelo|velorio|biopsia|"
    r"positivo|resultados?\s+del?\s+(?:analisis|estudio|test))\b"
)


def es_le_escribo(normalizada: str) -> bool:
    """Reconoce "¿le escribo?" / "¿le mando un mensaje?" como frase completa (no "¿me escribe mañana?")."""
    return PREGUNTA_LE_ESCRIBO.fullmatch(normalizada) is not None


def es_abierta(normalizada: str) -> bool:
    """Preguntas que claramente no son de sí o no: "¿qué como hoy?", "¿cuándo llueve?"."""
    palabras = normalizada.split()
    if not palabras:
        return False
    if palabras[0] in INTERROGATIVOS or normalizada.startswith("por que "):
        return True
    return palabras[0] == "que" and palabras[1:2] not in (["tal"], ["onda"], ["pasa"])


@comando(
    "8ball", "bola8", "bola", "pregunta",
    categoria="Para jugar",
    descripcion="Haceme una pregunta de sí o no.",
    uso="{p}8ball ¿se arma?\n{p}8ball le escribo",
)  # fmt: skip
async def bola8(ctx: Contexto) -> None:
    normalizada = texto_normalizado(ctx.texto_args)  # no se guarda en ningún lado
    if not normalizada:
        raise ErrorUsuario(ctx.frase("bola.vacia", BOLA_VACIA))
    if es_abierta(normalizada):
        await ctx.responder(BOLA_ABIERTA.format(p=ctx.prefijo))
        return
    veredicto = random.choices(VEREDICTOS, PESOS_VEREDICTOS)[0]
    if PALABRAS_DELICADAS.search(normalizada):
        await ctx.responder(BOLA_NEUTRAL[veredicto])
    elif es_le_escribo(normalizada) and random.random() < 0.5:
        await ctx.responder(ctx.frase(f"bola.escribo.{veredicto}", BOLA_LE_ESCRIBO[veredicto]))
    else:
        await ctx.responder(ctx.frase(f"bola.{veredicto}", BOLA_GENERAL[veredicto]))


# --------------------------------------------------------------------------- #
# !dado
# --------------------------------------------------------------------------- #

DADO_GENERAL = (
    "🎲 {tirada}",
    "🎲 {tirada}. Así cayó.",
    "🎲 {tirada}. A la vista de todo el grupo.",
    "🎲 {tirada}. Si convenía otra cosa, había que avisar antes.",
    "🎲 {tirada}. Yo tiro, ustedes arreglan.",
)
DADO_TODOS_IGUALES = "🎲 {tirada}. Se pusieron de acuerdo, parece."
DADO_MINIMO = "🎲 {tirada}. Se ve que estaba ahorrando."
DADO_MAXIMO = "🎲 {tirada}. Mejor que eso no te puedo ofrecer."

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


def formatear_tirada(tiradas: list[int]) -> str:
    if len(tiradas) == 1:
        return f"*{tiradas[0]}*"
    return f"{' + '.join(map(str, tiradas))} = *{sum(tiradas)}*"


@comando(
    "dado", "dados",
    categoria="Para jugar",
    descripcion="Tirá uno o varios dados.",
    uso="{p}dado → del 1 al 6\n{p}dado 20 → del 1 al 20\n{p}dado 2d6 → dos dados de 6",
)  # fmt: skip
async def dado(ctx: Contexto) -> None:
    try:
        cantidad, caras = leer_dados(ctx.texto_args)
    except ValueError:
        p = ctx.prefijo
        raise ErrorUsuario(
            f"Ese dado no lo tengo. Probá con {p}dado, {p}dado 20 o {p}dado 2d6 "
            f"(hasta {MAX_DADOS} dados de {MAX_CARAS} caras)."
        ) from None
    tiradas = [random.randint(1, caras) for _ in range(cantidad)]
    tirada = formatear_tirada(tiradas)
    especial = None
    if cantidad > 1 and len(set(tiradas)) == 1:
        especial = DADO_TODOS_IGUALES
    elif cantidad == 1 and tiradas[0] == 1:
        especial = DADO_MINIMO
    elif cantidad == 1 and tiradas[0] == caras:
        especial = DADO_MAXIMO
    if especial and random.random() < 0.5:
        await ctx.responder(especial.format(tirada=tirada))
    else:
        await ctx.responder(ctx.frase("dado", DADO_GENERAL, tirada=tirada))


# --------------------------------------------------------------------------- #
# !top5
# --------------------------------------------------------------------------- #

TOP_ENCABEZADOS = (
    "Así quedó la tabla. Los leo.",
    "Ranking del grupo, rigor científico discutible.",
    "Ya tengo los puestos. Alguien se va a querer bajar del sorteo.",
    "Ahí va. El primero puede dar unas palabras.",
    "Salió esto. Los reclamos van al que puso el comando.",
    "Bueno, alguien tenía que ordenar este asunto.",
)
PUESTOS = ("🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")


@comando(
    "top5", "top",
    categoria="Para jugar",
    descripcion="Armo el ranking del grupo. Los reclamos van al que lo pidió.",
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
            raise ErrorUsuario(
                f"El top puede ser de 2 a {len(PUESTOS)} puestos. Ejemplo: {ctx.prefijo}top 3 más puntuales"
            )
    titulo = " ".join(args)
    if not titulo:
        raise ErrorUsuario(f"Decime de qué es el top. Ejemplo: {ctx.prefijo}top5 más dormilones")

    integrantes = await ctx.integrantes()
    if not integrantes:
        raise ErrorUsuario("No encontré a nadie en el grupo para el top. Probá de nuevo en un rato.")
    elegidos = random.sample(integrantes, min(puestos, len(integrantes)))

    lineas = [ctx.frase("top", TOP_ENCABEZADOS), "", f"🏆 *Top {len(elegidos)}: {titulo}*"]
    lineas += [f"{PUESTOS[i]} {ctx.mencion(jid)}" for i, jid in enumerate(elegidos)]
    await ctx.responder_mencionando("\n".join(lineas), elegidos)


# --------------------------------------------------------------------------- #
# !excusa
# --------------------------------------------------------------------------- #

EXCUSAS = (
    "Me bajo hoy, mañana madrugo y ya sé que con ustedes «un ratito» termina con el sol en la cara.",
    "Hoy paso, ando cuidando la plata. Disfruten también por mi billetera.",
    "Me hice el que tenía energía hace un rato. Les pido disculpas por esa información.",
    "Ya me puse el pantalón de entrecasa. Perdí toda autoridad para prometer que salgo.",
    "Esta la miro de local. Pásenla lindo.",
    "Hoy tengo ganas de cenar, bañarme y que nadie me pregunte a dónde vamos después.",
    "Mañana tengo cosas temprano. Si caigo, ya sé que me voy a hacer el boludo con la hora.",
    "Hoy me ganó el sillón. Fue bastante desigual el partido.",
    "Les debo esta. Ya había quedado en comer en casa.",
    "Me bajo antes de convertirme en el que dice «ya salgo» durante dos horas.",
    "Estoy con menos batería que el celu. Y el celu está enchufado.",
    "Hoy no cuenten conmigo para la reserva. Prefiero avisarles ahora que hacerme el misterioso hasta las once.",
    "Me fijé cuánto sale la vuelta. De repente me dieron unas ganas de quedarme en casa.",
    "Me senté cinco minutos. Grave error de mi parte. Nos vemos en la próxima.",
    "Me comprometí con demasiados planes para alguien que solo puede estar en un lugar a la vez.",
    "Hoy necesito dormir como si mañana me actualizaran el sistema.",
    "Tengo la ropa de salir en el lavarropas. Mal manejo del plantel de mi parte.",
    "Hoy estoy para mandar stickers desde la cama. Ésa es mi participación.",
    "Mi versión de las seis dijo que sí sin consultar con mi versión de ahora.",
    "Me hago cargo, hoy me dio fiaca. Guárdenme el chisme para mañana.",
    "Estoy cocinando y calculé porciones como para quedarme hasta el lunes.",
    "Me toca hacer de persona responsable un día. Parece que justo cayó hoy.",
    "Hoy paso. Prefiero que me gasten cinco minutos por acá a escuchar la alarma mañana y acordarme de todos ustedes.",
    "Me queda un viaje de ida, uno de vuelta y cero ganas entre medio.",
    "Ya apoyé la cabeza en la almohada para probar. Funcionaba perfecto. Me quedo.",
    "Hoy ando con ganas de verlos, pero el cuerpo me autorizó videollamada nomás.",
    "Pido cambio. Que entre el que puso «capaz», tiene piernas frescas.",
    "Hoy no llego. Vayan cerrando con los que están, que tampoco voy a tenerlos organizando hasta mañana.",
)
EXCUSA_OTRA = (
    "Bueno, pero ¿qué les dijiste la última vez? Así no nos pisamos.",
    "¿La primera no pasó el control de calidad? Probá con esta.",
    "Elegí una sola, amigo. Si mandás las dos se te cae el personaje.",
    "Te paso otra. Después acordate de cuál usaste.",
    "Pará, ¿querés bajarte del plan o estás armando un guion?",
    "Ah, tenés un grupo exigente. Va otra.",
    "Si esta tampoco sirve, vas a tener que ir jajaj",
    "Bueno, cambiamos la declaración.",
    "Te tiro una más. La actuación corre por tu cuenta.",
    "¿Y si les decís que no vas? Bueno, va otra igual.",
)


@comando(
    "excusa", "excusas", "zafar",
    categoria="Para grupos",
    descripcion="Te doy una excusa para bajarte del plan. Mandarla te toca a vos.",
    uso="{p}excusa → una excusa lista para reenviar\nSi no te convence, mandá {p}excusa de nuevo y te paso otra.",
)  # fmt: skip
async def excusa(ctx: Contexto) -> None:
    # La bolsa de excusas es de cada persona: no le vuelve a tocar una reciente aunque otros usen el comando.
    texto = ctx.frase("excusa", EXCUSAS, clave=f"{ctx.clave_chat}|{ctx.persona}")
    racha = ctx.bot.memoria.racha(ctx.clave_chat, ctx.persona, "excusa")
    if not racha.seguida:
        await ctx.responder(texto)
        return
    await ctx.responder(ctx.frase("excusa.otra", EXCUSA_OTRA))
    await ctx.enviar(texto)  # aparte, para que se pueda reenviar sola
