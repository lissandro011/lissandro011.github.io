"""Configuración de Licha Bot (archivo config.toml en la carpeta del bot)."""

from __future__ import annotations

import logging
import re
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .conversor import OpcionesSticker

CARPETA_BOT = Path(__file__).resolve().parent.parent
ARCHIVO_CONFIG = CARPETA_BOT / "config.toml"
ARCHIVO_EJEMPLO = CARPETA_BOT / "config.ejemplo.toml"
NIVELES = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

log = logging.getLogger("licha.config")


class ErrorConfig(ValueError):
    """config.toml tiene un valor que no sirve. El mensaje explica cómo arreglarlo."""


@dataclass(frozen=True)
class ConfigStickers:
    paquete: str = "Licha Bot"
    autor: str = "Licha Bot"
    marca_de_agua: str = "Licha Bot"
    automatico_en_privado: bool = True
    max_segundos_video: float = 10.0
    max_mb_descarga: int = 25

    def opciones(self, **cambios: Any) -> OpcionesSticker:
        datos = {
            "paquete": self.paquete,
            "autor": self.autor,
            "marca_de_agua": self.marca_de_agua,
            "max_segundos": self.max_segundos_video,
        }
        datos.update(cambios)
        return OpcionesSticker(**datos)


@dataclass(frozen=True)
class Config:
    nombre: str = "Licha Bot"
    numero: str | None = None
    prefijos: tuple[str, ...] = ("!", ".")
    duenos: frozenset[str] = frozenset()
    responder_en_grupos: bool = True
    responder_en_privado: bool = True
    espera_entre_comandos: float = 3.0
    ignorar_mensajes_de_mas_de_minutos: float = 10.0
    avisar_comando_desconocido: bool = True
    saludar_por_privado: bool = True
    tareas_pesadas_simultaneas: int = 2
    stickers: ConfigStickers = field(default_factory=ConfigStickers)
    nivel_log: str = "INFO"
    nivel_log_whatsapp: str = "WARNING"
    archivo_sesion: Path = CARPETA_BOT / "datos" / "sesion.sqlite3"
    carpeta_logs: Path = CARPETA_BOT / "logs"
    datos: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def prefijo(self) -> str:
        """El prefijo principal (el primero de la lista), para mostrar en mensajes."""
        return self.prefijos[0]

    def seccion(self, nombre: str) -> dict[str, Any]:
        """Una sección de config.toml tal cual, para que los comandos nuevos tengan su propia configuración.

        Por ejemplo, con `[clima]` + `ciudad = "Rosario"` en config.toml:
        `ctx.config.seccion("clima").get("ciudad", "Buenos Aires")`.
        """
        valor = self.datos.get(nombre, {})
        return valor if isinstance(valor, dict) else {}


# --------------------------------------------------------------------------- #
# Validación
# --------------------------------------------------------------------------- #


def normalizar_numero(crudo: str, donde: str = "numero") -> str:
    """'+54 9 11 2345-6789' -> '5491123456789' (internacional, solo dígitos)."""
    digitos = re.sub(r"[\s+\-().]", "", str(crudo))
    if not digitos.isdigit() or not 8 <= len(digitos) <= 15:
        raise ErrorConfig(
            f"{donde} = {crudo!r} no es un número válido. Usá el formato internacional, "
            'solo números y sin "+". Ejemplo para Argentina: "5491123456789".'
        )
    return digitos


class _Lector:
    def __init__(self, datos: dict[str, Any], seccion: str):
        valor = datos.get(seccion, {})
        if not isinstance(valor, dict):
            raise ErrorConfig(f"[{seccion}] tiene que ser una sección (una línea [{seccion}] y debajo sus valores)")
        self.datos = valor
        self.seccion = seccion

    def _nombre(self, clave: str) -> str:
        return f"{clave} (en [{self.seccion}])"

    def texto(self, clave: str, defecto: str) -> str:
        valor = self.datos.get(clave, defecto)
        if not isinstance(valor, str):
            raise ErrorConfig(f'{self._nombre(clave)} tiene que ir entre comillas, por ejemplo: {clave} = "algo"')
        return valor.strip()

    def booleano(self, clave: str, defecto: bool) -> bool:
        valor = self.datos.get(clave, defecto)
        if not isinstance(valor, bool):
            raise ErrorConfig(f"{self._nombre(clave)} tiene que ser true o false (sin comillas)")
        return valor

    def numero(self, clave: str, defecto: float, minimo: float, entero: bool = False) -> float:
        valor = self.datos.get(clave, defecto)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or (entero and not isinstance(valor, int)):
            tipo = "un número entero" if entero else "un número"
            raise ErrorConfig(f"{self._nombre(clave)} tiene que ser {tipo} (sin comillas)")
        if valor < minimo:
            raise ErrorConfig(f"{self._nombre(clave)} tiene que ser {minimo:g} o más (vale {valor:g})")
        return valor

    def lista_textos(self, clave: str, defecto: list[str]) -> list[str]:
        valor = self.datos.get(clave, defecto)
        if isinstance(valor, str):
            valor = [valor]
        if not isinstance(valor, list) or not all(isinstance(v, (str, int)) for v in valor):
            raise ErrorConfig(f'{self._nombre(clave)} tiene que ser una lista, por ejemplo: {clave} = ["uno", "dos"]')
        return [str(v).strip() for v in valor if str(v).strip()]

    def nivel(self, clave: str, defecto: str) -> str:
        valor = self.texto(clave, defecto).upper()
        if valor not in NIVELES:
            raise ErrorConfig(f"{self._nombre(clave)} tiene que ser uno de: {', '.join(NIVELES)}")
        return valor


