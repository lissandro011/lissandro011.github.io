"""Comandos para organizar el grupo: !decreto (votar reglas) y !confirmo (lista de un plan).

Las votaciones y las listas se guardan en datos/licha.sqlite3: sobreviven a un
reinicio, hay una abierta por grupo y cada persona cuenta una sola vez.
"""

from __future__ import annotations

from licha_bot import ErrorUsuario, comando, escuchar
from licha_bot.almacen import Decreto, Plan
from licha_bot.contexto import Contexto
from licha_bot.frases import texto_normalizado


async def puede_cerrar(ctx: Contexto, creador: str) -> bool:
    """Cierra quien lo abrió, un admin del grupo o el dueño del bot."""
    return ctx.persona == creador or ctx.es_dueno or await ctx.es_admin()


# --------------------------------------------------------------------------- #
# !decreto
# --------------------------------------------------------------------------- #

DECRETO_APERTURA = (
    "Se abre la votación. A ver quién banca esto.",
    "Llegó un proyecto al grupo.",
    "Hay una regla nueva en discusión. Los leo.",
    "A pedido de una persona con acceso a internet, se vota lo siguiente.",
    "Bueno, ustedes sabrán qué grupo quieren tener.",
    "Esto todavía se puede frenar. Voten.",
)
DECRETO_VOTO = (
    "Anotado tu «{voto}».",
    "Quedó tu voto: {voto}.",
    "Un «{voto}» de tu parte. Tomo nota.",
    "Para el recuento figurás con «{voto}».",
)
DECRETO_CAMBIO = (
    "Pasaste de «{antes}» a «{voto}». Cuenta el último.",
    "Cambiaste a «{voto}». Actualicé la cuenta.",
)
DECRETO_REPETIDO = (
    "Ya estabas en «{voto}». Una persona, un voto, amigo.",
    "Tu «{voto}» ya figura. Entusiasmo veo que hay.",
)
DECRETO_APROBADO = (
    "Queda aprobado. {regla}",
    "Salió ley del grupo. {regla}",
    "Ganó el sí. Después nadie diga «yo no sabía». {regla}",
    "Aprobado por votación. Voy dejando esto por escrito. {regla}",
    "Lo votaron ustedes, eh. Queda aprobado. {regla}",
)
DECRETO_RECHAZADO = (
    "Ganó el no. No se aprueba la propuesta «{regla}».",
    "Queda rechazado. Al cajón va «{regla}».",
    "Hasta acá llegó el proyecto «{regla}». Ganó el no.",
    "El grupo leyó «{regla}» y votó que no.",
)
DECRETO_EMPATE = (
    "Empataron. «{regla}» queda sin aprobar.",
    "Mitad y mitad. A «{regla}» le faltó un voto para salir.",
    "Empate. No hay decreto. La propuesta era «{regla}».",
)
DECRETO_SIN_VOTOS = (
    "Nadie votó. «{regla}» queda sin aprobar.",
    "Cerró con cero votos. Ni para pelearse sirvió «{regla}».",
    "Levantamos la sesión. «{regla}» no recibió votos.",
)

VOTOS = {"si": "sí", "no": "no"}
LARGO_MAXIMO_REGLA = 500


def opciones_voto(p: str) -> str:
    return f"Voten con {p}decreto si / {p}decreto no"


def estado_decreto(ctx: Contexto, decreto: Decreto) -> str:
    si, no = ctx.bot.almacen.contar_votos(decreto.id)
    p = ctx.prefijo
    return (
        f"📜 En votación: «{decreto.texto}»\nSí: {si} · No: {no}\n{opciones_voto(p)}. Para cerrarla: {p}decreto cerrar"
    )


def resultado_decreto(ctx: Contexto, decreto: Decreto, si: int, no: int) -> str:
    if si == 0 and no == 0:
        texto = ctx.frase("decreto.cero", DECRETO_SIN_VOTOS, regla=decreto.texto)
    elif si == no:
        texto = ctx.frase("decreto.empate", DECRETO_EMPATE, regla=decreto.texto)
    elif si > no:
        texto = ctx.frase("decreto.aprobado", DECRETO_APROBADO, regla=decreto.texto)
    else:
        texto = ctx.frase("decreto.rechazado", DECRETO_RECHAZADO, regla=decreto.texto)
    return f"{texto}\nSí: {si} · No: {no}"


