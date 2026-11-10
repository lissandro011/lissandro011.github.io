"""Pruebas de los comandos de juego, grupo y del permiso para agregar al bot a grupos.

Usan los mismos mensajes simulados y el cliente falso de test_bot.py.
"""

import asyncio

import pytest
from neonize.proto.Neonize_pb2 import JoinedGroup
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message, StickerMessage
from test_bot import (  # noqa: F401  (comandos_cargados es un fixture automático)
    BOT,
    DUENO,
    GRUPO,
    JID,
    OTRO,
    Almacen,
    ClienteFalso,
    GroupInfo,
    GroupName,
    GroupParticipant,
    LichaBot,
    comandos_cargados,
    crear_bot,
    desde_dict,
    evento,
    procesar,
    respuesta,
    texto,
)

import comandos.diversion as diversion
import comandos.general as general
import comandos.grupo as grupo
import comandos.stickers as stickers
from licha_bot.frases import Bolsas, Memoria

TERCERO = "5493333333333"
GRUPO_JID = f"{GRUPO}@g.us"


def todas(banco, **datos) -> set[str]:
    """Todas las frases de un banco ya completadas."""
    return {f.format(p="!", **datos) for f in banco}


def integrante(numero: str, admin: bool = False) -> GroupParticipant:
    return GroupParticipant(JID=JID(User=numero, Server="s.whatsapp.net"), IsAdmin=admin)


class Reloj:
    def __init__(self):
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


def con_reloj(bot: LichaBot) -> Reloj:
    reloj = Reloj()
    bot.memoria._reloj = reloj
    return reloj


# --------------------------------------------------------------------------- #
# Bolsas y memoria
# --------------------------------------------------------------------------- #


def test_bolsa_usa_todas_antes_de_repetir_y_no_arranca_con_la_ultima():
    bolsas = Bolsas()
    opciones = ("a", "b", "c", "d")
    vistas = []
    for _ in range(40):
        vistas.append(bolsas.sacar("chat", "banco", opciones))
    for vuelta in range(10):
        assert sorted(vistas[vuelta * 4 : vuelta * 4 + 4]) == list(opciones)
    assert all(x != y for x, y in zip(vistas, vistas[1:], strict=False))  # nunca la misma dos veces seguidas


def test_bolsas_separadas_por_chat():
    bolsas = Bolsas()
    assert {bolsas.sacar("a", "b", ("x", "y")) for _ in range(2)} == {"x", "y"}
    assert {bolsas.sacar("otro", "b", ("x", "y")) for _ in range(2)} == {"x", "y"}


def test_memoria_cuenta_rachas_y_caduca():
    reloj = Reloj()
    memoria = Memoria(90, reloj=reloj)
    assert memoria.racha("c", "p", "moneda", dato="Cara").numero == 1
    reloj.ahora += 30
    racha = memoria.racha("c", "p", "moneda", dato="Cruz")
    assert racha.numero == 2 and racha.anterior == "Cara"
    reloj.ahora += 91
    assert memoria.racha("c", "p", "moneda").numero == 1


# --------------------------------------------------------------------------- #
# !moneda
# --------------------------------------------------------------------------- #


def tirar_moneda(bot, monkeypatch, lado, **kw):
    monkeypatch.setattr(diversion.random, "choice", lambda opciones: lado)
    procesar(bot, evento(texto("!moneda"), **kw))


def test_moneda_dos_caras_seguidas_no_dispara_chiste_de_cambio(monkeypatch):
    bot, cliente = crear_bot()
    tirar_moneda(bot, monkeypatch, "Cara")
    tirar_moneda(bot, monkeypatch, "Cara")
    tirar_moneda(bot, monkeypatch, "Cruz")
    primera, segunda, tercera = cliente.respuestas
    assert primera in todas(diversion.MONEDA_PRIMERA, lado="Cara")
    assert segunda in todas(diversion.MONEDA_IGUAL, lado="Cara")
    assert segunda not in todas(diversion.MONEDA_CAMBIO, lado="Cara")
    assert tercera in todas(diversion.MONEDA_CAMBIO, lado="Cruz")


def test_moneda_despues_de_un_rato_vuelve_a_ser_primera_tirada(monkeypatch):
    bot, cliente = crear_bot()
    reloj = con_reloj(bot)
    tirar_moneda(bot, monkeypatch, "Cara")
    reloj.ahora += bot.config.enseguida_segundos + 1
    tirar_moneda(bot, monkeypatch, "Cara")
    assert cliente.respuestas[1] in todas(diversion.MONEDA_PRIMERA, lado="Cara")


