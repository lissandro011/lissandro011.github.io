"""Pruebas del bot sin conectarse a WhatsApp.

Se arman eventos con los protobufs reales de neonize y se reemplaza el cliente
por uno falso que anota todo lo que el bot manda.
"""

import asyncio
import time

import pytest
from conftest import foto, gif
from neonize.aioze.events import MessageEv
from neonize.proto.Neonize_pb2 import JID, Device, GroupInfo, GroupParticipant, UploadResponse
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    ContextInfo,
    DocumentMessage,
    ExtendedTextMessage,
    FutureProofMessage,
    ImageMessage,
    Message,
    ReactionMessage,
    StickerMessage,
    VideoMessage,
)

from licha_bot.bot import SALIDA_ERROR, SALIDA_REINICIAR, LichaBot
from licha_bot.comandos import REGISTRO, Registro, cargar_comandos
from licha_bot.config import desde_dict
from licha_bot.conversor import inspeccionar_webp
from licha_bot.mensajes import buscar_media, parsear_comando, texto_de

DUENO = "5491111111111"
OTRO = "5492222222222"
BOT = "5490000000000"


# --------------------------------------------------------------------------- #
# Armado de mensajes
# --------------------------------------------------------------------------- #


def texto(t: str) -> Message:
    return Message(conversation=t)


def imagen(caption: str = "", **kw) -> Message:
    return Message(imageMessage=ImageMessage(caption=caption, mimetype="image/jpeg", mediaKey=b"k" * 32, **kw))


def video(caption: str = "", segundos: int = 3, **kw) -> Message:
    return Message(videoMessage=VideoMessage(caption=caption, seconds=segundos, mimetype="video/mp4", **kw))


def respuesta(t: str, citado: Message) -> Message:
    return Message(
        extendedTextMessage=ExtendedTextMessage(text=t, contextInfo=ContextInfo(stanzaID="Q1", quotedMessage=citado))
    )


def evento(msg: Message, *, de=OTRO, grupo=False, propio=False, server=None, ts=None, ver_una_vez=False) -> MessageEv:
    ev = MessageEv()
    ev.Info.ID = "MSG1"
    ev.Info.Pushname = "Ana"
    ev.Info.Timestamp = int(time.time()) if ts is None else ts
    fuente = ev.Info.MessageSource
    fuente.Chat.User = "120363000000000000" if grupo else de
    fuente.Chat.Server = server or ("g.us" if grupo else "s.whatsapp.net")
    fuente.Sender.User = de
    fuente.Sender.Server = "s.whatsapp.net"
    fuente.IsGroup = grupo
    fuente.IsFromMe = propio
    ev.IsViewOnce = ver_una_vez
    ev.Message.CopyFrom(msg)
    return ev


class ClienteFalso:
    def __init__(self, descarga: bytes = b"", error_al_conectar: Exception | None = None):
        self.descarga = descarga
        self.integrantes: list[GroupParticipant] = []
        self.error_al_conectar = error_al_conectar
        self._parado = asyncio.Event()
        self.respuestas: list[str] = []
        self.enviados: list[tuple] = []
        self.subidas: list[bytes] = []
        self.descargados: list[Message] = []
        self.detenido = False

    async def reply_message(self, mensaje, quoted, **_):
        assert isinstance(quoted, MessageEv)
        self.respuestas.append(mensaje)

    async def send_message(self, to, message, **_):
        self.enviados.append((to, message))

    async def build_reaction(self, chat, sender, message_id, reaction):
        return Message(reactionMessage=ReactionMessage(text=reaction))

    async def upload(self, binary, media_type=None):
        self.subidas.append(binary)
        return UploadResponse(url="https://mmg", DirectPath="/d", MediaKey=b"m", FileLength=len(binary))

    async def download_any(self, message):
        self.descargados.append(message)
        return self.descarga

    async def get_group_info(self, jid):
        return GroupInfo(JID=jid, Participants=self.integrantes)

    async def get_me(self):
        return Device(JID=JID(User=BOT, Server="s.whatsapp.net"), LID=JID(User="99", Server="lid"))

    async def connect(self):
        if self.error_al_conectar:
            raise self.error_al_conectar

    async def idle(self):
        await self._parado.wait()

    async def stop(self):
        self.detenido = True
        self._parado.set()

    # ayudas para los tests
    def stickers(self) -> list[StickerMessage]:
        return [m.stickerMessage for _, m in self.enviados if isinstance(m, Message) and m.HasField("stickerMessage")]

    def reacciones(self) -> list[str]:
        mensajes = [m for _, m in self.enviados if isinstance(m, Message)]
        return [m.reactionMessage.text for m in mensajes if m.HasField("reactionMessage")]


