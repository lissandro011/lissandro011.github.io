"""El `ctx` que recibe cada comando: quién escribió, qué mandó y cómo responder."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from neonize.aioze.events import MessageEv
from neonize.proto.Neonize_pb2 import JID
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    ContextInfo,
    ExtendedTextMessage,
    ImageMessage,
    Message,
    StickerMessage,
)
from neonize.utils.enum import MediaType
from neonize.utils.jid import Jid2String, JIDToNonAD, jid_is_lid

from . import conversor
from .errores import ErrorUsuario
from .frases import completar
from .mensajes import Media, buscar_media, contexto_de, jid_a_texto, numero_de, texto_de

if TYPE_CHECKING:
    from .bot import LichaBot
    from .comandos import Comando

log = logging.getLogger("licha.contexto")

T = TypeVar("T")

VER_UNA_VEZ = "No uso fotos ni videos de “ver una vez”."


def copiar_evento(ev: MessageEv) -> MessageEv:
    """Copia del evento: neonize modifica el mensaje que se cita al responder."""
    copia = MessageEv()
    copia.CopyFrom(ev)
    return copia


def contexto_de_respuesta(ev: MessageEv) -> ContextInfo:
    """Datos para que un mensaje salga como respuesta (citando) a `ev`."""
    citado = Message()
    citado.CopyFrom(ev.Message)
    # Como hace WhatsApp: el mensaje citado va sin su propia cita adentro.
    for descriptor, valor in citado.ListFields():
        if descriptor.message_type is not None and "contextInfo" in descriptor.message_type.fields_by_name:
            valor.ClearField("contextInfo")
    remitente = ev.Info.MessageSource.Sender
    if jid_is_lid(remitente):
        alternativo = ev.Info.MessageSource.SenderAlt
        if alternativo.User:
            remitente = alternativo
    return ContextInfo(
        stanzaID=ev.Info.ID,
        participant=Jid2String(JIDToNonAD(remitente)),
        quotedMessage=citado,
    )


class Contexto:
    """Todo lo que un comando necesita.

    Datos del mensaje:
        ctx.texto        texto completo del mensaje
        ctx.comando      nombre del comando usado (por ejemplo "s")
        ctx.args         palabras después del comando, como lista
        ctx.texto_args   todo lo que va después del comando, como texto
        ctx.prefijo      prefijo usado ("!" o ".")
        ctx.nombre       nombre de quien escribió (como lo tiene en su WhatsApp)
        ctx.numero       su número de teléfono, si WhatsApp lo informa
        ctx.es_grupo     True si se escribió en un grupo
        ctx.es_dueno     True si quien escribió está en la lista de dueños
        ctx.persona      identificador de quien escribió (para guardar votos, rachas, etc.)
        ctx.anterior     el comando que esa persona usó justo antes en este chat (o None)
        ctx.citado       ID del mensaje al que respondió (o "")

    Acciones (todas con await):
        ctx.responder("texto")              responde citando el mensaje
        ctx.enviar("texto")                 manda un mensaje sin citar
        ctx.reaccionar("👍")                reacciona al mensaje ("" la quita)
        ctx.responder_mencionando(t, jids)  responde etiquetando a esas personas
        ctx.integrantes()                   integrantes del grupo (sin el bot)
        ctx.es_admin()                      True si quien escribió es admin del grupo

    Frases:
        ctx.frase("banco", FRASES, dato=…)  saca una frase de la bolsa del chat y completa {dato} y {p}
        ctx.enviar_sticker(webp, animado)   manda un sticker
        ctx.enviar_imagen(jpeg, "pie")      manda una foto
        ctx.descargar(media)                baja la foto/video que mandaron
        ctx.en_segundo_plano(funcion, ...)  corre algo pesado sin trabar al bot
    """

    def __init__(
        self,
        bot: LichaBot,
        evento: MessageEv,
        *,
        prefijo: str = "",
        comando: str = "",
        texto_args: str = "",
        info: Comando | None = None,
    ):
        self.bot = bot
        self.cliente = bot.cliente
        self.config = bot.config
        self.evento = evento
        self.mensaje: Message = evento.Message
        self.texto = texto_de(evento.Message)
        self.prefijo = prefijo or bot.config.prefijo
        self.comando = comando
        self.texto_args = texto_args
        self.args = texto_args.split()
        self.info = info

        fuente = evento.Info.MessageSource
        self.chat = fuente.Chat
        self.remitente = fuente.Sender
        self.es_grupo = fuente.IsGroup
        self.nombre = evento.Info.Pushname or "che"
        self.numero = numero_de(fuente.Sender) or numero_de(fuente.SenderAlt)
        self.es_dueno = self.numero is not None and self.numero in bot.config.duenos
        self.persona = jid_a_texto(fuente.Sender)
        self.clave_chat = jid_a_texto(fuente.Chat)
        self.anterior: str | None = None
        contexto = contexto_de(evento.Message)
        self.citado = contexto.stanzaID if contexto is not None else ""

    # -- textos --------------------------------------------------------------- #

    def __repr__(self) -> str:
        return f"<Contexto {self.prefijo}{self.comando} de {self.nombre} en {jid_a_texto(self.chat)}>"

    def uso(self, cmd: Comando | None = None) -> str:
        """Texto de uso del comando, con el prefijo real."""
        cmd = cmd or self.info
        if cmd is None:
            return ""
        texto = cmd.uso or f"{{p}}{cmd.nombre}"
        return texto.replace("{p}", self.prefijo)

    def frase(self, banco: str, opciones: Sequence[str], clave: str | None = None, **datos: Any) -> str:
        """Saca la próxima frase del banco (una bolsa mezclada por chat) y completa {campos} y {p}.

        `clave` cambia de quién es la bolsa (por defecto, del chat).
        """
        plantilla = self.bot.frases.sacar(clave or self.clave_chat, banco, opciones)
        return completar(plantilla, p=self.prefijo, **datos)

    # -- responder -------------------------------------------------------------- #

    async def responder(self, texto: str) -> str:
        """Responde citando el mensaje. Devuelve el ID del mensaje enviado ("" si no se sabe)."""
        respuesta = await self.cliente.reply_message(texto, copiar_evento(self.evento))
        return getattr(respuesta, "ID", "") or ""

    async def enviar(self, texto: str) -> str:
        """Manda un mensaje al chat sin citar. Devuelve el ID del mensaje enviado ("" si no se sabe)."""
        respuesta = await self.cliente.send_message(self.chat, texto)
        return getattr(respuesta, "ID", "") or ""

    async def reaccionar(self, emoji: str) -> None:
        """Reacciona al mensaje con un emoji ("" quita la reacción). Si falla, no pasa nada."""
        try:
            reaccion = await self.cliente.build_reaction(self.chat, self.remitente, self.evento.Info.ID, emoji)
            await self.cliente.send_message(self.chat, reaccion)
        except Exception:
            log.debug("No pude reaccionar con %r", emoji, exc_info=True)

    @staticmethod
    def mencion(jid: JID) -> str:
        """Texto que etiqueta a alguien ("@549..."). Va junto con responder_mencionando."""
        return f"@{jid.User}"

    async def responder_mencionando(self, texto: str, jids: list[JID]) -> str:
        """Responde citando el mensaje y etiquetando a `jids` (usá ctx.mencion(jid) en el texto)."""
        contexto = contexto_de_respuesta(self.evento)
        contexto.mentionedJID.extend(Jid2String(JIDToNonAD(j)) for j in jids)
        mensaje = Message(extendedTextMessage=ExtendedTextMessage(text=texto, contextInfo=contexto))
        respuesta = await self.cliente.send_message(self.chat, mensaje)
        return getattr(respuesta, "ID", "") or ""

    async def _info_grupo(self):
        try:
            return await self.cliente.get_group_info(self.chat)
        except Exception as exc:
            raise ErrorUsuario(
                "No pude ver quiénes están en el grupo 😕 Probá de nuevo en un rato.",
                f"get_group_info falló: {exc!r}",
            ) from exc

    async def es_admin(self) -> bool:
        """True si quien escribió es admin del grupo (False fuera de grupos o si WhatsApp no responde)."""
        if not self.es_grupo:
            return False
        try:
            info = await self.cliente.get_group_info(self.chat)
        except Exception:
            log.debug("No pude leer los admins del grupo", exc_info=True)
            return False
        mios = {self.remitente.User, self.evento.Info.MessageSource.SenderAlt.User} - {""}
        return any(
            (p.IsAdmin or p.IsSuperAdmin) and {p.JID.User, p.LID.User, p.PhoneNumber.User} & mios
            for p in info.Participants
        )

    async def integrantes(self) -> list[JID]:
        """Integrantes del grupo, sin contar al bot. Fuera de un grupo devuelve una lista vacía."""
        if not self.es_grupo:
            return []
        info = await self._info_grupo()
        propios: set[str] = set()
        try:
            yo = await self.cliente.get_me()
            propios = {yo.JID.User, yo.LID.User} - {""}
        except Exception:
            log.debug("No pude saber el número del bot", exc_info=True)
        return [
            p.JID
            for p in info.Participants
            if p.JID.User and not ({p.JID.User, p.LID.User, p.PhoneNumber.User} & propios)
        ]

    async def enviar_sticker(self, webp: bytes, animado: bool = False, citar: bool = True) -> None:
        """Manda un sticker WebP de 512x512 (por ejemplo, el de conversor.crear_sticker)."""
        subida = await self.cliente.upload(webp, MediaType.MediaImage)
        mensaje = Message(
            stickerMessage=StickerMessage(
                URL=subida.url,
                directPath=subida.DirectPath,
                fileEncSHA256=subida.FileEncSHA256,
                fileLength=subida.FileLength,
                fileSHA256=subida.FileSHA256,
                mediaKey=subida.MediaKey,
                mimetype="image/webp",
                width=conversor.LIENZO,
                height=conversor.LIENZO,
                isAnimated=animado,
            )
        )
        if citar:
            mensaje.stickerMessage.contextInfo.CopyFrom(contexto_de_respuesta(self.evento))
        await self.cliente.send_message(self.chat, mensaje)

    async def enviar_imagen(self, imagen: bytes, texto: str = "", citar: bool = True) -> None:
        """Manda una foto (JPEG o PNG) con un texto opcional."""
        miniatura, ancho, alto = await asyncio.to_thread(conversor.miniatura_jpeg, imagen)
        mimetype = "image/png" if imagen.startswith(b"\x89PNG") else "image/jpeg"
        subida = await self.cliente.upload(imagen, MediaType.MediaImage)
        mensaje = Message(
            imageMessage=ImageMessage(
                URL=subida.url,
                directPath=subida.DirectPath,
                fileEncSHA256=subida.FileEncSHA256,
                fileLength=subida.FileLength,
                fileSHA256=subida.FileSHA256,
                mediaKey=subida.MediaKey,
                mimetype=mimetype,
                width=ancho,
                height=alto,
                caption=texto,
                JPEGThumbnail=miniatura,
            )
        )
        if citar:
            mensaje.imageMessage.contextInfo.CopyFrom(contexto_de_respuesta(self.evento))
        await self.cliente.send_message(self.chat, mensaje)

    # -- media ------------------------------------------------------------------ #

    def media(self) -> Media | None:
        """La foto, video, GIF o sticker del mensaje, o del mensaje al que se respondió.

        Lanza ErrorUsuario si es de "ver una vez" (respetamos esa intención).
        """
        if self.evento.IsViewOnce or self.evento.IsViewOnceV2 or self.evento.IsViewOnceV2Extension:
            raise ErrorUsuario(VER_UNA_VEZ)
        media = buscar_media(self.mensaje)
        if media is not None and media.ver_una_vez:
            raise ErrorUsuario(VER_UNA_VEZ)
        return media

    async def descargar(self, media: Media) -> bytes:
        """Descarga la media. Rechaza archivos más pesados que max_mb_descarga."""
        max_mb = self.config.stickers.max_mb_descarga
        if media.tamano > max_mb * 1024 * 1024:
            raise ErrorUsuario(f"El archivo es muy pesado (máximo {max_mb} MB).", f"{media.tamano} bytes")
        try:
            datos = await self.cliente.download_any(media.mensaje)
        except Exception as exc:
            raise ErrorUsuario(
                "No pude descargar el archivo (puede que ya no esté disponible en WhatsApp).",
                f"download_any falló: {exc!r}",
            ) from exc
        if not datos:
            raise ErrorUsuario("No pude descargar el archivo.", "la descarga vino vacía")
        return datos

    async def en_segundo_plano(self, funcion: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Corre una función lenta (convertir un video, por ejemplo) en otro hilo.

        Hay un límite de tareas pesadas a la vez (tareas_pesadas_simultaneas en
        config.toml) para que la PC no se sature si piden muchos stickers juntos.
        """
        async with self.bot.limite_tareas:
            return await asyncio.to_thread(funcion, *args, **kwargs)