def test_moneda_cuenta_por_persona(monkeypatch):
    bot, cliente = crear_bot()
    tirar_moneda(bot, monkeypatch, "Cara", de=OTRO)
    tirar_moneda(bot, monkeypatch, "Cara", de=TERCERO)
    assert cliente.respuestas[1] in todas(diversion.MONEDA_PRIMERA, lado="Cara")


# --------------------------------------------------------------------------- #
# !elegir
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "t, esperado",
    [
        ("pizza, empanadas o sushi", ["pizza", "empanadas", "sushi"]),
        ("bondi o Uber", ["bondi", "Uber"]),
        ("ir | quedarse", ["ir", "quedarse"]),
        ("ir al cine o al teatro | quedarnos", ["ir al cine o al teatro", "quedarnos"]),
        ("ir al cine o al teatro, quedarnos", ["ir al cine o al teatro", "quedarnos"]),
        ("rojo azul verde", ["rojo", "azul", "verde"]),
        ("¿Netflix o dormir?", ["Netflix", "dormir"]),
        ("siete u ocho", ["siete", "ocho"]),
        ("a,,  , b", ["a", "b"]),
        ("solo", ["solo"]),
    ],
)
def test_partir_opciones(t, esperado):
    assert diversion.partir_opciones(t) == esperado


def test_sin_repetir_conserva_la_escritura_original():
    assert diversion.sin_repetir(["Comida China", "comida china", "Sushi"]) == ["Comida China", "Sushi"]


def test_elegir_rojo_o_negro_jamas_menciona_comida():
    bot, cliente = crear_bot()
    for _ in range(40):
        procesar(bot, evento(texto("!elegir rojo o negro")))
    generales = todas(diversion.ELEGIR_GENERAL, opcion="rojo") | todas(diversion.ELEGIR_GENERAL, opcion="negro")
    for r in cliente.respuestas:
        assert r in generales
        assert not any(c in r.lower() for c in ("pizza", "hamburguesa", "bondi", "uber"))


def test_elegir_pizza_o_hamburguesas_usa_especificos_o_general():
    bot, cliente = crear_bot()
    for _ in range(30):
        procesar(bot, evento(texto("!elegir Pizza o hamburguesas")))
    validas = (
        todas(diversion.ELEGIR_GENERAL, opcion="Pizza")
        | todas(diversion.ELEGIR_GENERAL, opcion="hamburguesas")
        | {f for frases in diversion.ELEGIR_ESPECIFICOS.values() for f in frases if "ondi" not in f and "Uber" not in f}
    )
    assert set(cliente.respuestas) <= validas


def test_elegir_todas_iguales_y_sin_opciones():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!elegir pizza o Pizza")))
    procesar(bot, evento(texto("!elegir pizza")))
    procesar(bot, evento(texto("!elegir")))
    iguales, una, ninguna = cliente.respuestas
    assert iguales in todas(diversion.ELEGIR_TODAS_IGUALES, opcion="pizza")
    assert una in todas(diversion.ELEGIR_FALTAN) and ninguna in todas(diversion.ELEGIR_FALTAN)
    assert "!elegir" in una and "!elegir" in ninguna  # siempre muestra la sintaxis


def test_elegir_con_tres_opciones():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!elegir pizza, empanadas o sushi")))
    opciones = ("pizza", "empanadas", "sushi")
    assert any(cliente.respuestas[0] in todas(diversion.ELEGIR_GENERAL, opcion=o) for o in opciones)


# --------------------------------------------------------------------------- #
# !8ball
# --------------------------------------------------------------------------- #


def preguntar(bot, monkeypatch, pregunta, veredicto="no", especifico=True):
    monkeypatch.setattr(diversion.random, "choices", lambda opciones, pesos: [veredicto])
    monkeypatch.setattr(diversion.random, "random", lambda: 0.0 if especifico else 0.99)
    procesar(bot, evento(texto(f"!8ball {pregunta}")))


def test_8ball_pregunta_desconocida_recibe_veredicto_coherente(monkeypatch):
    bot, cliente = crear_bot()
    preguntar(bot, monkeypatch, "mañana llueve", "no")
    preguntar(bot, monkeypatch, "se arma el asado?", "sí")
    preguntar(bot, monkeypatch, "LLEGO A TIEMPO", "dudoso")
    no, si, dudoso = cliente.respuestas
    assert no in diversion.BOLA_GENERAL["no"]
    assert si in diversion.BOLA_GENERAL["sí"]
    assert dudoso in diversion.BOLA_GENERAL["dudoso"]


