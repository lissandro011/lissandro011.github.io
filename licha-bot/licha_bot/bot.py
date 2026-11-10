"""Conexión con WhatsApp y despacho de comandos."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import sys
import time
from collections import OrderedDict
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from neonize.aioze.client import NewAClient
from neonize.aioze.events import (
    ConnectedEv,
    ConnectFailureEv,
    DisconnectedEv,
    JoinedGroupEv,
    LoggedOutEv,
    MessageEv,
    PairStatusEv,
    TemporaryBanEv,
)
from neonize.proto.Neonize_pb2 import JID
from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import DeviceProps
from neonize.utils.enum import ClientName

from .almacen import Almacen
from .comandos import REGISTRO, Comando, Registro
from .config import Config
from .contexto import Contexto, copiar_evento
from .errores import ErrorUsuario
from .frases import Bolsas, Memoria
from .guardia import Guardia
from .mensajes import jid_a_texto, numero_de, parsear_comando, texto_de

log = logging.getLogger("licha.bot")

# Códigos de salida (iniciar.bat los usa para saber si reiniciar).
SALIDA_OK = 0
SALIDA_ERROR = 1
SALIDA_VINCULAR = 2  # no hay sesión, el código venció o se desvinculó desde el teléfono
SALIDA_REINICIAR = 3  # !reiniciar

# Chats donde respondemos: privados (número o LID) y grupos. Se ignoran
# estados, listas de difusión y canales.
SERVIDORES_PERMITIDOS = frozenset({"s.whatsapp.net", "lid", "g.us"})
ERROR_GENERICO = "Algo salió mal con ese comando 😕 Probá de nuevo en un rato."
TIEMPO_PARA_VINCULAR = 180  # segundos para ingresar el código en el teléfono
MENSAJES_RECORDADOS = 2000  # para no procesar dos veces el mismo mensaje

SIN_PERMISO = (
    "Mirá la confianza que agarró. Ese comando es del dueño.",
    "Ese botón lo toca el dueño, amigo.",
    "Buena iniciativa. Te falta ser el dueño.",
    "Te leí. Para eso tiene que venir el dueño.",
)


def sesion_guardada(archivo: Path) -> bool:
    """True si el archivo de sesión ya tiene un número vinculado."""
    if not archivo.exists():
        return False
    try:
        with sqlite3.connect(f"{archivo.resolve().as_uri()}?mode=ro", uri=True) as db:
            return db.execute("SELECT COUNT(*) FROM whatsmeow_device").fetchone()[0] > 0
    except sqlite3.Error:
        return False


def _silenciar_aviso_ffmpeg() -> None:
    # neonize avisa que falta ffmpeg al conectar, pero Licha Bot no lo usa:
    # los stickers se hacen con Pillow y PyAV.
    try:
        from neonize.utils import ffmpeg

        ffmpeg._ffmpeg_checked = True
    except Exception:
        pass


class LichaBot:
    def __init__(
        self, config: Config, registro: Registro = REGISTRO, cliente: Any = None, almacen: Almacen | None = None
    ):
        self.config = config
        self.registro = registro
        self.frases = Bolsas()
        self.memoria = Memoria(config.enseguida_segundos)
        self.guardia = Guardia(self)
        self._almacen = almacen
        self._vistos: OrderedDict[str, None] = OrderedDict()
        self.inicio = time.monotonic()
        self.codigo_salida = SALIDA_OK
        self.limite_tareas = asyncio.Semaphore(config.tareas_pesadas_simultaneas)
        self._ultimo_comando: dict[str, float] = {}
        self._vinculado = asyncio.Event()
        self._codigo_pedido = False
        self._deteniendo = False
        self._tareas: set[asyncio.Task[Any]] = set()
        self.cliente = cliente if cliente is not None else self._crear_cliente()

    def _crear_cliente(self) -> NewAClient:
        # El primer parámetro es el archivo SQLite donde neonize guarda la sesión.
        # `os` es el nombre que aparece en "Dispositivos vinculados" del teléfono.
        self.config.archivo_sesion.parent.mkdir(parents=True, exist_ok=True)
        cliente = NewAClient(
            str(self.config.archivo_sesion),
            props=DeviceProps(os=self.config.nombre, platformType=DeviceProps.CHROME),
        )
        cliente.event(ConnectedEv)(self._al_conectar)
        cliente.event(PairStatusEv)(self._al_vincular)
        cliente.event(LoggedOutEv)(self._al_cerrar_sesion)
        cliente.event(DisconnectedEv)(self._al_desconectar)
        cliente.event(ConnectFailureEv)(self._al_fallar_conexion)
        cliente.event(TemporaryBanEv)(self._al_ser_suspendido)
        cliente.event(MessageEv)(self._al_recibir_mensaje)
        cliente.event(JoinedGroupEv)(self._al_unirse_a_grupo)
        cliente.qr(self._al_recibir_qr)
        return cliente

    @property
    def almacen(self) -> Almacen:
        """Datos guardados (votaciones, listas, grupos autorizados). Se abre la primera vez que se usa."""
        if self._almacen is None:
            self._almacen = Almacen(self.config.archivo_datos)
        return self._almacen

    @property
    def segundos_activo(self) -> float:
        return time.monotonic() - self.inicio

    # -- ciclo de vida ------------------------------------------------------ #

    async def ejecutar(self) -> int:
        cfg = self.config
        if sesion_guardada(cfg.archivo_sesion):
            log.info("Sesión guardada encontrada; conectando a WhatsApp…")
        elif cfg.numero:
            log.info("Todavía no hay un número vinculado: voy a pedir un código para %s", cfg.numero)
        else:
            log.warning(
                "No hay número en config.toml ([bot] numero), así que voy a mostrar un código QR para "
                "escanear. Es más fácil vincular con código: completá el número y volvé a iniciar."
            )

        _silenciar_aviso_ffmpeg()
        try:
            await self.cliente.connect()
            await self.cliente.idle()  # vuelve cuando se llama a cliente.stop()
        except asyncio.CancelledError:  # Ctrl+C
            await self.detener(SALIDA_OK)
            raise
        except Exception as exc:
            log.error("No pude conectarme a WhatsApp: %s", exc)
            log.error("¿La PC tiene internet? iniciar.bat vuelve a intentar en unos segundos.")
            log.debug("Detalle del error", exc_info=True)
            return SALIDA_ERROR
        return self.codigo_salida

    async def detener(self, codigo: int = SALIDA_OK) -> None:
        if self._deteniendo:
            return
        self._deteniendo = True
        self.codigo_salida = codigo
        try:
            await self.cliente.stop()
        except Exception:
            log.exception("Error al desconectar")

    def _en_segundo_plano(self, coro: Coroutine[Any, Any, Any]) -> None:
        tarea = asyncio.get_running_loop().create_task(coro)
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    # -- vinculación -------------------------------------------------------- #

    async def _al_recibir_qr(self, cliente: NewAClient, qr: bytes) -> None:
        # neonize solo manda un QR cuando no hay sesión guardada.
        if self.config.numero:
            if not self._codigo_pedido:
                self._codigo_pedido = True  # el QR se renueva cada ~20 s; pedimos un solo código
                await self._pedir_codigo(cliente)
            return
        self._mostrar_qr(qr)

    async def _pedir_codigo(self, cliente: NewAClient) -> None:
        try:
            codigo = await cliente.PairPhone(
                self.config.numero, show_push_notification=True, client_name=ClientName.WINDOWS
            )
        except Exception:
            log.exception(
                "No pude pedir el código de vinculación para %s. Revisá que el número esté bien en "
                "config.toml (formato 5491123456789) y que tenga WhatsApp instalado.",
                self.config.numero,
            )
            await self.detener(SALIDA_VINCULAR)
            return
        aviso = (
            "\n"
            "  ╔══════════════════════════════════════════════════════╗\n"
            f"  ║   CÓDIGO PARA VINCULAR LICHA BOT:   {codigo:<17}║\n"
            "  ╚══════════════════════════════════════════════════════╝\n"
            "  En el celular con el chip del bot abrí WhatsApp y andá a:\n"
            "  ⋮ (o Configuración) > Dispositivos vinculados > Vincular un dispositivo >\n"
            "  'Vincular con el número de teléfono' e ingresá el código.\n"
            f"  Tenés {TIEMPO_PARA_VINCULAR // 60} minutos.\n"
        )
        log.warning(aviso)
        self._en_segundo_plano(self._esperar_vinculacion())

    def _mostrar_qr(self, qr: bytes) -> None:
        import segno  # viene con neonize

        codigo_qr = segno.make_qr(qr)
        archivo = self.config.archivo_sesion.parent / "qr.png"
        try:
            codigo_qr.save(str(archivo), scale=10, border=4)
        except OSError:
            log.exception("No pude guardar %s", archivo)
        print()
        try:
            codigo_qr.terminal(compact=True)
        except Exception:
            pass
        log.warning(
            "Escaneá el QR desde WhatsApp > Dispositivos vinculados > Vincular un dispositivo. "
            "Si en la consola no se ve bien, abrí %s (se renueva cada 20 segundos).",
            archivo,
        )
        if sys.platform == "win32" and not self._codigo_pedido:
            self._codigo_pedido = True
            try:
                os.startfile(archivo)  # type: ignore[attr-defined]  # abre la imagen la primera vez
            except OSError:
                pass

    async def _esperar_vinculacion(self) -> None:
        try:
            await asyncio.wait_for(self._vinculado.wait(), timeout=TIEMPO_PARA_VINCULAR)
        except TimeoutError:
            log.error("El código venció sin usarse. Cerrá y volvé a iniciar el bot para pedir otro.")
            await self.detener(SALIDA_VINCULAR)

    async def _al_vincular(self, _: NewAClient, ev: PairStatusEv) -> None:
        if ev.Status == PairStatusEv.SUCCESS:
            self._vinculado.set()
            log.info("¡Número vinculado! (%s). La sesión quedó guardada; no hace falta volver a vincular.", ev.ID.User)
        else:
            log.error("Falló la vinculación: %s", ev.Error)

    async def _al_conectar(self, _: NewAClient, __: ConnectedEv) -> None:
        self._vinculado.set()
        comandos = len(self.registro.todos())
        log.info(
            "✅ %s está conectado y escuchando (%d comandos). Probalo escribiéndole %smenu desde OTRO número.",
            self.config.nombre,
            comandos,
            self.config.prefijo,
        )
        self._en_segundo_plano(self._preparar_grupos())

    async def _preparar_grupos(self) -> None:
        try:
            await self.guardia.preparar()
        except Exception:
            log.exception("No pude revisar los grupos autorizados")

    async def _al_unirse_a_grupo(self, _: NewAClient, ev: JoinedGroupEv) -> None:
        try:
            await self.guardia.al_unirse(
                ev.GroupInfo.JID,
                ev.GroupInfo.GroupName.Name,
                ev.Sender if ev.HasField("Sender") else None,
                ev.SenderPN if ev.HasField("SenderPN") else None,
            )
        except Exception:
            log.exception("Error al entrar a un grupo")

    async def _al_desconectar(self, _: NewAClient, __: DisconnectedEv) -> None:
        if not self._deteniendo:
            log.warning("Se cortó la conexión con WhatsApp; reintentando sola…")

    async def _al_fallar_conexion(self, _: NewAClient, ev: ConnectFailureEv) -> None:
        log.error("WhatsApp rechazó la conexión (motivo %s): %s", ev.Reason, ev.Message)

    async def _al_ser_suspendido(self, _: NewAClient, ev: TemporaryBanEv) -> None:
        log.error(
            "WhatsApp suspendió temporalmente este número (código %s, vence en %s s). "
            "Dejá el bot apagado hasta entonces y bajá la cantidad de mensajes.",
            ev.Code,
            ev.Expire,
        )

    async def _al_cerrar_sesion(self, _: NewAClient, ev: LoggedOutEv) -> None:
        motivo = LoggedOutEv.DESCRIPTOR.fields_by_name["Reason"].enum_type.values_by_number.get(ev.Reason)
        log.error(
            "WhatsApp cerró la sesión (%s): el bot se desvinculó. Volvé a iniciarlo para vincularlo de nuevo.",
            motivo.name if motivo else ev.Reason,
        )
        await self.detener(SALIDA_VINCULAR)

    # -- mensajes ----------------------------------------------------------- #

    async def _al_recibir_mensaje(self, _: NewAClient, ev: MessageEv) -> None:
        try:
            await self.procesar(ev)
        except Exception:
            log.exception("Error procesando el mensaje %s", ev.Info.ID)

    def _es_viejo(self, ev: MessageEv) -> bool:
        limite = self.config.ignorar_mensajes_de_mas_de_minutos
        marca = ev.Info.Timestamp
        if not limite or not marca:
            return False
        segundos = marca / 1000 if marca > 10**11 else marca  # neonize puede mandarlo en ms
        return time.time() - segundos > limite * 60

    async def procesar(self, ev: MessageEv) -> None:
        """Decide qué hacer con un mensaje: comando, oyentes o nada."""
        fuente = ev.Info.MessageSource
        cfg = self.config
        if fuente.IsFromMe or ev.IsEdit or fuente.Chat.Server not in SERVIDORES_PERMITIDOS:
            return
        if (fuente.IsGroup and not cfg.responder_en_grupos) or (not fuente.IsGroup and not cfg.responder_en_privado):
            return
        if self._es_viejo(ev):
            log.debug("Ignoro el mensaje viejo %s", ev.Info.ID)
            return
        if self._repetido(ev):
            log.debug("Ignoro el mensaje repetido %s", ev.Info.ID)
            return
        if self._es_de_un_dueno(fuente):
            # Si quedó algún grupo esperando permiso del que no le pude avisar, se lo cuento ahora.
            await self._recordar_pendientes(fuente)
        if fuente.IsGroup and not await self._grupo_permitido(ev):
            return

        pedido = parsear_comando(texto_de(ev.Message), cfg.prefijos)
        if pedido is not None:
            prefijo, nombre, resto = pedido
            cmd = self.registro.buscar(nombre)
            if cmd is not None:
                ctx = Contexto(self, ev, prefijo=prefijo, comando=nombre, texto_args=resto, info=cmd)
                await self._ejecutar_comando(cmd, ctx)
                return
            if cfg.avisar_comando_desconocido and not fuente.IsGroup and nombre.isalnum():
                await self.cliente.reply_message(
                    f"No conozco el comando {prefijo}{nombre} 🤔 Escribí {prefijo}menu para ver la lista.",
                    copiar_evento(ev),
                )
                return

        if self.registro.oyentes:
            await self._avisar_oyentes(Contexto(self, ev))

    def _repetido(self, ev: MessageEv) -> bool:
        """True si ese mensaje ya se procesó (WhatsApp a veces manda el mismo evento dos veces)."""
        fuente = ev.Info.MessageSource
        clave = f"{jid_a_texto(fuente.Chat)}|{jid_a_texto(fuente.Sender)}|{ev.Info.ID}"
        if not ev.Info.ID:
            return False
        if clave in self._vistos:
            return True
        self._vistos[clave] = None
        if len(self._vistos) > MENSAJES_RECORDADOS:
            self._vistos.popitem(last=False)
        return False

    def _es_de_un_dueno(self, fuente) -> bool:
        """True si el mensaje lo escribió un dueño del bot ([bot] duenos en config.toml)."""
        return (numero_de(fuente.Sender) or numero_de(fuente.SenderAlt)) in self.config.duenos

    async def _recordar_pendientes(self, fuente) -> None:
        """Le avisa al dueño de los grupos que esperan permiso y de los que no se enteró."""
        if not self.guardia.activa:
            return
        # En privado le contesto en el mismo chat (ahí seguro llega); desde un grupo, por privado.
        destino = None if fuente.IsGroup else JID(User=fuente.Chat.User, Server=fuente.Chat.Server)
        try:
            await self.guardia.recordar_pendientes(destino)
        except Exception:
            log.exception("No pude avisarle al dueño de los grupos que esperan permiso")

    async def _grupo_permitido(self, ev: MessageEv) -> bool:
        """En grupos que el dueño no autorizó, el bot solo le contesta al dueño."""
        fuente = ev.Info.MessageSource
        chat = jid_a_texto(fuente.Chat)
        if self.guardia.permitido(chat):
            return True
        if self._es_de_un_dueno(fuente):
            return True
        if self.almacen.estado_grupo(chat) is None:  # entró sin que nos enteráramos: pedimos permiso igual
            await self.guardia.pedir_permiso(fuente.Chat)
        return False

    async def _ejecutar_comando(self, cmd: Comando, ctx: Contexto) -> None:
        donde = "un grupo" if ctx.es_grupo else "privado"
        if cmd.solo_dueno and not ctx.es_dueno:
            await ctx.responder(ctx.frase("sin_permiso", SIN_PERMISO))
            return
        if cmd.solo_grupos and not ctx.es_grupo:
            p = ctx.prefijo
            extra = [f"{p}{n}" for n in ("excusa", "elegir") if self.registro.buscar(n)]
            texto = f"{p}{cmd.nombre} se usa en grupos. Probalo en un grupo donde esté yo."
            if extra:
                texto += f" Por acá podés usar {' o '.join(extra)}."
            await ctx.responder(texto)
            return
        if cmd.solo_privado and ctx.es_grupo:
            await ctx.responder("Ese comando solo funciona por privado.")
            return

        clave = jid_a_texto(ctx.remitente)
        ahora = time.monotonic()
        espera = self.config.espera_entre_comandos
        if espera and not ctx.es_dueno and ahora - self._ultimo_comando.get(clave, -espera) < espera:
            log.info("%s mandó comandos muy seguido; espero", clave)
            await ctx.reaccionar("⏳")
            return
        self._ultimo_comando[clave] = ahora
        ctx.anterior = self.memoria.anotar_comando(jid_a_texto(ctx.chat), ctx.persona, cmd.nombre)

        log.info("%s%s de %s (%s) en %s", ctx.prefijo, ctx.comando, ctx.nombre, ctx.numero or clave, donde)
        inicio = time.monotonic()
        try:
            await cmd.funcion(ctx)
        except ErrorUsuario as exc:
            log.info("%s%s: %s", ctx.prefijo, ctx.comando, exc)
            await self._responder_sin_fallar(ctx, exc.mensaje)
        except Exception:
            log.exception("El comando %s%s falló", ctx.prefijo, ctx.comando)
            await self._responder_sin_fallar(ctx, ERROR_GENERICO)
        else:
            log.debug("%s%s terminó en %.1f s", ctx.prefijo, ctx.comando, time.monotonic() - inicio)

    async def _avisar_oyentes(self, ctx: Contexto) -> None:
        for oyente in self.registro.oyentes:
            try:
                if await oyente.funcion(ctx):
                    return
            except ErrorUsuario as exc:
                log.info("Oyente %s: %s", oyente.nombre, exc)
                await self._responder_sin_fallar(ctx, exc.mensaje)
                return
            except Exception:
                log.exception("El oyente %s (%s) falló", oyente.nombre, oyente.modulo)

    async def _responder_sin_fallar(self, ctx: Contexto, texto: str) -> None:
        try:
            await ctx.responder(texto)
        except Exception:
            log.exception("No pude responder al mensaje %s", ctx.evento.Info.ID)
