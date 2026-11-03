"""Configuración del bot a partir de variables de entorno.

Todas las variables son opcionales salvo WA_PHONE_NUMBER, que solo hace falta
la primera vez (para pedir el código de vinculación). Ver `.env.example`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from sticker import StickerOptions

BASE_DIR = Path(__file__).resolve().parent
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class ConfigError(ValueError):
    """Variable de entorno con un valor inválido."""


@dataclass(frozen=True)
class Config:
    phone: str | None
    session_db: Path
    command: str
    pack_name: str
    publisher: str
    watermark: str
    image_max_kb: int
    animated_max_kb: int
    max_video_seconds: float
    max_download_mb: int
    max_concurrent: int
    pair_timeout: int
    log_level: str
    neonize_log_level: str
    log_file: Path | None = None

    def sticker_options(self) -> StickerOptions:
        return StickerOptions(
            pack_name=self.pack_name,
            publisher=self.publisher,
            watermark=self.watermark,
            image_max_bytes=self.image_max_kb * 1024,
            animated_max_bytes=self.animated_max_kb * 1024,
            max_video_seconds=self.max_video_seconds,
        )


def normalize_phone(raw: str) -> str:
    """'+54 9 11 2345-6789' -> '5491123456789' (formato internacional, solo dígitos)."""
    digits = re.sub(r"[\s+\-().]", "", raw)
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        raise ConfigError(
            f"WA_PHONE_NUMBER inválido ({raw!r}): usá formato internacional, "
            "con código de país y sin '+', por ejemplo 5491123456789"
        )
    return digits


def _get(env: Mapping[str, str], name: str, default: str) -> str:
    value = env.get(name)
    return default if value is None else value.strip()


def _int(env: Mapping[str, str], name: str, default: int, minimum: int = 1) -> int:
    raw = _get(env, name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} debe ser un número entero (vale {raw!r})") from exc
    if value < minimum:
        raise ConfigError(f"{name} debe ser >= {minimum} (vale {value})")
    return value


def _float(env: Mapping[str, str], name: str, default: float, minimum: float) -> float:
    raw = _get(env, name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} debe ser un número (vale {raw!r})") from exc
    if value < minimum:
        raise ConfigError(f"{name} debe ser >= {minimum:g} (vale {value:g})")
    return value


def _level(env: Mapping[str, str], name: str, default: str) -> str:
    value = _get(env, name, default).upper()
    if value not in LOG_LEVELS:
        raise ConfigError(f"{name} debe ser uno de {', '.join(LOG_LEVELS)} (vale {value!r})")
    return value


def _path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else BASE_DIR / path  # relativo a la carpeta del bot


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env

    phone_raw = _get(env, "WA_PHONE_NUMBER", "")
    session = _path(_get(env, "WA_SESSION_DB", "data/session.sqlite3"))
    log_file = _get(env, "LOG_FILE", "")

    command = _get(env, "STICKER_COMMAND", ".sticker")
    if not command or any(ch.isspace() for ch in command):
        raise ConfigError("STICKER_COMMAND no puede estar vacío ni tener espacios")

    return Config(
        phone=normalize_phone(phone_raw) if phone_raw else None,
        session_db=session,
        command=command,
        pack_name=_get(env, "STICKER_PACK_NAME", "Licha.bot"),
        publisher=_get(env, "STICKER_PACK_PUBLISHER", "Licha.bot"),
        watermark=_get(env, "STICKER_WATERMARK", "Licha.bot"),
        image_max_kb=_int(env, "STICKER_IMAGE_MAX_KB", 100),
        animated_max_kb=_int(env, "STICKER_ANIMATED_MAX_KB", 500),
        max_video_seconds=_float(env, "STICKER_MAX_VIDEO_SECONDS", 10.0, minimum=0.5),
        max_download_mb=_int(env, "MAX_DOWNLOAD_MB", 25),
        max_concurrent=_int(env, "MAX_CONCURRENT_CONVERSIONS", 2),
        pair_timeout=_int(env, "PAIR_TIMEOUT_SECONDS", 180, minimum=30),
        log_level=_level(env, "LOG_LEVEL", "INFO"),
        neonize_log_level=_level(env, "NEONIZE_LOG_LEVEL", "WARNING"),
        log_file=_path(log_file) if log_file else None,
    )