def test_8ball_le_escribo_es_frase_completa(monkeypatch):
    bot, cliente = crear_bot()
    preguntar(bot, monkeypatch, "¿Le escribo?", "sí")
    preguntar(bot, monkeypatch, "le mando un mensaje o no", "no")
    preguntar(bot, monkeypatch, "¿me escribe mañana?", "no")
    escribo_si, mando_no, me_escribe = cliente.respuestas
    assert escribo_si in diversion.BOLA_LE_ESCRIBO["sí"]
    assert mando_no in diversion.BOLA_LE_ESCRIBO["no"]
    assert me_escribe in diversion.BOLA_GENERAL["no"]


def test_8ball_vacia_abierta_y_delicada(monkeypatch):
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!8ball")))
    preguntar(bot, monkeypatch, "¿qué como hoy?")
    preguntar(bot, monkeypatch, "¿sale bien la operación de mi vieja?", "no")
    vacia, abierta, delicada = cliente.respuestas
    assert vacia in todas(diversion.BOLA_VACIA) and "!8ball" in vacia
    assert abierta == diversion.BOLA_ABIERTA.format(p="!")
    assert delicada == "🎱 La bola dice que no."


# --------------------------------------------------------------------------- #
# !dado
# --------------------------------------------------------------------------- #


def test_leer_dados():
    assert diversion.leer_dados("") == (1, 6)
    assert diversion.leer_dados("20") == (1, 20)
    assert diversion.leer_dados("2d6") == (2, 6)
    assert diversion.leer_dados("D12") == (1, 12)
    for malo in ("1", "abc", "11d6", "2d1", "d5000"):
        with pytest.raises(ValueError):
            diversion.leer_dados(malo)


def test_dado_muestra_la_tirada_real(monkeypatch):
    bot, cliente = crear_bot()
    valores = iter([3, 3, 4])
    monkeypatch.setattr(diversion.random, "randint", lambda a, b: next(valores))
    monkeypatch.setattr(diversion.random, "random", lambda: 0.0)  # usa la frase especial si corresponde
    procesar(bot, evento(texto("!dado 2d6")))
    procesar(bot, evento(texto("!dado")))
    procesar(bot, evento(texto("!dado banana")))
    iguales, uno, malo = cliente.respuestas
    assert iguales == diversion.DADO_TODOS_IGUALES.format(tirada="3 + 3 = *6*")
    assert uno in todas(diversion.DADO_GENERAL, tirada="*4*")
    assert "!dado 2d6" in malo


def test_dado_minimo_y_maximo(monkeypatch):
    bot, cliente = crear_bot()
    valores = iter([1, 20])
    monkeypatch.setattr(diversion.random, "randint", lambda a, b: next(valores))
    monkeypatch.setattr(diversion.random, "random", lambda: 0.0)
    procesar(bot, evento(texto("!dado")))
    procesar(bot, evento(texto("!dado 20")))
    assert cliente.respuestas == [
        diversion.DADO_MINIMO.format(tirada="*1*"),
        diversion.DADO_MAXIMO.format(tirada="*20*"),
    ]


# --------------------------------------------------------------------------- #
# !top5
# --------------------------------------------------------------------------- #


def test_top5_etiqueta_integrantes_sin_el_bot():
    bot, cliente = crear_bot()
    numeros = [f"54911000000{i:02d}" for i in range(8)]
    cliente.integrantes = [integrante(BOT)] + [integrante(n) for n in numeros]
    ev = evento(texto("!top5 más dormilones"), grupo=True)
    procesar(bot, ev)
    ext = cliente.enviados[0][1].extendedTextMessage
    encabezado, vacia, titulo, *puestos = ext.text.split("\n")
    assert encabezado in diversion.TOP_ENCABEZADOS and vacia == ""
    assert titulo == "🏆 *Top 5: más dormilones*" and len(puestos) == 5
    assert ext.contextInfo.stanzaID == ev.Info.ID  # responde citando
    mencionados = list(ext.contextInfo.mentionedJID)
    assert len(mencionados) == len(set(mencionados)) == 5
    assert all(m.split("@")[0] in numeros and f"@{m.split('@')[0]}" in ext.text for m in mencionados)


