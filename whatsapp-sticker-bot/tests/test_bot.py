"""Pruebas del bot sin conectarse a WhatsApp.

Se arman eventos con los protobufs reales de neonize y se reemplaza el cliente
por uno falso que registra qué se envió.
"""

import asyncio
import io
import sqlite3
from pathlib import Path

import pytest
from neonize.aioze.events import MessageEv
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    ContextInfo,
    ExtendedTextMessage,
    FutureProofMessage,
    ImageMessage,
    Message,
    VideoMessage,
)
from PIL import Image

import bot
from bot import VIEW_ONCE_ERROR, Reject, StickerRequest, parse_request
from config import ConfigError, load_config, normalize_phone

CMD = ".sticker"
USAGE = bot.usage_text(CMD, 10)


def image(caption="", **kw) -> Message:
    return Message(imageMessage=ImageMessage(caption=caption, mediaKey=b"k" * 32, directPath="/img", **kw))


def video(caption="", seconds=5, **kw) -> Message:
    return Message(videoMessage=VideoMessage(caption=caption, seconds=seconds, mediaKey=b"v" * 32, **kw))


def reply(text: str, quoted: Message) -> Message:
    return Message(
        extendedTextMessage=ExtendedTextMessage(
            text=text, contextInfo=ContextInfo(stanzaID="Q1", quotedMessage=quoted)
        )
    )


def event(message: Message, *, from_me=False, server="s.whatsapp.net", view_once=False) -> MessageEv:
    ev = MessageEv()
    ev.Info.ID = "MSG1"
    ev.Info.MessageSource.Chat.User = "5491100000000" if server != "broadcast" else "status"
    ev.Info.MessageSource.Chat.Server = server
    ev.Info.MessageSource.Sender.User = "5491100000000"
    ev.Info.MessageSource.Sender.Server = "s.whatsapp.net"
    ev.Info.MessageSource.IsFromMe = from_me
    ev.Info.MessageSource.IsGroup = server == "g.us"
    ev.IsViewOnce = view_once
    ev.Message.CopyFrom(message)
    return ev


def parse(ev):
    return parse_request(ev, CMD, USAGE)


# --------------------------------------------------------------------------- #
# Interpretación de mensajes
# --------------------------------------------------------------------------- #


def test_imagen_con_caption():
    req = parse(event(image(".sticker")))
    assert isinstance(req, StickerRequest) and req.kind == "image"
    assert req.media.imageMessage.mediaKey == b"k" * 32


@pytest.mark.parametrize("caption", [".STICKER", "  .Sticker \n"])
def test_comando_sin_importar_mayusculas_ni_espacios(caption):
    assert isinstance(parse(event(image(caption))), StickerRequest)


@pytest.mark.parametrize("caption", ["", "hola", ".sticker2", "haceme un .sticker", ".s"])
def test_ignora_lo_que_no_es_el_comando(caption):
    assert parse(event(image(caption))) is None
    assert parse(event(Message(conversation=caption))) is None


def test_ignora_mensajes_propios():
    assert parse(event(image(".sticker"), from_me=True)) is None


def test_ignora_estados():
    assert parse(event(image(".sticker"), server="broadcast")) is None


def test_funciona_en_grupos():
    assert isinstance(parse(event(image(".sticker"), server="g.us")), StickerRequest)


def test_video_con_caption():
    req = parse(event(video(".sticker", seconds=7, gifPlayback=True)))
    assert isinstance(req, StickerRequest) and req.kind == "video" and req.seconds == 7


def test_respuesta_a_una_imagen():
    req = parse(event(reply(".sticker", image("una foto"))))
    assert isinstance(req, StickerRequest) and req.kind == "image"
    assert req.media.imageMessage.directPath == "/img"


def test_respuesta_a_un_video_en_chat_temporal():
    quoted = Message(ephemeralMessage=FutureProofMessage(message=video(seconds=3)))
    req = parse(event(reply(".sticker", quoted)))
    assert isinstance(req, StickerRequest) and req.kind == "video"


def test_respuesta_a_ver_una_vez_se_rechaza():
    quoted = Message(viewOnceMessageV2=FutureProofMessage(message=image()))
    assert parse(event(reply(".sticker", quoted))) == Reject(VIEW_ONCE_ERROR)


def test_media_de_ver_una_vez_se_rechaza():
    assert parse(event(image(".sticker"), view_once=True)) == Reject(VIEW_ONCE_ERROR)


def test_comando_sin_media_responde_como_usarlo():
    assert parse(event(Message(conversation=".sticker"))) == Reject(USAGE)
    assert parse(event(reply(".sticker", Message(conversation="texto")))) == Reject(USAGE)


def test_la_media_se_copia_y_no_depende_del_evento():
    # neonize borra el contextInfo del evento al citarlo: el pedido no debe romperse.
    ev = event(reply(".sticker", image()))
    req = parse(ev)
    ev.Message.extendedTextMessage.contextInfo.Clear()
    assert req.media.imageMessage.mediaKey == b"k" * 32