@comando(
    "decreto", "decretos", "ley",
    categoria="Para grupos",
    descripcion="Proponé una regla y que el grupo la vote.",
    uso=(
        "{p}decreto El que llega tarde paga el hielo → proponé una regla\n"
        "{p}decreto si / {p}decreto no → votá (podés cambiar tu voto hasta el cierre)\n"
        "{p}decreto estado → mirá cómo va\n"
        "{p}decreto cerrar → cerrala y mirá el resultado (quien la propuso, un admin o el dueño)\n"
        "Se usa en grupos. Hay una votación abierta por grupo y gana el sí si tiene más votos que el no."
    ),
    solo_grupos=True,
)  # fmt: skip
async def decreto(ctx: Contexto) -> None:
    almacen = ctx.bot.almacen
    p = ctx.prefijo
    texto = ctx.texto_args.strip()
    palabra = texto_normalizado(texto) if len(texto.split()) == 1 else ""
    abierto = almacen.decreto_abierto(ctx.clave_chat)

    if not texto or palabra == "estado":
        if abierto is None:
            raise ErrorUsuario(
                f"No hay ninguna votación abierta. Proponé una con {p}decreto <regla>. "
                f"Ejemplo: {p}decreto El que llega tarde paga el hielo"
            )
        await ctx.responder(estado_decreto(ctx, abierto))
        return

    if palabra in VOTOS:
        if abierto is None:
            raise ErrorUsuario(f"No hay nada para votar. Proponé una regla con {p}decreto <regla>.")
        voto = VOTOS[palabra]
        antes = almacen.votar(abierto.id, ctx.persona, voto)
        if antes is None:
            await ctx.responder(ctx.frase("decreto.voto", DECRETO_VOTO, voto=voto))
        elif antes == voto:
            await ctx.responder(ctx.frase("decreto.repetido", DECRETO_REPETIDO, voto=voto))
        else:
            await ctx.responder(ctx.frase("decreto.cambio", DECRETO_CAMBIO, voto=voto, antes=antes))
        return

    if palabra == "cerrar":
        if abierto is None:
            raise ErrorUsuario(f"No hay ninguna votación para cerrar. Para proponer una: {p}decreto <regla>")
        if not await puede_cerrar(ctx, abierto.autor):
            raise ErrorUsuario(
                f"La cierra quien la propuso, un admin del grupo o el dueño. Mientras tanto: {p}decreto estado"
            )
        si, no = almacen.contar_votos(abierto.id)
        if not almacen.cerrar_decreto(abierto.id):
            return  # otro la cerró recién
        await ctx.responder(resultado_decreto(ctx, abierto, si, no))
        return

    if len(texto) > LARGO_MAXIMO_REGLA:
        raise ErrorUsuario(f"La regla es muy larga (máximo {LARGO_MAXIMO_REGLA} letras). Resumila un poco.")
    nuevo, creado = almacen.abrir_decreto(ctx.clave_chat, texto, ctx.persona)
    if not creado:
        raise ErrorUsuario(
            f"Ya hay una votación abierta: «{nuevo.texto}».\n"
            f"{opciones_voto(p)}. Cuando se cierre ({p}decreto cerrar) podés proponer la tuya."
        )
    encabezado = ctx.frase("decreto.apertura", DECRETO_APERTURA)
    await ctx.responder(f"{encabezado}\n\n📜 «{nuevo.texto}»\n\n{opciones_voto(p)}")


# --------------------------------------------------------------------------- #
# !confirmo
# --------------------------------------------------------------------------- #

PLAN_APERTURA = (
    "Se arma «{plan}». A ver con quién contamos.",
    "Abro lista para «{plan}». Ahora sí, uno por vez.",
    "«{plan}». Si van, anótense así alguien puede hacer la cuenta.",
    "Quién se prende a «{plan}». Los del «capaz» también tienen su sector.",
)
PLAN_RESPUESTAS = {
    "voy": (
        "{nombre}, adentro.",
        "Anotado, {nombre}. Contamos con vos.",
        "{nombre} puso que va. Uno que se la juega.",
        "Dale, {nombre}. Ya figurás en la lista.",
        "{nombre}, te cuento para «{plan}».",
    ),
    "capaz": (
        "{nombre} queda en el famoso «veo».",
        "Anoté a {nombre} en «capaz». Un pie adentro.",
        "{nombre}, cuando sepas pasate a «voy» o «me bajo».",
        "{nombre} pidió tiempo para analizar la propuesta.",
        "A {nombre} dejalo en lápiz por ahora.",
    ),
    "me bajo": (
        "Dale, {nombre}. Esta la mirás de afuera.",
        "Anotado, {nombre}. Para esta no te contamos.",
        "{nombre} se baja. Avisó, se valora.",
        "{nombre}, quedaste en «me bajo».",
        "Listo, {nombre}. Te dejamos el chisme para después.",
    ),
}
PLAN_CAMBIO = (
    "{nombre}, pasaste de «{antes}» a «{ahora}». Ya quedó.",
    "Actualicé lo tuyo, {nombre}. Ahora figurás en «{ahora}».",
)
PLAN_REPETIDO = (
    "{nombre}, ya estabas en «{ahora}». Te cuento una sola vez, por más onda que le pongas.",
    "Ya figurás en «{ahora}», {nombre}. Todo en orden.",
)
PLAN_CIERRE = (
    "Cierro la lista de «{plan}». Así quedó.",
    "Último recuento de «{plan}».",
    "Lista cerrada. Estos son los números de «{plan}».",
    "Hasta acá anotamos para «{plan}».",
)
REMATE_SIEMPRE = "Hasta acá llegó el parte de asistencia."