def test_top_se_ajusta_a_los_disponibles_y_errores():
    bot, cliente = crear_bot()
    cliente.integrantes = [integrante("5491100000001"), integrante("5491100000002")]
    procesar(bot, evento(texto("!top 3 mejores cocineros"), grupo=True))
    assert "🏆 *Top 2: mejores cocineros*" in cliente.enviados[0][1].extendedTextMessage.text

    procesar(bot, evento(texto("!top5"), grupo=True))
    procesar(bot, evento(texto("!top 50 algo"), grupo=True))
    procesar(bot, evento(texto("!top5 algo")))  # por privado
    sin_titulo, muchos, privado = cliente.respuestas
    assert "!top5 más dormilones" in sin_titulo
    assert "de 2 a 10" in muchos
    assert "se usa en grupos" in privado


# --------------------------------------------------------------------------- #
# !ping
# --------------------------------------------------------------------------- #


def test_tercer_ping_de_dos_usuarios_no_se_mezcla():
    bot, cliente = crear_bot()
    for de in (OTRO, OTRO, TERCERO, OTRO, TERCERO):
        procesar(bot, evento(texto("!ping"), de=de, grupo=True))
    a1, a2, b1, a3, b2 = cliente.respuestas
    assert a1 in general.PING_PRIMERO and b1 in general.PING_PRIMERO
    assert a2 in general.PING_SEGUNDO and b2 in general.PING_SEGUNDO
    assert a3 in general.PING_RACHA


def test_otro_comando_corta_la_racha_del_ping():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!ping")))
    procesar(bot, evento(texto("!moneda")))
    procesar(bot, evento(texto("!ping")))
    assert cliente.respuestas[2] in general.PING_PRIMERO


def test_estado_dice_hace_cuanto_esta_prendido():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!estado")))
    assert "Prendido hace" in cliente.respuestas[0]


# --------------------------------------------------------------------------- #
# !excusa
# --------------------------------------------------------------------------- #


def test_segunda_excusa_trae_comentario_y_excusa_nueva():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!excusa")))
    procesar(bot, evento(texto("!excusa")))
    primera, comentario = cliente.respuestas
    assert primera in diversion.EXCUSAS
    assert comentario in diversion.EXCUSA_OTRA
    ((_, segunda),) = cliente.textos()  # la excusa nueva va sola, para poder reenviarla
    assert segunda in diversion.EXCUSAS and segunda != primera


def test_excusas_no_se_repiten_para_la_misma_persona_aunque_otros_pidan():
    bot, cliente = crear_bot()
    reloj = con_reloj(bot)
    mias = []
    for _ in range(len(diversion.EXCUSAS)):
        procesar(bot, evento(texto("!excusa"), de=OTRO))
        mias.append(cliente.respuestas[-1])
        procesar(bot, evento(texto("!excusa"), de=TERCERO))
        reloj.ahora += 1000  # cada pedido "de entrada": solo la excusa
    assert sorted(mias) == sorted(diversion.EXCUSAS)


def test_excusa_funciona_por_privado():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!excusa")))
    assert cliente.respuestas[0] in diversion.EXCUSAS


# --------------------------------------------------------------------------- #
# !decreto
# --------------------------------------------------------------------------- #


def decreto(bot, t, de=OTRO):
    procesar(bot, evento(texto(f"!decreto {t}".strip()), de=de, grupo=True))


def test_decreto_abre_vota_y_cambiar_voto_altera_ambos_totales():
    bot, cliente = crear_bot()
    decreto(bot, "El que llega tarde paga el hielo")
    apertura = cliente.respuestas[-1]
    assert "«El que llega tarde paga el hielo»" in apertura and "!decreto si / !decreto no" in apertura
    assert apertura.split("\n")[0] in grupo.DECRETO_APERTURA

    decreto(bot, "Sí")
    decreto(bot, "estado")
    assert "Sí: 1 · No: 0" in cliente.respuestas[-1]
    decreto(bot, "no")
    assert cliente.respuestas[1] in todas(grupo.DECRETO_VOTO, voto="sí")
    assert cliente.respuestas[-1] in todas(grupo.DECRETO_CAMBIO, voto="no", antes="sí")
    decreto(bot, "estado")
    assert "Sí: 0 · No: 1" in cliente.respuestas[-1]


def test_decreto_voto_repetido_no_suma():
    bot, cliente = crear_bot()
    decreto(bot, "Prohibido el audio de más de un minuto")
    decreto(bot, "si")
    decreto(bot, "SI")
    decreto(bot, "si", de=TERCERO)
    assert cliente.respuestas[2] in todas(grupo.DECRETO_REPETIDO, voto="sí")
    decreto(bot, "estado")
    assert "Sí: 2 · No: 0" in cliente.respuestas[-1]