def test_session_exists(tmp_path):
    db = tmp_path / "s.sqlite3"
    assert not bot.session_exists(db)
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE whatsmeow_device (jid TEXT)")
    assert not bot.session_exists(db)
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO whatsmeow_device VALUES ('549@s.whatsapp.net')")
    assert bot.session_exists(db)


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #


def test_config_por_defecto():
    cfg = load_config({})
    assert cfg.phone is None and cfg.command == ".sticker"
    assert cfg.session_db == Path(bot.__file__).resolve().parent / "data" / "session.sqlite3"
    opts = cfg.sticker_options()
    assert (opts.pack_name, opts.watermark) == ("Licha.bot", "Licha.bot")
    assert (opts.image_max_bytes, opts.animated_max_bytes) == (100 * 1024, 500 * 1024)


def test_config_personalizada(tmp_path):
    cfg = load_config(
        {
            "WA_PHONE_NUMBER": "+54 9 11 2345-6789",
            "WA_SESSION_DB": str(tmp_path / "x.db"),
            "STICKER_WATERMARK": "",
            "STICKER_MAX_VIDEO_SECONDS": "6",
            "LOG_LEVEL": "debug",
        }
    )
    assert cfg.phone == "5491123456789"
    assert cfg.session_db == tmp_path / "x.db"
    assert cfg.watermark == "" and cfg.max_video_seconds == 6 and cfg.log_level == "DEBUG"


@pytest.mark.parametrize(
    "env",
    [
        {"WA_PHONE_NUMBER": "abc"},
        {"WA_PHONE_NUMBER": "123"},
        {"MAX_DOWNLOAD_MB": "mucho"},
        {"MAX_CONCURRENT_CONVERSIONS": "0"},
        {"LOG_LEVEL": "VERBOSE"},
        {"STICKER_COMMAND": ".hacer sticker"},
    ],
)
def test_config_invalida(env):
    with pytest.raises(ConfigError):
        load_config(env)


def test_normalize_phone():
    assert normalize_phone("(549) 11-2345.6789") == "5491123456789"


# --------------------------------------------------------------------------- #
# Flujo completo del handler con un cliente falso
# --------------------------------------------------------------------------- #


class FakeClient:
    def __init__(self, media: bytes = b"", fail_download: bool = False):
        self.media = media
        self.fail_download = fail_download
        self.downloads: list[Message] = []
        self.stickers: list[dict] = []
        self.replies: list[str] = []

    async def download_any(self, message):
        self.downloads.append(message)
        if self.fail_download:
            raise RuntimeError("media expired")
        return self.media

    async def send_sticker(self, to, file, quoted=None, passthrough=False, **kw):
        self.stickers.append({"to": to, "file": file, "quoted": quoted, "passthrough": passthrough})

    async def reply_message(self, text, quoted, **kw):
        self.replies.append(text)