# Qué escribe la gente -> estado guardado.
ESTADOS = {"voy": "voy", "capaz": "capaz", "me bajo": "me bajo", "mebajo": "me bajo", "no voy": "me bajo"}
SUBCOMANDOS_PLAN = {"", "resumen", "cerrar"}
LARGO_MAXIMO_PLAN = 120


def cantidad(n: int, singular: str, plural: str) -> str:
    """'Va 1', 'Van 4'."""
    return f"{singular if n == 1 else plural} {n}"


def remates(voy: int, capaz: int, bajo: int) -> list[str]:
    """Remates que tienen sentido con esos números (se elige uno solo)."""
    opciones = []
    if voy > 0 and capaz > 0:
        opciones.append(f"{cantidad(voy, 'Va', 'Van')}. Hay {capaz} en «veo». Ustedes sabrán si contar con esa gente.")
        opciones.append(f"Para reservar, yo arrancaría por {voy}. El resto está leyendo la letra chica.")
    if capaz >= 2 and capaz > voy:
        opciones.append("Hay más gente evaluando el plan que gente yendo.")
    if capaz == 1:
        opciones.append("Queda una persona en «capaz». El suspenso tiene nombre.")
    if voy >= 2 and capaz == 0:
        opciones.append("Esta vez se decidieron todos los que contestaron. Mirá qué lindo.")
    if voy == 1 and capaz == 0:
        opciones.append("Hay una persona firme. Falta que esto se convierta en juntada.")
    if voy == 0 and capaz > 0:
        opciones.append("Confirmados, cero. Expectativa, bastante.")
    if voy == 0 and capaz == 0 and bajo > 0:
        opciones.append("Todos los que contestaron se bajaron. El plan estuvo lindo mientras era una idea.")
    if voy == 0 and capaz == 0 and bajo == 0:
        opciones.append("Todavía no contestó nadie. Por ahora el plan es una expresión de deseo.")
    opciones.append(REMATE_SIEMPRE)
    return opciones


def resumen_plan(ctx: Contexto, plan: Plan) -> str:
    listas = ctx.bot.almacen.respuestas_plan(plan.id)
    voy, capaz, bajo = (listas[e] for e in ("voy", "capaz", "me bajo"))
    opciones = remates(len(voy), len(capaz), len(bajo))
    remate = ctx.frase("plan.remate", opciones)
    return "\n".join([
        f"📋 *{plan.nombre}*",
        f"✅ Voy ({len(voy)}): {', '.join(voy) or '-'}",
        f"🤔 Capaz ({len(capaz)}): {', '.join(capaz) or '-'}",
        f"👋 Me bajo ({len(bajo)}): {', '.join(bajo) or '-'}",
        "",
        remate,
    ])  # fmt: skip


def como_anotarse(p: str) -> str:
    return (
        f"Anotate con {p}confirmo voy, {p}confirmo capaz o {p}confirmo me bajo "
        "(o respondé a este mensaje con voy, capaz o me bajo)."
    )


async def anotar(ctx: Contexto, plan: Plan, estado: str) -> None:
    antes = ctx.bot.almacen.responder_plan(plan.id, ctx.persona, ctx.nombre, estado)
    datos = {"nombre": ctx.nombre, "plan": plan.nombre, "ahora": estado}
    if antes is None:
        texto = ctx.frase(f"plan.{estado}", PLAN_RESPUESTAS[estado], **datos)
    elif antes == estado:
        texto = ctx.frase("plan.repetido", PLAN_REPETIDO, **datos)
    else:
        texto = ctx.frase("plan.cambio", PLAN_CAMBIO, antes=antes, **datos)
    await ctx.responder(texto)