@pytest.fixture(scope="module", autouse=True)
def comandos_cargados():
    REGISTRO.limpiar()
    assert cargar_comandos() == []
    yield
    REGISTRO.limpiar()


def crear_bot(descarga: bytes = b"", **config) -> tuple[LichaBot, ClienteFalso]:
    datos = {"bot": {"duenos": [DUENO], "espera_entre_comandos": 0, **config.pop("bot", {})}, **config}
    cliente = ClienteFalso(descarga)
    return LichaBot(desde_dict(datos), cliente=cliente), cliente


def procesar(bot: LichaBot, ev: MessageEv) -> None:
    asyncio.run(bot.procesar(ev))


# --------------------------------------------------------------------------- #
# Ciclo de vida
# --------------------------------------------------------------------------- #


def test_sin_internet_termina_con_error_para_que_iniciar_bat_reintente():
    cliente = ClienteFalso(error_al_conectar=RuntimeError("failed to dial whatsapp web websocket"))
    bot = LichaBot(desde_dict({}), cliente=cliente)
    assert asyncio.run(bot.ejecutar()) == SALIDA_ERROR


def test_reiniciar_devuelve_su_codigo_de_salida():
    bot, cliente = crear_bot()

    async def correr():
        tarea = asyncio.create_task(bot.ejecutar())
        await asyncio.sleep(0.01)
        await bot.detener(SALIDA_REINICIAR)
        return await tarea

    assert asyncio.run(correr()) == SALIDA_REINICIAR
    assert cliente.detenido


# --------------------------------------------------------------------------- #
# Lectura de mensajes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "msg, esperado",
    [
        (texto("!menu"), "!menu"),
        (imagen("!s"), "!s"),
        (respuesta(".sticker", imagen()), ".sticker"),
        (Message(ephemeralMessage=FutureProofMessage(message=texto("!ping"))), "!ping"),
        (Message(documentMessage=DocumentMessage(caption="!s")), "!s"),
    ],
)
def test_texto_de(msg, esperado):
    assert texto_de(msg) == esperado


@pytest.mark.parametrize(
    "t, esperado",
    [
        ("!sticker", ("!", "sticker", "")),
        ("  .S  Mi pack | Yo ", (".", "S", "Mi pack | Yo")),
        ("!", None),
        ("! sticker", None),
        ("hola", None),
        ("...", (".", "..", "")),
    ],
)
def test_parsear_comando(t, esperado):
    assert parsear_comando(t, ("!", ".")) == esperado


def test_buscar_media_directa_citada_y_documento():
    assert buscar_media(imagen("!s")).tipo == "imagen"
    citada = buscar_media(respuesta("!s", video(segundos=5)))
    assert citada.tipo == "video" and citada.citada and citada.segundos == 5
    doc = buscar_media(Message(documentMessage=DocumentMessage(mimetype="image/png")))
    assert doc.tipo == "documento"
    assert buscar_media(Message(documentMessage=DocumentMessage(mimetype="application/pdf"))) is None
    assert buscar_media(texto("!s")) is None


# --------------------------------------------------------------------------- #
# Registro de comandos
# --------------------------------------------------------------------------- #


