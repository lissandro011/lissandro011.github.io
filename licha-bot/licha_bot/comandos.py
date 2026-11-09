"""Registro de comandos de Licha Bot.

Cada archivo .py de la carpeta `comandos/` se carga solo al arrancar. Para
crear un comando alcanza con escribir una función `async` y decorarla:

    from licha_bot import comando

    @comando("hola", "buenas", descripcion="Saluda")
    async def hola(ctx):
        await ctx.responder(f"¡Hola, {ctx.nombre}!")

`@escuchar` registra funciones que reciben los mensajes que NO son comandos
(por ejemplo, para hacer stickers automáticos cuando te mandan una foto).
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
import sys
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .contexto import Contexto

log = logging.getLogger("licha.comandos")

FuncionComando = Callable[["Contexto"], Awaitable[Any]]


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes: 'Menú' -> 'menu'."""
    descompuesto = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


@dataclass
class Comando:
    nombre: str
    funcion: FuncionComando
    alias: tuple[str, ...] = ()
    descripcion: str = ""
    uso: str = ""  # cómo se usa; "{p}" se reemplaza por el prefijo
    categoria: str = "General"
    solo_grupos: bool = False
    solo_privado: bool = False
    solo_dueno: bool = False
    oculto: bool = False  # no aparece en el menú
    modulo: str = ""

    @property
    def nombres(self) -> tuple[str, ...]:
        return (self.nombre, *self.alias)


@dataclass
class Oyente:
    nombre: str
    funcion: FuncionComando  # devuelve True si se ocupó del mensaje
    modulo: str = ""


@dataclass
class Registro:
    """Todos los comandos y oyentes del bot."""

    _por_nombre: dict[str, Comando] = field(default_factory=dict)
    _comandos: list[Comando] = field(default_factory=list)
    oyentes: list[Oyente] = field(default_factory=list)

    def agregar(self, cmd: Comando) -> None:
        nombres = [normalizar(n) for n in cmd.nombres]
        for nombre in nombres:
            if not nombre or any(c.isspace() for c in nombre):
                raise ValueError(f"Nombre de comando inválido: {nombre!r}")
            if nombre in self._por_nombre:
                otro = self._por_nombre[nombre]
                raise ValueError(
                    f"El comando {nombre!r} ({cmd.modulo}) ya existe en {otro.modulo or 'otro archivo'}"
                )
        for nombre in nombres:
            self._por_nombre[nombre] = cmd
        self._comandos.append(cmd)

    def buscar(self, nombre: str) -> Comando | None:
        return self._por_nombre.get(normalizar(nombre))

    def todos(self) -> list[Comando]:
        return list(self._comandos)

    def por_categoria(self, incluir_ocultos: bool = False) -> dict[str, list[Comando]]:
        grupos: dict[str, list[Comando]] = {}
        for cmd in self._comandos:
            if cmd.oculto and not incluir_ocultos:
                continue
            grupos.setdefault(cmd.categoria, []).append(cmd)
        return grupos

    def limpiar(self) -> None:
        self._por_nombre.clear()
        self._comandos.clear()
        self.oyentes.clear()

    # -- decoradores ------------------------------------------------------- #

    def comando(
        self,
        nombre: str,
        *alias: str,
        descripcion: str = "",
        uso: str = "",
        categoria: str = "General",
        solo_grupos: bool = False,
        solo_privado: bool = False,
        solo_dueno: bool = False,
        oculto: bool = False,
    ) -> Callable[[FuncionComando], FuncionComando]:
        """Registra una función `async def f(ctx)` como comando."""

        def decorador(funcion: FuncionComando) -> FuncionComando:
            if not inspect.iscoroutinefunction(funcion):
                raise TypeError(f"El comando {nombre!r} tiene que ser una función 'async def'")
            self.agregar(
                Comando(
                    nombre=nombre,
                    funcion=funcion,
                    alias=alias,
                    descripcion=descripcion,
                    uso=uso,
                    categoria=categoria,
                    solo_grupos=solo_grupos,
                    solo_privado=solo_privado,
                    solo_dueno=solo_dueno,
                    oculto=oculto,
                    modulo=funcion.__module__,
                )
            )
            return funcion

        return decorador

    def escuchar(self, funcion: FuncionComando) -> FuncionComando:
        """Registra una función `async def f(ctx)` que recibe los mensajes que no son comandos.

        Si devuelve True, los oyentes siguientes no reciben ese mensaje.
        """
        if not inspect.iscoroutinefunction(funcion):
            raise TypeError(f"El oyente {funcion.__name__!r} tiene que ser una función 'async def'")
        self.oyentes.append(Oyente(funcion.__name__, funcion, funcion.__module__))
        return funcion


REGISTRO = Registro()
comando = REGISTRO.comando
escuchar = REGISTRO.escuchar


def cargar_comandos(paquete: str = "comandos") -> list[str]:
    """Importa todos los archivos de la carpeta de comandos (salvo los que empiezan con _).

    Si un archivo tiene un error, se anota en el log y se siguen cargando los
    demás: un comando roto no tira abajo al bot. Devuelve los archivos que fallaron.
    """
    try:
        modulo_paquete = importlib.import_module(paquete)
    except ImportError:
        log.exception("No encontré la carpeta de comandos %r", paquete)
        return [paquete]

    fallidos = []
    for info in sorted(pkgutil.iter_modules(modulo_paquete.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        nombre_completo = f"{paquete}.{info.name}"
        try:
            if nombre_completo in sys.modules:
                importlib.reload(sys.modules[nombre_completo])
            else:
                importlib.import_module(nombre_completo)
        except Exception:
            log.exception("No pude cargar %s/%s.py; el resto de los comandos funciona igual", paquete, info.name)
            fallidos.append(info.name)
    return fallidos