@comando(
    "confirmo", "plan", "lista",
    categoria="Para grupos",
    descripcion="Abrí la lista. Cada uno pone voy, capaz o me bajo.",
    uso=(
        "{p}confirmo armar previa del sábado → abrí la lista\n"
        "{p}confirmo voy / {p}confirmo capaz / {p}confirmo me bajo → anotate o cambiá tu respuesta\n"
        "También podés responder al mensaje de la lista con voy, capaz o me bajo.\n"
        "{p}confirmo → mirá el resumen\n"
        "{p}confirmo cerrar → cerrá la lista con el recuento final (quien la armó, un admin o el dueño)\n"
        "Se usa en grupos. Hay una lista abierta por grupo."
    ),
    solo_grupos=True,
)  # fmt: skip
async def confirmo(ctx: Contexto) -> None:
    almacen = ctx.bot.almacen
    p = ctx.prefijo
    texto = ctx.texto_args.strip()
    normal = texto_normalizado(texto)
    abierto = almacen.plan_abierto(ctx.clave_chat)

    primera, _, resto = texto.partition(" ")
    if texto_normalizado(primera) == "armar":
        nombre = resto.strip()
        if not nombre:
            raise ErrorUsuario(f"¿Qué armamos? Ejemplo: {p}confirmo armar previa del sábado")
        if len(nombre) > LARGO_MAXIMO_PLAN:
            raise ErrorUsuario(f"El nombre del plan es muy largo (máximo {LARGO_MAXIMO_PLAN} letras).")
        plan, creado = almacen.abrir_plan(ctx.clave_chat, nombre, ctx.persona)
        if not creado:
            raise ErrorUsuario(
                f"Ya hay una lista abierta: «{plan.nombre}». Anotate con {p}confirmo voy, "
                f"mirá cómo va con {p}confirmo o cerrala con {p}confirmo cerrar."
            )
        encabezado = ctx.frase("plan.apertura", PLAN_APERTURA, plan=plan.nombre)
        mensaje = await ctx.responder(f"{encabezado}\n{como_anotarse(p)}")
        almacen.anotar_mensaje_plan(ctx.clave_chat, mensaje, plan.id)
        return

    if normal in ESTADOS:
        if abierto is None:
            raise ErrorUsuario(f"No hay ninguna lista abierta. Armá una con {p}confirmo armar <plan>")
        await anotar(ctx, abierto, ESTADOS[normal])
        return

    if normal in SUBCOMANDOS_PLAN:
        if abierto is None:
            que = "cerrar" if normal == "cerrar" else "mostrar"
            raise ErrorUsuario(f"No hay ninguna lista para {que}. Armá una con {p}confirmo armar previa del sábado")
        if normal == "cerrar":
            if not await puede_cerrar(ctx, abierto.organizador):
                raise ErrorUsuario(
                    f"La cierra quien la armó, un admin del grupo o el dueño. Mientras tanto: {p}confirmo"
                )
            resumen = resumen_plan(ctx, abierto)
            if not almacen.cerrar_plan(abierto.id):
                return  # otro la cerró recién
            encabezado = ctx.frase("plan.cierre", PLAN_CIERRE, plan=abierto.nombre)
            mensaje = await ctx.responder(f"{encabezado}\n\n{resumen}")
        else:
            mensaje = await ctx.responder(resumen_plan(ctx, abierto))
        almacen.anotar_mensaje_plan(ctx.clave_chat, mensaje, abierto.id)
        return

    raise ErrorUsuario(
        f"No te entendí. Para abrir una lista: {p}confirmo armar <plan>. "
        f"Para anotarte: {p}confirmo voy, capaz o me bajo. Para ver más: {p}ayuda confirmo"
    )


@escuchar
async def respuesta_suelta(ctx: Contexto) -> bool:
    """Un "voy", "capaz" o "me bajo" que responde a la convocatoria o a un resumen del plan."""
    if not ctx.es_grupo or not ctx.citado:
        return False
    estado = ESTADOS.get(texto_normalizado(ctx.texto))
    if estado is None:
        return False
    plan = ctx.bot.almacen.plan_de_mensaje(ctx.clave_chat, ctx.citado)
    if plan is None:
        return False  # respondió a otra cosa: no anotamos a nadie
    if not plan.abierto:
        abierto = ctx.bot.almacen.plan_abierto(ctx.clave_chat)
        aviso = f"Esa lista («{plan.nombre}») ya está cerrada."
        if abierto is not None:
            aviso += f" La abierta es «{abierto.nombre}»: anotate con {ctx.prefijo}confirmo {estado}."
        await ctx.responder(aviso)
        return True
    await anotar(ctx, plan, estado)
    return True