def test_se_cargan_los_comandos_de_la_carpeta():
    nombres = {c.nombre for c in REGISTRO.todos()}
    assert {"sticker", "imagen", "menu", "ping", "reiniciar", "apagar"} <= nombres
    assert {"dado", "moneda", "8ball", "elegir", "top5"} <= nombres
    assert "numero" not in nombres  # _plantilla.py no se carga
    assert REGISTRO.buscar("S").nombre == "sticker"
    assert REGISTRO.buscar("menú").nombre == "menu"  # sin importar tildes ni mayúsculas


def test_registro_rechaza_duplicados_y_funciones_comunes():
    registro = Registro()

    @registro.comando("hola", "buenas")
    async def hola(ctx):
        pass

    with pytest.raises(ValueError):

        @registro.comando("Buenas")
        async def otra(ctx):
            pass

    with pytest.raises(TypeError):

        @registro.comando("sync")
        def sincronica(ctx):
            pass


# --------------------------------------------------------------------------- #
# Despacho
# --------------------------------------------------------------------------- #


def test_ping():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!ping")))
    assert len(cliente.respuestas) == 1 and "Pong" in cliente.respuestas[0]


def test_menu_lista_los_comandos_sin_los_de_dueno():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto(".menu")))
    menu = cliente.respuestas[0]
    assert "Licha Bot" in menu and ".sticker" in menu and ".ping" in menu
    assert "reiniciar" not in menu
    assert menu.index("Stickers") < menu.index("General")


def test_menu_del_dueno_muestra_sus_comandos():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!menu"), de=DUENO))
    assert "!reiniciar" in cliente.respuestas[0]


def test_ayuda_de_un_comando():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!ayuda s")))
    assert "!s recortar" in cliente.respuestas[0]
    assert "También" in cliente.respuestas[0]


def test_comando_desconocido_por_privado_avisa_y_en_grupo_no():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!cualquiera")))
    assert "No conozco" in cliente.respuestas[0]
    procesar(bot, evento(texto("!cualquiera"), grupo=True))
    assert len(cliente.respuestas) == 1


@pytest.mark.parametrize(
    "kw",
    [
        {"propio": True},
        {"server": "broadcast"},
        {"server": "newsletter"},
        {"ts": int(time.time()) - 3600},
    ],
)
def test_mensajes_ignorados(kw):
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!ping"), **kw))
    assert cliente.respuestas == [] and cliente.enviados == []


def test_saludo_por_privado_una_sola_vez():
    import comandos.general

    comandos.general._ultimo_saludo.clear()
    bot, cliente = crear_bot(foto())
    procesar(bot, evento(texto("hola"), de="5493333333333"))
    procesar(bot, evento(texto("¿estás?"), de="5493333333333"))
    assert len(cliente.respuestas) == 1 and "!menu" in cliente.respuestas[0]
    procesar(bot, evento(texto("hola"), de="5494444444444", grupo=True))
    procesar(bot, evento(imagen("hola"), de="5495555555555"))  # foto con texto: va al sticker automático
    assert len(cliente.respuestas) == 1
    assert len(cliente.stickers()) == 1


def test_no_responde_en_grupos_si_esta_desactivado():
    bot, cliente = crear_bot(bot={"responder_en_grupos": False})
    procesar(bot, evento(texto("!ping"), grupo=True))
    assert cliente.respuestas == []


def test_espera_entre_comandos():
    bot, cliente = crear_bot(bot={"espera_entre_comandos": 60})
    procesar(bot, evento(texto("!ping")))
    procesar(bot, evento(texto("!ping")))
    assert len(cliente.respuestas) == 1
    assert cliente.reacciones() == ["⏳"]


def test_comando_de_dueno():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!reiniciar")))
    assert "solo para el dueño" in cliente.respuestas[0] and not cliente.detenido

    procesar(bot, evento(texto("!reiniciar"), de=DUENO))
    assert cliente.detenido and bot.codigo_salida == SALIDA_REINICIAR