def test_decreto_empate_y_cero_votos_cierran_distinto():
    bot, cliente = crear_bot()
    decreto(bot, "Regla uno")
    decreto(bot, "si")
    decreto(bot, "no", de=TERCERO)
    decreto(bot, "cerrar")
    empate = cliente.respuestas[-1]
    assert empate.split("\n")[0] in todas(grupo.DECRETO_EMPATE, regla="Regla uno")
    assert empate.endswith("Sí: 1 · No: 1")

    decreto(bot, "Regla dos")
    decreto(bot, "cerrar")
    cero = cliente.respuestas[-1]
    assert cero.split("\n")[0] in todas(grupo.DECRETO_SIN_VOTOS, regla="Regla dos")
    assert cero.endswith("Sí: 0 · No: 0")


def test_decreto_aprobado_y_rechazado():
    bot, cliente = crear_bot()
    decreto(bot, "Regla linda")
    decreto(bot, "si")
    decreto(bot, "cerrar")
    assert cliente.respuestas[-1].split("\n")[0] in todas(grupo.DECRETO_APROBADO, regla="Regla linda")
    decreto(bot, "Regla fea")
    decreto(bot, "no")
    decreto(bot, "cerrar")
    assert cliente.respuestas[-1].split("\n")[0] in todas(grupo.DECRETO_RECHAZADO, regla="Regla fea")


def test_decreto_subcomandos_no_se_guardan_como_propuestas():
    bot, cliente = crear_bot()
    for t in ("si", "no", "estado", "cerrar", ""):
        decreto(bot, t)
    assert bot.almacen.decreto_abierto(GRUPO_JID) is None
    assert all("!decreto" in r for r in cliente.respuestas)  # cada error dice qué usar


def test_decreto_otra_propuesta_muestra_la_abierta():
    bot, cliente = crear_bot()
    decreto(bot, "Primera regla")
    decreto(bot, "Segunda regla", de=TERCERO)
    assert "«Primera regla»" in cliente.respuestas[-1]
    assert bot.almacen.decreto_abierto(GRUPO_JID).texto == "Primera regla"


def test_decreto_cerrar_solo_quien_propuso_admin_o_dueno():
    bot, cliente = crear_bot()
    cliente.integrantes = [integrante(OTRO), integrante(TERCERO), integrante("5494444444444", admin=True)]
    decreto(bot, "Regla")
    decreto(bot, "cerrar", de=TERCERO)
    assert "quien la propuso" in cliente.respuestas[-1]
    assert bot.almacen.decreto_abierto(GRUPO_JID) is not None
    decreto(bot, "cerrar", de="5494444444444")  # admin
    assert bot.almacen.decreto_abierto(GRUPO_JID) is None

    decreto(bot, "Otra regla")
    decreto(bot, "cerrar", de=DUENO)
    assert bot.almacen.decreto_abierto(GRUPO_JID) is None


def test_decreto_y_confirmo_por_privado_explican_que_son_de_grupos():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!decreto algo")))
    procesar(bot, evento(texto("!confirmo armar algo")))
    for r in cliente.respuestas:
        assert "se usa en grupos" in r and "!excusa" in r


# --------------------------------------------------------------------------- #
# !confirmo
# --------------------------------------------------------------------------- #


def confirmo(bot, t, de=OTRO, nombre="Ana"):
    procesar(bot, evento(texto(f"!confirmo {t}".strip()), de=de, grupo=True, nombre=nombre))


def resumen(bot, cliente) -> str:
    confirmo(bot, "resumen")
    return cliente.respuestas[-1]


def test_confirmo_abre_con_como_anotarse():
    bot, cliente = crear_bot()
    confirmo(bot, "armar Previa del Sábado")
    apertura = cliente.respuestas[-1]
    assert apertura.split("\n")[0] in todas(grupo.PLAN_APERTURA, plan="Previa del Sábado")
    assert "!confirmo voy" in apertura and "me bajo" in apertura


def test_confirmo_pasar_de_capaz_a_voy_no_duplica():
    bot, cliente = crear_bot()
    confirmo(bot, "armar asado")
    confirmo(bot, "capaz")
    assert cliente.respuestas[-1] in todas(grupo.PLAN_RESPUESTAS["capaz"], nombre="Ana", plan="asado")
    confirmo(bot, "voy")
    assert cliente.respuestas[-1] in todas(grupo.PLAN_CAMBIO, nombre="Ana", antes="capaz", ahora="voy")
    confirmo(bot, "voy")
    assert cliente.respuestas[-1] in todas(grupo.PLAN_REPETIDO, nombre="Ana", ahora="voy")
    texto_resumen = resumen(bot, cliente)
    assert "✅ Voy (1): Ana" in texto_resumen and "🤔 Capaz (0): -" in texto_resumen
    assert texto_resumen.splitlines()[0] == "📋 *asado*"


