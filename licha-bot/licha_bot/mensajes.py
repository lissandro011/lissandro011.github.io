"""Lectura de mensajes de WhatsApp: texto, comandos, fotos, videos y respuestas.

Son funciones puras sobre los protobufs de neonize (no usan la red), así que
se pueden probar sin conectarse a WhatsApp.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import ContextInfo, Message

ENVOLTORIOS_VER_UNA_VEZ = ("viewOnceMessage", "viewOnceMessageV2", "viewOnceMessageV2Extension")
OTROS_ENVOLTORIOS = ("ephemeralMessage", "documentWithCaptionMessage")
CAMPOS_CON_CONTEXTO = ("extendedTextMessage", "imageMessage", "videoMessage", "stickerMessage", "documentMessage")

TipoMedia = Literal["imagen", "video", "sticker", "documento"]


@dataclass(frozen=True)
class Media:
    """Una foto, video, GIF, sticker o documento con imagen/video adentro."""

    tipo: TipoMedia
    mensaje: Message  # mensaje con solo la media, listo para descargar
    mimetype: str
    tamano: int  # bytes, según WhatsApp
    segundos: int = 0  # duración (solo videos)
    animado: bool = False  # videos, GIFs y stickers animados
    citada: bool = False  # True si vino del mensaje al que se respondió
    ver_una_vez: bool = False


def desenvolver(msg: Message) -> tuple[Message, bool]:
    """Saca envoltorios (efímero, ver una vez, ...). Devuelve (mensaje, era_ver_una_vez)."""
    ver_una_vez = False
    for _ in range(5):  # los envoltorios se pueden anidar, pero no infinitamente
        for campo in ENVOLTORIOS_VER_UNA_VEZ + OTROS_ENVOLTORIOS:
            if msg.HasField(campo):
                ver_una_vez = ver_una_vez or campo in ENVOLTORIOS_VER_UNA_VEZ
                msg = getattr(msg, campo).message
                break
        else:
            break
    return msg, ver_una_vez


def texto_de(msg: Message) -> str:
    """Texto del mensaje: el texto plano o el pie de foto/video/documento."""
    msg, _ = desenvolver(msg)
    if msg.conversation:
        return msg.conversation
    if msg.HasField("extendedTextMessage"):
        return msg.extendedTextMessage.text
    for campo in ("imageMessage", "videoMessage", "documentMessage"):
        if msg.HasField(campo):
            return getattr(msg, campo).caption
    return ""


def parsear_comando(texto: str, prefijos: tuple[str, ...]) -> tuple[str, str, str] | None:
    """'!sticker Mi pack' -> ('!', 'sticker', 'Mi pack'). None si no es un comando."""
    texto = texto.strip()
    for prefijo in sorted(prefijos, key=len, reverse=True):
        if not texto.startswith(prefijo):
            continue
        resto = texto[len(prefijo) :]
        if not resto or resto[0].isspace():
            return None  # "!" solo o "! algo" no son comandos
        partes = resto.split(maxsplit=1)
        return prefijo, partes[0], partes[1].strip() if len(partes) > 1 else ""
    return None


def media_de(msg: Message, *, citada: bool = False) -> Media | None:
    """La media que trae el mensaje (sin mirar respuestas), o None."""
    msg, ver_una_vez = desenvolver(msg)
    if msg.HasField("imageMessage"):
        m = msg.imageMessage
        return Media(
            "imagen", Message(imageMessage=m), m.mimetype, m.fileLength,
            citada=citada, ver_una_vez=ver_una_vez or m.viewOnce,
        )  # fmt: skip
    if msg.HasField("videoMessage"):
        m = msg.videoMessage
        return Media(
            "video", Message(videoMessage=m), m.mimetype, m.fileLength, m.seconds, animado=True,
            citada=citada, ver_una_vez=ver_una_vez or m.viewOnce,
        )  # fmt: skip
    if msg.HasField("stickerMessage"):
        m = msg.stickerMessage
        return Media(
            "sticker", Message(stickerMessage=m), m.mimetype or "image/webp", m.fileLength,
            animado=m.isAnimated, citada=citada,
        )  # fmt: skip
    if msg.HasField("documentMessage"):
        m = msg.documentMessage
        mime = m.mimetype.lower()
        if mime.startswith(("image/", "video/")):  # fotos mandadas "como documento"
            return Media(
                "documento", Message(documentMessage=m), mime, m.fileLength,
                animado=mime.startswith("video/") or mime == "image/gif", citada=citada,
            )  # fmt: skip
    return None


def contexto_de(msg: Message) -> ContextInfo | None:
    """Datos de respuesta/mención del mensaje (si los tiene)."""
    msg, _ = desenvolver(msg)
    for campo in CAMPOS_CON_CONTEXTO:
        if msg.HasField(campo):
            sub = getattr(msg, campo)
            return sub.contextInfo if sub.HasField("contextInfo") else None
    return None


def mensaje_citado(msg: Message) -> Message | None:
    """El mensaje al que se respondió, o None si no es una respuesta."""
    contexto = contexto_de(msg)
    if contexto is not None and contexto.HasField("quotedMessage"):
        return contexto.quotedMessage
    return None


def buscar_media(msg: Message) -> Media | None:
    """Media del mensaje o, si no trae, la del mensaje al que se respondió."""
    propia = media_de(msg)
    if propia is not None:
        return propia
    citado = mensaje_citado(msg)
    return media_de(citado, citada=True) if citado is not None else None


def numero_de(jid) -> str | None:
    """Número de teléfono de un JID de WhatsApp ('54911...@s.whatsapp.net'), o None."""
    if jid is not None and jid.Server == "s.whatsapp.net" and jid.User:
        return jid.User
    return None


def jid_a_texto(jid) -> str:
    return f"{jid.User}@{jid.Server}" if jid.User else jid.Server
