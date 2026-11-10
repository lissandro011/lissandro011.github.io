"""Cómo elige Licha lo que dice: bolsas de frases y memoria corta de lo que acaba de pasar.

- Bolsas: para cada grupo de frases hay una bolsa mezclada por chat. Se saca
  una por vez; al vaciarse se vuelve a mezclar sin arrancar con la última que
  salió. Así no se repite una frase hasta haber usado todas.
- Memoria: recuerda por chat, persona y comando cuántas veces seguidas se usó
  algo "enseguida" (config: enseguida_segundos) y un dato del uso anterior
  (por ejemplo, de qué lado cayó la moneda).

Todo vive en memoria y caduca solo: si el bot se reinicia, se empieza de cero.
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from .comandos import normalizar

CADUCIDAD_BOLSAS = 24 * 3600  # una bolsa sin usar por un día se olvida
LIMPIAR_CADA = 500  # cada cuántos usos se borran las entradas viejas


def texto_normalizado(texto: str) -> str:
    """Minúsculas, sin tildes, sin signos y con espacios simples: '¿Le escribo?!' -> 'le escribo'."""
    sin_signos = re.sub(r"[^\w\s]", " ", normalizar(texto))
    return " ".join(sin_signos.split())


def completar(plantilla: str, **datos: Any) -> str:
    """Reemplaza {campo} por su valor. Los valores no se vuelven a interpretar (un "{" del usuario es seguro)."""
    return plantilla.format_map(datos)


@dataclass
class _Bolsa:
    opciones: tuple[str, ...]
    pendientes: list[int] = field(default_factory=list)
    ultima: int | None = None
    usada: float = 0.0


class Bolsas:
    def __init__(self, reloj: Callable[[], float] = time.monotonic, azar: random.Random | None = None):
        self._bolsas: dict[tuple[str, str], _Bolsa] = {}
        self._reloj = reloj
        self._azar = azar or random.Random()
        self._usos = 0

    def sacar(self, clave: str, banco: str, opciones: Sequence[str]) -> str:
        """Saca la próxima frase de la bolsa `banco` del chat (o persona) `clave`."""
        if not opciones:
            raise ValueError(f"El banco {banco!r} está vacío")
        ahora = self._reloj()
        self._limpiar(ahora)
        opciones = tuple(opciones)
        bolsa = self._bolsas.get((clave, banco))
        if bolsa is None or bolsa.opciones != opciones or ahora - bolsa.usada > CADUCIDAD_BOLSAS:
            bolsa = _Bolsa(opciones)
            self._bolsas[(clave, banco)] = bolsa
        if not bolsa.pendientes:
            orden = list(range(len(opciones)))
            self._azar.shuffle(orden)
            # Se saca desde el final: que la próxima no sea la última que salió.
            if len(orden) > 1 and orden[-1] == bolsa.ultima:
                otro = self._azar.randrange(len(orden) - 1)
                orden[-1], orden[otro] = orden[otro], orden[-1]
            bolsa.pendientes = orden
        indice = bolsa.pendientes.pop()
        bolsa.ultima = indice
        bolsa.usada = ahora
        return opciones[indice]

    def _limpiar(self, ahora: float) -> None:
        self._usos += 1
        if self._usos % LIMPIAR_CADA:
            return
        for clave in [c for c, b in self._bolsas.items() if ahora - b.usada > CADUCIDAD_BOLSAS]:
            del self._bolsas[clave]


@dataclass
class Racha:
    numero: int  # 1 = primera vez (o pasó más de "enseguida" desde la anterior)
    anterior: Any = None  # dato guardado en el uso anterior de la racha (None si es la primera)

    @property
    def seguida(self) -> bool:
        return self.numero > 1


@dataclass
class _Uso:
    numero: int
    momento: float
    dato: Any


class Memoria:
    """Rachas por (chat, persona, comando) y último comando de cada persona en cada chat."""

    def __init__(self, enseguida: float, reloj: Callable[[], float] = time.monotonic):
        self.enseguida = enseguida
        self._reloj = reloj
        self._usos: dict[tuple[str, str, str], _Uso] = {}
        self._ultimo_comando: dict[tuple[str, str], tuple[str, float]] = {}
        self._cuenta = 0

    def anotar_comando(self, chat: str, persona: str, comando: str) -> str | None:
        """Anota el comando que va a correr y devuelve el anterior de esa persona en ese chat."""
        ahora = self._reloj()
        self._limpiar(ahora)
        previo = self._ultimo_comando.get((chat, persona))
        self._ultimo_comando[(chat, persona)] = (comando, ahora)
        if previo is None or ahora - previo[1] > self.enseguida:
            return None
        return previo[0]

    def racha(self, chat: str, persona: str, comando: str, dato: Any = None, cortar: bool = False) -> Racha:
        """Registra un uso y dice cuántas veces seguidas (enseguida) lo usó esa persona.

        `dato` queda guardado para el próximo uso (llega como `Racha.anterior`).
        Con `cortar=True` la racha vuelve a empezar aunque esté dentro del tiempo.
        """
        ahora = self._reloj()
        clave = (chat, persona, comando)
        previo = self._usos.get(clave)
        if previo is None or cortar or ahora - previo.momento > self.enseguida:
            resultado = Racha(1)
        else:
            resultado = Racha(previo.numero + 1, previo.dato)
        self._usos[clave] = _Uso(resultado.numero, ahora, dato)
        return resultado

    def _limpiar(self, ahora: float) -> None:
        self._cuenta += 1
        if self._cuenta % LIMPIAR_CADA:
            return
        viejo = ahora - max(self.enseguida, 60) * 2
        self._usos = {c: u for c, u in self._usos.items() if u.momento > viejo}
        self._ultimo_comando = {c: v for c, v in self._ultimo_comando.items() if v[1] > viejo}