def test_confirmo_resumen_con_remate_aplicable():
    bot, cliente = crear_bot()
    confirmo(bot, "armar previa")
    texto_resumen = resumen(bot, cliente)
    assert texto_resumen.splitlines()[-1] in {
        "Todavía no contestó nadie. Por ahora el plan es una expresión de deseo.",
        grupo.REMATE_SIEMPRE,
    }
    confirmo(bot, "voy", de=OTRO, nombre="Ana")
    confirmo(bot, "voy", de=TERCERO, nombre="Beto")
    confirmo(bot, "capaz", de="5494444444444", nombre="Caro")
    texto_resumen = resumen(bot, cliente)
    assert "✅ Voy (2): Ana, Beto" in texto_resumen and "🤔 Capaz (1): Caro" in texto_resumen
    assert texto_resumen.splitlines()[-1] in set(grupo.remates(2, 1, 0))


def test_remates_cantidades_en_espanol():
    assert grupo.remates(1, 3, 0)[0].startswith("Va 1. Hay 3 en «veo»")
    assert grupo.remates(4, 3, 0)[0].startswith("Van 4. Hay 3 en «veo»")
    assert "Todos los que contestaron se bajaron." in grupo.remates(0, 0, 2)[0]


def test_respuesta_suelta_citando_la_convocatoria():
    bot, cliente = crear_bot()
    confirmo(bot, "armar fulbito")
    id_convocatoria = "BOT1"  # el cliente falso numera los mensajes del bot
    procesar(bot, evento(respuesta("Capaz", Message(conversation="..."), id_convocatoria), grupo=True, nombre="Beto",
                         de=TERCERO))  # fmt: skip
    assert cliente.respuestas[-1] in todas(grupo.PLAN_RESPUESTAS["capaz"], nombre="Beto", plan="fulbito")
    # Un "voy" suelto en otra charla (sin citar el plan) no anota a nadie.
    procesar(bot, evento(texto("voy"), grupo=True, de="5494444444444"))
    procesar(bot, evento(respuesta("voy", Message(conversation="otra cosa"), "OTRO_MENSAJE"), grupo=True))
    assert "🤔 Capaz (1): Beto" in resumen(bot, cliente)
    assert "✅ Voy (0): -" in cliente.respuestas[-1]


def test_voy_citando_un_plan_cerrado_no_entra_en_el_siguiente():
    bot, cliente = crear_bot()
    confirmo(bot, "armar plan viejo")  # su convocatoria es BOT1
    confirmo(bot, "cerrar")
    cierre = cliente.respuestas[-1]
    assert cierre.split("\n")[0] in todas(grupo.PLAN_CIERRE, plan="plan viejo") and "📋 *plan viejo*" in cierre
    confirmo(bot, "armar plan nuevo")
    procesar(bot, evento(respuesta("voy", Message(conversation="..."), "BOT1"), grupo=True, de=TERCERO))
    assert "ya está cerrada" in cliente.respuestas[-1] and "plan nuevo" in cliente.respuestas[-1]
    assert "✅ Voy (0): -" in resumen(bot, cliente)


def test_confirmo_una_lista_por_grupo_y_permisos_de_cierre():
    bot, cliente = crear_bot()
    confirmo(bot, "armar cumple")
    confirmo(bot, "armar otro plan", de=TERCERO)
    assert "«cumple»" in cliente.respuestas[-1]
    confirmo(bot, "cerrar", de=TERCERO)
    assert "quien la armó" in cliente.respuestas[-1]
    confirmo(bot, "cerrar")
    assert bot.almacen.plan_abierto(GRUPO_JID) is None
    confirmo(bot, "cerrar")
    assert "!confirmo armar" in cliente.respuestas[-1]


def test_listas_y_votaciones_sobreviven_a_un_reinicio(tmp_path):
    archivo = tmp_path / "licha.sqlite3"
    datos = {"bot": {"duenos": [DUENO], "espera_entre_comandos": 0}}
    bot = LichaBot(desde_dict(datos), cliente=ClienteFalso(), almacen=Almacen(archivo))
    confirmo(bot, "armar previa")
    confirmo(bot, "voy")
    decreto(bot, "Regla persistente")
    decreto(bot, "si")
    bot.almacen.cerrar()

    cliente = ClienteFalso()
    bot2 = LichaBot(desde_dict(datos), cliente=cliente, almacen=Almacen(archivo))
    confirmo(bot2, "")
    decreto(bot2, "estado")
    assert "✅ Voy (1): Ana" in cliente.respuestas[0]
    assert "Sí: 1 · No: 0" in cliente.respuestas[1]


