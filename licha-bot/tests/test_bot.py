"""Pruebas del bot sin conectarse a WhatsApp.

Se arman eventos con los protobufs reales de neonize y se reemplaza el cliente
por uno falso que anota todo lo que el bot manda.
"""

import asyncio
import dataclasses
import time

import pytest
from conftest import foto, gif
from neonize.aioze.events import LoggedOutEv, MessageEv
from neonize.proto.Neonize_pb2 import UploadResponse
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

from licha_bot.bot import SALIDA_ERROR, SALIDA_REINICIAR, LichaBot, borrar_sesion_cerrada
from licha_bot.comandos import REGISTRO, Registro, cargar_comandos
from licha_bot.config import desde_dict
from licha_bot.conversor import inspeccionar_webp
from licha_bot.mensajes import buscar_media, parsear_comando, texto_de

DUENO = "5491111111111"
OTRO = "5492222222222"


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


def test_al_desvincularse_se_reinicia_y_borra_la_sesion_vieja(tmp_path):
    sesion = tmp_path / "sesion.sqlite3"
    sesion.write_bytes(b"vieja")
    (tmp_path / "sesion.sqlite3-wal").write_bytes(b"wal")
    bot, cliente = crear_bot()
    bot.config = dataclasses.replace(bot.config, archivo_sesion=sesion)

    async def correr():
        tarea = asyncio.create_task(bot.ejecutar())
        await asyncio.sleep(0.01)
        await bot._al_cerrar_sesion(cliente, LoggedOutEv(Reason="LOGGED_OUT"))
        return await tarea

    assert asyncio.run(correr()) == SALIDA_REINICIAR
    assert sesion.exists()  # todavía en uso: se borra al próximo inicio
    assert borrar_sesion_cerrada(sesion)
    assert list(tmp_path.iterdir()) == []
    assert not borrar_sesion_cerrada(sesion)  # sin marca no toca nada


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
    assert "dado" not in nombres  # _plantilla.py no se carga
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