def make_bot(tmp_path, fake: FakeClient) -> bot.StickerBot:
    cfg = load_config({"WA_SESSION_DB": str(tmp_path / "s.sqlite3")})
    b = bot.StickerBot(cfg)
    b.client = fake
    return b


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), (255, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


def test_handler_convierte_y_responde_con_sticker(tmp_path):
    fake = FakeClient(media=png_bytes())
    b = make_bot(tmp_path, fake)
    ev = event(reply(".sticker", image()))
    asyncio.run(b.on_message(None, ev))

    assert fake.replies == []
    assert len(fake.stickers) == 1
    sent = fake.stickers[0]
    assert sent["passthrough"] is True and sent["quoted"] is ev
    assert sent["to"].User == "5491100000000"
    assert fake.downloads[0].HasField("imageMessage")
    with Image.open(io.BytesIO(sent["file"])) as img:
        assert img.format == "WEBP" and img.size == (512, 512)


def test_handler_error_de_descarga_responde_corto(tmp_path, caplog):
    fake = FakeClient(fail_download=True)
    asyncio.run(make_bot(tmp_path, fake).on_message(None, event(image(".sticker"))))
    assert fake.stickers == []
    assert fake.replies == ["No pude descargar el archivo (puede que ya no esté disponible)."]
    assert "media expired" in caplog.text  # el detalle queda en el log


def test_handler_archivo_roto_responde_corto(tmp_path):
    fake = FakeClient(media=b"no es una imagen")
    asyncio.run(make_bot(tmp_path, fake).on_message(None, event(image(".sticker"))))
    assert fake.replies == ["No pude leer la imagen."]


def test_handler_video_largo_no_se_descarga(tmp_path):
    fake = FakeClient()
    asyncio.run(make_bot(tmp_path, fake).on_message(None, event(video(".sticker", seconds=30))))
    assert fake.downloads == []
    assert fake.replies == ["El video dura 30 s; el máximo es 10 s."]


def test_handler_archivo_pesado_no_se_descarga(tmp_path):
    fake = FakeClient()
    ev = event(image(".sticker", fileLength=200 * 1024 * 1024))
    asyncio.run(make_bot(tmp_path, fake).on_message(None, ev))
    assert fake.downloads == []
    assert fake.replies == ["El archivo es muy pesado (máx. 25 MB)."]


def test_handler_error_inesperado_responde_generico(tmp_path, monkeypatch, caplog):
    fake = FakeClient(media=png_bytes())

    def boom(*_):
        raise RuntimeError("detalle interno")

    monkeypatch.setattr(bot.sticker, "image_to_sticker", boom)
    asyncio.run(make_bot(tmp_path, fake).on_message(None, event(image(".sticker"))))
    assert fake.replies == [bot.GENERIC_ERROR]
    assert "detalle interno" in caplog.text


def test_handler_ignora_mensajes_que_no_son_comando(tmp_path):
    fake = FakeClient(media=png_bytes())
    b = make_bot(tmp_path, fake)
    asyncio.run(b.on_message(None, event(image("linda foto"))))
    asyncio.run(b.on_message(None, event(image(".sticker"), from_me=True)))
    assert fake.downloads == fake.stickers == fake.replies == []


def test_handler_responde_uso_sin_media(tmp_path):
    fake = FakeClient()
    asyncio.run(make_bot(tmp_path, fake).on_message(None, event(Message(conversation=".sticker"))))
    assert fake.replies == [USAGE]


def test_run_sin_sesion_ni_telefono_pide_vincular(tmp_path):
    b = make_bot(tmp_path, FakeClient())
    assert asyncio.run(b.run()) == bot.EXIT_NEEDS_PAIRING


# --------------------------------------------------------------------------- #
# Vinculación con código (pair code)
# --------------------------------------------------------------------------- #


class FakePairClient(FakeClient):
    def __init__(self):
        super().__init__()
        self.pair_calls: list[tuple] = []
        self.stopped = 0

    async def PairPhone(self, phone, show_push_notification, client_name=None, client_type=None):
        self.pair_calls.append((phone, show_push_notification))
        return "ABCD-EFGH"

    async def stop(self):
        self.stopped += 1


def make_pair_bot(tmp_path, phone="5491123456789", timeout=0.2):
    from dataclasses import replace

    env = {"WA_SESSION_DB": str(tmp_path / "s.sqlite3")}
    if phone:
        env["WA_PHONE_NUMBER"] = phone
    b = bot.StickerBot(replace(load_config(env), pair_timeout=timeout))
    fake = FakePairClient()
    b.client = fake
    return b, fake


def test_qr_pide_un_solo_codigo_y_lo_muestra(tmp_path, caplog):
    b, fake = make_pair_bot(tmp_path, timeout=5)

    async def scenario():
        await b.on_qr(fake, b"qr1")
        await b.on_qr(fake, b"qr2")  # el QR rota: no se vuelve a pedir código
        b._paired.set()  # simula que el usuario ingresó el código
        await asyncio.sleep(0.05)

    asyncio.run(scenario())
    assert fake.pair_calls == [("5491123456789", True)]
    assert "ABCD-EFGH" in caplog.text
    assert fake.stopped == 0 and b.exit_code == bot.EXIT_OK


def test_codigo_vencido_detiene_con_codigo_2(tmp_path, caplog):
    b, fake = make_pair_bot(tmp_path, timeout=0.1)

    async def scenario():
        await b.on_qr(fake, b"qr")
        await asyncio.sleep(0.3)

    asyncio.run(scenario())
    assert fake.stopped == 1 and b.exit_code == bot.EXIT_NEEDS_PAIRING
    assert "venció" in caplog.text


def test_qr_sin_telefono_detiene_sin_pedir_codigo(tmp_path):
    b, fake = make_pair_bot(tmp_path, phone=None)
    asyncio.run(b.on_qr(fake, b"qr"))
    assert fake.pair_calls == [] and fake.stopped == 1
    assert b.exit_code == bot.EXIT_NEEDS_PAIRING


def test_vinculacion_exitosa_marca_como_vinculado(tmp_path):
    from neonize.aioze.events import PairStatusEv

    b, fake = make_pair_bot(tmp_path)
    ev = PairStatusEv(Status=PairStatusEv.SUCCESS)
    ev.ID.User = "5491123456789"
    asyncio.run(b.on_pair_status(fake, ev))
    assert b._paired.is_set()


def test_sesion_cerrada_desde_el_telefono(tmp_path, caplog):
    from neonize.aioze.events import LoggedOutEv

    b, fake = make_pair_bot(tmp_path)
    reason = LoggedOutEv.DESCRIPTOR.fields_by_name["Reason"].enum_type.values_by_name["LOGGED_OUT"].number
    asyncio.run(b.on_logged_out(fake, LoggedOutEv(Reason=reason)))
    assert fake.stopped == 1 and b.exit_code == bot.EXIT_NEEDS_PAIRING
    assert "LOGGED_OUT" in caplog.text