def test_listas_aisladas_por_chat():
    bot, cliente = crear_bot()
    confirmo(bot, "armar previa")
    assert bot.almacen.plan_abierto("otro@g.us") is None


# --------------------------------------------------------------------------- #
# !menu y !ayuda
# --------------------------------------------------------------------------- #


def test_menu_primera_vez_y_despues_saludos_rotan():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!menu"), grupo=True))
    procesar(bot, evento(texto("!menu"), grupo=True))
    primero, segundo = cliente.respuestas
    assert primero.splitlines()[3] == general.SALUDO_PRIMERA_VEZ
    assert segundo.splitlines()[3] in general.SALUDOS_MENU


def test_menu_en_grupo_tiene_el_formato_pedido():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!menu"), grupo=True))
    menu = cliente.respuestas[0]
    assert menu.startswith("🤖 *Licha Bot*\n\nMandame una foto, video o GIF y te lo hago sticker.\n")
    for linea in (
        "🎲 *Para jugar*",
        "• !dado — Tirá uno o varios dados.",
        "• !confirmo armar <plan> — Abrí la lista. Cada uno pone voy, capaz o me bajo.",
        "• !decreto <regla> — Proponé una regla y que el grupo la vote.",
        "• !excusa — Te doy una excusa para bajarte del plan. Mandarla te toca a vos.",
        "• !ayuda <comando> — Te muestro cómo se usa.",
        "¿Armamos algo? Probá con *!confirmo armar previa del sábado*.",
        "Para ver cómo se usa uno, mandá *!ayuda sticker*.",
    ):
        assert linea in menu.splitlines()
    assert "Solo Licha" not in menu and "(solo grupos)" not in menu


def test_menu_por_privado_marca_los_de_grupo():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!menu")))
    menu = cliente.respuestas[0]
    assert "• !confirmo armar <plan> (solo grupos) — Abrí la lista. Cada uno pone voy, capaz o me bajo." in menu
    assert "• !decreto <regla> (solo grupos) — Proponé una regla y que el grupo la vote." in menu
    assert "• !excusa — " in menu
    assert "¿Lo dejamos a la suerte? Probá con *!elegir bondi o Uber*." in menu


def test_ayuda_sin_nombre_desconocido_y_con_ejemplos():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!ayuda")))
    procesar(bot, evento(texto("!ayuda cualquiera")))
    procesar(bot, evento(texto("!ayuda confirmo")))
    procesar(bot, evento(texto("!ayuda decreto")))
    falta, desconocido, ayuda_confirmo, ayuda_decreto = cliente.respuestas
    assert falta in todas(general.AYUDA_FALTA)
    assert desconocido == general.AYUDA_DESCONOCIDO.format(p="!")
    for ejemplo in ("!confirmo armar", "!confirmo capaz", "!confirmo cerrar", "!confirmo →"):
        assert ejemplo in ayuda_confirmo
    for ejemplo in ("!decreto si", "!decreto no", "!decreto estado", "!decreto cerrar"):
        assert ejemplo in ayuda_decreto


# --------------------------------------------------------------------------- #
# Stickers y dueño siguen por sus rutas
# --------------------------------------------------------------------------- #


def test_sticker_de_un_sticker_sin_cambios():
    bot, cliente = crear_bot()
    procesar(bot, evento(respuesta("!s", Message(stickerMessage=StickerMessage(mimetype="image/webp")))))
    assert cliente.respuestas[0].split(" Si querés")[0] in stickers.STICKER_YA_ES
    assert cliente.stickers() == [] and cliente.descargados == []


def test_reiniciar_y_apagar_del_dueno_con_frases():
    import comandos.dueno as dueno

    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!apagar"), de=DUENO))
    assert cliente.respuestas[0] in dueno.APAGANDO and cliente.detenido


def test_mensaje_repetido_se_procesa_una_sola_vez():
    bot, cliente = crear_bot()
    ev = evento(texto("!ping"))
    procesar(bot, ev)
    procesar(bot, ev)
    assert len(cliente.respuestas) == 1


# --------------------------------------------------------------------------- #
# Solo el dueño agrega el bot a grupos
# --------------------------------------------------------------------------- #

NUEVO = "120363999999999999"