def desde_dict(datos: dict[str, Any]) -> Config:
    bot = _Lector(datos, "bot")
    stk = _Lector(datos, "stickers")
    reg = _Lector(datos, "registro")

    numero = bot.texto("numero", "")
    prefijos = tuple(bot.lista_textos("prefijos", ["!", "."]))
    if not prefijos:
        raise ErrorConfig('prefijos (en [bot]) no puede estar vacío. Ejemplo: prefijos = ["!", "."]')
    if any(any(c.isspace() for c in p) for p in prefijos):
        raise ErrorConfig("prefijos (en [bot]) no pueden tener espacios")

    return Config(
        nombre=bot.texto("nombre", "Licha Bot") or "Licha Bot",
        numero=normalizar_numero(numero, "numero (en [bot])") if numero else None,
        prefijos=prefijos,
        duenos=frozenset(normalizar_numero(n, "duenos (en [bot])") for n in bot.lista_textos("duenos", [])),
        responder_en_grupos=bot.booleano("responder_en_grupos", True),
        responder_en_privado=bot.booleano("responder_en_privado", True),
        espera_entre_comandos=bot.numero("espera_entre_comandos", 3, minimo=0),
        ignorar_mensajes_de_mas_de_minutos=bot.numero("ignorar_mensajes_de_mas_de_minutos", 10, minimo=0),
        avisar_comando_desconocido=bot.booleano("avisar_comando_desconocido", True),
        saludar_por_privado=bot.booleano("saludar_por_privado", True),
        tareas_pesadas_simultaneas=int(bot.numero("tareas_pesadas_simultaneas", 2, minimo=1, entero=True)),
        stickers=ConfigStickers(
            paquete=stk.texto("paquete", "Licha Bot"),
            autor=stk.texto("autor", "Licha Bot"),
            marca_de_agua=stk.texto("marca_de_agua", "Licha Bot"),
            automatico_en_privado=stk.booleano("automatico_en_privado", True),
            max_segundos_video=stk.numero("max_segundos_video", 10, minimo=1),
            max_mb_descarga=int(stk.numero("max_mb_descarga", 25, minimo=1, entero=True)),
        ),
        nivel_log=reg.nivel("nivel", "INFO"),
        nivel_log_whatsapp=reg.nivel("nivel_whatsapp", "WARNING"),
        datos=datos,
    )


def cargar_config(archivo: Path = ARCHIVO_CONFIG) -> Config:
    """Lee config.toml. Si no existe, lo crea copiando config.ejemplo.toml."""
    if not archivo.exists():
        if archivo == ARCHIVO_CONFIG and ARCHIVO_EJEMPLO.exists():
            shutil.copyfile(ARCHIVO_EJEMPLO, archivo)
            log.warning("No había config.toml: lo creé a partir de config.ejemplo.toml")
        else:
            raise ErrorConfig(f"No encontré el archivo de configuración {archivo}")
    try:
        # utf-8-sig: el Bloc de notas a veces guarda el archivo con BOM
        texto = archivo.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ErrorConfig(
            f"{archivo.name} no está guardado en UTF-8. Abrilo con el Bloc de notas y usá "
            "Archivo > Guardar como > Codificación: UTF-8."
        ) from exc
    try:
        datos = tomllib.loads(texto)
    except tomllib.TOMLDecodeError as exc:
        raise ErrorConfig(
            f"{archivo.name} tiene un error de formato: {exc}. Revisá que los textos estén "
            "entre comillas y que no falte ningún corchete."
        ) from exc
    return desde_dict(datos)
