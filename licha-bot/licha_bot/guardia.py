"""Quién puede meter al bot en un grupo.

Con `[grupos] solo_el_dueno_agrega = true` (y al menos un número en `duenos`):

- Si un dueño agrega al bot (o se une desde el celular del bot), queda autorizado.
- Si lo agrega otra persona, el bot avisa en el grupo, le pide permiso al dueño
  por privado con un código y espera `minutos_para_autorizar`:
      !autorizar <código>  → se queda
      !rechazar <código>   → se va
  Si nadie contesta, se va solo.
- En un grupo sin autorizar el bot no le contesta a nadie, salvo a los dueños.
- Los grupos donde el bot ya estaba la primera vez que arranca con esto quedan
  autorizados, para que actualizar no lo saque de ningún lado.

El aviso por privado al dueño:

- El número de `duenos` se busca en WhatsApp (`is_on_whatsapp`) para escribirle al
  JID real. Así funciona igual si WhatsApp usa otra forma del número (por ejemplo,
  los celulares argentinos con y sin el 9) y, si el número no existe, queda avisado
  en el log en vez de fallar en silencio.
- Cada grupo pendiente recuerda si el aviso llegó. Si no llegó (el bot estaba sin
  conexión, el número estaba mal, WhatsApp falló), lo reintenta al conectarse y se
  lo cuenta al dueño en cuanto le escribe, sin que tenga que mirar !grupos.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING

from neonize.proto.Neonize_pb2 import JID

from .almacen import GrupoPendiente
from .mensajes import jid_a_texto, numero_de

if TYPE_CHECKING:
    from .bot import LichaBot

log = logging.getLogger("licha.guardia")

META_INICIADO = "grupos_iniciados"


def jid_de_texto(texto: str) -> JID:
    usuario, _, servidor = texto.partition("@")
    return JID(User=usuario, Server=servidor or "s.whatsapp.net")


class Guardia:
    def __init__(self, bot: LichaBot):
        self.bot = bot
        self._esperas: dict[str, asyncio.Task[None]] = {}
        self._lista = False
        self._propios: set[str] | None = None
        self._jids_duenos: dict[str, JID] = {}  # número de config.toml → JID real en WhatsApp

    # -- estado ------------------------------------------------------------------- #

    @property
    def activa(self) -> bool:
        cfg = self.bot.config
        return cfg.grupos.solo_el_dueno_agrega and bool(cfg.duenos)

    @property
    def lista(self) -> bool:
        """True cuando ya se anotaron los grupos donde el bot estaba antes de esta función."""
        if not self._lista:
            self._lista = self.bot.almacen.meta(META_INICIADO) is not None
        return self._lista

    @property
    def minutos(self) -> float:
        return self.bot.config.grupos.minutos_para_autorizar

    def es_dueno(self, *jids: JID | None) -> bool:
        return any(numero_de(j) in self.bot.config.duenos for j in jids if j is not None and numero_de(j))

    async def _es_el_bot(self, jid: JID | None) -> bool:
        if jid is None or not jid.User:
            return False
        if self._propios is None:
            try:
                yo = await self.bot.cliente.get_me()
                self._propios = {yo.JID.User, yo.LID.User} - {""}
            except Exception:
                log.debug("No pude saber el número del bot", exc_info=True)
                return False
        return jid.User in self._propios

    def permitido(self, chat: str) -> bool:
        """¿El bot puede contestar en este grupo?"""
        almacen = self.bot.almacen
        estado = almacen.estado_grupo(chat)
        if estado == "autorizado":
            return True
        if not self.activa or not self.lista:
            # Sin la restricción (o antes de anotar los grupos viejos) todo grupo queda autorizado,
            # así activarla más adelante no saca al bot de donde ya estaba.
            almacen.autorizar_grupo(chat)
            return True
        return False

    # -- avisos al dueño ------------------------------------------------------------ #

    async def jid_dueno(self, numero: str) -> JID:
        """El JID con el que WhatsApp conoce a ese dueño (el número de config.toml si no lo encuentra)."""
        guardado = self._jids_duenos.get(numero)
        if guardado is not None:
            return guardado
        por_numero = JID(User=numero, Server="s.whatsapp.net")
        try:
            respuestas = await self.bot.cliente.is_on_whatsapp(f"+{numero}")
        except Exception:
            # Sin conexión todavía: le escribo al número tal cual y lo vuelvo a buscar la próxima.
            log.debug("No pude buscar al dueño +%s en WhatsApp", numero, exc_info=True)
            return por_numero
        encontrado = next((r for r in respuestas if r.IsIn and r.JID.User), None)
        if encontrado is None:
            log.error(
                "El número de dueño +%s no está en WhatsApp: no le puedo avisar nada por privado. "
                "Revisá duenos en config.toml (formato internacional, solo números y sin «+»).",
                numero,
            )
            return por_numero
        jid = JID(User=encontrado.JID.User, Server=encontrado.JID.Server or "s.whatsapp.net")
        if encontrado.JID.User != numero:
            log.info("En WhatsApp el dueño +%s es +%s: le escribo ahí", numero, encontrado.JID.User)
        self._jids_duenos[numero] = jid
        return jid

    async def avisar_duenos(self, texto: str) -> int:
        """Manda un aviso por privado a todos los dueños. Devuelve a cuántos les llegó."""
        llegaron = 0
        for numero in sorted(self.bot.config.duenos):
            if await self._enviar(await self.jid_dueno(numero), texto):
                llegaron += 1
        return llegaron

    def _aviso(self, grupo: GrupoPendiente, recordatorio: bool = False) -> str:
        p = self.bot.config.prefijo
        faltan = max(0.0, (grupo.vence - time.time()) / 60)
        cuanto = f"{faltan:.0f}" if faltan >= 1 else "menos de 1"
        nombre = grupo.nombre or "sin nombre"
        cabeza = (
            f"🔔 Perdón, no te había podido avisar: {grupo.agregado_por} me agregó al grupo «{nombre}»."
            if recordatorio
            else f"🔔 {grupo.agregado_por} me agregó al grupo «{nombre}»."
        )
        return (
            f"{cabeza}\n"
            f"Para que me quede: {p}autorizar {grupo.codigo}\n"
            f"Para sacarme: {p}rechazar {grupo.codigo}\n"
            f"Si no contestás en {cuanto} minutos, me voy solo."
        )

    def _pendientes_sin_avisar(self) -> list[GrupoPendiente]:
        return [g for g in self.bot.almacen.pendientes() if not g.avisado]

    async def recordar_pendientes(self, destino: JID | None = None) -> int:
        """Le cuenta al dueño los grupos que esperan permiso y de los que no se enteró.

        `destino` es el chat donde contestarle (el privado desde el que acaba de escribir);
        sin destino, se les escribe a todos los dueños. Devuelve cuántos avisos salieron.
        """
        avisados = 0
        for grupo in self._pendientes_sin_avisar():
            texto = self._aviso(grupo, recordatorio=True)
            llego = await self._enviar(destino, texto) if destino is not None else bool(await self.avisar_duenos(texto))
            if llego:
                self.bot.almacen.marcar_avisado(grupo.chat)
                avisados += 1
                log.info("Le recordé al dueño el grupo %s", grupo.chat)
        return avisados

    # -- al conectar ---------------------------------------------------------------- #

    async def preparar(self) -> None:
        """Al conectarse: anota los grupos viejos (una sola vez) y retoma las esperas pendientes."""
        almacen = self.bot.almacen
        if not self.lista:
            try:
                grupos = await self.bot.cliente.get_joined_groups()
            except Exception:
                log.warning("No pude leer la lista de grupos; lo intento en la próxima conexión", exc_info=True)
                return
            for grupo in grupos:
                almacen.autorizar_grupo(jid_a_texto(grupo.JID), grupo.GroupName.Name)
            almacen.poner_meta(META_INICIADO, str(int(time.time())))
            self._lista = True
            log.info("Anoté %d grupos donde ya estaba como autorizados", len(grupos))
        for pendiente in almacen.pendientes():
            self._programar_vencimiento(pendiente.chat, pendiente.vence)
        if self.bot.config.grupos.solo_el_dueno_agrega and not self.bot.config.duenos:
            log.warning(
                "solo_el_dueno_agrega está activado pero no hay números en duenos (config.toml): "
                "cualquiera puede agregar el bot a un grupo hasta que completes duenos."
            )
        for numero in sorted(self.bot.config.duenos):
            await self.jid_dueno(numero)  # deja el JID listo y avisa en el log si el número está mal
        if await self.recordar_pendientes():  # avisos que quedaron sin mandar (bot apagado, número mal, etc.)
            log.info("Mandé los avisos de grupos que habían quedado pendientes")

    # -- cuando lo agregan a un grupo ------------------------------------------------- #

    async def al_unirse(self, chat_jid: JID, nombre: str = "", quien: JID | None = None, quien_pn: JID | None = None):
        """El bot entró a un grupo (lo agregaron, o se unió con un link)."""
        chat = jid_a_texto(chat_jid)
        almacen = self.bot.almacen
        p = self.bot.config.prefijo
        sin_quien = quien is None or not quien.User
        if (
            not self.activa
            or almacen.estado_grupo(chat) == "autorizado"
            or self.es_dueno(quien, quien_pn)
            or sin_quien  # unirse con un link solo se puede desde el celular del bot
            or await self._es_el_bot(quien)
        ):
            almacen.autorizar_grupo(chat, nombre)
            log.info("Entré al grupo %s (%s)", nombre or chat, chat)
            await self._enviar(
                chat_jid, f"👋 ¡Hola! Soy {self.bot.config.nombre}. Mandá {p}menu para ver lo que sé hacer."
            )
            return
        await self.pedir_permiso(chat_jid, nombre, quien, quien_pn)

    async def pedir_permiso(
        self, chat_jid: JID, nombre: str = "", quien: JID | None = None, quien_pn: JID | None = None
    ) -> None:
        chat = jid_a_texto(chat_jid)
        almacen = self.bot.almacen
        if not nombre:
            try:
                nombre = (await self.bot.cliente.get_group_info(chat_jid)).GroupName.Name
            except Exception:
                log.debug("No pude leer el nombre del grupo %s", chat, exc_info=True)
        usados = {g.codigo for g in almacen.pendientes()}
        codigo = f"{random.randint(1000, 9999)}"
        while codigo in usados:
            codigo = f"{random.randint(1000, 9999)}"
        numero = numero_de(quien_pn) or numero_de(quien)
        agregado_por = f"+{numero}" if numero else "Alguien"
        vence = time.time() + self.minutos * 60
        if not almacen.grupo_pendiente(chat, nombre, agregado_por, codigo, vence):
            return  # ya estaba esperando permiso (o lo autorizaron mientras tanto)
        log.info("%s me agregó al grupo %s (%s): pido permiso al dueño (código %s)", agregado_por, nombre, chat, codigo)
        pendiente = GrupoPendiente(chat, nombre, agregado_por, codigo, vence)
        llegaron = await self.avisar_duenos(self._aviso(pendiente))
        if llegaron:
            almacen.marcar_avisado(chat)
        else:
            log.error(
                "No le pude avisar a ningún dueño que me agregaron al grupo %s (%s). Código: %s. "
                "Se lo recuerdo en cuanto me escriba por privado; mientras tanto lo puede ver con %sgrupos.",
                nombre or chat,
                chat,
                codigo,
                self.bot.config.prefijo,
            )
        m = f"{self.minutos:g}"
        aclaracion = (
            f"Ya le avisé: si no me autoriza en {m} minutos, me voy solo."
            if llegaron
            else f"Lo estoy buscando: si no me autoriza en {m} minutos, me voy solo."
        )
        await self._enviar(
            chat_jid, f"👋 ¡Hola! Para quedarme en este grupo necesito el permiso del dueño. {aclaracion}"
        )
        self._programar_vencimiento(chat, vence)

    def _programar_vencimiento(self, chat: str, vence: float) -> None:
        if chat in self._esperas and not self._esperas[chat].done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        tarea = loop.create_task(self._esperar_y_vencer(chat, vence))
        self._esperas[chat] = tarea
        tarea.add_done_callback(lambda _: self._esperas.pop(chat, None) if self._esperas.get(chat) is tarea else None)

    async def _esperar_y_vencer(self, chat: str, vence: float) -> None:
        await asyncio.sleep(max(0.0, vence - time.time()))
        await self.vencer(chat)

    async def vencer(self, chat: str) -> None:
        """Se terminó el tiempo: si el grupo sigue esperando permiso, el bot se va."""
        if self.bot.almacen.estado_grupo(chat) != "pendiente":
            return
        log.info("Nadie autorizó el grupo %s a tiempo; me voy", chat)
        await self.salir(chat, "👋 Me voy: el dueño no me autorizó a quedarme en este grupo.")

    # -- decisiones del dueño ------------------------------------------------------- #

    def buscar_pendiente(self, codigo: str) -> str | None:
        codigo = codigo.strip()
        return next((g.chat for g in self.bot.almacen.pendientes() if g.codigo == codigo), None)

    async def autorizar(self, chat: str, avisar_en_grupo: bool = True) -> None:
        nombre = next((g.nombre for g in self.bot.almacen.pendientes() if g.chat == chat), "")
        era_pendiente = self.bot.almacen.estado_grupo(chat) == "pendiente"
        self.bot.almacen.autorizar_grupo(chat, nombre)
        self._cancelar(chat)
        log.info("El dueño autorizó el grupo %s", chat)
        if avisar_en_grupo and era_pendiente:
            p = self.bot.config.prefijo
            await self._enviar(
                jid_de_texto(chat), f"✅ El dueño me dejó quedarme. Mandá {p}menu para ver lo que sé hacer."
            )

    async def salir(self, chat: str, despedida: str) -> None:
        self._cancelar(chat)
        jid = jid_de_texto(chat)
        await self._enviar(jid, despedida)
        try:
            await self.bot.cliente.leave_group(jid)
        except Exception:
            log.exception("No pude salir del grupo %s", chat)
        self.bot.almacen.borrar_grupo(chat)

    def _cancelar(self, chat: str) -> None:
        tarea = self._esperas.pop(chat, None)
        if tarea is not None and tarea is not asyncio.current_task():
            tarea.cancel()

    async def _enviar(self, jid: JID, texto: str) -> bool:
        """Manda un mensaje. False si WhatsApp no lo aceptó (queda avisado en el log)."""
        try:
            await self.bot.cliente.send_message(jid, texto)
            return True
        except Exception:
            log.warning("No pude mandar un mensaje a %s", jid_a_texto(jid), exc_info=True)
            return False