def bot_con_guardia(**config):
    bot, cliente = crear_bot(**config)
    cliente.grupos = [GroupInfo(JID=JID(User=GRUPO, Server="g.us"), GroupName=GroupName(Name="Los de siempre"))]
    asyncio.run(bot.guardia.preparar())
    return bot, cliente


def unirse(bot, quien=None, nombre="Grupo nuevo"):
    ev = JoinedGroup()
    ev.GroupInfo.JID.CopyFrom(JID(User=NUEVO, Server="g.us"))
    ev.GroupInfo.GroupName.Name = nombre
    if quien:
        ev.Sender.CopyFrom(JID(User=quien, Server="s.whatsapp.net"))
    asyncio.run(bot._al_unirse_a_grupo(None, ev))


def test_los_grupos_donde_ya_estaba_quedan_autorizados():
    bot, cliente = bot_con_guardia()
    assert bot.almacen.estado_grupo(GRUPO_JID) == "autorizado"
    procesar(bot, evento(texto("!ping"), grupo=True))
    assert len(cliente.respuestas) == 1


def test_si_lo_agrega_otro_pide_permiso_al_dueno_y_no_contesta():
    bot, cliente = bot_con_guardia()
    unirse(bot, quien=OTRO)
    mensajes = dict(cliente.textos())
    assert "permiso del dueño" in mensajes[f"{NUEVO}@g.us"]
    aviso = mensajes[f"{DUENO}@s.whatsapp.net"]
    (pendiente,) = bot.almacen.pendientes()
    assert f"!autorizar {pendiente.codigo}" in aviso and f"+{OTRO}" in aviso and "Grupo nuevo" in aviso

    ev = evento(texto("!ping"), grupo=True)
    ev.Info.MessageSource.Chat.User = NUEVO
    procesar(bot, ev)
    assert cliente.respuestas == []  # en un grupo sin autorizar no le contesta a nadie


def test_el_dueno_autoriza_con_el_codigo():
    bot, cliente = bot_con_guardia()
    unirse(bot, quien=OTRO)
    (pendiente,) = bot.almacen.pendientes()
    procesar(bot, evento(texto(f"!autorizar {pendiente.codigo}"), de=DUENO))
    assert bot.almacen.estado_grupo(f"{NUEVO}@g.us") == "autorizado"
    assert "me quedo" in cliente.respuestas[-1]
    assert any(d == f"{NUEVO}@g.us" and "me dejó quedarme" in t for d, t in cliente.textos())


def test_sin_respuesta_se_va_solo_y_rechazar_lo_saca():
    bot, cliente = bot_con_guardia()
    unirse(bot, quien=OTRO)
    asyncio.run(bot.guardia.vencer(f"{NUEVO}@g.us"))
    assert cliente.salidas == [f"{NUEVO}@g.us"]
    assert bot.almacen.estado_grupo(f"{NUEVO}@g.us") is None

    unirse(bot, quien=TERCERO)
    (pendiente,) = bot.almacen.pendientes()
    procesar(bot, evento(texto(f"!rechazar {pendiente.codigo}"), de=DUENO))
    assert cliente.salidas == [f"{NUEVO}@g.us"] * 2


def test_si_lo_agrega_el_dueno_queda_autorizado():
    bot, cliente = bot_con_guardia()
    unirse(bot, quien=DUENO)
    assert bot.almacen.estado_grupo(f"{NUEVO}@g.us") == "autorizado"
    assert bot.almacen.pendientes() == []
    assert not any(d.endswith("@s.whatsapp.net") for d, _ in cliente.textos())  # no molesta al dueño


def test_otros_no_pueden_autorizar():
    bot, cliente = bot_con_guardia()
    unirse(bot, quien=OTRO)
    (pendiente,) = bot.almacen.pendientes()
    procesar(bot, evento(texto(f"!autorizar {pendiente.codigo}"), de=OTRO))
    assert bot.almacen.estado_grupo(f"{NUEVO}@g.us") == "pendiente"


def test_grupo_desconocido_pide_permiso_aunque_no_llegue_el_aviso_de_union():
    bot, cliente = bot_con_guardia()
    ev = evento(texto("!ping"), grupo=True)
    ev.Info.MessageSource.Chat.User = NUEVO
    procesar(bot, ev)
    assert cliente.respuestas == []
    assert bot.almacen.estado_grupo(f"{NUEVO}@g.us") == "pendiente"


def test_sin_restriccion_cualquiera_puede_agregarlo():
    bot, cliente = bot_con_guardia(grupos={"solo_el_dueno_agrega": False})
    unirse(bot, quien=OTRO)
    assert bot.almacen.estado_grupo(f"{NUEVO}@g.us") == "autorizado"
