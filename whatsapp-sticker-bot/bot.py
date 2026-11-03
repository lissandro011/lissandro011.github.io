"""Licha.bot: bot de WhatsApp que convierte imágenes y videos en stickers.

    python bot.py

Si no hay una sesión guardada, pide un código de vinculación (pair code) para
el número de WA_PHONE_NUMBER y lo muestra en el log. Después la sesión queda en
el SQLite de WA_SESSION_DB y no hace falta volver a vincular.

Códigos de salida: 0 = detenido normalmente, 1 = error, 2 = hace falta vincular
el número (sin sesión y sin WA_PHONE_NUMBER, código vencido o sesión cerrada
desde el teléfono).
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sqlite3
import sys
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Literal

from neonize.aioze.client import NewAClient
from neonize.aioze.events import ConnectedEv, DisconnectedEv, LoggedOutEv, MessageEv, PairStatusEv
from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import DeviceProps
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message
from neonize.utils import log as neonize_log
from neonize.utils.enum import ClientName

import sticker
from config import Config, ConfigError, load_config

log = logging.getLogger("licha.bot")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NEEDS_PAIRING = 2

GENERIC_ERROR = "No pude crear el sticker 😕 Probá de nuevo o con otro archivo."
VIEW_ONCE_ERROR = "No hago stickers de fotos o videos de “ver una vez”."

# Chats en los que respondemos: privados (número o LID) y grupos. Se ignoran
# estados (status@broadcast), listas de difusión y canales.
ALLOWED_SERVERS = frozenset({"s.whatsapp.net", "lid", "g.us"})
VIEW_ONCE_WRAPPERS = ("viewOnceMessage", "viewOnceMessageV2", "viewOnceMessageV2Extension")
OTHER_WRAPPERS = ("ephemeralMessage", "documentWithCaptionMessage")


# --------------------------------------------------------------------------- #
# Interpretación de mensajes (sin red: se prueba en tests/test_bot.py)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class StickerRequest:
    kind: Literal["image", "video"]
    media: Message  # mensaje con solo la media, listo para client.download_any()
    seconds: int  # duración informada por WhatsApp (0 en imágenes)
    file_length: int


@dataclass(frozen=True)
class Reject:
    """El comando llegó pero no se puede atender: se responde `reason`."""

    reason: str


def usage_text(command: str, max_seconds: float) -> str:
    return (
        f"Mandá una imagen o un video/GIF de hasta {max_seconds:g} s con el texto {command}, "
        f"o respondé a uno con {command}."
    )


def command_text(msg: Message) -> str:
    """Texto que acompaña al mensaje: caption de la media o texto plano."""
    if msg.HasField("imageMessage"):
        return msg.imageMessage.caption
    if msg.HasField("videoMessage"):
        return msg.videoMessage.caption
    if msg.conversation:
        return msg.conversation
    if msg.HasField("extendedTextMessage"):
        return msg.extendedTextMessage.text
    return ""


def unwrap(msg: Message) -> tuple[Message, bool]:
    """Saca envoltorios (efímero, ver una vez, ...). Devuelve (mensaje, era_ver_una_vez)."""
    view_once = False
    for _ in range(5):  # los envoltorios pueden anidarse, pero no indefinidamente
        for field in VIEW_ONCE_WRAPPERS + OTHER_WRAPPERS:
            if msg.HasField(field):
                view_once = view_once or field in VIEW_ONCE_WRAPPERS
                msg = getattr(msg, field).message
                break
        else:
            break
    return msg, view_once


def media_request(msg: Message) -> StickerRequest | None:
    if msg.HasField("imageMessage"):
        img = msg.imageMessage
        return StickerRequest("image", Message(imageMessage=img), 0, img.fileLength)
    if msg.HasField("videoMessage"):
        vid = msg.videoMessage
        return StickerRequest("video", Message(videoMessage=vid), vid.seconds, vid.fileLength)
    return None


def parse_request(ev: MessageEv, command: str, usage: str) -> StickerRequest | Reject | None:
    """Decide qué hacer con un mensaje entrante.

    None -> ignorarlo; Reject -> responder un aviso; StickerRequest -> convertir.
    """
    source = ev.Info.MessageSource
    if source.IsFromMe or source.Chat.Server not in ALLOWED_SERVERS:
        return None

    msg = ev.Message  # neonize/whatsmeow ya le sacan los envoltorios al mensaje principal
    if command_text(msg).strip().lower() != command.lower():
        return None

    if ev.IsViewOnce or ev.IsViewOnceV2 or ev.IsViewOnceV2Extension:
        return Reject(VIEW_ONCE_ERROR)

    direct = media_request(msg)
    if direct is not None:
        if direct.media.imageMessage.viewOnce or direct.media.videoMessage.viewOnce:
            return Reject(VIEW_ONCE_ERROR)
        return direct

    if msg.HasField("extendedTextMessage"):
        context = msg.extendedTextMessage.contextInfo
        if context.HasField("quotedMessage"):
            quoted, view_once = unwrap(context.quotedMessage)
            if view_once:
                return Reject(VIEW_ONCE_ERROR)
            request = media_request(quoted)
            if request is not None:
                return request

    return Reject(usage)


def session_exists(path: Path) -> bool:
    """True si el SQLite ya tiene un dispositivo vinculado (tabla de whatsmeow)."""
    if not path.exists():
        return False
    try:
        # as_uri() arma una URI válida también en Windows (file:///C:/...) y con espacios.
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
            return db.execute("SELECT COUNT(*) FROM whatsmeow_device").fetchone()[0] > 0
    except sqlite3.Error:
        return False


def jid_str(jid: Any) -> str:
    return f"{jid.User}@{jid.Server}" if jid.User else jid.Server


# --------------------------------------------------------------------------- #
# Bot
# --------------------------------------------------------------------------- #


class StickerBot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.opts = cfg.sticker_options()
        self.usage = usage_text(cfg.command, cfg.max_video_seconds)
        # El nombre del cliente es la ruta del SQLite donde neonize guarda la sesión.
        # `os` es el nombre que aparece en "Dispositivos vinculados" del teléfono.
        self.client = NewAClient(
            # Con barras "/" (C:/...): es la forma de ruta que documenta SQLite en Windows.
            cfg.session_db.as_posix(),
            props=DeviceProps(os="Licha.bot", platformType=DeviceProps.CHROME),
        )
        self.exit_code = EXIT_OK
        self._semaphore = asyncio.Semaphore(cfg.max_concurrent)
        self._paired = asyncio.Event()
        self._pair_requested = False
        self._stopping = False
        self._tasks: set[asyncio.Task[Any]] = set()

        self.client.event(ConnectedEv)(self.on_connected)
        self.client.event(PairStatusEv)(self.on_pair_status)
        self.client.event(LoggedOutEv)(self.on_logged_out)
        self.client.event(DisconnectedEv)(self.on_disconnected)
        self.client.event(MessageEv)(self.on_message)
        self.client.qr(self.on_qr)

    # -- ciclo de vida ------------------------------------------------------ #

    async def run(self) -> int:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._spawn_shutdown, sig)
            except (NotImplementedError, RuntimeError):  # Windows
                pass

        if session_exists(self.cfg.session_db):
            log.info("Sesión encontrada en %s; conectando…", self.cfg.session_db)
        elif self.cfg.phone:
            log.info("No hay sesión guardada: se va a pedir un código de vinculación para %s", self.cfg.phone)
        else:
            log.error(
                "No hay sesión guardada en %s. Definí WA_PHONE_NUMBER (ej. 5491123456789) "
                "para vincular el número con un código.",
                self.cfg.session_db,
            )
            return EXIT_NEEDS_PAIRING

        await self.client.connect()
        try:
            await self.client.idle()  # vuelve cuando se llama a client.stop()
        except Exception:
            log.exception("La conexión con WhatsApp terminó con un error")
            return EXIT_ERROR
        return self.exit_code

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _spawn_shutdown(self, sig: signal.Signals) -> None:
        log.info("Recibí %s; cerrando…", sig.name)
        self._spawn(self.shutdown(EXIT_OK))

    async def shutdown(self, code: int) -> None:
        if self._stopping:
            return
        self._stopping = True
        self.exit_code = code
        try:
            await self.client.stop()
        except Exception:
            log.exception("Error al detener el cliente")

    # -- vinculación -------------------------------------------------------- #

    async def on_qr(self, client: NewAClient, _qr: bytes) -> None:
        # neonize solo emite un QR cuando no hay sesión guardada. No lo mostramos:
        # pedimos un código de vinculación (el QR se renueva cada ~20 s, pedimos uno solo).
        if self._pair_requested:
            return
        self._pair_requested = True
        if not self.cfg.phone:
            log.error("Hace falta vincular el número pero WA_PHONE_NUMBER no está definido.")
            await self.shutdown(EXIT_NEEDS_PAIRING)
            return
        try:
            code = await client.PairPhone(self.cfg.phone, show_push_notification=True, client_name=ClientName.LINUX)
        except Exception:
            log.exception("No se pudo pedir el código de vinculación para %s", self.cfg.phone)
            await self.shutdown(EXIT_NEEDS_PAIRING)
            return
        log.warning(
            "\n\n    CÓDIGO DE VINCULACIÓN:  %s\n\n"
            "    En el teléfono: WhatsApp > Dispositivos vinculados > Vincular un dispositivo >\n"
            "    Vincular con el número de teléfono, e ingresá el código. Vence en ~2 minutos.\n",
            code,
        )
        self._spawn(self._pair_watchdog())

    async def _pair_watchdog(self) -> None:
        try:
            await asyncio.wait_for(self._paired.wait(), timeout=self.cfg.pair_timeout)
        except asyncio.TimeoutError:
            log.error("El código de vinculación venció sin usarse. Volvé a ejecutar el bot para pedir otro.")
            await self.shutdown(EXIT_NEEDS_PAIRING)

    async def on_pair_status(self, _: NewAClient, ev: PairStatusEv) -> None:
        if ev.Status == PairStatusEv.SUCCESS:
            self._paired.set()
            log.info("¡Número vinculado! (%s). La sesión quedó guardada en %s", ev.ID.User, self.cfg.session_db)
        else:
            log.error("Falló la vinculación: %s", ev.Error)

    async def on_connected(self, _: NewAClient, __: ConnectedEv) -> None:
        self._paired.set()
        log.info("Conectado a WhatsApp. Esperando %s…", self.cfg.command)

    async def on_disconnected(self, _: NewAClient, __: DisconnectedEv) -> None:
        if not self._stopping:
            log.warning("Se cortó la conexión con WhatsApp; neonize reintenta solo.")

    async def on_logged_out(self, _: NewAClient, ev: LoggedOutEv) -> None:
        reason = LoggedOutEv.DESCRIPTOR.fields_by_name["Reason"].enum_type.values_by_number.get(ev.Reason)
        log.error(
            "WhatsApp cerró la sesión (%s): el dispositivo se desvinculó. Hay que volver a vincular.",
            reason.name if reason else ev.Reason,
        )
        await self.shutdown(EXIT_NEEDS_PAIRING)

    # -- stickers ----------------------------------------------------------- #

    async def on_message(self, _: NewAClient, ev: MessageEv) -> None:
        try:
            request = parse_request(ev, self.cfg.command, self.usage)
        except Exception:
            log.exception("No pude interpretar el mensaje %s", ev.Info.ID)
            return
        if request is None:
            return
        if isinstance(request, Reject):
            await self._reply(ev, request.reason)
            return
        async with self._semaphore:
            await self._make_and_send(ev, request)

    async def _make_and_send(self, ev: MessageEv, request: StickerRequest) -> None:
        msg_id = ev.Info.ID
        chat = ev.Info.MessageSource.Chat
        log.info("Pedido %s: sticker de %s en %s", msg_id, request.kind, jid_str(chat))
        started = time.monotonic()
        try:
            data = await self._download(request)
            convert = sticker.image_to_sticker if request.kind == "image" else sticker.video_to_sticker
            webp = await asyncio.to_thread(convert, data, self.opts)
            # passthrough=True: el WebP ya está listo (tamaño, EXIF, marca); neonize solo lo sube.
            await self.client.send_sticker(chat, webp, quoted=ev, passthrough=True)
        except sticker.StickerError as exc:
            log.warning("Pedido %s rechazado: %s", msg_id, exc)
            await self._reply(ev, exc.user_message)
        except Exception:
            log.exception("Pedido %s: error inesperado creando el sticker", msg_id)
            await self._reply(ev, GENERIC_ERROR)
        else:
            elapsed = time.monotonic() - started
            log.info("Pedido %s: sticker enviado (%.0f KB, %.1f s)", msg_id, len(webp) / 1024, elapsed)

    async def _download(self, request: StickerRequest) -> bytes:
        max_bytes = self.cfg.max_download_mb * 1024 * 1024
        if request.file_length > max_bytes:
            raise sticker.StickerError(
                f"El archivo es muy pesado (máx. {self.cfg.max_download_mb} MB).",
                f"archivo de {request.file_length} bytes",
            )
        if request.kind == "video" and request.seconds > self.opts.max_video_seconds:
            raise sticker.StickerError(
                f"El video dura {request.seconds} s; el máximo es {self.opts.max_video_seconds:g} s.",
                f"video de {request.seconds}s rechazado antes de descargar",
            )
        try:
            data = await self.client.download_any(request.media)
        except Exception as exc:
            raise sticker.StickerError(
                "No pude descargar el archivo (puede que ya no esté disponible).",
                f"download_any falló: {exc!r}",
            ) from exc
        if not data:
            raise sticker.StickerError("No pude descargar el archivo.", "la descarga vino vacía")
        return data

    async def _reply(self, ev: MessageEv, text: str) -> None:
        try:
            await self.client.reply_message(text, ev)
        except Exception:
            log.exception("No pude responder al mensaje %s", ev.Info.ID)


# --------------------------------------------------------------------------- #


def setup_logging(cfg: Config) -> None:
    handlers: list[logging.Handler] = []
    if sys.stderr is not None:  # con pythonw.exe no hay consola
        handlers.append(logging.StreamHandler())
    if cfg.log_file is not None:
        # Útil cuando no hay consola (tarea programada de Windows): rota a los 5 MB.
        cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(cfg.log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"))
    # neonize configura el logging raíz al importarse; lo reemplazamos (force=True).
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers or [logging.NullHandler()],
        force=True,
    )
    # Este nivel también define qué manda el core en Go (whatsmeow) al log.
    neonize_log.setLevel(cfg.neonize_log_level)
    for name in ("neonize", "whatsmeow", "Whatsmeow"):
        logging.getLogger(name).setLevel(cfg.neonize_log_level)
    log.setLevel(cfg.log_level)
    logging.getLogger("sticker").setLevel(cfg.log_level)


def main() -> int:
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        try:
            load_dotenv(Path(__file__).resolve().with_name(".env"))  # no pisa variables ya definidas
        except OSError as exc:  # p. ej. .env sin permiso de lectura (systemd ya lo cargó como root)
            print(f"Aviso: no pude leer .env ({exc}); uso solo las variables de entorno.", file=sys.stderr)

    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return EXIT_ERROR

    setup_logging(cfg)
    problem = sticker.ffmpeg_problem()
    if problem:
        log.warning("ffmpeg: %s. Los stickers de imágenes andan, pero los de video van a fallar.", problem)
    cfg.session_db.parent.mkdir(parents=True, exist_ok=True)
    try:
        return asyncio.run(StickerBot(cfg).run())
    except KeyboardInterrupt:
        # En Windows no hay manejadores de señales en asyncio: Ctrl+C llega como excepción.
        log.info("Detenido con Ctrl+C.")
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