def test_error_inesperado_en_un_comando():
    registro = Registro()

    @registro.comando("roto")
    async def roto(ctx):
        raise RuntimeError("bug")

    cliente = ClienteFalso()
    bot = LichaBot(desde_dict({}), registro=registro, cliente=cliente)
    procesar(bot, evento(texto("!roto")))
    assert "Algo salió mal" in cliente.respuestas[0]


# --------------------------------------------------------------------------- #
# Stickers
# --------------------------------------------------------------------------- #


def test_sticker_de_una_foto():
    bot, cliente = crear_bot(foto())
    procesar(bot, evento(imagen("!s")))
    (sticker,) = cliente.stickers()
    assert sticker.mimetype == "image/webp" and not sticker.isAnimated
    assert sticker.contextInfo.stanzaID == "MSG1"  # sale como respuesta al pedido
    assert cliente.descargados[0].HasField("imageMessage")
    assert inspeccionar_webp(cliente.subidas[0])["exif"]["sticker-pack-name"] == "Licha Bot"


def test_sticker_respondiendo_a_un_gif_con_paquete_propio():
    bot, cliente = crear_bot(gif())
    procesar(bot, evento(respuesta("!sticker recortar Mi pack | Ana", video(gifPlayback=True))))
    (sticker,) = cliente.stickers()
    assert sticker.isAnimated
    exif = inspeccionar_webp(cliente.subidas[0])["exif"]
    assert (exif["sticker-pack-name"], exif["sticker-pack-publisher"]) == ("Mi pack", "Ana")
    assert cliente.reacciones() == ["⏳", ""]  # avisa mientras procesa y después quita la reacción


def test_sticker_sin_foto_explica_como_usarlo():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!s")))
    assert "Mandá una foto" in cliente.respuestas[0]
    assert cliente.stickers() == []


def test_no_hace_stickers_de_ver_una_vez():
    bot, cliente = crear_bot(foto())
    procesar(bot, evento(imagen("!s"), ver_una_vez=True))
    assert "ver una vez" in cliente.respuestas[0]
    assert cliente.descargados == []


def test_archivo_muy_pesado_no_se_descarga():
    bot, cliente = crear_bot(foto(), stickers={"max_mb_descarga": 1})
    procesar(bot, evento(imagen("!s", fileLength=5 * 1024 * 1024)))
    assert "muy pesado" in cliente.respuestas[0]
    assert cliente.descargados == []


def test_sticker_automatico_por_privado():
    bot, cliente = crear_bot(foto())
    procesar(bot, evento(imagen()))
    assert len(cliente.stickers()) == 1


def test_sin_sticker_automatico_en_grupos_ni_si_esta_desactivado():
    bot, cliente = crear_bot(foto())
    procesar(bot, evento(imagen(), grupo=True))
    bot2, cliente2 = crear_bot(foto(), stickers={"automatico_en_privado": False})
    procesar(bot2, evento(imagen()))
    assert cliente.enviados == [] and cliente2.enviados == []


def test_imagen_de_un_sticker():
    webp_bot, webp_cliente = crear_bot(foto())
    procesar(webp_bot, evento(imagen("!s")))
    webp = webp_cliente.subidas[0]

    bot, cliente = crear_bot(webp)
    procesar(bot, evento(respuesta("!imagen", Message(stickerMessage=StickerMessage(mimetype="image/webp")))))
    (_, mensaje) = cliente.enviados[0]
    assert mensaje.imageMessage.mimetype == "image/jpeg"
    assert mensaje.imageMessage.width == 512 and mensaje.imageMessage.JPEGThumbnail


def test_imagen_sin_sticker_explica_como_usarlo():
    bot, cliente = crear_bot()
    procesar(bot, evento(respuesta("!imagen", imagen())))
    assert "Respondé a un sticker" in cliente.respuestas[0]


# --------------------------------------------------------------------------- #
# Diversión
# --------------------------------------------------------------------------- #


def test_leer_dados():
    from comandos.diversion import leer_dados

    assert leer_dados("") == (1, 6)
    assert leer_dados("20") == (1, 20)
    assert leer_dados("2d6") == (2, 6)
    assert leer_dados("D12") == (1, 12)
    for malo in ("1", "abc", "11d6", "2d1", "d5000"):
        with pytest.raises(ValueError):
            leer_dados(malo)


def test_dado_moneda_y_8ball():
    bot, cliente = crear_bot()
    for t in ("!dado", "!dado 2d6", "!dado banana", "!moneda", "!8ball ¿Llueve?", "!8ball"):
        procesar(bot, evento(texto(t)))
    dado, dos_dados, malo, mon, bola, sin_pregunta = cliente.respuestas
    assert dado.startswith("🎲 Salió") and 1 <= int(dado.split("*")[1]) <= 6
    assert "+" in dos_dados and 2 <= int(dos_dados.split("*")[1]) <= 12
    assert "No entendí" in malo
    assert "cara" in mon or "cruz" in mon
    assert bola.startswith("🎱")
    assert "pregunta" in sin_pregunta


@pytest.mark.parametrize(
    "t, esperado",
    [
        ("pizza, empanadas o sushi", ["pizza", "empanadas", "sushi"]),
        ("ir | quedarse", ["ir", "quedarse"]),
        ("rojo azul verde", ["rojo", "azul", "verde"]),
        ("¿Netflix o dormir?", ["Netflix", "dormir"]),
        ("comida china, comida china, Comida China", ["comida china"]),
        ("siete u ocho", ["siete", "ocho"]),
        ("solo", ["solo"]),
    ],
)
def test_leer_opciones(t, esperado):
    from comandos.diversion import leer_opciones

    assert leer_opciones(t) == esperado


def test_elegir():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!elegir pizza, empanadas o sushi")))
    procesar(bot, evento(texto("!elegir pizza")))
    elegido, error = cliente.respuestas
    assert elegido.split("*")[1] in {"pizza", "empanadas", "sushi"}
    assert "al menos dos" in error


def integrante(numero: str) -> GroupParticipant:
    return GroupParticipant(JID=JID(User=numero, Server="s.whatsapp.net"))


def test_top5_etiqueta_integrantes_sin_el_bot():
    bot, cliente = crear_bot()
    numeros = [f"54911000000{i:02d}" for i in range(8)]
    cliente.integrantes = [integrante(BOT)] + [integrante(n) for n in numeros]
    procesar(bot, evento(texto("!top5 más dormilones"), grupo=True))
    (_, mensaje) = cliente.enviados[0]
    ext = mensaje.extendedTextMessage
    assert ext.text.startswith("🏆 *Top 5: más dormilones*")
    assert ext.contextInfo.stanzaID == "MSG1"  # responde citando
    mencionados = list(ext.contextInfo.mentionedJID)
    assert len(mencionados) == len(set(mencionados)) == 5
    assert all(m.split("@")[0] in numeros and f"@{m.split('@')[0]}" in ext.text for m in mencionados)


def test_top_con_cantidad_y_grupo_chico():
    bot, cliente = crear_bot()
    cliente.integrantes = [integrante("5491100000001"), integrante("5491100000002")]
    procesar(bot, evento(texto("!top 3 mejores cocineros"), grupo=True))
    ext = cliente.enviados[0][1].extendedTextMessage
    assert ext.text.startswith("🏆 *Top 2: mejores cocineros*")
    assert len(ext.contextInfo.mentionedJID) == 2


def test_top_errores():
    bot, cliente = crear_bot()
    procesar(bot, evento(texto("!top5"), grupo=True))
    procesar(bot, evento(texto("!top 50 algo"), grupo=True))
    procesar(bot, evento(texto("!top5 algo"), grupo=True))  # grupo sin integrantes
    procesar(bot, evento(texto("!top5 algo")))  # por privado
    sin_titulo, muchos, vacio, privado = cliente.respuestas
    assert "de qué es el top" in sin_titulo
    assert "de 2 a 10" in muchos
    assert "No encontré a nadie" in vacio
    assert "solo funciona en grupos" in privado
